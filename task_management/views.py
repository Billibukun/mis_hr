from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Case, When, Value, IntegerField
from django.http import JsonResponse, HttpResponse

from .models import (
    Task, TaskCategory, TaskPriority, TaskStatus, TaskComment, 
    TaskStatusChange, TaskAttachment, TaskReminder, TaskDependency,
    Workflow, WorkflowStatus
)

from core.models import EmployeeProfile, Department
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from datetime import timedelta
import csv
import json


@login_required
def task_list(request):
    """List all tasks with filters"""
    # Get filter parameters
    status_id = request.GET.get('status', '')
    priority_id = request.GET.get('priority', '')
    category_id = request.GET.get('category', '')
    due_from = request.GET.get('due_from', '')
    due_to = request.GET.get('due_to', '')
    assigned_to_id = request.GET.get('assigned_to', '')
    search = request.GET.get('search', '')
    
    employee_profile = request.user.employee_profile
    
    # Check if user can view all tasks
    can_view_all = request.user.user_permissions.get('can_view_all_tasks', False)
    
    # Base queryset - if can view all, show all tasks, otherwise show only assigned tasks
    if can_view_all:
        tasks = Task.objects.all().select_related(
            'status', 'priority', 'category', 'assigned_to', 
            'assigned_to__user', 'creator', 'completed_by'
        )
    else:
        tasks = Task.objects.filter(
            Q(assigned_to=employee_profile) | 
            Q(creator=request.user)
        ).select_related(
            'status', 'priority', 'category', 'assigned_to', 
            'assigned_to__user', 'creator', 'completed_by'
        )
    
    # Add custom ordering by priority and due date
    tasks = tasks.annotate(
        priority_order=Case(
            When(priority__isnull=True, then=Value(0)),
            default='priority__level',
            output_field=IntegerField(),
        ),
        overdue_order=Case(
            When(due_date__lt=timezone.now(), status__is_completed=False, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by('-overdue_order', '-priority_order', 'due_date')
    
    # Apply filters
    if status_id:
        tasks = tasks.filter(status_id=status_id)
    
    if priority_id:
        tasks = tasks.filter(priority_id=priority_id)
    
    if category_id:
        tasks = tasks.filter(category_id=category_id)
    
    if due_from:
        tasks = tasks.filter(due_date__gte=due_from)
    
    if due_to:
        tasks = tasks.filter(due_date__lte=due_to)
    
    if assigned_to_id:
        tasks = tasks.filter(assigned_to_id=assigned_to_id)
    
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search)
        )
    
    # Get overdue tasks
    today = timezone.now()
    overdue_tasks = tasks.filter(
        due_date__lt=today,
        status__is_completed=False
    )
    
    # Get due today tasks
    due_today_tasks = tasks.filter(
        due_date__date=today.date(),
        status__is_completed=False
    )
    
    # Get upcoming tasks (due in the next 7 days)
    upcoming_tasks = tasks.filter(
        due_date__gt=today,
        due_date__lte=today + timedelta(days=7),
        status__is_completed=False
    )
    
    # Get recently completed tasks
    completed_tasks = tasks.filter(
        status__is_completed=True
    ).order_by('-completed_at')[:10]
    
    # Get filter options
    statuses = TaskStatus.objects.all().order_by('order')
    priorities = TaskPriority.objects.all().order_by('-level')
    categories = TaskCategory.objects.all().order_by('name')
    
    # Get assignable employees
    if request.user.user_permissions.get('can_assign_tasks', False):
        assignable_employees = EmployeeProfile.objects.filter(
            user__is_active=True
        ).select_related('user').order_by('user__last_name')
    else:
        assignable_employees = []
    
    context = {
        'tasks': tasks,
        'overdue_tasks': overdue_tasks,
        'due_today_tasks': due_today_tasks,
        'upcoming_tasks': upcoming_tasks,
        'completed_tasks': completed_tasks,
        'statuses': statuses,
        'priorities': priorities,
        'categories': categories,
        'assignable_employees': assignable_employees,
        'can_view_all': can_view_all,
        'can_create_tasks': request.user.user_permissions.get('can_create_tasks', False),
        'can_assign_tasks': request.user.user_permissions.get('can_assign_tasks', False),
        'filter_status': status_id,
        'filter_priority': priority_id,
        'filter_category': category_id,
        'filter_due_from': due_from,
        'filter_due_to': due_to,
        'filter_assigned_to': assigned_to_id,
        'search': search,
    }
    
    return render(request, 'task_management/task_list.html', context)


@login_required
def task_detail(request, pk):
    """View task details"""
    task = get_object_or_404(Task, pk=pk)
    
    # Check if user is authorized to view this task
    is_assigned = task.assigned_to == request.user.employee_profile
    is_creator = task.creator == request.user
    can_view_all = request.user.user_permissions.get('can_view_all_tasks', False)
    
    if not (is_assigned or is_creator or can_view_all):
        messages.error(request, "You don't have permission to view this task.")
        return redirect('task_management:task_list')
    
    # Get related data
    comments = TaskComment.objects.filter(task=task).select_related('user').order_by('created_at')
    status_changes = TaskStatusChange.objects.filter(task=task).select_related(
        'previous_status', 'new_status', 'changed_by'
    ).order_by('-changed_at')
    attachments = TaskAttachment.objects.filter(task=task).select_related('uploaded_by').order_by('-uploaded_at')
    reminders = TaskReminder.objects.filter(task=task).select_related('recipient').order_by('reminder_date')
    dependencies = TaskDependency.objects.filter(task=task).select_related('dependency')
    dependent_tasks = TaskDependency.objects.filter(dependency=task).select_related('task')
    
    # Check if current user can update the task
    can_update = (is_assigned or is_creator or 
                 request.user.user_permissions.get('can_manage_tasks', False))
    
    # Check if task has dependencies that aren't completed
    has_incomplete_dependencies = dependencies.filter(
        dependency__status__is_completed=False
    ).exists()
    
    context = {
        'task': task,
        'comments': comments,
        'status_changes': status_changes,
        'attachments': attachments,
        'reminders': reminders,
        'dependencies': dependencies,
        'dependent_tasks': dependent_tasks,
        'is_assigned': is_assigned,
        'is_creator': is_creator,
        'can_update': can_update,
        'has_incomplete_dependencies': has_incomplete_dependencies,
    }
    
    return render(request, 'task_management/task_detail.html', context)


@login_required
def task_create(request):
    """Create a new task"""
    if not request.user.user_permissions.get('can_create_tasks', False):
        messages.error(request, "You don't have permission to create tasks.")
        return redirect('task_management:task_list')
    
    if request.method == 'POST':
        workflow.name = request.POST.get('name')
        workflow.description = request.POST.get('description')
        
        if not workflow.name:
            messages.error(request, "Workflow name is required.")
            return redirect('task_management:workflow_update', pk=workflow.pk)
        
        workflow.save()
        
        messages.success(request, f"Workflow '{workflow.name}' updated successfully.")
        return redirect('task_management:workflow_detail', pk=workflow.pk)
    
    context = {
        'workflow': workflow,
    }
    
    return render(request, 'task_management/workflow_form.html', context)


@login_required
def workflow_delete(request, pk):
    """Delete a workflow"""
    workflow = get_object_or_404(Workflow, pk=pk)
    
    # Check if user can manage workflows
    if not request.user.user_permissions.get('can_manage_workflows', False):
        messages.error(request, "You don't have permission to delete workflows.")
        return redirect('task_management:workflow_list')
    
    # Check if workflow is being used by any tasks
    if Task.objects.filter(workflow=workflow).exists():
        messages.error(request, "Cannot delete this workflow because it is being used by existing tasks.")
        return redirect('task_management:workflow_detail', pk=workflow.pk)
    
    if request.method == 'POST':
        name = workflow.name
        workflow.delete()
        messages.success(request, f"Workflow '{name}' deleted successfully.")
        return redirect('task_management:workflow_list')
    
    context = {
        'workflow': workflow,
    }
    
    return render(request, 'task_management/workflow_confirm_delete.html', context)


@login_required
def workflow_status_manage(request, workflow_pk):
    """Manage statuses for a workflow"""
    workflow = get_object_or_404(Workflow, pk=workflow_pk)
    
    # Check if user can manage workflows
    if not request.user.user_permissions.get('can_manage_workflows', False):
        messages.error(request, "You don't have permission to manage workflow statuses.")
        return redirect('task_management:workflow_detail', pk=workflow.pk)
    
    if request.method == 'POST':
        # Delete all existing workflow statuses
        WorkflowStatus.objects.filter(workflow=workflow).delete()
        
        # Get status IDs and orders from the form
        status_ids = request.POST.getlist('status_id')
        orders = request.POST.getlist('order')
        
        # Create new workflow statuses
        for i, status_id in enumerate(status_ids):
            if status_id:  # Skip empty fields
                WorkflowStatus.objects.create(
                    workflow=workflow,
                    status_id=status_id,
                    order=orders[i]
                )
        
        # Process transitions
        transitions_json = request.POST.get('transitions', '{}')
        transitions = json.loads(transitions_json)
        
        for from_id, to_ids in transitions.items():
            from_status = WorkflowStatus.objects.get(workflow=workflow, status_id=from_id)
            for to_id in to_ids:
                to_status = TaskStatus.objects.get(id=to_id)
                from_status.allowed_next_statuses.add(to_status)
        
        messages.success(request, "Workflow statuses updated successfully.")
        return redirect('task_management:workflow_detail', pk=workflow.pk)
    
    # Get all statuses
    all_statuses = TaskStatus.objects.all().order_by('order')
    
    # Get existing workflow statuses
    workflow_statuses = WorkflowStatus.objects.filter(
        workflow=workflow
    ).select_related('status').order_by('order')
    
    context = {
        'workflow': workflow,
        'all_statuses': all_statuses,
        'workflow_statuses': workflow_statuses,
    }
    
    return render(request, 'task_management/workflow_status_manage.html', context)


@login_required
def task_dashboard(request):
    """Dashboard for task management"""
    employee_profile = request.user.employee_profile
    
    # Get task statistics
    today = timezone.now().date()
    
    # My tasks stats
    my_tasks = Task.objects.filter(assigned_to=employee_profile)
    my_total = my_tasks.count()
    my_completed = my_tasks.filter(status__is_completed=True).count()
    my_overdue = my_tasks.filter(
        due_date__lt=today,
        status__is_completed=False
    ).count()
    my_upcoming = my_tasks.filter(
        due_date__gte=today,
        status__is_completed=False
    ).count()
    
    # Created by me stats
    created_tasks = Task.objects.filter(creator=request.user)
    created_total = created_tasks.count()
    created_completed = created_tasks.filter(status__is_completed=True).count()
    created_pending = created_tasks.filter(status__is_completed=False).count()
    
    # Department stats (if in a department)
    if employee_profile.current_department:
        dept_tasks = Task.objects.filter(
            assigned_department=employee_profile.current_department
        )
        dept_total = dept_tasks.count()
        dept_completed = dept_tasks.filter(status__is_completed=True).count()
        dept_pending = dept_tasks.filter(status__is_completed=False).count()
    else:
        dept_total = dept_completed = dept_pending = 0
    
    # Get overall stats if user can view all tasks
    if request.user.user_permissions.get('can_view_all_tasks', False):
        all_tasks = Task.objects.all()
        all_total = all_tasks.count()
        all_completed = all_tasks.filter(status__is_completed=True).count()
        all_pending = all_tasks.filter(status__is_completed=False).count()
        
        # Get completion rate by department
        dept_completion = Department.objects.annotate(
            total_tasks=Count('department_tasks'),
            completed_tasks=Count('department_tasks', filter=Q(department_tasks__status__is_completed=True))
        ).filter(total_tasks__gt=0).annotate(
            completion_rate=100.0 * F('completed_tasks') / F('total_tasks')
        ).order_by('-completion_rate')[:5]
        
        # Get tasks by category
        category_counts = TaskCategory.objects.annotate(
            task_count=Count('task')
        ).filter(task_count__gt=0).order_by('-task_count')[:5]
        
        # Get tasks by priority
        priority_counts = TaskPriority.objects.annotate(
            task_count=Count('task')
        ).filter(task_count__gt=0).order_by('-level')
    else:
        all_total = all_completed = all_pending = 0
        dept_completion = []
        category_counts = []
        priority_counts = []
    
    # Get recent activity
    recent_tasks = Task.objects.order_by('-modified_at')[:10]
    recent_comments = TaskComment.objects.select_related(
        'task', 'user'
    ).order_by('-created_at')[:10]
    recent_status_changes = TaskStatusChange.objects.select_related(
        'task', 'previous_status', 'new_status', 'changed_by'
    ).order_by('-changed_at')[:10]
    
    context = {
        'my_total': my_total,
        'my_completed': my_completed,
        'my_overdue': my_overdue,
        'my_upcoming': my_upcoming,
        'created_total': created_total,
        'created_completed': created_completed,
        'created_pending': created_pending,
        'dept_total': dept_total,
        'dept_completed': dept_completed,
        'dept_pending': dept_pending,
        'all_total': all_total,
        'all_completed': all_completed,
        'all_pending': all_pending,
        'dept_completion': dept_completion,
        'category_counts': category_counts,
        'priority_counts': priority_counts,
        'recent_tasks': recent_tasks,
        'recent_comments': recent_comments,
        'recent_status_changes': recent_status_changes,
        'can_view_all': request.user.user_permissions.get('can_view_all_tasks', False),
    }
    
    return render(request, 'task_management/task_dashboard.html', context)


@login_required
def task_export(request):
    """Export tasks to CSV"""
    # Check if user can export data
    if not request.user.user_permissions.get('can_export_data', False):
        messages.error(request, "You don't have permission to export task data.")
        return redirect('task_management:task_list')
    
    # Get filter parameters
    status_id = request.GET.get('status', '')
    priority_id = request.GET.get('priority', '')
    category_id = request.GET.get('category', '')
    assigned_to_id = request.GET.get('assigned_to', '')
    
    # Base queryset
    tasks = Task.objects.all().select_related(
        'status', 'priority', 'category', 'assigned_to', 
        'assigned_to__user', 'creator', 'completed_by'
    )
    
    # Apply filters
    if status_id:
        tasks = tasks.filter(status_id=status_id)
    
    if priority_id:
        tasks = tasks.filter(priority_id=priority_id)
    
    if category_id:
        tasks = tasks.filter(category_id=category_id)
    
    if assigned_to_id:
        tasks = tasks.filter(assigned_to_id=assigned_to_id)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tasks_export.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    writer.writerow(['ID', 'Title', 'Status', 'Priority', 'Category', 'Assigned To', 
                     'Created By', 'Created At', 'Due Date', 'Completed', 'Completed By', 
                     'Completed At', 'Description'])
    
    # Add task data
    for task in tasks:
        writer.writerow([
            task.id,
            task.title,
            task.status.name if task.status else '',
            task.priority.name if task.priority else '',
            task.category.name if task.category else '',
            task.assigned_to.user.get_full_name() if task.assigned_to else '',
            task.creator.get_full_name() if task.creator else '',
            task.created_at.strftime('%Y-%m-%d %H:%M') if task.created_at else '',
            task.due_date.strftime('%Y-%m-%d %H:%M') if task.due_date else '',
            'Yes' if task.status and task.status.is_completed else 'No',
            task.completed_by.get_full_name() if task.completed_by else '',
            task.completed_at.strftime('%Y-%m-%d %H:%M') if task.completed_at else '',
            task.description
        ])
    
    return response

@login_required
def task_update(request, pk):
    """Update an existing task"""
    task = get_object_or_404(Task, pk=pk)
    
    # Check if user is authorized to update this task
    is_assigned = task.assigned_to == request.user.employee_profile
    is_creator = task.creator == request.user
    can_manage = request.user.user_permissions.get('can_manage_tasks', False)
    
    if not (is_assigned or is_creator or can_manage):
        messages.error(request, "You don't have permission to update this task.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    if request.method == 'POST':
        # Process form data
        task.title = request.POST.get('title')
        task.description = request.POST.get('description')
        task.category_id = request.POST.get('category') or None
        
        # Get current status for comparison
        old_status_id = task.status_id
        new_status_id = request.POST.get('status')
        
        # Update status
        task.status_id = new_status_id
        
        # Record status change if different
        if old_status_id != new_status_id:
            TaskStatusChange.objects.create(
                task=task,
                previous_status_id=old_status_id,
                new_status_id=new_status_id,
                changed_by=request.user,
                comments=request.POST.get('status_change_comment', '')
            )
            
            # Check if task is now completed based on new status
            new_status = TaskStatus.objects.get(id=new_status_id)
            if new_status.is_completed and not task.completed_at:
                task.completed_at = timezone.now()
                task.completed_by = request.user
            # Or if task was completed but now isn't
            elif not new_status.is_completed and task.completed_at:
                task.completed_at = None
                task.completed_by = None
        
        # Update other fields
        task.priority_id = request.POST.get('priority')
        
        # Only users with assign permission can change assignment
        if request.user.user_permissions.get('can_assign_tasks', False):
            task.assigned_to_id = request.POST.get('assigned_to') or None
            task.assigned_department_id = request.POST.get('assigned_department') or None
        
        task.due_date = request.POST.get('due_date') or None
        
        task.save()
        
        messages.success(request, f"Task '{task.title}' updated successfully.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    # Get form options
    statuses = TaskStatus.objects.all().order_by('order')
    priorities = TaskPriority.objects.all().order_by('-level')
    categories = TaskCategory.objects.all().order_by('name')
    departments = Department.objects.all().order_by('name')
    
    # Get assignable employees
    if request.user.user_permissions.get('can_assign_tasks', False):
        assignable_employees = EmployeeProfile.objects.filter(
            user__is_active=True
        ).select_related('user').order_by('user__last_name')
    else:
        assignable_employees = []
    
    context = {
        'task': task,
        'statuses': statuses,
        'priorities': priorities,
        'categories': categories,
        'departments': departments,
        'assignable_employees': assignable_employees,
        'can_assign': request.user.user_permissions.get('can_assign_tasks', False),
    }
    
    return render(request, 'task_management/task_form.html', context)


@login_required
def task_delete(request, pk):
    """Delete a task"""
    task = get_object_or_404(Task, pk=pk)
    
    # Check if user is authorized to delete this task
    is_creator = task.creator == request.user
    can_manage = request.user.user_permissions.get('can_manage_tasks', False)
    
    if not (is_creator or can_manage):
        messages.error(request, "You don't have permission to delete this task.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    # Check if task has dependent tasks
    dependent_tasks = TaskDependency.objects.filter(dependency=task)
    if dependent_tasks.exists():
        messages.error(request, "Cannot delete this task because other tasks depend on it.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    if request.method == 'POST':
        title = task.title
        task.delete()
        messages.success(request, f"Task '{title}' deleted successfully.")
        return redirect('task_management:task_list')
    
    context = {
        'task': task,
    }
    
    return render(request, 'task_management/task_confirm_delete.html', context)


@login_required
def task_add_comment(request, pk):
    """Add a comment to a task"""
    task = get_object_or_404(Task, pk=pk)
    
    # Check if user is authorized to comment on this task
    is_assigned = task.assigned_to == request.user.employee_profile
    is_creator = task.creator == request.user
    can_view_all = request.user.user_permissions.get('can_view_all_tasks', False)
    
    if not (is_assigned or is_creator or can_view_all):
        messages.error(request, "You don't have permission to comment on this task.")
        return redirect('task_management:task_list')
    
    if request.method == 'POST':
        comment_text = request.POST.get('comment')
        
        if not comment_text:
            messages.error(request, "Comment cannot be empty.")
            return redirect('task_management:task_detail', pk=task.pk)
        
        # Create comment
        comment = TaskComment.objects.create(
            task=task,
            user=request.user,
            comment=comment_text
        )
        
        messages.success(request, "Comment added successfully.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    return redirect('task_management:task_detail', pk=task.pk)


@login_required
def task_add_attachment(request, pk):
    """Add attachment metadata to a task"""
    task = get_object_or_404(Task, pk=pk)
    
    # Check if user is authorized to add attachments to this task
    is_assigned = task.assigned_to == request.user.employee_profile
    is_creator = task.creator == request.user
    can_manage = request.user.user_permissions.get('can_manage_tasks', False)
    
    if not (is_assigned or is_creator or can_manage):
        messages.error(request, "You don't have permission to add attachments to this task.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    if request.method == 'POST':
        file_name = request.POST.get('file_name')
        file_reference = request.POST.get('file_reference')
        
        if not file_name or not file_reference:
            messages.error(request, "File name and reference are required.")
            return redirect('task_management:task_detail', pk=task.pk)
        
        # Create attachment
        attachment = TaskAttachment.objects.create(
            task=task,
            file_name=file_name,
            file_reference=file_reference,
            uploaded_by=request.user
        )
        
        messages.success(request, "Attachment added successfully.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    return redirect('task_management:task_detail', pk=task.pk)


@login_required
def task_add_reminder(request, pk):
    """Add a reminder for a task"""
    task = get_object_or_404(Task, pk=pk)
    
    # Check if user is authorized to add reminders for this task
    is_assigned = task.assigned_to == request.user.employee_profile
    is_creator = task.creator == request.user
    can_manage = request.user.user_permissions.get('can_manage_tasks', False)
    
    if not (is_assigned or is_creator or can_manage):
        messages.error(request, "You don't have permission to add reminders for this task.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    if request.method == 'POST':
        reminder_date = request.POST.get('reminder_date')
        recipient_id = request.POST.get('recipient')
        
        if not reminder_date or not recipient_id:
            messages.error(request, "Reminder date and recipient are required.")
            return redirect('task_management:task_detail', pk=task.pk)
        
        # Create reminder
        reminder = TaskReminder.objects.create(
            task=task,
            reminder_date=reminder_date,
            recipient_id=recipient_id
        )
        
        messages.success(request, "Reminder added successfully.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    # Get potential recipients
    recipients = [task.assigned_to.user] if task.assigned_to else []
    if task.creator not in recipients:
        recipients.append(task.creator)
    
    context = {
        'task': task,
        'recipients': recipients,
    }
    
    return render(request, 'task_management/task_add_reminder.html', context)


@login_required
def task_add_dependency(request, pk):
    """Add a dependency for a task"""
    task = get_object_or_404(Task, pk=pk)
    
    # Check if user is authorized to add dependencies for this task
    is_creator = task.creator == request.user
    can_manage = request.user.user_permissions.get('can_manage_tasks', False)
    
    if not (is_creator or can_manage):
        messages.error(request, "You don't have permission to add dependencies for this task.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    if request.method == 'POST':
        dependency_id = request.POST.get('dependency')
        
        if not dependency_id:
            messages.error(request, "Dependency task is required.")
            return redirect('task_management:task_detail', pk=task.pk)
        
        # Ensure not creating a circular dependency
        if int(dependency_id) == task.id:
            messages.error(request, "A task cannot depend on itself.")
            return redirect('task_management:task_detail', pk=task.pk)
        
        # Check if dependency already exists
        if TaskDependency.objects.filter(task=task, dependency_id=dependency_id).exists():
            messages.error(request, "This dependency already exists.")
            return redirect('task_management:task_detail', pk=task.pk)
        
        # Create dependency
        dependency = TaskDependency.objects.create(
            task=task,
            dependency_id=dependency_id
        )
        
        messages.success(request, "Dependency added successfully.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    # Get potential dependencies (exclude completed tasks and current task)
    dependencies = Task.objects.exclude(
        id=task.id
    ).exclude(
        id__in=TaskDependency.objects.filter(task=task).values_list('dependency_id', flat=True)
    ).order_by('-created_at')
    
    # If already has many dependencies, limit the list
    if TaskDependency.objects.filter(task=task).count() > 5:
        dependencies = dependencies.filter(
            Q(assigned_to=task.assigned_to) |
            Q(creator=task.creator)
        )
    
    context = {
        'task': task,
        'dependencies': dependencies,
    }
    
    return render(request, 'task_management/task_add_dependency.html', context)


@login_required
def task_remove_dependency(request, pk, dependency_pk):
    """Remove a dependency from a task"""
    dependency = get_object_or_404(TaskDependency, task_id=pk, dependency_id=dependency_pk)
    task = dependency.task
    
    # Check if user is authorized to remove dependencies from this task
    is_creator = task.creator == request.user
    can_manage = request.user.user_permissions.get('can_manage_tasks', False)
    
    if not (is_creator or can_manage):
        messages.error(request, "You don't have permission to remove dependencies from this task.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    if request.method == 'POST':
        dependency.delete()
        messages.success(request, "Dependency removed successfully.")
        return redirect('task_management:task_detail', pk=task.pk)
    
    context = {
        'task': task,
        'dependency': dependency,
    }
    
    return render(request, 'task_management/dependency_confirm_delete.html', context)


@login_required
def workflow_list(request):
    """List all workflows"""
    # Check if user can manage workflows
    if not request.user.user_permissions.get('can_manage_workflows', False):
        messages.error(request, "You don't have permission to manage workflows.")
        return redirect('task_management:task_list')
    
    workflows = Workflow.objects.all().order_by('name')
    
    context = {
        'workflows': workflows,
    }
    
    return render(request, 'task_management/workflow_list.html', context)


@login_required
def workflow_detail(request, pk):
    """View workflow details"""
    workflow = get_object_or_404(Workflow, pk=pk)
    
    # Check if user can manage workflows
    if not request.user.user_permissions.get('can_manage_workflows', False):
        messages.error(request, "You don't have permission to view workflow details.")
        return redirect('task_management:task_list')
    
    # Get workflow statuses with their allowed next statuses
    workflow_statuses = WorkflowStatus.objects.filter(
        workflow=workflow
    ).select_related('status').order_by('order')
    
    # Get tasks using this workflow
    tasks = Task.objects.filter(workflow=workflow).select_related(
        'status', 'assigned_to', 'assigned_to__user'
    ).order_by('-created_at')[:10]
    
    context = {
        'workflow': workflow,
        'workflow_statuses': workflow_statuses,
        'tasks': tasks,
    }
    
    return render(request, 'task_management/workflow_detail.html', context)


@login_required
def workflow_create(request):
    """Create a new workflow"""
    # Check if user can manage workflows
    if not request.user.user_permissions.get('can_manage_workflows', False):
        messages.error(request, "You don't have permission to create workflows.")
        return redirect('task_management:workflow_list')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        
        if not name:
            messages.error(request, "Workflow name is required.")
            return redirect('task_management:workflow_create')
        
        # Create workflow
        workflow = Workflow.objects.create(
            name=name,
            description=description
        )
        
        messages.success(request, f"Workflow '{name}' created successfully.")
        return redirect('task_management:workflow_status_manage', workflow_pk=workflow.pk)
    
    context = {}
    
    return render(request, 'task_management/workflow_form.html', context)


@login_required
def workflow_update(request, pk):
    """Update a workflow"""
    workflow = get_object_or_404(Workflow, pk=pk)
    
    # Check if user can manage workflows
    if not request.user.user_permissions.get('can_manage_workflows', False):
        messages.error(request, "You don't have permission to update workflows.")
        return redirect('task_management:workflow_list')
    
    if request.method == 'POST':
        workflow.name = request.POST.get('name')
        workflow.description = request.POST.get('description')
        
        if not workflow.name:
            messages.error(request, "Workflow name is required.")
            return redirect('task_management:workflow_update', pk=workflow.pk)
        
        workflow.save()
        
        messages.success(request, f"Workflow '{workflow.name}' updated successfully.")
        return redirect('task_management:workflow_detail', pk=workflow.pk)
    
    context = {
        'workflow': workflow,
    }