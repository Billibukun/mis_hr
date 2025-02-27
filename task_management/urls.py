from django.urls import path
from . import views

app_name = 'task_management'

urlpatterns = [
    # Task views
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/dashboard/', views.task_dashboard, name='task_dashboard'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/update/', views.task_update, name='task_update'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/add-comment/', views.task_add_comment, name='task_add_comment'),
    path('tasks/<int:pk>/add-attachment/', views.task_add_attachment, name='task_add_attachment'),
    path('tasks/<int:pk>/add-reminder/', views.task_add_reminder, name='task_add_reminder'),
    path('tasks/<int:pk>/add-dependency/', views.task_add_dependency, name='task_add_dependency'),
    path('tasks/<int:pk>/remove-dependency/<int:dependency_pk>/', views.task_remove_dependency, name='task_remove_dependency'),
    path('tasks/export/', views.task_export, name='task_export'),
    
    # Workflow views
    path('workflows/', views.workflow_list, name='workflow_list'),
    path('workflows/<int:pk>/', views.workflow_detail, name='workflow_detail'),
    path('workflows/create/', views.workflow_create, name='workflow_create'),
    path('workflows/<int:pk>/update/', views.workflow_update, name='workflow_update'),
    path('workflows/<int:pk>/delete/', views.workflow_delete, name='workflow_delete'),
    path('workflows/<int:workflow_pk>/statuses/', views.workflow_status_manage, name='workflow_status_manage'),
]