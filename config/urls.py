from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from portal import views
from portal import management_views as management
from portal import profile_views

urlpatterns = [
    path('owner-recovery/', views.owner_recovery, name='owner_recovery'),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='portal/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('manage/', management.management_home, name='management_home'),
    path('manage/support-tickets/', management.support_tickets, name='support_tickets'),
    path('manage/support-tickets/<int:ticket_id>/update/', management.update_support_ticket, name='update_support_ticket'),
    path('profile/', profile_views.my_profile, name='my_profile'),
    path('manage/company/create/', management.create_company, name='create_company'),
    path('manage/company/join/', management.join_company, name='join_company'),
    path('manage/company/switch/', management.switch_company, name='switch_company'),
    path('manage/users/', management.company_users, name='company_users'),
    path('manage/users/<int:membership_id>/toggle/', management.toggle_membership, name='toggle_membership'),
    path('manage/support/', management.support_management, name='support_management'),
    path('manage/integrations/', management.integration_management, name='integration_management'),
    path('manage/integrations/<int:credential_id>/toggle/', management.toggle_integration, name='toggle_integration'),
    path('manage/tax-documents/', management.tax_documents, name='tax_documents'),
    path('manage/tax-documents/<int:document_id>/download/', management.download_tax_document, name='download_tax_document'),
    path('manage/tax-documents/<int:document_id>/review/', management.review_tax_document, name='review_tax_document'),
    path('manage/audit/', management.audit_log, name='audit_log'),
    path('', views.home, name='home'),
    path('apply/<int:job_id>/', views.apply, name='apply'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
]
