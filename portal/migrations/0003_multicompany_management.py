import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('portal', '0002_platformcontrol'),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=180)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('legal_name', models.CharField(blank=True, max_length=220)),
                ('tax_id_last4', models.CharField(blank=True, max_length=4)),
                ('pin_hash', models.CharField(max_length=256)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='companies_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='CompanyMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('company_owner', 'Company owner'), ('company_admin', 'Company administrator'), ('manager', 'Manager'), ('employee', 'Employee'), ('viewer', 'Read-only viewer'), ('support_user', 'Support user'), ('support_admin', 'Support administrator')], default='employee', max_length=24)),
                ('is_active', models.BooleanField(default=True)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='portal.company')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='company_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['company__name', 'user__username']},
        ),
        migrations.CreateModel(
            name='AuditEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=100)),
                ('target_type', models.CharField(blank=True, max_length=100)),
                ('target_id', models.CharField(blank=True, max_length=100)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='platform_audit_events', to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_events', to='portal.company')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='IntegrationCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(max_length=120)),
                ('account_label', models.CharField(max_length=160)),
                ('external_username', models.CharField(blank=True, max_length=254)),
                ('encrypted_secret', models.TextField(help_text='Fernet-encrypted API token/secret; never store a third-party account password here.')),
                ('scopes', models.CharField(blank=True, max_length=500)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='integrations', to='portal.company')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='integrations_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['company__name', 'provider', 'account_label']},
        ),
        migrations.CreateModel(
            name='TaxDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_type', models.CharField(choices=[('w4', 'Federal W-4'), ('w9', 'Form W-9'), ('i9', 'Form I-9'), ('1099', 'Form 1099'), ('w2', 'Form W-2'), ('payroll', 'Payroll / tax statement'), ('other', 'Other tax document')], max_length=20)),
                ('tax_year', models.PositiveSmallIntegerField()),
                ('status', models.CharField(choices=[('uploaded', 'Uploaded'), ('review', 'Needs review'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='uploaded', max_length=20)),
                ('file', models.FileField(upload_to='private_tax_upload_path')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_note', models.CharField(blank=True, max_length=500)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tax_documents', to='portal.company')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tax_documents', to=settings.AUTH_USER_MODEL)),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tax_documents_uploaded', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-uploaded_at']},
        ),
        migrations.AddField(
            model_name='job',
            name='company_account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='jobs', to='portal.company'),
        ),
        migrations.AddConstraint(
            model_name='companymembership',
            constraint=models.UniqueConstraint(fields=('user', 'company'), name='unique_user_company_membership'),
        ),
    ]
