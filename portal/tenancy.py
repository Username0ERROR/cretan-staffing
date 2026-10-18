import os
import secrets

from cryptography.fernet import Fernet, InvalidToken
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import PermissionDenied, ImproperlyConfigured

from .models import AuditEvent, Company, CompanyMembership

MASTER_ROLES = {'master_admin'}
SUPPORT_ROLES = {'support_admin', 'support_user'}
COMPANY_ADMIN_ROLES = {'company_owner', 'company_admin'}
COMPANY_ROLES = COMPANY_ADMIN_ROLES | {'manager', 'employee', 'viewer'}
ALL_MEMBERSHIP_ROLES = SUPPORT_ROLES | COMPANY_ROLES

def is_master_admin(user):
    configured = os.environ.get('STAFF_LOGIN_USERNAME', '').strip()
    return bool(user.is_authenticated and user.is_active and user.is_superuser and configured and user.username == configured)

def membership_for(user, company):
    return CompanyMembership.objects.filter(user=user, company=company, is_active=True).first()

def role_for(user, company=None):
    if is_master_admin(user):
        return 'master_admin'
    if company is None:
        return ''
    membership = membership_for(user, company)
    return membership.role if membership else ''

def can_manage_company(user, company):
    return is_master_admin(user) or role_for(user, company) in COMPANY_ADMIN_ROLES

def require_master_admin(user):
    if not is_master_admin(user):
        raise PermissionDenied('Only the main platform administrator can perform this action.')

def require_company_access(user, company):
    if not is_master_admin(user) and not membership_for(user, company):
        raise PermissionDenied('You do not have access to this company.')

def require_company_admin(user, company):
    if not can_manage_company(user, company):
        raise PermissionDenied('Only this company owner or administrator can manage company users.')

def make_company_pin():
    # Shown once at company creation; only a password hash is persisted.
    return secrets.token_urlsafe(9).replace('-', 'A').replace('_', 'B')[:12].upper()

def verify_company_pin(company, pin):
    return bool(pin and check_password(pin.strip().upper(), company.pin_hash))

def audit(actor, action, company=None, target_type='', target_id='', metadata=None):
    AuditEvent.objects.create(
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        company=company, action=action, target_type=target_type,
        target_id=str(target_id or ''), metadata=metadata or {},
    )

def _fernet():
    key = os.environ.get('CREDENTIAL_ENCRYPTION_KEY', '').strip()
    if not key:
        raise ImproperlyConfigured('CREDENTIAL_ENCRYPTION_KEY is not configured; integration secrets cannot be saved.')
    try:
        return Fernet(key.encode('ascii'))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured('CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key.') from exc

def encrypt_secret(value):
    return _fernet().encrypt(value.encode('utf-8')).decode('ascii')

def decrypt_secret(value):
    try:
        return _fernet().decrypt(value.encode('ascii')).decode('utf-8')
    except InvalidToken as exc:
        raise ImproperlyConfigured('The integration secret could not be decrypted; check the encryption key.') from exc
