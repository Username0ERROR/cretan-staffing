import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()

# Optional first-run staff account provisioning. Credentials are supplied only
# through Render environment variables and are never stored in source control.
username = os.environ.get('STAFF_LOGIN_USERNAME', '').strip()
password = os.environ.get('STAFF_LOGIN_PASSWORD', '')
email = os.environ.get('STAFF_LOGIN_EMAIL', '').strip()
if username and password:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
