from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Core app (dashboard, auth, etc.)
    path('', include('core.urls')),
    
    # HR modules (training, leave, etc.)
    path('hr/', include('hr_modules.urls')),
    
    # Task management
    path('tasks/', include('task_management.urls')),
    
    # File management
    path('files/', include('file_management.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)