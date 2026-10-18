from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from portal import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='portal/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.home, name='home'),
    path('apply/<int:job_id>/', views.apply, name='apply'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
]
