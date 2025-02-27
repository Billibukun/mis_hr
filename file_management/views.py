from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, F
from django.http import JsonResponse, HttpResponse

from .models import (
    File, FileCategory, FileAccessLevel, FileSharePermission, 
    FileAccessLog, FileTag, FileTagAssignment, FileComment,
    Folder, FolderFile
)

from core.models import EmployeeProfile, Department
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from datetime import timedelta
import csv
import json
import mimetypes
import uuid


@login_required
def file_list(request):
    """List all files with filters"""
    # Get filter parameters
    category_id = request.GET.get('category', '')
    status = request.GET.get('status', '')
    file_type = request.GET.get('file_type', '')
    created_by_id = request.GET.get('created_by', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    employee_profile = request.user.employee_profile
    
    # Check if user can view all files
    can_view_all = request.user.user_permissions.get('can_view_all_files', False)
    
    # Base queryset - filter by access permissions
    if can_view_all:
        files = File.objects.filter(status='ACTIVE').select_related(
            'category', 'access_level', 'created_by', 'owner_employee', 'owner_department'
        )
    else:
        # Files the user can access
        files = File.objects.filter(
            # Files created by the user
            Q(created_by=request.user) |
            # Files owned by the user's employee profile
            Q(owner_employee=employee_profile) |
            # Files owned by the user's department
            Q(owner_department=employee_profile.current_department) |
            # Files explicitly shared with the user
            Q(share_permissions__user=request.user) |
            # Files shared with the user's department
            Q(share_permissions__department=employee_profile.current_department) |
            # Public files with appropriate access level
            Q(is_public=True)
        ).filter(status='ACTIVE').select_related(
            'category', 'access_level', 'created_by', 'owner_employee', 'owner_department'
        ).distinct()
    
    # Order by recency
    files = files.order_by('-created_at')
    
    # Apply filters
    if category_id:
        files = files.filter(category_id=category_id)
    
    if status:
        files = files.filter(status=status)
    
    if file_type:
        files = files.filter(file_type=file_type)
    
    if created_by_id:
        files = files.filter(created_by_id=created_by_id)
    
    if date_from:
        files = files.filter(created_at__date__gte=date_from)
    
    if date_to:
        files = files.filter(created_at__date__lte=date_to)
    
    if search:
        files = files.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(file_reference__icontains=search)
        )
    
    # Get filter options
    categories = FileCategory.objects.all().order_by('name')
    
    # Get recent files
    recent_files = File.objects.filter(
        created_by=request.user,
        status='ACTIVE'
    ).order_by('-created_at')[:5]
    
    # Get shared files
    shared_files = File.objects.filter(
        share_permissions__user=request.user,
        status='ACTIVE'
    ).exclude(
        created_by=request.user
    ).order_by('-share_permissions__granted_at')[:5]
    
    # Get file types for filter
    file_types = File.objects.values_list('file_type', flat=True).distinct()
    
    context = {
        'files': files,
        'recent_files': recent_files,
        'shared_files': shared_files,
        'categories': categories,
        'file_types': file_types,
        'can_manage_files': request.user.user_permissions.get('can_manage_files', False),
        'can_view_all': can_view_all,
        'filter_category': category_id,
        'filter_status': status,
        'filter_file_type': file_type,
        'filter_created_by': created_by_id,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'search': search,
    }
    
    return render(request, 'file_management/file_list.html', context)


@login_required
def file_detail(request, pk):
    """View file details"""
    file = get_object_or_404(File, pk=pk)
    
    # Check if user has permission to view this file
    if not user_can_access_file(request.user, file, 'VIEW'):
        messages.error(request, "You don't have permission to view this file.")
        return redirect('file_management:file_list')
    
    # Log access
    FileAccessLog.objects.create(
        file=file,
        user=request.user,
        action='VIEW',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
    )
    
    # Get related data
    comments = FileComment.objects.filter(file=file).select_related('user').order_by('created_at')
    tags = FileTagAssignment.objects.filter(file=file).select_related('tag', 'assigned_by')
    
    # Get share permissions
    share_permissions = FileSharePermission.objects.filter(file=file).select_related(
        'user', 'department', 'granted_by'
    )
    
    # Get folders containing this file
    folders = FolderFile.objects.filter(file=file).select_related('folder', 'added_by')
    
    # Get access logs
    access_logs = FileAccessLog.objects.filter(file=file).select_related('user').order_by('-timestamp')[:10]
    
    # Check if user has edit permission
    can_edit = user_can_access_file(request.user, file, 'EDIT')
    
    # Check if user can manage file permissions
    can_manage_permissions = (
        file.created_by == request.user or 
        request.user.user_permissions.get('can_manage_file_permissions', False)
    )
    
    context = {
        'file': file,
        'comments': comments,
        'tags': tags,
        'share_permissions': share_permissions,
        'folders': folders,
        'access_logs': access_logs,
        'can_edit': can_edit,
        'can_delete': user_can_access_file(request.user, file, 'DELETE'),
        'can_manage_permissions': can_manage_permissions,
    }
    
    return render(request, 'file_management/file_detail.html', context)


@login_required
def file_upload(request):
    """Upload a new file (metadata only)"""
    if request.method == 'POST':
        # Process form data
        title = request.POST.get('title')
        description = request.POST.get('description')
        category_id = request.POST.get('category') or None
        access_level_id = request.POST.get('access_level')
        is_confidential = request.POST.get('is_confidential') == 'on'
        
        file_type = request.POST.get('file_type')
        file_size = request.POST.get('file_size') or None
        
        # Generate a unique file reference (in a real system, this would be linked to actual storage)
        file_reference = f"file_{uuid.uuid4()}.{file_type}"
        
        # Validate required fields
        if not all([title, file_reference, file_type, access_level_id]):
            messages.error(request, "Please fill all required fields.")
            return redirect('file_management:file_upload')
        
        # Create file
        file = File.objects.create(
            title=title,
            description=description,
            category_id=category_id,
            file_reference=file_reference,
            file_type=file_type,
            file_size=file_size,
            created_by=request.user,
            access_level_id=access_level_id,
            is_confidential=is_confidential,
            owner_employee=request.user.employee_profile,
            owner_department=request.user.employee_profile.current_department,
            status='ACTIVE',
            version='1.0',
            is_latest_version=True
        )
        
        # Add tags if provided
        tags = request.POST.get('tags', '').split(',')
        for tag_name in tags:
            tag_name = tag_name.strip()
            if tag_name:
                tag, created = FileTag.objects.get_or_create(name=tag_name)
                FileTagAssignment.objects.create(
                    file=file,
                    tag=tag,
                    assigned_by=request.user
                )
        
        messages.success(request, f"File '{title}' uploaded successfully.")
        return redirect('file_management:file_detail', pk=file.pk)
    
    # Get form options
    categories = FileCategory.objects.all().order_by('name')
    access_levels = FileAccessLevel.objects.all()
    
    context = {
        'categories': categories,
        'access_levels': access_levels,
    }
    
    return render(request, 'file_management/file_upload.html', context)


@login_required
def file_update(request, pk):
    """Update file metadata"""
    file = get_object_or_404(File, pk=pk)
    
    # Check if user has permission to edit this file
    if not user_can_access_file(request.user, file, 'EDIT'):
        messages.error(request, "You don't have permission to edit this file.")
        return redirect('file_management:file_detail', pk=file.pk)
    
    if request.method == 'POST':
        # Process form data
        file.title = request.POST.get('title')
        file.description = request.POST.get('description')
        file.category_id = request.POST.get('category') or None
        file.access_level_id = request.POST.get('access_level')
        file.is_confidential = request.POST.get('is_confidential') == 'on'
        file.modified_by = request.user
        
        file.save()
        
        # Update tags if provided
        existing_tags = FileTagAssignment.objects.filter(file=file)
        existing_tags.delete()
        
        tags = request.POST.get('tags', '').split(',')
        for tag_name in tags:
            tag_name = tag_name.strip()
            if tag_name:
                tag, created = FileTag.objects.get_or_create(name=tag_name)
                FileTagAssignment.objects.create(
                    file=file,
                    tag=tag,
                    assigned_by=request.user
                )
        
        # Log access
        FileAccessLog.objects.create(
            file=file,
            user=request.user,
            action='EDIT',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
        )
        
        messages.success(request, f"File '{file.title}' updated successfully.")
        return redirect('file_management:file_detail', pk=file.pk)
    
    # Get form options
    categories = FileCategory.objects.all().order_by('name')
    access_levels = FileAccessLevel.objects.all()
    
    # Get current tags
    current_tags = FileTagAssignment.objects.filter(file=file).values_list('tag__name', flat=True)
    
    context = {
        'file': file,
        'categories': categories,
        'access_levels': access_levels,
        'current_tags': ','.join(current_tags),
    }
    
    return render(request, 'file_management/file_update.html', context)


@login_required
def file_delete(request, pk):
    """Delete a file (mark as DELETED)"""
    file = get_object_or_404(File, pk=pk)
    
    # Check if user has permission to delete this file
    if not user_can_access_file(request.user, file, 'DELETE'):
        messages.error(request, "You don't have permission to delete this file.")
        return redirect('file_management:file_detail', pk=file.pk)
    
    if request.method == 'POST':
        # Mark file as deleted
        file.status = 'DELETED'
        file.modified_by = request.user
        file.save()
        
        # Log access
        FileAccessLog.objects.create(
            file=file,
            user=request.user,
            action='DELETE',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
        )
        
        messages.success(request, f"File '{file.title}' deleted successfully.")
        return redirect('file_management:file_list')
    
    context = {
        'file': file,
    }
    
    return render(request, 'file_management/file_confirm_delete.html', context)


@login_required
def file_download(request, pk):
    """Download a file (in a real system, this would serve the actual file)"""
    file = get_object_or_404(File, pk=pk)
    
    # Check if user has permission to view this file
    if not user_can_access_file(request.user, file, 'VIEW'):
        messages.error(request, "You don't have permission to download this file.")
        return redirect('file_management:file_list')
    
    # Log access
    FileAccessLog.objects.create(
        file=file,
        user=request.user,
        action='DOWNLOAD',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
    )
    
    # In a real system, this would serve the actual file
    # For now, just redirect back with a message
    messages.info(request, f"Download initiated for '{file.title}'.")
    return redirect('file_management:file_detail', pk=file.pk)


@login_required
def file_share(request, pk):
    """Share a file with users or departments"""
    file = get_object_or_404(File, pk=pk)
    
    # Check if user has permission to share this file
    if not user_can_access_file(request.user, file, 'FULL'):
        messages.error(request, "You don't have permission to share this file.")
        return redirect('file_management:file_detail', pk=file.pk)
    
    if request.method == 'POST':
        share_type = request.POST.get('share_type')
        permission = request.POST.get('permission')
        expires_at = request.POST.get('expires_at') or None
        
        if share_type == 'user':
            user_id = request.POST.get('user_id')
            if user_id:
                # Check if share already exists
                if FileSharePermission.objects.filter(file=file, user_id=user_id).exists():
                    messages.error(request, "This file is already shared with this user.")
                else:
                    FileSharePermission.objects.create(
                        file=file,
                        user_id=user_id,
                        permission=permission,
                        expires_at=expires_at,
                        granted_by=request.user
                    )
                    messages.success(request, "File shared with user successfully.")
            else:
                messages.error(request, "Please select a user.")
        
        elif share_type == 'department':
            department_id = request.POST.get('department_id')
            if department_id:
                # Check if share already exists
                if FileSharePermission.objects.filter(file=file, department_id=department_id).exists():
                    messages.error(request, "This file is already shared with this department.")
                else:
                    FileSharePermission.objects.create(
                        file=file,
                        department_id=department_id,
                        permission=permission,
                        expires_at=expires_at,
                        granted_by=request.user
                    )
                    messages.success(request, "File shared with department successfully.")
            else:
                messages.error(request, "Please select a department.")
        
        return redirect('file_management:file_detail', pk=file.pk)
    
    # Get share options
    users = User.objects.filter(is_active=True).order_by('last_name')
    departments = Department.objects.all().order_by('name')
    
    # Get existing shares
    existing_shares = FileSharePermission.objects.filter(file=file).select_related('user', 'department', 'granted_by')
    
    context = {
        'file': file,
        'users': users,
        'departments': departments,
        'existing_shares': existing_shares,
    }
    
    return render(request, 'file_management/file_share.html', context)


@login_required
def file_share_revoke(request, pk, share_pk):
    """Revoke a file share permission"""
    file = get_object_or_404(File, pk=pk)
    share = get_object_or_404(FileSharePermission, pk=share_pk, file=file)
    
    # Check if user has permission to manage shares
    if not (file.created_by == request.user or 
            request.user.user_permissions.get('can_manage_file_permissions', False) or
            share.granted_by == request.user):
        messages.error(request, "You don't have permission to revoke this share.")
        return redirect('file_management:file_detail', pk=file.pk)
    
    if request.method == 'POST':
        share.delete()
        messages.success(request, "File share permission revoked successfully.")
        return redirect('file_management:file_detail', pk=file.pk)
    
    context = {
        'file': file,
        'share': share,
    }
    
    return render(request, 'file_management/share_confirm_revoke.html', context)


@login_required
def file_add_comment(request, pk):
    """Add a comment to a file"""
    file = get_object_or_404(File, pk=pk)
    
    # Check if user has permission to view this file
    if not user_can_access_file(request.user, file, 'VIEW'):
        messages.error(request, "You don't have permission to comment on this file.")
        return redirect('file_management:file_list')
    
    if request.method == 'POST':
        comment_text = request.POST.get('comment')
        
        if not comment_text:
            messages.error(request, "Comment cannot be empty.")
            return redirect('file_management:file_detail', pk=file.pk)
        
        # Create comment
        comment = FileComment.objects.create(
            file=file,
            user=request.user,
            comment=comment_text
        )
        
        messages.success(request, "Comment added successfully.")
        return redirect('file_management:file_detail', pk=file.pk)
    
    return redirect('file_management:file_detail', pk=file.pk)


@login_required
def folder_list(request):
    """List all folders"""
    employee_profile = request.user.employee_profile
    
    # Get parent folder if specified
    parent_id = request.GET.get('parent', None)
    
    # Base folders query
    if parent_id:
        parent = get_object_or_404(Folder, pk=parent_id)
        folders = Folder.objects.filter(parent=parent)
        breadcrumbs = get_folder_breadcrumbs(parent)
    else:
        folders = Folder.objects.filter(parent=None)
        breadcrumbs = []
    
    # Filter folders by access permission
    if not request.user.user_permissions.get('can_view_all_files', False):
        folders = folders.filter(
            # Folders owned by the user
            Q(owner=request.user) |
            # Folders owned by the user's department
            Q(department=employee_profile.current_department) |
            # Public folders
            Q(is_public=True)
        )
    
    # Get files in the current folder
    if parent_id:
        folder_files = FolderFile.objects.filter(folder_id=parent_id).select_related('file', 'added_by')
        
        # Filter files by access permission
        if not request.user.user_permissions.get('can_view_all_files', False):
            visible_files = []
            for folder_file in folder_files:
                if user_can_access_file(request.user, folder_file.file, 'VIEW'):
                    visible_files.append(folder_file)
            folder_files = visible_files
    else:
        folder_files = []
    
    # Get recent folders
    recent_folders = Folder.objects.filter(
        Q(owner=request.user) |
        Q(department=employee_profile.current_department)
    ).order_by('-modified_at')[:5]
    
    context = {
        'folders': folders,
        'folder_files': folder_files,
        'parent_id': parent_id,
        'breadcrumbs': breadcrumbs,
        'recent_folders': recent_folders,
        'can_manage_files': request.user.user_permissions.get('can_manage_files', False),
    }
    
    return render(request, 'file_management/folder_list.html', context)


@login_required
def folder_create(request):
    """Create a new folder"""
    # Get parent folder if specified
    parent_id = request.GET.get('parent', None)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        parent_id = request.POST.get('parent')
        department_id = request.POST.get('department')
        is_public = request.POST.get('is_public') == 'on'
        access_level_id = request.POST.get('access_level')
        
        if not name:
            messages.error(request, "Folder name is required.")
            return redirect('file_management:folder_create')
        
        # Create folder
        folder = Folder.objects.create(
            name=name,
            description=description,
            parent_id=parent_id or None,
            owner=request.user,
            department_id=department_id or None,
            is_public=is_public,
            access_level_id=access_level_id
        )
        
        messages.success(request, f"Folder '{name}' created successfully.")
        
        # Redirect to parent folder if specified
        if parent_id:
            return redirect('file_management:folder_list', parent=parent_id)
        else:
            return redirect('file_management:folder_list')
    
    # Get form options
    departments = Department.objects.all().order_by('name')
    access_levels = FileAccessLevel.objects.all()
    
    # Get parent folder if specified
    parent = None
    if parent_id:
        parent = get_object_or_404(Folder, pk=parent_id)
    
    context = {
        'departments': departments,
        'access_levels': access_levels,
        'parent': parent,
    }
    
    return render(request, 'file_management/folder_form.html', context)


@login_required
def folder_update(request, pk):
    """Update a folder"""
    folder = get_object_or_404(Folder, pk=pk)
    
    # Check if user has permission to edit this folder
    if not (folder.owner == request.user or 
            request.user.user_permissions.get('can_manage_files', False)):
        messages.error(request, "You don't have permission to edit this folder.")
        return redirect('file_management:folder_list')
    
    if request.method == 'POST':
        folder.name = request.POST.get('name')
        folder.description = request.POST.get('description')
        folder.department_id = request.POST.get('department') or None
        folder.is_public = request.POST.get('is_public') == 'on'
        folder.access_level_id = request.POST.get('access_level')
        
        folder.save()
        
        messages.success(request, f"Folder '{folder.name}' updated successfully.")
        
        # Redirect to parent folder if exists
        if folder.parent:
            return redirect('file_management:folder_list', parent=folder.parent.pk)
        else:
            return redirect('file_management:folder_list')
    
    # Get form options
    departments = Department.objects.all().order_by('name')
    access_levels = FileAccessLevel.objects.all()
    
    context = {
        'folder': folder,
        'departments': departments,
        'access_levels': access_levels,
    }
    
    return render(request, 'file_management/folder_form.html', context)


@login_required
def folder_delete(request, pk):
    """Delete a folder"""
    folder = get_object_or_404(Folder, pk=pk)
    
    # Check if user has permission to delete this folder
    if not (folder.owner == request.user or 
            request.user.user_permissions.get('can_manage_files', False)):
        messages.error(request, "You don't have permission to delete this folder.")
        return redirect('file_management:folder_list')
    
    # Get parent folder ID for redirect
    parent_id = folder.parent.pk if folder.parent else None
    
    # Check if folder has subfolders
    if Folder.objects.filter(parent=folder).exists():
        messages.error(request, "Cannot delete folder that contains subfolders.")
        if parent_id:
            return redirect('file_management:folder_list', parent=parent_id)
        else:
            return redirect('file_management:folder_list')
    
    if request.method == 'POST':
        folder.delete()
        messages.success(request, f"Folder '{folder.name}' deleted successfully.")
        
        if parent_id:
            return redirect('file_management:folder_list', parent=parent_id)
        else:
            return redirect('file_management:folder_list')
    
    context = {
        'folder': folder,
    }
    
    return render(request, 'file_management/folder_confirm_delete.html', context)


@login_required
def folder_add_file(request, pk):
    """Add a file to a folder"""
    folder = get_object_or_404(Folder, pk=pk)
    
    # Check if user has permission to edit this folder
    if not (folder.owner == request.user or 
            request.user.user_permissions.get('can_manage_files', False)):
        messages.error(request, "You don't have permission to add files to this folder.")
        return redirect('file_management:folder_list', parent=pk)
    
    if request.method == 'POST':
        file_id = request.POST.get('file_id')
        
        if not file_id:
            messages.error(request, "Please select a file.")
            return redirect('file_management:folder_add_file', pk=folder.pk)
        
        # Check if file already in folder
        if FolderFile.objects.filter(folder=folder, file_id=file_id).exists():
            messages.error(request, "This file is already in the folder.")
            return redirect('file_management:folder_list', parent=pk)
        
        # Check if user has access to the file
        file = get_object_or_404(File, pk=file_id)
        if not user_can_access_file(request.user, file, 'VIEW'):
            messages.error(request, "You don't have permission to access this file.")
            return redirect('file_management:folder_list', parent=pk)
        
        # Add file to folder
        folder_file = FolderFile.objects.create(
            folder=folder,
            file=file,
            added_by=request.user
        )
        
        messages.success(request, f"File '{file.title}' added to folder successfully.")
        return redirect('file_management:folder_list', parent=pk)
    
    # Get files the user has access to
    employee_profile = request.user.employee_profile
    
    if request.user.user_permissions.get('can_view_all_files', False):
        files = File.objects.filter(status='ACTIVE').select_related('category')
    else:
        # Files the user can access
        files = File.objects.filter(
            # Files created by the user
            Q(created_by=request.user) |
            # Files owned by the user
            Q(owner_employee=employee_profile) |
            # Files owned by the user's department
            Q(owner_department=employee_profile.current_department) |
            # Files explicitly shared with the user
            Q(share_permissions__user=request.user) |
            # Files shared with the user's department
            Q(share_permissions__department=employee_profile.current_department) |
            # Public files
            Q(is_public=True)
        ).filter(status='ACTIVE').select_related('category').distinct()
    
    # Exclude files already in the folder
    existing_file_ids = FolderFile.objects.filter(folder=folder).values_list('file_id', flat=True)
    files = files.exclude(id__in=existing_file_ids)
    
    context = {
        'folder': folder,
        'files': files,
    }
    
    return render(request, 'file_management/folder_add_file.html', context)


@login_required
def folder_remove_file(request, folder_pk, file_pk):
    """Remove a file from a folder"""
    folder_file = get_object_or_404(FolderFile, folder_id=folder_pk, file_id=file_pk)
    
    # Check if user has permission to edit this folder
    if not (folder_file.folder.owner == request.user or 
            folder_file.added_by == request.user or
            request.user.user_permissions.get('can_manage_files', False)):
        messages.error(request, "You don't have permission to remove files from this folder.")
        return redirect('file_management:folder_list', parent=folder_pk)
    
    if request.method == 'POST':
        folder_file.delete()
        messages.success(request, "File removed from folder successfully.")
        return redirect('file_management:folder_list', parent=folder_pk)
    
    context = {
        'folder_file': folder_file,
    }
    
    return render(request, 'file_management/folder_file_confirm_remove.html', context)


@login_required
def file_search(request):
    """Advanced file search"""
    query = request.GET.get('q', '')
    
    if query:
        # Search files by title, description, and tags
        employee_profile = request.user.employee_profile
        
        # Base queryset with access permissions
        if request.user.user_permissions.get('can_view_all_files', False):
            files = File.objects.filter(status='ACTIVE')
        else:
            # Files the user can access
            files = File.objects.filter(
                # Files created by the user
                Q(created_by=request.user) |
                # Files owned by the user
                Q(owner_employee=employee_profile) |
                # Files owned by the user's department
                Q(owner_department=employee_profile.current_department) |
                # Files explicitly shared with the user
                Q(share_permissions__user=request.user) |
                # Files shared with the user's department
                Q(share_permissions__department=employee_profile.current_department) |
                # Public files
                Q(is_public=True)
            ).filter(status='ACTIVE').distinct()
        
        # Apply search query
        files = files.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(tag_assignments__tag__name__icontains=query)
        ).select_related(
            'category', 'created_by', 'owner_employee', 'owner_department'
        ).distinct()
    else:
        files = File.objects.none()
    
    context = {
        'files': files,
        'query': query,
    }
    
    return render(request, 'file_management/file_search.html', context)


@login_required
def file_version_upload(request, pk):
    """Upload a new version of a file"""
    file = get_object_or_404(File, pk=pk)
    
    # Check if user has permission to edit this file
    if not user_can_access_file(request.user, file, 'EDIT'):
        messages.error(request, "You don't have permission to upload a new version of this file.")
        return redirect('file_management:file_detail', pk=file.pk)
    
    if request.method == 'POST':
        version = request.POST.get('version')
        
        if not version:
            messages.error(request, "Please provide a version number.")
            return redirect('file_management:file_version_upload', pk=file.pk)
        
        # Update the current file's version status
        file.is_latest_version = False
        file.save()
        
        # Create a new version
        new_file = File.objects.create(
            title=file.title,
            description=file.description,
            category=file.category,
            file_reference=f"{file.file_reference.split('.')[0]}_{version}.{file.file_type}",
            file_type=file.file_type,
            file_size=request.POST.get('file_size') or file.file_size,
            created_by=request.user,
            access_level=file.access_level,
            is_confidential=file.is_confidential,
            owner_employee=file.owner_employee,
            owner_department=file.owner_department,
            status='ACTIVE',
            version=version,
            is_latest_version=True,
            previous_version=file
        )
        
        # Copy tags
        for tag_assignment in FileTagAssignment.objects.filter(file=file):
            FileTagAssignment.objects.create(
                file=new_file,
                tag=tag_assignment.tag,
                assigned_by=request.user
            )
        
        # Copy share permissions
        for share in FileSharePermission.objects.filter(file=file):
            FileSharePermission.objects.create(
                file=new_file,
                user=share.user,
                department=share.department,
                permission=share.permission,
                expires_at=share.expires_at,
                granted_by=request.user
            )
        
        # Log access
        FileAccessLog.objects.create(
            file=file,
            user=request.user,
            action='EDIT',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
        )
        
        messages.success(request, f"New version {version} uploaded successfully.")
        return redirect('file_management:file_detail', pk=new_file.pk)
    
    context = {
        'file': file,
    }
    
    return render(request, 'file_management/file_version_upload.html', context)


@login_required
def file_export(request):
    """Export file metadata to CSV"""
    # Check if user can export data
    if not request.user.user_permissions.get('can_export_data', False):
        messages.error(request, "You don't have permission to export file metadata.")
        return redirect('file_management:file_list')
    
    # Get filter parameters
    category_id = request.GET.get('category', '')
    file_type = request.GET.get('file_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset
    files = File.objects.filter(status='ACTIVE').select_related(
        'category', 'created_by', 'owner_employee', 'owner_department'
    )
    
    # Apply filters
    if category_id:
        files = files.filter(category_id=category_id)
    
    if file_type:
        files = files.filter(file_type=file_type)
    
    if date_from:
        files = files.filter(created_at__date__gte=date_from)
    
    if date_to:
        files = files.filter(created_at__date__lte=date_to)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="files_export.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    writer.writerow(['Title', 'Description', 'Category', 'File Type', 'Created By',
                     'Created At', 'Owner', 'Department', 'Version', 'Tags'])
    
    # Add file data
    for file in files:
        # Get tags
        tags = FileTagAssignment.objects.filter(file=file).values_list('tag__name', flat=True)
        tags_str = ', '.join(tags)
        
        writer.writerow([
            file.title,
            file.description,
            file.category.name if file.category else '',
            file.file_type,
            file.created_by.get_full_name() if file.created_by else '',
            file.created_at.strftime('%Y-%m-%d %H:%M') if file.created_at else '',
            file.owner_employee.user.get_full_name() if file.owner_employee else '',
            file.owner_department.name if file.owner_department else '',
            file.version,
            tags_str
        ])
    
    return response


# Helper Functions
def user_can_access_file(user, file, permission='VIEW'):
    """Check if a user has the specified permission for a file"""
    employee_profile = user.employee_profile
    
    # Superusers and staff can access everything
    if user.is_superuser or user.is_staff:
        return True
    
    # File creators can do anything with their files
    if file.created_by == user:
        return True
    
    # File owners can do anything with their files
    if file.owner_employee == employee_profile:
        return True
    
    # Check explicit permissions
    if permission == 'VIEW':
        # Public files can be viewed by anyone
        if file.is_public:
            return True
        
        # Check department ownership
        if file.owner_department and file.owner_department == employee_profile.current_department:
            return True
        
        # Check share permissions
        share = FileSharePermission.objects.filter(
            Q(file=file) &
            (Q(user=user) | Q(department=employee_profile.current_department)) &
            (Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now().date()))
        ).first()
        
        return share is not None
    
    elif permission in ['EDIT', 'DELETE']:
        # Check department ownership with stricter permissions
        if file.owner_department and file.owner_department == employee_profile.current_department:
            return user.user_permissions.get('can_manage_files', False)
        
        # Check share permissions with edit/delete access
        share = FileSharePermission.objects.filter(
            Q(file=file) &
            (Q(user=user) | Q(department=employee_profile.current_department)) &
            (Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now().date())) &
            (Q(permission=permission) | Q(permission='FULL'))
        ).first()
        
        return share is not None
    
    elif permission == 'FULL':
        # Only file creator, owner, or admins have full control
        return (
            file.created_by == user or
            file.owner_employee == employee_profile or
            user.user_permissions.get('can_manage_file_permissions', False)
        )
    
    return False


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_folder_breadcrumbs(folder):
    """Get breadcrumb trail for a folder"""
    breadcrumbs = []
    current = folder
    
    while current:
        breadcrumbs.insert(0, current)
        current = current.parent
    
    return breadcrumbs