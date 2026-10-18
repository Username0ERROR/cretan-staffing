from django.contrib import admin
from .models import Job, Application

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title','company','location','is_published','created_at')
    list_filter = ('is_published','employment_type')
    search_fields = ('title','company','location')

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('full_name','job','email','created_at')
    search_fields = ('full_name','email','job__title')
    list_filter = ('created_at',)


from .models import PlatformControl


@admin.register(PlatformControl)
class PlatformControlAdmin(admin.ModelAdmin):
    list_display = ('maintenance_mode', 'updated_at')
    fields = ('maintenance_mode', 'maintenance_message', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not PlatformControl.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
