from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve, reverse
from django.contrib.auth.views import LoginView
from django.conf import settings
from .permissions import get_user_permissions

class PermissionMiddleware:
    """
    Middleware to check user permissions for each request
    and store permissions in the request for easy access
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Define URL patterns that don't require permission checks
        self.public_urls = [
            'login',
            'logout',
            'password_reset',
            'password_reset_done',
            'password_reset_confirm',
            'password_reset_complete',
            'static',
            'media',
            'admin:',  # Django admin URLs (handled by admin's own permission system)
        ]
        
        # Define permission requirements for URL namespaces
        self.permission_map = {
            'hr_modules:': {
                'training': 'can_manage_trainings',
                'leave': 'can_manage_leaves',
                'examination': 'can_manage_examinations',
                'promotion': 'can_manage_promotions',
                'transfer': 'can_manage_transfers',
                'educational_upgrade': 'can_manage_educational_upgrades',
                'retirement': 'can_manage_retirements',
            },
            'task_management:': 'can_create_tasks',
            'file_management:': 'can_manage_files',
            'admin:': 'can_manage_users',  # Additional check on top of Django admin permissions
        }
        
    def __call__(self, request):
        # Skip permission checks for unauthenticated users
        # They will be redirected to login by Django's authentication system
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Get the current URL name
        url_name = resolve(request.path_info).url_name
        namespace = resolve(request.path_info).namespace
        
        # Check if the URL is public or doesn't need permission checks
        full_url_name = f"{namespace}:{url_name}" if namespace else url_name
        if self._is_public_url(full_url_name):
            return self.get_response(request)
        
        # Get user permissions and add them to the request
        request.user_permissions = get_user_permissions(request.user)
        
        # Check if the user has the required permissions for this URL
        if not self._has_required_permission(request.user, request.user_permissions, namespace, url_name):
            messages.error(request, "You do not have permission to access this page.")
            return redirect('dashboard')  # Redirect to a safe page
        
        # Proceed with the request
        return self.get_response(request)
    
    def _is_public_url(self, url_name):
        """Check if a URL is in the public URLs list"""
        return any(url_name.startswith(public_url) for public_url in self.public_urls)
    
    def _has_required_permission(self, user, user_permissions, namespace, url_name):
        """Check if the user has the required permissions for the URL"""
        # Superusers have all permissions
        if user.is_superuser:
            return True
        
        # Staff users can access all except admin
        if user.is_staff and not namespace == 'admin':
            return True
        
        # Check namespace permissions
        namespace_with_colon = f"{namespace}:" if namespace else ""
        
        if namespace_with_colon in self.permission_map:
            permission_req = self.permission_map[namespace_with_colon]
            
            # If permission_req is a dict, check for specific URL patterns
            if isinstance(permission_req, dict):
                for url_pattern, permission_name in permission_req.items():
                    if url_name.startswith(url_pattern):
                        return permission_name in user_permissions and user_permissions[permission_name]
                
                # If no specific pattern matched, allow access (could be a dashboard or index page)
                return True
            
            # If permission_req is a string, check that specific permission
            else:
                return permission_req in user_permissions and user_permissions[permission_req]
        
        # If no specific permissions defined for this namespace, allow access
        return True