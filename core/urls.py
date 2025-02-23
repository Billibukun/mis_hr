# core/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    path('', CustomLoginView.as_view(), name='login'), # Login URL
    path('logout/', CustomLogoutView.as_view(), name='logout'), # Logout URL
    path('profile/update/', update_employee_profile, name='update_employee_profile'), # Profile Update URL
    path('profile/update/success/', profile_updated_success, name='profile_updated_success'), # Profile Update Success URL
    path('users/upload/csv/', upload_users_csv, name='upload_users_csv'), # User CSV Upload URL (under /admin/)
    path('admin/users/upload/csv/success/', upload_users_success, name='upload_users_success'), # User CSV Upload Success URL (under /admin/)
]