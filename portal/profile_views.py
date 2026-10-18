from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import AuditEvent
from .tenancy import audit, is_master_admin


@login_required
@require_http_methods(['GET', 'POST'])
def my_profile(request):
    user = request.user
    error = ''
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()[:150]
        last_name = request.POST.get('last_name', '').strip()[:150]
        email = request.POST.get('email', '').strip()[:254]
        if not email:
            error = 'An email address is required.'
        elif user.__class__.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            error = 'That email address is already associated with another account.'
        else:
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.save(update_fields=['first_name', 'last_name', 'email'])
            audit(user, 'profile.updated', None, 'User', user.pk, {'fields': ['first_name', 'last_name', 'email']})
            messages.success(request, 'Your profile was updated.')
            return redirect('my_profile')
    memberships = user.company_memberships.filter(is_active=True).select_related('company')
    return render(request, 'portal/profile.html', {
        'profile_user': user, 'memberships': memberships,
        'is_master_admin': is_master_admin(user), 'error': error,
    })


from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from .models import AccountSecurity


@login_required
@require_http_methods(['GET', 'POST'])
def change_password(request):
    error = ''
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        if not check_password(current, request.user.password):
            error = 'Current password was not accepted.'
        elif len(password1) < 12:
            error = 'Choose a password with at least 12 characters.'
        elif password1 != password2:
            error = 'The new passwords do not match.'
        elif password1 == current:
            error = 'Choose a new password different from the temporary password.'
        else:
            request.user.set_password(password1)
            request.user.save(update_fields=['password'])
            AccountSecurity.objects.update_or_create(user=request.user, defaults={'force_password_change': False})
            update_session_auth_hash(request, request.user)
            audit(request.user, 'account.password_changed', None, 'User', request.user.pk, {})
            messages.success(request, 'Password updated successfully.')
            return redirect('support_tickets' if request.user.groups.filter(name__in=('support_user', 'support_admin')).exists() else 'management_home')
    return render(request, 'portal/change_password.html', {'error': error})
