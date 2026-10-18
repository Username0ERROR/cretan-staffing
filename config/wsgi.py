import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()

# Bootstrap the owner from Render environment variables after migrations.
# Existing account activation state is intentionally preserved: pausing the
# owner account must keep the platform locked across restarts and redeploys.
# Keep credentials in Render environment variables, never in source control.
username = os.environ.get('STAFF_LOGIN_USERNAME', '').strip()
password = os.environ.get('STAFF_LOGIN_PASSWORD', '')
email = os.environ.get('STAFF_LOGIN_EMAIL', '').strip()

if username and password:
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.filter(username=username).first()

    if user is None:
        User.objects.create_superuser(username=username, email=email, password=password)
    else:
        changed_fields = []
        if email and user.email != email:
            user.email = email
            changed_fields.append('email')
        if not user.is_staff:
            user.is_staff = True
            changed_fields.append('is_staff')
        if not user.is_superuser:
            user.is_superuser = True
            changed_fields.append('is_superuser')
        if not user.check_password(password):
            user.set_password(password)
            changed_fields.append('password')
        # Do not set is_active=True here. An inactive owner is the deadlock.
        if changed_fields:
            user.save(update_fields=changed_fields)
