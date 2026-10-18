import os

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Application, AuditEvent, Company, CompanyMembership, IntegrationCredential, Job, PlatformControl


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'location', 'is_published', 'created_at')
    list_filter = ('is_published', 'employment_type')
    search_fields = ('title', 'company', 'location')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'job', 'email', 'created_at')
    search_fields = ('full_name', 'email', 'job__title')
    list_filter = ('created_at',)


@admin.register(PlatformControl)
class PlatformControlAdmin(admin.ModelAdmin):
    list_display = ('maintenance_mode', 'updated_at')
    fields = ('maintenance_mode', 'maintenance_message', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not PlatformControl.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class ProtectedOwnerUserAdmin(DjangoUserAdmin):
    # Disabling Django's bulk delete action prevents bypassing the owner guard.
    actions = [action for action in DjangoUserAdmin.actions if action != 'delete_selected']

    def _is_protected_owner(self, obj):
        owner_username = os.environ.get('STAFF_LOGIN_USERNAME', '').strip()
        return bool(owner_username and obj and obj.username == owner_username)

    def has_delete_permission(self, request, obj=None):
        if self._is_protected_owner(obj):
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        if self._is_protected_owner(obj):
            raise PermissionError('The configured platform owner account cannot be deleted.')
        return super().delete_model(request, obj)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if self._is_protected_owner(obj):
            fields.extend(field for field in ('username', 'is_superuser') if field not in fields)
        return fields


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_by', 'created_at')
    search_fields = ('name', 'legal_name', 'slug')
    list_filter = ('is_active',)
    exclude = ('pin_hash',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'role', 'is_active', 'updated_at')
    list_filter = ('role', 'is_active', 'company')
    search_fields = ('user__username', 'user__email', 'company__name')


@admin.register(IntegrationCredential)
class IntegrationCredentialAdmin(admin.ModelAdmin):
    list_display = ('company', 'provider', 'account_label', 'external_username', 'is_active', 'updated_at')
    list_filter = ('provider', 'is_active', 'company')
    search_fields = ('company__name', 'provider', 'account_label', 'external_username')
    exclude = ('encrypted_secret',)
    readonly_fields = ('created_at', 'updated_at')

    def has_add_permission(self, request):
        return False


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'company', 'action', 'target_type', 'target_id')
    list_filter = ('action', 'company', 'created_at')
    search_fields = ('actor__username', 'company__name', 'action', 'target_type', 'target_id')
    readonly_fields = ('actor', 'company', 'action', 'target_type', 'target_id', 'metadata', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
