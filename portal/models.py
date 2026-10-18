import os
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from .storage import EncryptedPrivateStorage


def private_tax_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower()[:12]
    return f'private-tax/company-{instance.company_id}/user-{instance.owner_id}/{instance.pk or "new"}{suffix}'


class Company(models.Model):
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    legal_name = models.CharField(max_length=220, blank=True)
    tax_id_last4 = models.CharField(max_length=4, blank=True)
    pin_hash = models.CharField(max_length=256)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='companies_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CompanyMembership(models.Model):
    ROLE_CHOICES = [
        ('company_owner', 'Company owner'),
        ('company_admin', 'Company administrator'),
        ('manager', 'Manager'),
        ('employee', 'Employee'),
        ('viewer', 'Read-only viewer'),
        ('support_user', 'Support user'),
        ('support_admin', 'Support administrator'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='company_memberships')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=24, choices=ROLE_CHOICES, default='employee')
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'company'], name='unique_user_company_membership')]
        ordering = ['company__name', 'user__username']

    def __str__(self):
        return f'{self.user} — {self.company} ({self.role})'


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='platform_audit_events')
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_events')
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} ({self.created_at:%Y-%m-%d %H:%M})'


class IntegrationCredential(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='integrations')
    provider = models.CharField(max_length=120)
    endpoint_url = models.URLField(max_length=500, blank=True, help_text='HTTPS base URL for the connected system, such as a Horilla instance.')
    account_label = models.CharField(max_length=160)
    external_username = models.CharField(max_length=254, blank=True)
    encrypted_secret = models.TextField(help_text='Fernet-encrypted API token/secret; never store a third-party account password here.')
    scopes = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='integrations_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['company__name', 'provider', 'account_label']

    def __str__(self):
        return f'{self.company}: {self.provider} — {self.account_label}'


class TaxDocument(models.Model):
    TYPE_CHOICES = [
        ('w4', 'Federal W-4'),
        ('w9', 'Form W-9'),
        ('i9', 'Form I-9'),
        ('1099', 'Form 1099'),
        ('w2', 'Form W-2'),
        ('payroll', 'Payroll / tax statement'),
        ('other', 'Other tax document'),
    ]
    STATUS_CHOICES = [('uploaded', 'Uploaded'), ('review', 'Needs review'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tax_documents')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tax_documents')
    document_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    tax_year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    file = models.FileField(upload_to=private_tax_upload_path, storage=EncryptedPrivateStorage())
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='tax_documents_uploaded')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.get_document_type_display()} {self.tax_year} — {self.owner}'


class Job(models.Model):
    title = models.CharField(max_length=160)
    company = models.CharField(max_length=160)
    company_account = models.ForeignKey(Company, null=True, blank=True, on_delete=models.CASCADE, related_name='jobs')
    location = models.CharField(max_length=160, default='United States')
    employment_type = models.CharField(max_length=60, default='Full-time')
    description = models.TextField()
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.title} — {self.company}'


class Application(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.full_name} — {self.job.title}'


class PlatformControl(models.Model):
    """Singleton control for site availability, managed by the owner in Django Admin."""
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.CharField(
        max_length=240,
        default='Cretan Staffing is temporarily undergoing scheduled maintenance. Please check back soon.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Website availability'
        verbose_name_plural = 'Website availability'

    def __str__(self):
        return 'Website maintenance controls'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SupportTicket(models.Model):
    STATUS_CHOICES = [('open', 'Open'), ('in_progress', 'In progress'), ('waiting', 'Waiting for user'), ('resolved', 'Resolved'), ('closed', 'Closed')]
    PRIORITY_CHOICES = [('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')]
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name='support_tickets')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets_created')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='support_tickets_assigned')
    subject = models.CharField(max_length=180)
    description = models.TextField(max_length=5000)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'#{self.pk} {self.subject}'
