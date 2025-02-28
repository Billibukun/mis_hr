from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget

from .models import (
    FileCategory, FileAccessLevel, File, FileSharePermission, 
    FileAccessLog, FileTag, FileTagAssignment, FileComment,
    Folder, FolderFile
)
from core.models import EmployeeProfile, Department
from django.contrib.auth.models import User


# Resource classes for import/export
class FileResource(resources.ModelResource):
    category = Field(column_name='category', attribute='category',
                   widget=ForeignKeyWidget(FileCategory, 'name'))
    access_level = Field(column_name='access_level', attribute='access_level',
                       widget=ForeignKeyWidget(FileAccessLevel, 'name'))
    created_by = Field(column_name='created_by', attribute='created_by',
                     widget=ForeignKeyWidget(User, 'username'))
    owner_employee = Field(column_name='owner_employee', attribute='owner_employee',
                         widget=ForeignKeyWidget(EmployeeProfile, 'file_number'))
    owner_department = Field(column_name='owner_department', attribute='owner_department',
                           widget=ForeignKeyWidget(Department, 'name'))
    
    class Meta:
        model = File
        fields = ('id', 'title', 'description', 'category', 'file_reference', 'file_type',
                'file_size', 'created_by', 'created_at', 'access_level', 'is_confidential',
                'owner_employee', 'owner_department', 'status', 'version', 'is_latest_version')
        import_id_fields = ['id']
        exclude = ('content_type', 'object_id')


class FolderResource(resources.ModelResource):
    owner = Field(column_name='owner', attribute='owner',
                widget=ForeignKeyWidget(User, 'username'))
    department = Field(column_name='department', attribute='department',
                     widget=ForeignKeyWidget(Department, 'name'))
    access_level = Field(column_name='access_level', attribute='access_level',
                       widget=ForeignKeyWidget(FileAccessLevel, 'name'))
    
    class Meta:
        model = Folder
        fields = ('id', 'name', 'description', 'parent', 'owner', 'department',
                'is_public', 'access_level', 'created_at')
        import_id_fields = ['id']


# Inline Admin classes
class FileSharePermissionInline(admin.TabularInline):
    model = FileSharePermission
    extra = 1
    fields = ('user', 'department', 'permission', 'granted_by', 'granted_at', 'expires_at')
    readonly_fields = ('granted_at',)


class FileCommentInline(admin.TabularInline):
    model = FileComment
    extra = 1
    fields = ('user', 'comment', 'created_at')
    readonly_fields = ('created_at',)


class FileTagAssignmentInline(admin.TabularInline):
    model = FileTagAssignment
    extra = 1
    fields = ('tag', 'assigned_by', 'assigned_at')
    readonly_fields = ('assigned_at',)


class FolderFileInline(admin.TabularInline):
    model = FolderFile
    extra = 1
    fields = ('file', 'added_by', 'added_at')
    readonly_fields = ('added_at',)


# Admin classes
@admin.register(FileCategory)
class FileCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


@admin.register(FileAccessLevel)
class FileAccessLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


@admin.register(File)
class FileAdmin(ImportExportModelAdmin):
    resource_class = FileResource
    list_display = ('title', 'category', 'file_type', 'status', 'created_by', 'created_at', 'version', 'is_latest_version')
    list_filter = ('status', 'file_type', 'category', 'is_confidential', 'is_latest_version')
    search_fields = ('title', 'description', 'file_reference', 'created_by__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'modified_at')
    inlines = [
        FileSharePermissionInline,
        FileCommentInline,
        FileTagAssignmentInline
    ]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'category')
        }),
        ('File Details', {
            'fields': ('file_reference', 'file_type', 'file_size')
        }),
        ('Access Control', {
            'fields': ('access_level', 'is_confidential')
        }),
        ('Ownership', {
            'fields': ('created_by', 'modified_by', 'owner_employee', 'owner_department')
        }),
        ('Status and Versioning', {
            'fields': ('status', 'version', 'is_latest_version', 'previous_version')
        }),
        ('Metadata', {
            'fields': ('created_at', 'modified_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FileSharePermission)
class FileSharePermissionAdmin(admin.ModelAdmin):
    list_display = ('file', 'user', 'department', 'permission', 'granted_by', 'granted_at', 'expires_at')
    list_filter = ('permission', 'granted_at', 'expires_at')
    search_fields = ('file__title', 'user__username', 'department__name')
    date_hierarchy = 'granted_at'


@admin.register(FileAccessLog)
class FileAccessLogAdmin(admin.ModelAdmin):
    list_display = ('file', 'user', 'action', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('file__title', 'user__username', 'ip_address')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)


@admin.register(FileTag)
class FileTagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(FileTagAssignment)
class FileTagAssignmentAdmin(admin.ModelAdmin):
    list_display = ('file', 'tag', 'assigned_by', 'assigned_at')
    list_filter = ('assigned_at', 'tag')
    search_fields = ('file__title', 'tag__name', 'assigned_by__username')
    date_hierarchy = 'assigned_at'


@admin.register(FileComment)
class FileCommentAdmin(admin.ModelAdmin):
    list_display = ('file', 'user', 'comment_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('file__title', 'user__username', 'comment')
    date_hierarchy = 'created_at'
    
    def comment_preview(self, obj):
        return obj.comment[:50] + "..." if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = "Comment"


@admin.register(Folder)
class FolderAdmin(ImportExportModelAdmin):
    resource_class = FolderResource
    list_display = ('name', 'parent', 'owner', 'department', 'is_public', 'created_at')
    list_filter = ('is_public', 'created_at')
    search_fields = ('name', 'description', 'owner__username', 'department__name')
    date_hierarchy = 'created_at'
    inlines = [FolderFileInline]


@admin.register(FolderFile)
class FolderFileAdmin(admin.ModelAdmin):
    list_display = ('folder', 'file', 'added_by', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('folder__name', 'file__title', 'added_by__username')
    date_hierarchy = 'added_at'