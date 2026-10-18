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
