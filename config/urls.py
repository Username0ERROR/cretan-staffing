from django.contrib import admin
from django.urls import path
from portal import views

urlpatterns = [path('admin/', admin.site.urls), path('', views.home, name='home'), path('apply/<int:job_id>/', views.apply, name='apply'), path('staff/', views.staff_dashboard, name='staff_dashboard')]
