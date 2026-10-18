from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

# These are local non-human identities for integration ownership/auditing.
# This does NOT create vendor accounts or issue API credentials.
SERVICES = (
    'ats', 'email', 'calendar', 'crm', 'document_storage',
    'background_tasks', 'monitoring', 'payments', 'screening',
    'payroll', 'e_signature', 'analytics',
)

class Command(BaseCommand):
    help = 'Provision local service identities for integrations (WordPress is excluded).'

    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name='service_account')
        for service in SERVICES:
            username = f'svc_{service}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': '', 'is_active': False, 'is_staff': False, 'is_superuser': False},
            )
            user.set_unusable_password()
            user.is_active = False
            user.is_staff = False
            user.is_superuser = False
            user.save()
            user.groups.add(group)
            state = 'created' if created else 'verified'
            self.stdout.write(f'{state}: {username} (non-interactive, inactive)')
        self.stdout.write(self.style.SUCCESS(
            f'Provisioned {len(SERVICES)} local service identities. '
            'External provider accounts/API credentials must be configured separately. WordPress was not included.'
        ))
