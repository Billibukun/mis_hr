from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget

from .models import (
    TaskCategory, TaskPriority, TaskStatus, Task, TaskComment,
    TaskStatusChange, TaskAttachment, TaskReminder, TaskDependency,
    Workflow, WorkflowStatus
)
from core.models import EmployeeProfile, Department
from django.contrib.auth.models import User


# Resource classes for import/export
class TaskResource(resources.ModelResource):
    status = Field(column_name='status', attribute='status',
                 widget=ForeignKeyWidget(TaskStatus, 'name'))
    priority = Field(column_name='priority', attribute='priority',
                   widget=ForeignKeyWidget(TaskPriority, 'name'))
    category = Field(column_name='category', attribute='category',
                   widget=ForeignKeyWidget(TaskCategory, 'name'))
    assigned_to = Field(column_name='assigned_to', attribute='assigned_to',
                      widget=ForeignKeyWidget(EmployeeProfile, 'file_number'))
    assigned_department = Field(column_name='assigned_department', attribute='assigned_department',
                             widget=ForeignKeyWidget(Department, 'name'))
    creator = Field(column_name='creator', attribute='creator',
                  widget=ForeignKeyWidget(User, 'username'))
    
    class Meta:
        model = Task
        fields = ('id', 'title', 'description', 'status', 'priority', 'category',
                'assigned_to', 'assigned_department', 'creator', 'due_date',
                'is_recurring', 'recurring_frequency')
        import_id_fields = ['id']


class WorkflowResource(resources.ModelResource):
    class Meta:
        model = Workflow
        fields = ('id', 'name', 'description')
        import_id_fields = ['id']


# Inline Admin classes
class TaskCommentInline(admin.TabularInline):
    model = TaskComment
    extra = 1
    fields = ('user', 'comment', 'created_at')
    readonly_fields = ('created_at',)


class TaskStatusChangeInline(admin.TabularInline):
    model = TaskStatusChange
    extra = 0
    fields = ('previous_status', 'new_status', 'changed_by', 'changed_at', 'comments')
    readonly_fields = ('changed_at',)


class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 1
    fields = ('file_name', 'file_reference', 'uploaded_by', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


class TaskReminderInline(admin.TabularInline):
    model = TaskReminder
    extra = 1
    fields = ('reminder_date', 'is_sent', 'sent_at', 'recipient')
    readonly_fields = ('sent_at',)


class TaskDependencyInline(admin.TabularInline):
    model = TaskDependency
    extra = 1
    fields = ('dependency',)
    fk_name = 'task'


class WorkflowStatusInline(admin.TabularInline):
    model = WorkflowStatus
    extra = 1
    filter_horizontal = ('allowed_next_statuses',)


# Admin classes
@admin.register(TaskCategory)
class TaskCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'color_code')
    search_fields = ('name', 'description')


@admin.register(TaskPriority)
class TaskPriorityAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'color_code')
    list_filter = ('level',)
    search_fields = ('name',)
    ordering = ('-level',)


@admin.register(TaskStatus)
class TaskStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_completed', 'color_code')
    list_filter = ('is_completed',)
    search_fields = ('name', 'description')
    ordering = ('order',)


@admin.register(Task)
class TaskAdmin(ImportExportModelAdmin):
    resource_class = TaskResource
    list_display = ('title', 'status', 'priority', 'assigned_to', 'due_date', 'is_completed', 'is_overdue')
    list_filter = ('status', 'priority', 'category', 'is_recurring', 'creator')
    search_fields = ('title', 'description', 'assigned_to__user__username')
    date_hierarchy = 'due_date'
    readonly_fields = ('created_at', 'modified_at', 'completed_at')
    inlines = [
        TaskStatusChangeInline,
        TaskCommentInline,
        TaskAttachmentInline,
        TaskReminderInline,
        TaskDependencyInline
    ]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'status', 'priority', 'category')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'assigned_department', 'creator', 'workflow')
        }),
        ('Scheduling', {
            'fields': ('due_date', 'is_recurring', 'recurring_frequency')
        }),
        ('Completion', {
            'fields': ('completed_at', 'completed_by')
        }),
        ('Metadata', {
            'fields': ('created_at', 'modified_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_completed(self, obj):
        return obj.is_completed
    is_completed.boolean = True
    
    def is_overdue(self, obj):
        return obj.is_overdue
    is_overdue.boolean = True


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'comment_preview', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('comment', 'task__title', 'user__username')
    date_hierarchy = 'created_at'
    
    def comment_preview(self, obj):
        return obj.comment[:50] + "..." if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = "Comment"


@admin.register(TaskStatusChange)
class TaskStatusChangeAdmin(admin.ModelAdmin):
    list_display = ('task', 'previous_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('previous_status', 'new_status', 'changed_at')
    search_fields = ('task__title', 'changed_by__username', 'comments')
    date_hierarchy = 'changed_at'


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ('task', 'file_name', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('file_name', 'task__title', 'uploaded_by__username')
    date_hierarchy = 'uploaded_at'


@admin.register(TaskReminder)
class TaskReminderAdmin(admin.ModelAdmin):
    list_display = ('task', 'reminder_date', 'is_sent', 'recipient')
    list_filter = ('is_sent', 'reminder_date')
    search_fields = ('task__title', 'recipient__username')
    date_hierarchy = 'reminder_date'


@admin.register(Workflow)
class WorkflowAdmin(ImportExportModelAdmin):
    resource_class = WorkflowResource
    list_display = ('name', 'description', 'status_count')
    search_fields = ('name', 'description')
    inlines = [WorkflowStatusInline]
    
    def status_count(self, obj):
        return obj.statuses.count()
    status_count.short_description = "Number of Statuses"


@admin.register(WorkflowStatus)
class WorkflowStatusAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'status', 'order')
    list_filter = ('workflow', 'status')
    search_fields = ('workflow__name', 'status__name')
    filter_horizontal = ('allowed_next_statuses',)