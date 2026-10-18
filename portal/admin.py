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
