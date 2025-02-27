from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from core.models import EmployeeProfile, Department


class FileCategory(models.Model):
    """Categories for files and documents"""
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "File Categories"


class FileAccessLevel(models.Model):
    """Access level definitions for files"""
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    
    # Roles that can access files with this level
    allowed_roles = models.JSONField(help_text="List of role names that can access files with this level")
    
    def __str__(self):
        return self.name


class File(models.Model):
    """File metadata (no actual file storage)"""
    FILE_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ARCHIVED', 'Archived'),
        ('DELETED', 'Deleted'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(FileCategory, on_delete=models.SET_NULL, null=True, blank=True)
    
    # File can be related to any model (employee, training, leave request, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # File reference (could be a path, URL, or any reference to the actual file)
    file_reference = models.CharField(max_length=255, help_text="Reference to the actual file")
    file_type = models.CharField(max_length=10, help_text="File extension (e.g., PDF, DOCX)")
    file_size = models.PositiveIntegerField(help_text="File size in bytes", null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_files')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_files')
    modified_at = models.DateTimeField(auto_now=True)
    
    # Access control
    access_level = models.ForeignKey(FileAccessLevel, on_delete=models.SET_NULL, null=True)
    is_confidential = models.BooleanField(default=False)
    
    # Ownership
    owner_employee = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_files')
    owner_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='department_files')
    
    # Status
    status = models.CharField(max_length=10, choices=FILE_STATUS_CHOICES, default='ACTIVE')
    
    # Version tracking
    version = models.CharField(max_length=20, default='1.0')
    is_latest_version = models.BooleanField(default=True)
    previous_version = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='newer_versions')
    
    def __str__(self):
        return self.title


class FileSharePermission(models.Model):
    """Explicit sharing permissions for files"""
    PERMISSION_CHOICES = [
        ('VIEW', 'View'),
        ('EDIT', 'Edit'),
        ('DELETE', 'Delete'),
        ('FULL', 'Full Control'),
    ]
    
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='share_permissions')
    
    # Share with specific user
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='file_permissions')
    
    # Share with department
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True, related_name='file_permissions')
    
    # Permission level
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default='VIEW')
    
    # Grant period
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Who granted the permission
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_file_permissions')
    
    def __str__(self):
        shared_with = self.user.username if self.user else f"Department: {self.department.name}"
        return f"{self.file.title} - {shared_with} ({self.permission})"


class FileAccessLog(models.Model):
    """Log of file access events"""
    ACTION_CHOICES = [
        ('VIEW', 'Viewed'),
        ('DOWNLOAD', 'Downloaded'),
        ('EDIT', 'Edited'),
        ('DELETE', 'Deleted'),
        ('SHARE', 'Shared'),
        ('PRINT', 'Printed'),
    ]
    
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='access_logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} {self.action} {self.file.title} at {self.timestamp}"


class FileTag(models.Model):
    """Tags for files"""
    name = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return self.name


class FileTagAssignment(models.Model):
    """Assignment of tags to files"""
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='tag_assignments')
    tag = models.ForeignKey(FileTag, on_delete=models.CASCADE, related_name='file_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.file.title} - {self.tag.name}"
    
    class Meta:
        unique_together = ('file', 'tag')


class FileComment(models.Model):
    """Comments on files"""
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Comment on {self.file.title} by {self.user.username}"


class Folder(models.Model):
    """Virtual folders for organizing files"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    
    # Ownership
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_folders')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='department_folders')
    
    # Access control
    is_public = models.BooleanField(default=False)
    access_level = models.ForeignKey(FileAccessLevel, on_delete=models.SET_NULL, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    def get_path(self):
        """Get the full path of the folder"""
        if self.parent:
            return f"{self.parent.get_path()}/{self.name}"
        return self.name


class FolderFile(models.Model):
    """Files contained in folders"""
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files')
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='folders')
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.file.title} in {self.folder.name}"
    
    class Meta:
        unique_together = ('folder', 'file')