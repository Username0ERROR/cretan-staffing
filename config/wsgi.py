import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()

# Bootstrap the staff login from Render environment variables.
# This runs after migrations because the Render start command migrates first.
# Keep credentials in Render only; never hard-code them here.
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
        # If the configured username already exists, make it the configured
        # staff administrator and sync its password from the environment.
        changed_fields = []
        if email and user.email != email:
            user.email = email
            changed_fields.append('email')
        if not user.is_active:
            user.is_active = True
            changed_fields.append('is_active')
        if not user.is_staff:
            user.is_staff = True
            changed_fields.append('is_staff')
        if not user.is_superuser:
            user.is_superuser = True
            changed_fields.append('is_superuser')
        if not user.check_password(password):
            user.set_password(password)
            changed_fields.append('password')
        if changed_fields:
            user.save()
