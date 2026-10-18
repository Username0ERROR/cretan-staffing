from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from .models import Application, Job

DEMO_JOBS = [
 {'title':'Warehouse Associate','company':'Cretan Staffing Demo Client','location':'Greeneville, TN / On-site','employment_type':'Full-time','description':'Support receiving, inventory, picking, packing, and safe warehouse operations. Reliable attendance and attention to detail are important.'},
 {'title':'Customer Support Representative','company':'Cretan Staffing Demo Client','location':'Remote — United States','employment_type':'Full-time','description':'Help customers resolve routine account and product questions, document interactions, and escalate complex issues to the appropriate team.'},
 {'title':'Administrative Coordinator','company':'Cretan Staffing Demo Client','location':'Hybrid — Tennessee','employment_type':'Contract','description':'Coordinate schedules, maintain records, prepare reports, and support day-to-day office operations.'},
]

ROLE_LABELS = {'candidate':'Candidate','recruiter':'Recruiter','manager':'Manager','admin':'Administrator','client':'Client'}

def user_role(user):
    if user.is_superuser:
        return 'admin'
    roles = user.groups.filter(name__in=ROLE_LABELS.keys()).values_list('name', flat=True)
    for role in ('admin', 'manager', 'recruiter', 'client', 'candidate'):
        if role in roles:
            return role
    return 'candidate'

def home(request):
    if not Job.objects.exists():
        for item in DEMO_JOBS:
            Job.objects.get_or_create(title=item['title'], company=item['company'], defaults={**item, 'is_published': True})
    jobs = Job.objects.filter(is_published=True).order_by('-created_at')
    return render(request, 'portal/home.html', {'jobs': jobs, 'application_count': Application.objects.count()})

@require_http_methods(['GET', 'POST'])
def signup(request):
    errors = []
    values = {'username': '', 'email': '', 'role': 'candidate'}
    if request.method == 'POST':
        values = {key: request.POST.get(key, '').strip() for key in ('username', 'email', 'role')}
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        username = values['username']
        email = values['email']
        role = values['role']
        if len(username) < 3:
            errors.append('Username must contain at least 3 characters.')
        if User.objects.filter(username__iexact=username).exists():
            errors.append('That username is already in use.')
        if not email or User.objects.filter(email__iexact=email).exists():
            errors.append('Enter an email address that is not already registered.')
        if role not in ('candidate', 'client'):
            errors.append('Choose a permitted account type.')
        if len(password1) < 12:
            errors.append('Password must be at least 12 characters long.')
        if password1 != password2:
            errors.append('Passwords do not match.')
        if not errors:
            user = User.objects.create_user(username=username, email=email, password=password1)
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
            if role == 'client':
                user.is_active = False
                user.save(update_fields=['is_active'])
                messages.success(request, 'Account request received. Cretan Staffing must approve your client account before you can sign in.')
                return redirect('login')
            login(request, user)
            messages.success(request, 'Your candidate account has been created.')
            return redirect('dashboard')
    return render(request, 'portal/signup.html', {'errors': errors, 'values': values})

@login_required
def dashboard(request):
    role = user_role(request.user)
    if role == 'client' and not request.user.is_active:
        return render(request, 'portal/dashboard.html', {'role_label':'Client', 'dashboard_message':'Your account is awaiting review.', 'pending':True, 'cards':[], 'actions':[]})
    jobs_count = Job.objects.filter(is_published=True).count()
    app_count = Application.objects.count()
    role_content = {
        'candidate': ('Your career workspace', [{'value':jobs_count,'label':'Open sample roles'},{'value':'Ready','label':'Profile status'}], [
            {'kicker':'Opportunities','title':'Explore open jobs','description':'Browse published roles and submit an application.','url':'/','link_label':'Browse jobs'},
            {'kicker':'Applications','title':'Your applications','description':'Application tracking is being connected to your candidate profile.'}
        ]),
        'client': ('Your employer workspace', [{'value':'Active','label':'Account status'},{'value':jobs_count,'label':'Sample public roles'}], [
            {'kicker':'Employer tools','title':'Client workspace','description':'Coordinate job requests and hiring needs with Cretan Staffing. Job posting and applicant access controls are being developed.','url':'','link_label':''}
        ]),
        'recruiter': ('Recruiting operations', [{'value':jobs_count,'label':'Published jobs'},{'value':app_count,'label':'Applications'},{'value':User.objects.filter(is_active=True).count(),'label':'Active accounts'}], [
            {'kicker':'Recruiting','title':'Recruiter workspace','description':'Review incoming applications and manage recruiting activity.','url':'/staff/','link_label':'Open recruiter workspace'}
        ]),
        'manager': ('Team and compliance oversight', [{'value':jobs_count,'label':'Published jobs'},{'value':app_count,'label':'Applications'},{'value':User.objects.filter(is_active=False).count(),'label':'Accounts awaiting review'}], [
            {'kicker':'Oversight','title':'Review queue','description':'Review account requests and supervise staffing workflows.','url':'/staff/','link_label':'Open operations'}
        ]),
        'admin': ('Platform administration', [{'value':jobs_count,'label':'Published jobs'},{'value':app_count,'label':'Applications'},{'value':User.objects.count(),'label':'User accounts'}], [
            {'kicker':'Administration','title':'User and role management','description':'Manage user permissions through Django Admin. Assign roles only after verifying the person’s authorization.','url':'/admin/','link_label':'Open Django Admin'},
        ])
    }
    message, cards, actions = role_content[role]
    return render(request, 'portal/dashboard.html', {'role_label':ROLE_LABELS[role], 'dashboard_message':message, 'pending':False, 'cards':cards, 'actions':actions, 'role':role})

@login_required
def staff_dashboard(request):
    role = user_role(request.user)
    if role not in ('recruiter', 'manager', 'admin'):
        raise PermissionDenied('This workspace is restricted to Cretan Staffing staff.')
    return render(request, 'portal/staff.html', {'jobs': Job.objects.all().order_by('-created_at'), 'applications': Application.objects.select_related('job').order_by('-created_at')[:100]})

@require_http_methods(['GET', 'POST'])
def apply(request, job_id):
    job = get_object_or_404(Job, pk=job_id, is_published=True)
    if request.method == 'POST':
        name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()
        if not name or not email:
            messages.error(request, 'Please provide your name and email address.')
        else:
            Application.objects.create(job=job, full_name=name[:160], email=email[:254], message=message[:5000])
            messages.success(request, 'Demo application submitted. A recruiter would follow up in a production version.')
            return redirect('home')
    return render(request, 'portal/apply.html', {'job': job})
