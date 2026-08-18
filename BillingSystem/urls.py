"""
URL configuration for BillingSystem project.
"""

from django.contrib import admin
from django.urls import path
from billing_app import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('login/admin/',                  views.admin_login,              name='admin_login'),
    path('login/admin/forgot-password/',  views.admin_password_reset,     name='admin_password_reset'),

    path('login/distributor/',                  views.distributor_login,          name='distributor_login'),
    path('login/distributor/forgot-password/',  views.distributor_password_reset, name='distributor_password_reset'),

    path('dashboard/admin/',       views.admin_dashboard,       name='admin_dashboard'),
    path('dashboard/distributor/', views.distributor_dashboard, name='distributor_dashboard'),

    path('logout/', views.user_logout, name='logout'),
]
