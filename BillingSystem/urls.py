"""
URL configuration for BillingSystem project.
"""

from django.contrib import admin
from django.urls import path
from billing_app import views

urlpatterns = [
    path('', views.portal_home, name='portal_home'),
    path('admin/', admin.site.urls),

    path('login/admin/',                  views.admin_login,          name='admin_login'),
    path('login/admin/forgot-password/',  views.admin_password_reset, name='admin_password_reset'),

    path('login/distributor/',                    views.distributor_login,           name='distributor_login'),
    path('login/distributor/forgot-password/',    views.distributor_forgot_password, name='distributor_password_reset'),
    path('login/distributor/verify-otp/',         views.distributor_verify_otp,      name='distributor_verify_otp'),
    path('login/distributor/resend-otp/',         views.distributor_resend_otp,      name='distributor_resend_otp'),
    path('login/distributor/reset-password/',     views.distributor_reset_password,  name='distributor_reset_password'),

    path('register/distributor/',                 views.distributor_register,        name='distributor_register'),

    path('dashboard/admin/',       views.admin_dashboard,       name='admin_dashboard'),
    path('dashboard/distributor/', views.distributor_dashboard, name='distributor_dashboard'),

    path('distributor/profile/',       views.distributor_profile, name='distributor_profile'),
    path('distributor/profile/edit/',  views.edit_profile,        name='edit_profile'),
    path('distributor/customers/',                           views.customer_list,   name='customer_list'),
    path('distributor/customers/add/',                       views.add_customer,    name='add_customer'),
    path('distributor/customers/<int:customer_id>/edit/',    views.edit_customer,   name='edit_customer'),
    path('distributor/customers/<int:customer_id>/delete/',  views.delete_customer, name='delete_customer'),

    path('logout/', views.user_logout, name='logout'),
]


