import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


def _cipher():
    key = os.environ.get('CREDENTIAL_ENCRYPTION_KEY', '').strip()
    if not key:
        raise ImproperlyConfigured('CREDENTIAL_ENCRYPTION_KEY must be configured before storing private files.')
    try:
        return Fernet(key.encode('ascii'))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured('CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key.') from exc


@deconstructible
class EncryptedPrivateStorage(FileSystemStorage):
    """Local private storage that encrypts bytes before writing to disk."""
    def __init__(self, location=None, base_url=None, file_permissions_mode=None, directory_permissions_mode=None):
        super().__init__(
            location=location or os.environ.get('PRIVATE_MEDIA_ROOT', str(settings.BASE_DIR / 'private_media')),
            base_url=base_url or None,
            file_permissions_mode=file_permissions_mode,
            directory_permissions_mode=directory_permissions_mode,
        )

    def _save(self, name, content):
        raw = content.read()
        if hasattr(content, 'seek'):
            content.seek(0)
        encrypted = _cipher().encrypt(raw)
        return super()._save(name, ContentFile(encrypted))

    def _open(self, name, mode='rb'):
        encrypted_file = super()._open(name, mode)
        try:
            encrypted = encrypted_file.read()
        finally:
            encrypted_file.close()
        try:
            plaintext = _cipher().decrypt(encrypted)
        except InvalidToken as exc:
            raise ImproperlyConfigured('Private document could not be decrypted; check CREDENTIAL_ENCRYPTION_KEY.') from exc
        return ContentFile(plaintext, name=os.path.basename(name))
