from django.urls import path
from . import views

app_name = 'file_management'

urlpatterns = [
    # File views
    path('files/', views.file_list, name='file_list'),
    path('files/<int:pk>/', views.file_detail, name='file_detail'),
    path('files/upload/', views.file_upload, name='file_upload'),
    path('files/<int:pk>/update/', views.file_update, name='file_update'),
    path('files/<int:pk>/delete/', views.file_delete, name='file_delete'),
    path('files/<int:pk>/download/', views.file_download, name='file_download'),
    path('files/<int:pk>/share/', views.file_share, name='file_share'),
    path('files/<int:pk>/share/<int:share_pk>/revoke/', views.file_share_revoke, name='file_share_revoke'),
    path('files/<int:pk>/comment/', views.file_add_comment, name='file_add_comment'),
    path('files/<int:pk>/version-upload/', views.file_version_upload, name='file_version_upload'),
    path('files/export/', views.file_export, name='file_export'),
    path('files/search/', views.file_search, name='file_search'),
    
    # Folder views
    path('folders/', views.folder_list, name='folder_list'),
    path('folders/create/', views.folder_create, name='folder_create'),
    path('folders/<int:pk>/update/', views.folder_update, name='folder_update'),
    path('folders/<int:pk>/delete/', views.folder_delete, name='folder_delete'),
    path('folders/<int:pk>/add-file/', views.folder_add_file, name='folder_add_file'),
    path('folders/<int:folder_pk>/remove-file/<int:file_pk>/', views.folder_remove_file, name='folder_remove_file'),
]