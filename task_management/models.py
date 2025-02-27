from django.db import models
from django.contrib.auth.models import User
from core.models import EmployeeProfile, Department
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class TaskCategory(models.Model):
    """Categories for tasks"""
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    color_code = models.CharField(max_length=7, help_text="Hex color code (e.g. #FF5733)", default="#3498db")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Task Categories"


class TaskPriority(models.Model):
    """Priority levels for tasks"""
    name = models.CharField(max_length=20)
    level = models.PositiveIntegerField(unique=True, help_text="Higher number means higher priority")
    color_code = models.CharField(max_length=7, help_text="Hex color code (e.g. #FF5733)", default="#3498db")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Task Priorities"
        ordering = ['-level']


class TaskStatus(models.Model):
    """Status options for tasks"""
    name = models.CharField(max_length=20)
    description = models.TextField(blank=True, null=True)
    color_code = models.CharField(max_length=7, help_text="Hex color code (e.g. #FF5733)", default="#3498db")
    order = models.PositiveIntegerField(default=0, help_text="Order in workflow")
    is_completed = models.BooleanField(default=False, help_text="Whether this status means the task is completed")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Task Statuses"
        ordering = ['order']


class Workflow(models.Model):
    """Predefined workflows for task management"""
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    statuses = models.ManyToManyField(TaskStatus, through='WorkflowStatus')
    
    def __str__(self):
        return self.name


class WorkflowStatus(models.Model):
    """Statuses within a workflow with transition rules"""
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE)
    status = models.ForeignKey(TaskStatus, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(help_text="Order in the workflow")
    
    allowed_next_statuses = models.ManyToManyField(TaskStatus, blank=True, related_name="previous_workflow_statuses")
    
    def __str__(self):
        return f"{self.workflow.name} - {self.status.name} (Step {self.order})"
    
    class Meta:
        unique_together = ('workflow', 'status')
        ordering = ['workflow', 'order']


class Task(models.Model):
    """Tasks to be assigned and tracked"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(TaskCategory, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Task can be related to any model (leave request, promotion, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    workflow = models.ForeignKey(Workflow, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey(TaskStatus, on_delete=models.SET_NULL, null=True)
    priority = models.ForeignKey(TaskPriority, on_delete=models.SET_NULL, null=True)
    
    assigned_to = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assigned_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='department_tasks')
    
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_tasks')
    
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(max_length=20, blank=True, null=True, 
                                          choices=[('DAILY', 'Daily'), 
                                                  ('WEEKLY', 'Weekly'), 
                                                  ('MONTHLY', 'Monthly'),
                                                  ('QUARTERLY', 'Quarterly'),
                                                  ('YEARLY', 'Yearly')])
    
    def __str__(self):
        return self.title
    
    @property
    def is_completed(self):
        return self.status.is_completed if self.status else False
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.due_date and not self.is_completed:
            return timezone.now() > self.due_date
        return False


class TaskComment(models.Model):
    """Comments on tasks"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment on {self.task.title} by {self.user.username}"


class TaskStatusChange(models.Model):
    """History of status changes for tasks"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='status_changes')
    previous_status = models.ForeignKey(TaskStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='previous_status_changes')
    new_status = models.ForeignKey(TaskStatus, on_delete=models.SET_NULL, null=True, related_name='new_status_changes')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    comments = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.task.title}: {self.previous_status} → {self.new_status}"


class TaskAttachment(models.Model):
    """File attachments for tasks (metadata only)"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file_name = models.CharField(max_length=255)
    file_reference = models.CharField(max_length=255, help_text="Reference to file in file management system")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.file_name} - {self.task.title}"


class TaskReminder(models.Model):
    """Reminders for tasks"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='reminders')
    reminder_date = models.DateTimeField()
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_reminders')
    
    def __str__(self):
        return f"Reminder for {self.task.title} at {self.reminder_date}"


class TaskDependency(models.Model):
    """Dependencies between tasks"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependencies')
    dependency = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependent_tasks')
    
    def __str__(self):
        return f"{self.task.title} depends on {self.dependency.title}"
    
    class Meta:
        unique_together = ('task', 'dependency')
        verbose_name_plural = "Task Dependencies"