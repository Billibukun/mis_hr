# core/urls.py
from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.HomeView.as_view(), name='home'),
    path('profile/update/', views.EmployeeProfileUpdateView.as_view(), name='update_employee_profile'),
    # Newsletter URLs
    path('newsletter/', views.NewsletterListView.as_view(), name='newsletter_list'),
    path('newsletter/create/', views.NewsletterCreateView.as_view(), name='newsletter_create'),
    path('newsletter/<int:pk>/update/', views.NewsletterUpdateView.as_view(), name='newsletter_update'),
    path('newsletter/<int:pk>/delete/', views.NewsletterDeleteView.as_view(), name='newsletter_delete'),
    path('newsletter/<int:pk>/', views.NewsletterDetailView.as_view(), name='newsletter_detail'),
]