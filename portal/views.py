from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from .models import Application, Job

DEMO_JOBS = [
 {'title':'Warehouse Associate','company':'Cretan Staffing Demo Client','location':'Greeneville, TN / On-site','employment_type':'Full-time','description':'Support receiving, inventory, picking, packing, and safe warehouse operations. Reliable attendance and attention to detail are important.'},
 {'title':'Customer Support Representative','company':'Cretan Staffing Demo Client','location':'Remote — United States','employment_type':'Full-time','description':'Help customers resolve routine account and product questions, document interactions, and escalate complex issues to the appropriate team.'},
 {'title':'Administrative Coordinator','company':'Cretan Staffing Demo Client','location':'Hybrid — Tennessee','employment_type':'Contract','description':'Coordinate schedules, maintain records, prepare reports, and support day-to-day office operations.'},
]

def home(request):
    if not Job.objects.exists():
        for item in DEMO_JOBS:
            Job.objects.get_or_create(title=item['title'], company=item['company'], defaults={**item, 'is_published': True})
    jobs = Job.objects.filter(is_published=True).order_by('-created_at')
    return render(request, 'portal/home.html', {'jobs': jobs, 'application_count': Application.objects.count()})

@require_http_methods(['GET','POST'])
def apply(request, job_id):
    job = get_object_or_404(Job, pk=job_id, is_published=True)
    if request.method == 'POST':
        name = request.POST.get('full_name','').strip()
        email = request.POST.get('email','').strip()
        message = request.POST.get('message','').strip()
        if not name or not email:
            messages.error(request, 'Please provide your name and email address.')
        else:
            Application.objects.create(job=job, full_name=name[:160], email=email[:254], message=message[:5000])
            messages.success(request, 'Demo application submitted. A recruiter would follow up in a production version.')
            return redirect('home')
    return render(request, 'portal/apply.html', {'job': job})

@staff_member_required
def staff_dashboard(request):
    return render(request, 'portal/staff.html', {'jobs': Job.objects.all().order_by('-created_at'), 'applications': Application.objects.select_related('job').order_by('-created_at')[:100]})
