import ipaddress
import os
import secrets
import socket
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from .models import AccountSecurity, AuditEvent, Company, CompanyMembership, IntegrationCredential, SupportTicket, TaxDocument
from .tenancy import (
    COMPANY_ADMIN_ROLES, SUPPORT_ROLES, audit, can_manage_company, decrypt_secret,
    encrypt_secret, is_master_admin, make_company_pin, membership_for, require_company_access,
    require_company_admin, require_master_admin, role_for, verify_company_pin,
)

User = get_user_model()
ALLOWED_DOC_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg'}
MAX_DOC_BYTES = 10 * 1024 * 1024


def _companies_for(user):
    if is_master_admin(user):
        return Company.objects.filter(is_active=True)
    return Company.objects.filter(memberships__user=user, memberships__is_active=True, is_active=True).distinct()


def _active_company(request):
    companies = _companies_for(request.user)
    selected_id = request.session.get('active_company_id')
    company = companies.filter(pk=selected_id).first() if selected_id else None
    if company is None:
        company = companies.first()
        if company:
            request.session['active_company_id'] = company.pk
    return company


def _management_context(request, **extra):
    company = _active_company(request)
    context = {
        'companies': _companies_for(request.user),
        'active_company': company,
        'is_master_admin': is_master_admin(request.user),
        'is_support': bool(request.user.groups.filter(name__in=SUPPORT_ROLES).exists()),
        'company_role': role_for(request.user, company) if company else '',
    }
    context.update(extra)
    return context


@login_required
def management_home(request):
    company = _active_company(request)
    if not company and not is_master_admin(request.user):
        return render(request, 'portal/company_setup.html', _management_context(request))
    audit(request.user, 'management.dashboard.viewed', company, 'Company', company.pk if company else '', {})
    if is_master_admin(request.user):
        users_count = User.objects.count()
        companies_count = Company.objects.count()
        membership_count = CompanyMembership.objects.filter(is_active=True).count()
        events = AuditEvent.objects.select_related('actor', 'company')[:15]
    else:
        users_count = CompanyMembership.objects.filter(company=company, is_active=True).count()
        companies_count = 1
        membership_count = users_count
        events = AuditEvent.objects.filter(company=company).select_related('actor', 'company')[:15]
    return render(request, 'portal/management.html', _management_context(
        request, users_count=users_count, companies_count=companies_count,
        membership_count=membership_count, recent_events=events,
        company_admin=bool(company and can_manage_company(request.user, company)),
    ))


@login_required
@require_http_methods(['POST'])
def switch_company(request):
    company = get_object_or_404(_companies_for(request.user), pk=request.POST.get('company_id'))
    request.session['active_company_id'] = company.pk
    audit(request.user, 'company.switched', company, 'Company', company.pk)
    messages.success(request, f'Workspace switched to {company.name}.')
    return redirect('management_home')


@login_required
@require_http_methods(['GET', 'POST'])
def create_company(request):
    require_master_admin(request.user)
    generated_pin = ''
    error = ''
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        legal_name = request.POST.get('legal_name', '').strip()
        slug = slugify(request.POST.get('slug', '').strip() or name)
        owner_username = request.POST.get('owner_username', '').strip()
        if not name or not slug:
            error = 'Enter a company name.'
        elif Company.objects.filter(slug=slug).exists():
            error = 'That company URL key is already in use.'
        elif owner_username and not User.objects.filter(username=owner_username).exists():
            error = 'Owner username not found. Create the user account first, then assign them to this company.'
        else:
            generated_pin = make_company_pin()
            company = Company.objects.create(
                name=name, legal_name=legal_name, slug=slug,
                pin_hash=make_password(generated_pin), created_by=request.user,
            )
            CompanyMembership.objects.create(user=request.user, company=company, role='company_owner')
            if owner_username and owner_username != request.user.username:
                owner = User.objects.get(username=owner_username)
                CompanyMembership.objects.update_or_create(
                    user=owner, company=company,
                    defaults={'role': 'company_owner', 'is_active': True},
                )
            request.session['active_company_id'] = company.pk
            audit(request.user, 'company.created', company, 'Company', company.pk, {'slug': slug})
            messages.success(request, 'Company created. Copy the company PIN now; it is only shown once.')
            return render(request, 'portal/company_created.html', _management_context(
                request, created_company=company, company_pin=generated_pin,
            ))
    return render(request, 'portal/company_create.html', _management_context(request, error=error))


@login_required
@require_http_methods(['GET', 'POST'])
def join_company(request):
    error = ''
    if request.method == 'POST':
        pin = request.POST.get('company_pin', '').strip().upper()
        matches = [c for c in Company.objects.filter(is_active=True) if verify_company_pin(c, pin)]
        if len(matches) != 1:
            error = 'That company PIN was not recognized.'
        else:
            company = matches[0]
            membership = CompanyMembership.objects.filter(user=request.user, company=company).first()
            if membership is None:
                membership = CompanyMembership.objects.create(user=request.user, company=company, role='employee', is_active=True)
            elif not membership.is_active:
                membership.is_active = True
                membership.save(update_fields=['is_active', 'updated_at'])
            request.session['active_company_id'] = company.pk
            audit(request.user, 'company.joined_by_pin', company, 'Membership', membership.pk)
            messages.success(request, f'You joined {company.name}. A company administrator can update your role.')
            return redirect('management_home')
    return render(request, 'portal/company_join.html', _management_context(request, error=error))


@login_required
@require_http_methods(['GET', 'POST'])
def company_users(request):
    company = _active_company(request)
    if not company:
        return redirect('management_home')
    require_company_access(request.user, company)
    if request.user.groups.filter(name__in=SUPPORT_ROLES).exists():
        raise PermissionDenied('Support accounts cannot change company membership permissions.')
    if not (can_manage_company(request.user, company) or is_master_admin(request.user)):
        raise PermissionDenied('Only company administrators can manage memberships.')
    error = ''
    allowed_roles = [('company_admin', 'Company administrator'), ('manager', 'Manager'), ('employee', 'Employee'), ('viewer', 'Read-only viewer')]
    if is_master_admin(request.user):
        allowed_roles += [('support_user', 'Support user'), ('support_admin', 'Support administrator')]
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        role = request.POST.get('role', 'employee')
        target = User.objects.filter(username__iexact=username).first()
        valid_roles = {r[0] for r in allowed_roles}
        if not target:
            error = 'User not found. Ask them to create an account first.'
        elif role not in valid_roles:
            error = 'That role is not available to your account.'
        elif target == request.user and membership_for(request.user, company) and membership_for(request.user, company).role == 'company_owner' and role != 'company_owner':
            error = 'A company owner cannot downgrade their own owner role.'
        elif target.username == os.environ.get('STAFF_LOGIN_USERNAME', '').strip():
            error = 'The protected platform owner role cannot be changed here.'
        else:
            membership, _ = CompanyMembership.objects.update_or_create(
                user=target, company=company, defaults={'role': role, 'is_active': True},
            )
            audit(request.user, 'membership.role_assigned', company, 'Membership', membership.pk, {'username': target.username, 'role': role})
            messages.success(request, f'{target.username} now has the {membership.get_role_display()} role in {company.name}.')
            return redirect('company_users')
    memberships = CompanyMembership.objects.filter(company=company).select_related('user')
    return render(request, 'portal/company_users.html', _management_context(
        request, memberships=memberships, allowed_roles=allowed_roles, error=error,
        can_manage=True,
    ))


@login_required
@require_http_methods(['POST'])
def toggle_membership(request, membership_id):
    membership = get_object_or_404(CompanyMembership.objects.select_related('company', 'user'), pk=membership_id)
    company = membership.company
    if request.user.groups.filter(name__in=SUPPORT_ROLES).exists():
        raise PermissionDenied('Support accounts cannot change company membership permissions.')
    if not is_master_admin(request.user):
        require_company_admin(request.user, company)
    if membership.user.username == os.environ.get('STAFF_LOGIN_USERNAME', '').strip():
        raise PermissionDenied('The platform owner membership cannot be disabled here.')
    if membership.user == request.user and membership.role == 'company_owner':
        raise PermissionDenied('You cannot remove your own company-owner access.')
    membership.is_active = not membership.is_active
    membership.save(update_fields=['is_active', 'updated_at'])
    audit(request.user, 'membership.activated' if membership.is_active else 'membership.paused', company, 'Membership', membership.pk, {'username': membership.user.username})
    messages.success(request, f'{membership.user.username} access {"restored" if membership.is_active else "paused"}.')
    return redirect('company_users')


@login_required
@require_http_methods(['GET', 'POST'])
def support_management(request):
    require_master_admin(request.user)
    error = ''
    temporary_password = ''
    created_username = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', '')
        target = User.objects.filter(username__iexact=username).first()
        if role not in SUPPORT_ROLES:
            error = 'Choose support_user or support_admin.'
        elif target and target.username == request.user.username:
            error = 'The main admin is already the top-level platform role.'
        elif target is None and (len(username) < 3 or not email):
            error = 'To create a new support account, provide a username of at least 3 characters and an email address.'
        elif target is None and User.objects.filter(email__iexact=email).exists():
            error = 'That email address is already in use.'
        else:
            if target is None:
                temporary_password = secrets.token_urlsafe(18)
                target = User.objects.create_user(username=username, email=email, password=temporary_password)
                AccountSecurity.objects.create(user=target, force_password_change=True)
                created_username = target.username
                audit(request.user, 'platform.support_account_created', None, 'User', target.pk, {'username': target.username, 'role': role})
            group, _ = __import__('django.contrib.auth.models', fromlist=['Group']).Group.objects.get_or_create(name=role)
            target.groups.add(group)
            audit(request.user, 'platform.support_role_assigned', None, 'User', target.pk, {'username': target.username, 'role': role})
            if temporary_password:
                support_users = User.objects.filter(groups__name__in=SUPPORT_ROLES).distinct().order_by('username')
                response = render(request, 'portal/support_management.html', _management_context(
                    request, error='', support_users=support_users,
                    temporary_password=temporary_password, created_username=created_username,
                ))
                response['Cache-Control'] = 'no-store'
                return response
            messages.success(request, f'{target.username} was granted {role.replace("_", " ")} access.')
            return redirect('support_management')
    support_users = User.objects.filter(groups__name__in=SUPPORT_ROLES).distinct().order_by('username')
    return render(request, 'portal/support_management.html', _management_context(
        request, error=error, support_users=support_users,
        temporary_password=temporary_password, created_username=created_username,
    ))


@login_required
@require_http_methods(['GET', 'POST'])
def integration_management(request):
    company = _active_company(request)
    if not company:
        return redirect('management_home')
    require_company_access(request.user, company)
    if request.user.groups.filter(name__in=SUPPORT_ROLES).exists():
        raise PermissionDenied('Support accounts cannot manage integration credentials.')
    if not (can_manage_company(request.user, company) or is_master_admin(request.user)):
        raise PermissionDenied('Only company owners and administrators can manage integrations.')
    error = ''
    if request.method == 'POST':
        provider = request.POST.get('provider', '').strip()[:120]
        endpoint_url = request.POST.get('endpoint_url', '').strip()[:500]
        label = request.POST.get('account_label', '').strip()[:160]
        external_username = request.POST.get('external_username', '').strip()[:254]
        secret = request.POST.get('secret', '')
        scopes = request.POST.get('scopes', '').strip()[:500]
        if not provider or not label or not secret:
            error = 'Provider, account label, and API token/secret are required.'
        elif endpoint_url and not endpoint_url.lower().startswith('https://'):
            error = 'Integration endpoints must use HTTPS.'
        else:
            try:
                encrypted = encrypt_secret(secret)
            except ImproperlyConfigured as exc:
                error = str(exc)
            else:
                credential = IntegrationCredential.objects.create(
                    company=company, provider=provider, endpoint_url=endpoint_url, account_label=label,
                    external_username=external_username, encrypted_secret=encrypted,
                    scopes=scopes, created_by=request.user,
                )
                audit(request.user, 'integration.created', company, 'IntegrationCredential', credential.pk, {'provider': provider, 'label': label})
                messages.success(request, 'Integration saved encrypted. The secret will not be shown again.')
                return redirect('integration_management')
    credentials = IntegrationCredential.objects.filter(company=company).order_by('-created_at')
    return render(request, 'portal/integrations.html', _management_context(
        request, credentials=credentials, error=error,
    ))


@login_required
@require_http_methods(['POST'])
def toggle_integration(request, credential_id):
    credential = get_object_or_404(IntegrationCredential.objects.select_related('company'), pk=credential_id)
    if request.user.groups.filter(name__in=SUPPORT_ROLES).exists():
        raise PermissionDenied('Support accounts cannot manage integration credentials.')
    if not (is_master_admin(request.user) or can_manage_company(request.user, credential.company)):
        raise PermissionDenied('Only company owners and administrators can manage integrations.')
    credential.is_active = not credential.is_active
    credential.save(update_fields=['is_active', 'updated_at'])
    audit(request.user, 'integration.activated' if credential.is_active else 'integration.disabled', credential.company, 'IntegrationCredential', credential.pk, {'provider': credential.provider})
    return redirect('integration_management')


@login_required
@require_http_methods(['GET', 'POST'])
def tax_documents(request):
    company = _active_company(request)
    if not company:
        return redirect('management_home')
    require_company_access(request.user, company)
    membership = membership_for(request.user, company)
    # Support personnel are explicitly excluded from document access.
    if request.user.groups.filter(name__in=SUPPORT_ROLES).exists() or (membership and membership.role in SUPPORT_ROLES):
        raise PermissionDenied('Support roles cannot view or download tax documents.')
    can_review = is_master_admin(request.user) or (membership and membership.role in COMPANY_ADMIN_ROLES | {'manager'})
    error = ''
    if request.method == 'POST':
        uploaded = request.FILES.get('file')
        try:
            year = int(request.POST.get('tax_year', date.today().year))
        except ValueError:
            year = 0
        if not (is_master_admin(request.user) or membership is not None):
            error = 'Only a company administrator or an employee uploading their own document can upload documents.'
        elif not uploaded:
            error = 'Choose a document to upload.'
        elif os.path.splitext(uploaded.name)[1].lower() not in ALLOWED_DOC_EXTENSIONS:
            error = 'Only PDF, PNG, JPG, and JPEG documents are accepted.'
        elif uploaded.size > MAX_DOC_BYTES:
            error = 'The file exceeds the 10 MB limit.'
        elif year < 2000 or year > date.today().year + 1:
            error = 'Enter a valid tax year.'
        elif request.POST.get('document_type', 'other') not in dict(TaxDocument.TYPE_CHOICES):
            error = 'Choose a valid document type.'
        else:
            owner_id = request.POST.get('owner_id') if can_review else request.user.pk
            owner = User.objects.filter(pk=owner_id).first() if owner_id else request.user
            if owner is None or not CompanyMembership.objects.filter(company=company, user=owner, is_active=True).exists():
                error = 'Select an active user in this company.'
            else:
                doc = TaxDocument.objects.create(
                    company=company, owner=owner, document_type=request.POST.get('document_type', 'other'),
                    tax_year=year, file=uploaded, uploaded_by=request.user,
                )
                audit(request.user, 'tax_document.uploaded', company, 'TaxDocument', doc.pk, {'owner_id': owner.pk, 'type': doc.document_type, 'year': year})
                messages.success(request, 'Tax document uploaded to the private document area.')
                return redirect('tax_documents')
    docs = TaxDocument.objects.filter(company=company).select_related('owner', 'uploaded_by')
    if not can_review:
        docs = docs.filter(owner=request.user)
    members = CompanyMembership.objects.filter(company=company, is_active=True).select_related('user')
    return render(request, 'portal/tax_documents.html', _management_context(
        request, documents=docs, members=members, can_review=can_review, error=error,
        document_types=TaxDocument.TYPE_CHOICES, current_year=date.today().year,
    ))


@login_required
def download_tax_document(request, document_id):
    doc = get_object_or_404(TaxDocument.objects.select_related('company', 'owner'), pk=document_id)
    require_company_access(request.user, doc.company)
    membership = membership_for(request.user, doc.company)
    can_review = is_master_admin(request.user) or (membership and membership.role in COMPANY_ADMIN_ROLES | {'manager'})
    if request.user.groups.filter(name__in=SUPPORT_ROLES).exists() or (membership and membership.role in SUPPORT_ROLES):
        raise PermissionDenied('Support personnel cannot download tax documents.')
    if not can_review and doc.owner_id != request.user.pk:
        raise PermissionDenied('You can only download your own tax documents.')
    try:
        handle = doc.file.open('rb')
    except (FileNotFoundError, ValueError, OSError):
        raise Http404('The private document is not available in storage.')
    audit(request.user, 'tax_document.downloaded', doc.company, 'TaxDocument', doc.pk)
    response = FileResponse(handle, as_attachment=True, filename=os.path.basename(doc.file.name))
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@require_http_methods(['POST'])
def review_tax_document(request, document_id):
    if request.user.groups.filter(name__in=SUPPORT_ROLES).exists():
        raise PermissionDenied('Support personnel cannot review tax documents.')
    doc = get_object_or_404(TaxDocument.objects.select_related('company'), pk=document_id)
    if not (is_master_admin(request.user) or can_manage_company(request.user, doc.company) or role_for(request.user, doc.company) == 'manager'):
        raise PermissionDenied('Only company administrators can review tax documents.')
    status = request.POST.get('status', '')
    if status not in {'review', 'approved', 'rejected'}:
        raise Http404('Unknown document status.')
    doc.status = status
    doc.review_note = request.POST.get('review_note', '').strip()[:500]
    doc.reviewed_at = __import__('django.utils.timezone', fromlist=['now']).now()
    doc.save(update_fields=['status', 'review_note', 'reviewed_at'])
    audit(request.user, 'tax_document.reviewed', doc.company, 'TaxDocument', doc.pk, {'status': status})
    messages.success(request, 'Document review status updated.')
    return redirect('tax_documents')


@login_required
def audit_log(request):
    if is_master_admin(request.user):
        events = AuditEvent.objects.select_related('actor', 'company')
    else:
        company = _active_company(request)
        if not company:
            return redirect('management_home')
        require_company_access(request.user, company)
        role = role_for(request.user, company)
        if role not in COMPANY_ADMIN_ROLES | {'manager', 'support_admin'}:
            raise PermissionDenied('Audit logs are limited to company managers and administrators.')
        events = AuditEvent.objects.filter(company=company).select_related('actor', 'company')
    return render(request, 'portal/audit_log.html', _management_context(request, events=events[:250]))


@login_required
@require_http_methods(['GET', 'POST'])
def support_tickets(request):
    support_staff = request.user.groups.filter(name__in=SUPPORT_ROLES).exists()
    company = _active_company(request)
    error = ''
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()[:180]
        description = request.POST.get('description', '').strip()[:5000]
        if not subject or not description:
            error = 'Enter a subject and a description.'
        else:
            ticket = SupportTicket.objects.create(
                company=company, created_by=request.user, subject=subject,
                description=description, priority=request.POST.get('priority', 'normal')
                if request.POST.get('priority', 'normal') in {'low', 'normal', 'high', 'urgent'} else 'normal',
            )
            audit(request.user, 'support_ticket.created', company, 'SupportTicket', ticket.pk, {'priority': ticket.priority})
            messages.success(request, f'Support request #{ticket.pk} was created.')
            return redirect('support_tickets')
    if support_staff:
        tickets = SupportTicket.objects.select_related('company', 'created_by', 'assigned_to')
    elif company and (is_master_admin(request.user) or role_for(request.user, company) in COMPANY_ADMIN_ROLES | {'manager'}):
        tickets = SupportTicket.objects.filter(company=company).select_related('company', 'created_by', 'assigned_to')
    else:
        tickets = SupportTicket.objects.filter(created_by=request.user).select_related('company', 'created_by', 'assigned_to')
    return render(request, 'portal/support_tickets.html', _management_context(
        request, tickets=tickets[:200], error=error, support_staff=support_staff,
        ticket_statuses=SupportTicket.STATUS_CHOICES, ticket_priorities=SupportTicket.PRIORITY_CHOICES,
        support_users=User.objects.filter(groups__name__in=SUPPORT_ROLES, is_active=True).distinct().order_by('username'),
    ))


@login_required
@require_http_methods(['POST'])
def update_support_ticket(request, ticket_id):
    if not request.user.groups.filter(name__in=SUPPORT_ROLES).exists() and not is_master_admin(request.user):
        raise PermissionDenied('Only support staff can update support requests.')
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)
    status = request.POST.get('status', '')
    assigned_username = request.POST.get('assigned_to', '').strip()
    if status not in dict(SupportTicket.STATUS_CHOICES):
        raise PermissionDenied('Invalid ticket status.')
    assignee = None
    if assigned_username:
        assignee = User.objects.filter(username=assigned_username, groups__name__in=SUPPORT_ROLES, is_active=True).first()
        if assignee is None:
            messages.error(request, 'Choose an active support user or leave the ticket unassigned.')
            return redirect('support_tickets')
    ticket.status = status
    ticket.assigned_to = assignee
    ticket.save(update_fields=['status', 'assigned_to', 'updated_at'])
    audit(request.user, 'support_ticket.updated', ticket.company, 'SupportTicket', ticket.pk, {'status': status})
    messages.success(request, f'Support request #{ticket.pk} updated.')
    return redirect('support_tickets')


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_public_https_endpoint(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use a public HTTPS endpoint without embedded credentials.')
    if parsed.port not in (None, 443):
        raise ValueError('Only the standard HTTPS port is allowed.')
    if parsed.query or parsed.fragment:
        raise ValueError('Enter a base URL without query parameters or fragments.')
    hostname = parsed.hostname.rstrip('.').lower()
    if hostname == 'localhost' or hostname.endswith(('.local', '.internal', '.localhost')):
        raise ValueError('Private and local network endpoints are not allowed.')
    try:
        literal = ipaddress.ip_address(hostname)
        addresses = [literal]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)]
        except (OSError, ValueError) as exc:
            raise ValueError('The endpoint hostname could not be resolved.') from exc
    if not addresses or any(not addr.is_global for addr in addresses):
        raise ValueError('The endpoint must resolve only to public IP addresses.')
    return parsed


@login_required
@require_http_methods(['POST'])
def test_integration(request, credential_id):
    credential = get_object_or_404(IntegrationCredential.objects.select_related('company'), pk=credential_id)
    if request.user.groups.filter(name__in=SUPPORT_ROLES).exists():
        raise PermissionDenied('Support accounts cannot test integration credentials.')
    if not (is_master_admin(request.user) or can_manage_company(request.user, credential.company)):
        raise PermissionDenied('Only company owners and administrators can test integrations.')
    if not credential.endpoint_url:
        messages.error(request, 'Add the system HTTPS base URL before testing this connection.')
        return redirect('integration_management')
    try:
        _validate_public_https_endpoint(credential.endpoint_url)
        base = credential.endpoint_url.rstrip('/')
        target = base + '/api/v1/' if 'horilla' in credential.provider.lower() else base
        _validate_public_https_endpoint(target)
        token = decrypt_secret(credential.encrypted_secret)
        request_obj = Request(target, headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'User-Agent': 'CretanStaffing-IntegrationCheck/1.0',
        }, method='GET')
        opener = build_opener(_NoRedirect())
        try:
            response = opener.open(request_obj, timeout=8)
            status_code = response.getcode()
            response.close()
        except HTTPError as exc:
            status_code = exc.code
        if 200 <= status_code < 300:
            audit(request.user, 'integration.connection_test_succeeded', credential.company, 'IntegrationCredential', credential.pk, {'provider': credential.provider, 'status_code': status_code})
            messages.success(request, f'{credential.provider} responded with HTTP {status_code}. This confirms reachability, not that every API scope or sync operation is configured.')
        elif status_code in (401, 403):
            audit(request.user, 'integration.connection_test_auth_failed', credential.company, 'IntegrationCredential', credential.pk, {'provider': credential.provider, 'status_code': status_code})
            messages.error(request, f'The endpoint responded with HTTP {status_code}. Check the API token and required scopes.')
        elif status_code in (301, 302, 303, 307, 308):
            messages.error(request, 'The endpoint redirected. Enter the final HTTPS API URL directly; redirects are not followed for security.')
        else:
            audit(request.user, 'integration.connection_test_failed', credential.company, 'IntegrationCredential', credential.pk, {'provider': credential.provider, 'status_code': status_code})
            messages.error(request, f'The endpoint responded with HTTP {status_code}. Check the base URL and API root path.')
    except (ValueError, ImproperlyConfigured, URLError, TimeoutError, OSError) as exc:
        messages.error(request, str(exc)[:220] or 'Connection test failed.')
    return redirect('integration_management')
