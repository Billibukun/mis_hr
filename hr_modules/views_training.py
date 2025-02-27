import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import HttpResponse, JsonResponse

from .models import Training, TrainingType, TrainingParticipant
from core.models import EmployeeProfile
from task_management.models import Task, TaskStatus

from datetime import timedelta


@login_required
def training_list(request):
    """List all trainings with filters"""
    today = timezone.now().date()
    
    # Get filter parameters
    status = request.GET.get('status', '')
    type_id = request.GET.get('type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    trainings = Training.objects.all().select_related('training_type').order_by('-start_date')
    
    # Apply filters
    if status:
        trainings = trainings.filter(status=status)
    
    if type_id:
        trainings = trainings.filter(training_type_id=type_id)
    
    if date_from:
        trainings = trainings.filter(start_date__gte=date_from)
    
    if date_to:
        trainings = trainings.filter(end_date__lte=date_to)
    
    if search:
        trainings = trainings.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(location__icontains=search)
        )
    
    # Get available trainings for this employee
    employee_profile = request.user.employee_profile
    available_trainings = Training.objects.filter(
        Q(status='UPCOMING') | Q(status='ONGOING'),
    ).exclude(
        participants__employee=employee_profile
    ).order_by('start_date')
    
    # Get my trainings
    my_trainings = TrainingParticipant.objects.filter(
        employee=employee_profile
    ).select_related('training').order_by('-training__start_date')
    
    # Get training types for filter
    training_types = TrainingType.objects.all()
    
    context = {
        'trainings': trainings,
        'available_trainings': available_trainings,
        'my_trainings': my_trainings,
        'training_types': training_types,
        'filter_status': status,
        'filter_type': type_id,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'search': search,
    }
    
    return render(request, 'hr_modules/training/training_list.html', context)


@login_required
def training_detail(request, pk):
    """View training details and participants"""
    training = get_object_or_404(Training, pk=pk)
    
    # Check if current user is a participant
    employee_profile = request.user.employee_profile
    try:
        participant = TrainingParticipant.objects.get(
            training=training,
            employee=employee_profile
        )
        is_participant = True
    except TrainingParticipant.DoesNotExist:
        participant = None
        is_participant = False
    
    # Get all participants
    participants = TrainingParticipant.objects.filter(
        training=training
    ).select_related('employee', 'employee__user').order_by('employee__user__last_name')
    
    context = {
        'training': training,
        'participants': participants,
        'is_participant': is_participant,
        'participant': participant,
    }
    
    return render(request, 'hr_modules/training/training_detail.html', context)


@login_required
def training_create(request):
    """Create a new training"""
    if not request.user.user_permissions.get('can_manage_trainings', False):
        messages.error(request, "You don't have permission to create training programs.")
        return redirect('hr_modules:training_list')
    
    if request.method == 'POST':
        # Process form data
        title = request.POST.get('title')
        description = request.POST.get('description')
        training_type_id = request.POST.get('training_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        location = request.POST.get('location')
        capacity = request.POST.get('capacity')
        organizer = request.POST.get('organizer')
        
        # Validate form data
        if not all([title, description, training_type_id, start_date, end_date, location, capacity]):
            messages.error(request, "Please fill all required fields.")
            return redirect('hr_modules:training_create')
        
        # Create training
        training = Training.objects.create(
            title=title,
            description=description,
            training_type_id=training_type_id,
            start_date=start_date,
            end_date=end_date,
            location=location,
            capacity=int(capacity),
            organizer=organizer,
            status='UPCOMING',
            created_by=request.user,
            modified_by=request.user
        )
        
        messages.success(request, f"Training '{title}' created successfully.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    # Get all training types for the form
    training_types = TrainingType.objects.all()
    
    context = {
        'training_types': training_types,
    }
    
    return render(request, 'hr_modules/training/training_form.html', context)


@login_required
def training_update(request, pk):
    """Update an existing training"""
    training = get_object_or_404(Training, pk=pk)
    
    if not request.user.user_permissions.get('can_manage_trainings', False):
        messages.error(request, "You don't have permission to update training programs.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    if request.method == 'POST':
        # Process form data
        training.title = request.POST.get('title')
        training.description = request.POST.get('description')
        training.training_type_id = request.POST.get('training_type')
        training.start_date = request.POST.get('start_date')
        training.end_date = request.POST.get('end_date')
        training.location = request.POST.get('location')
        training.capacity = int(request.POST.get('capacity'))
        training.organizer = request.POST.get('organizer')
        training.status = request.POST.get('status')
        training.modified_by = request.user
        
        training.save()
        
        messages.success(request, f"Training '{training.title}' updated successfully.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    # Get all training types for the form
    training_types = TrainingType.objects.all()
    
    context = {
        'training': training,
        'training_types': training_types,
    }
    
    return render(request, 'hr_modules/training/training_form.html', context)


@login_required
def training_delete(request, pk):
    """Delete a training"""
    training = get_object_or_404(Training, pk=pk)
    
    if not request.user.user_permissions.get('can_manage_trainings', False):
        messages.error(request, "You don't have permission to delete training programs.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    if request.method == 'POST':
        title = training.title
        training.delete()
        messages.success(request, f"Training '{title}' deleted successfully.")
        return redirect('hr_modules:training_list')
    
    context = {
        'training': training,
    }
    
    return render(request, 'hr_modules/training/training_confirm_delete.html', context)


@login_required
def training_nominate(request, pk):
    """Nominate an employee for a training"""
    training = get_object_or_404(Training, pk=pk)
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        
        if not employee_id:
            messages.error(request, "Please select an employee.")
            return redirect('hr_modules:training_detail', pk=training.pk)
        
        # Check if employee already nominated
        if TrainingParticipant.objects.filter(training=training, employee_id=employee_id).exists():
            messages.error(request, "Employee already nominated for this training.")
            return redirect('hr_modules:training_detail', pk=training.pk)
        
        # Create participant
        participant = TrainingParticipant.objects.create(
            training=training,
            employee_id=employee_id,
            status='NOMINATED',
            nomination_by=request.user
        )
        
        # Create notification task for the employee
        employee = EmployeeProfile.objects.get(id=employee_id)
        Task.objects.create(
            title=f"Training Nomination: {training.title}",
            description=f"You have been nominated for the training: {training.title}. Please confirm your participation.",
            status=TaskStatus.objects.get(name='Pending'),
            assigned_to=employee,
            creator=request.user,
            due_date=timezone.now() + timedelta(days=3)
        )
        
        messages.success(request, "Employee nominated successfully.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    # Get eligible employees
    employees = EmployeeProfile.objects.filter(
        user__is_active=True
    ).select_related('user', 'current_department').order_by('user__last_name')
    
    # Exclude already nominated employees
    nominated_employee_ids = TrainingParticipant.objects.filter(
        training=training
    ).values_list('employee_id', flat=True)
    
    employees = employees.exclude(id__in=nominated_employee_ids)
    
    context = {
        'training': training,
        'employees': employees,
    }
    
    return render(request, 'hr_modules/training/training_nominate.html', context)


@login_required
def training_register(request, pk):
    """Register for a training"""
    training = get_object_or_404(Training, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if already registered
    if TrainingParticipant.objects.filter(training=training, employee=employee_profile).exists():
        messages.error(request, "You are already registered for this training.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    # Check if capacity is full
    if TrainingParticipant.objects.filter(training=training).count() >= training.capacity:
        messages.error(request, "This training is already at full capacity.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    # Register for training
    participant = TrainingParticipant.objects.create(
        training=training,
        employee=employee_profile,
        status='CONFIRMED',
        nomination_by=request.user
    )
    
    messages.success(request, f"You have been registered for '{training.title}'.")
    return redirect('hr_modules:training_detail', pk=training.pk)


@login_required
def training_cancel_registration(request, pk):
    """Cancel registration for a training"""
    training = get_object_or_404(Training, pk=pk)
    employee_profile = request.user.employee_profile
    
    try:
        participant = TrainingParticipant.objects.get(
            training=training,
            employee=employee_profile
        )
        
        # Only allow cancellation if not attended or completed
        if participant.status not in ['ATTENDED', 'COMPLETED']:
            participant.status = 'CANCELLED'
            participant.save()
            messages.success(request, f"Your registration for '{training.title}' has been cancelled.")
        else:
            messages.error(request, "Cannot cancel registration for completed training.")
    
    except TrainingParticipant.DoesNotExist:
        messages.error(request, "You are not registered for this training.")
    
    return redirect('hr_modules:training_detail', pk=training.pk)


@login_required
def training_update_status(request, pk, participant_id):
    """Update participant status"""
    training = get_object_or_404(Training, pk=pk)
    participant = get_object_or_404(TrainingParticipant, pk=participant_id, training=training)
    
    if not request.user.user_permissions.get('can_manage_trainings', False):
        messages.error(request, "You don't have permission to update participant status.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        attendance = request.POST.get('attendance')
        performance = request.POST.get('performance')
        certificate_issued = request.POST.get('certificate_issued') == 'on'
        comments = request.POST.get('comments')
        
        participant.status = status
        if attendance:
            participant.attendance_record = float(attendance)
        if performance:
            participant.performance_score = float(performance)
        participant.certificate_issued = certificate_issued
        participant.comments = comments
        participant.save()
        
        messages.success(request, "Participant status updated successfully.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    context = {
        'training': training,
        'participant': participant,
    }
    
    return render(request, 'hr_modules/training/participant_update.html', context)


@login_required
def training_export_participants(request, pk):
    """Export training participants to CSV"""
    training = get_object_or_404(Training, pk=pk)
    
    if not request.user.user_permissions.get('can_manage_trainings', False):
        messages.error(request, "You don't have permission to export participant data.")
        return redirect('hr_modules:training_detail', pk=training.pk)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{training.title}_participants.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    writer.writerow(['Name', 'File Number', 'Department', 'Status', 'Attendance', 'Performance', 'Certificate'])
    
    # Add participant data
    participants = TrainingParticipant.objects.filter(
        training=training
    ).select_related('employee', 'employee__user', 'employee__current_department')
    
    for participant in participants:
        writer.writerow([
            participant.employee.user.get_full_name(),
            participant.employee.file_number,
            participant.employee.current_department.name if participant.employee.current_department else '',
            participant.get_status_display(),
            f"{participant.attendance_record}%" if participant.attendance_record else '',
            participant.performance_score if participant.performance_score else '',
            'Yes' if participant.certificate_issued else 'No'
        ])
    
    return response