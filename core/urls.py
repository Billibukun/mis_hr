from django.urls import path
from . import views
from .auth_views import login_view, logout_view, change_password, password_reset_request, password_reset_confirm
from .onboarding_views import (
    profile_complete, staff_onboarding, staff_bulk_upload, staff_list,
    verify_employee, resolve_verification_issues, 
    get_lgas_for_state, get_units_for_department
)

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Authentication
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('change-password/', change_password, name='change_password'),
    path('password-reset/', password_reset_request, name='password_reset'),
    path('password-reset/confirm/', password_reset_confirm, name='password_reset_confirm'),
    
    # Profile
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/complete/', profile_complete, name='profile_complete'),
    
    # Department and Employee
    path('department/<int:pk>/', views.department_detail, name='department_detail'),
    path('employee/<int:pk>/', views.employee_detail, name='employee_detail'),
    
    # Staff Management (HR)
    path('staff/onboarding/', staff_onboarding, name='staff_onboarding'),
    path('staff/bulk-upload/', staff_bulk_upload, name='staff_bulk_upload'),
    path('staff/list/', staff_list, name='staff_list'),
    path('staff/verify/<int:employee_id>/', verify_employee, name='verify_employee'),
    path('staff/resolve-issues/<int:verification_id>/', resolve_verification_issues, name='resolve_verification_issues'),
    
    # AJAX endpoints
    path('ajax/lgas/', get_lgas_for_state, name='ajax_lgas'),
    path('ajax/units/', get_units_for_department, name='ajax_units'),
]