from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import AuditEvent


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs):
    AuditEvent.objects.create(
        actor=user,
        action='auth.login',
        metadata={'method': 'owner_recovery' if request and request.path == '/owner-recovery/' else 'web'},
    )


@receiver(user_logged_out)
def record_logout(sender, request, user, **kwargs):
    if user and getattr(user, 'is_authenticated', False):
        AuditEvent.objects.create(
            actor=user,
            action='auth.logout',
            metadata={'method': 'web'},
        )
