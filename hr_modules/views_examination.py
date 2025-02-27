from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from django.http import HttpResponse

from .models import ExaminationType, Examination, ExaminationParticipant
from core.models import EmployeeProfile
from task_management.models import Task, TaskStatus

from datetime import timedelta
import csv


@login_required
def examination_list(request):
    """List all examinations with filters"""
    # Get filter parameters
    status = request.GET.get('status', '')
    type_id = request.GET.get('type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    examinations = Examination.objects.all().select_related('examination_type').order_by('-scheduled_date')
    
    # Apply filters
    if status:
        examinations = examinations.filter(status=status)
    
    if type_id:
        examinations = examinations.filter(examination_type_id=type_id)
    
    if date_from:
        examinations = examinations.filter(scheduled_date__gte=date_from)
    
    if date_to:
        examinations = examinations.filter(scheduled_date__lte=date_to)
    
    if search:
        examinations = examinations.filter(
            Q(title__icontains=search) | 
            Q(venue__icontains=search)
        )
    
    # Get examination types for filter
    examination_types = ExaminationType.objects.all()
    
    # Get employee profile
    employee_profile = request.user.employee_profile
    
    # Get my examinations
    my_examinations = ExaminationParticipant.objects.filter(
        employee=employee_profile
    ).select_related('examination').order_by('-examination__scheduled_date')
    
    # Get upcoming examinations I can register for
    upcoming_examinations = Examination.objects.filter(
        status='SCHEDULED',
        scheduled_date__gte=timezone.now().date(),
        registration_deadline__gte=timezone.now().date()
    ).exclude(
        participants__employee=employee_profile
    ).order_by('scheduled_date')
    
    context = {
        'examinations': examinations,
        'my_examinations': my_examinations,
        'upcoming_examinations': upcoming_examinations,
        'examination_types': examination_types,
        'filter_status': status,
        'filter_type': type_id,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'search': search,
    }
    
    return render(request, 'hr_modules/examination/examination_list.html', context)


@login_required
def examination_detail(request, pk):
    """View examination details and participants"""
    examination = get_object_or_404(Examination, pk=pk)
    
    # Check if current user is a participant
    employee_profile = request.user.employee_profile
    try:
        participant = ExaminationParticipant.objects.get(
            examination=examination,
            employee=employee_profile
        )
        is_participant = True
    except ExaminationParticipant.DoesNotExist:
        participant = None
        is_participant = False
    
    # Get all participants
    participants = ExaminationParticipant.objects.filter(
        examination=examination
    ).select_related('employee', 'employee__user').order_by('employee__user__last_name')
    
    # Get statistics if the examination is completed
    if examination.status == 'COMPLETED':
        stats = ExaminationParticipant.objects.filter(
            examination=examination,
            status__in=['PASSED', 'FAILED']
        ).aggregate(
            avg_score=Avg('score'),
            max_score=Max('score'),
            min_score=Min('score'),
            pass_count=Count('id', filter=Q(status='PASSED')),
            fail_count=Count('id', filter=Q(status='FAILED')),
            total_count=Count('id'),
        )
    else:
        stats = None
    
    # Check if registration is open
    can_register = (
        examination.status == 'SCHEDULED' and
        examination.scheduled_date >= timezone.now().date() and
        examination.registration_deadline >= timezone.now().date() and
        ExaminationParticipant.objects.filter(examination=examination).count() < examination.max_participants and
        not is_participant
    )
    
    # Check if user can manage examinations
    can_manage = request.user.user_permissions.get('can_manage_examinations', False)
    
    context = {
        'examination': examination,
        'participants': participants,
        'is_participant': is_participant,
        'participant': participant,
        'can_register': can_register,
        'can_manage': can_manage,
        'stats': stats,
    }
    
    return render(request, 'hr_modules/examination/examination_detail.html', context)


@login_required
def examination_create(request):
    """Create a new examination"""
    if not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to create examinations.")
        return redirect('hr_modules:examination_list')
    
    if request.method == 'POST':
        # Process form data
        title = request.POST.get('title')
        examination_type_id = request.POST.get('examination_type')
        scheduled_date = request.POST.get('scheduled_date')
        registration_deadline = request.POST.get('registration_deadline')
        venue = request.POST.get('venue')
        max_participants = request.POST.get('max_participants')
        
        # Validate form data
        if not all([title, examination_type_id, scheduled_date, registration_deadline, venue, max_participants]):
            messages.error(request, "Please fill all required fields.")
            return redirect('hr_modules:examination_create')
        
        # Create examination
        examination = Examination.objects.create(
            title=title,
            examination_type_id=examination_type_id,
            scheduled_date=scheduled_date,
            registration_deadline=registration_deadline,
            venue=venue,
            max_participants=int(max_participants),
            status='SCHEDULED',
            created_by=request.user
        )
        
        messages.success(request, f"Examination '{title}' created successfully.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    # Get all examination types for the form
    examination_types = ExaminationType.objects.all()
    
    context = {
        'examination_types': examination_types,
    }
    
    return render(request, 'hr_modules/examination/examination_form.html', context)


@login_required
def examination_update(request, pk):
    """Update an existing examination"""
    examination = get_object_or_404(Examination, pk=pk)
    
    if not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to update examinations.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    if request.method == 'POST':
        # Process form data
        examination.title = request.POST.get('title')
        examination.examination_type_id = request.POST.get('examination_type')
        examination.scheduled_date = request.POST.get('scheduled_date')
        examination.registration_deadline = request.POST.get('registration_deadline')
        examination.venue = request.POST.get('venue')
        examination.max_participants = int(request.POST.get('max_participants'))
        examination.status = request.POST.get('status')
        
        examination.save()
        
        messages.success(request, f"Examination '{examination.title}' updated successfully.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    # Get all examination types for the form
    examination_types = ExaminationType.objects.all()
    
    context = {
        'examination': examination,
        'examination_types': examination_types,
    }
    
    return render(request, 'hr_modules/examination/examination_form.html', context)


@login_required
def examination_delete(request, pk):
    """Delete an examination"""
    examination = get_object_or_404(Examination, pk=pk)
    
    if not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to delete examinations.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    if request.method == 'POST':
        title = examination.title
        examination.delete()
        messages.success(request, f"Examination '{title}' deleted successfully.")
        return redirect('hr_modules:examination_list')
    
    context = {
        'examination': examination,
    }
    
    return render(request, 'hr_modules/examination/examination_confirm_delete.html', context)


@login_required
def examination_register(request, pk):
    """Register for an examination"""
    examination = get_object_or_404(Examination, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if registration is open
    if (examination.status != 'SCHEDULED' or 
        examination.scheduled_date < timezone.now().date() or
        examination.registration_deadline < timezone.now().date()):
        messages.error(request, "Registration for this examination is closed.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    # Check if already registered
    if ExaminationParticipant.objects.filter(examination=examination, employee=employee_profile).exists():
        messages.error(request, "You are already registered for this examination.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    # Check if space available
    if ExaminationParticipant.objects.filter(examination=examination).count() >= examination.max_participants:
        messages.error(request, "This examination has reached maximum capacity.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    # Register for examination
    participant = ExaminationParticipant.objects.create(
        examination=examination,
        employee=employee_profile,
        status='REGISTERED'
    )
    
    messages.success(request, f"You have been registered for '{examination.title}'.")
    return redirect('hr_modules:examination_detail', pk=examination.pk)


@login_required
def examination_cancel_registration(request, pk):
    """Cancel registration for an examination"""
    examination = get_object_or_404(Examination, pk=pk)
    employee_profile = request.user.employee_profile
    
    try:
        participant = ExaminationParticipant.objects.get(
            examination=examination,
            employee=employee_profile
        )
        
        # Only allow cancellation if not yet attended
        if participant.status in ['REGISTERED', 'APPROVED']:
            participant.delete()
            messages.success(request, f"Your registration for '{examination.title}' has been cancelled.")
        else:
            messages.error(request, "Cannot cancel registration once you've attended or completed the examination.")
    
    except ExaminationParticipant.DoesNotExist:
        messages.error(request, "You are not registered for this examination.")
    
    return redirect('hr_modules:examination_detail', pk=examination.pk)


@login_required
def examination_update_participants(request, pk):
    """Bulk update examination participants"""
    examination = get_object_or_404(Examination, pk=pk)
    
    if not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to update participant status.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    if request.method == 'POST':
        # Process form data for each participant
        for key, value in request.POST.items():
            if key.startswith('status_'):
                participant_id = key.split('_')[1]
                status = value
                
                try:
                    participant = ExaminationParticipant.objects.get(pk=participant_id, examination=examination)
                    participant.status = status
                    
                    # Get score if provided
                    score_key = f'score_{participant_id}'
                    if score_key in request.POST and request.POST[score_key]:
                        participant.score = float(request.POST[score_key])
                    
                    # Get position if provided
                    position_key = f'position_{participant_id}'
                    if position_key in request.POST and request.POST[position_key]:
                        participant.position = int(request.POST[position_key])
                    
                    # Get comments if provided
                    comments_key = f'comments_{participant_id}'
                    if comments_key in request.POST:
                        participant.comments = request.POST[comments_key]
                    
                    participant.save()
                
                except (ExaminationParticipant.DoesNotExist, ValueError):
                    continue
        
        # Update examination status if all participants are processed
        if request.POST.get('update_examination_status'):
            examination.status = request.POST.get('examination_status')
            examination.save()
        
        messages.success(request, "Participant statuses updated successfully.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    # Get all participants
    participants = ExaminationParticipant.objects.filter(
        examination=examination
    ).select_related('employee', 'employee__user').order_by('employee__user__last_name')
    
    context = {
        'examination': examination,
        'participants': participants,
    }
    
    return render(request, 'hr_modules/examination/examination_update_participants.html', context)


@login_required
def examination_export_results(request, pk):
    """Export examination results to CSV"""
    examination = get_object_or_404(Examination, pk=pk)
    
    if not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to export examination results.")
        return redirect('hr_modules:examination_detail', pk=examination.pk)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{examination.title}_results.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    writer.writerow(['Name', 'File Number', 'Department', 'Status', 'Score', 'Position', 'Comments'])
    
    # Add participant data
    participants = ExaminationParticipant.objects.filter(
        examination=examination
    ).select_related('employee', 'employee__user', 'employee__current_department').order_by('-score')
    
    for participant in participants:
        writer.writerow([
            participant.employee.user.get_full_name(),
            participant.employee.file_number,
            participant.employee.current_department.name if participant.employee.current_department else '',
            participant.get_status_display(),
            participant.score if participant.score is not None else '',
            participant.position if participant.position is not None else '',
            participant.comments or ''
        ])
    
    return response


@login_required
def examination_type_list(request):
    """List all examination types"""
    if not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to view examination types.")
        return redirect('hr_modules:examination_list')
    
    examination_types = ExaminationType.objects.all()
    
    context = {
        'examination_types': examination_types,
    }
    
    return render(request, 'hr_modules/examination/examination_type_list.html', context)


@login_required
def examination_type_create(request):
    """Create a new examination type"""
    if not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to create examination types.")
        return redirect('hr_modules:examination_type_list')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        eligibility_criteria = request.POST.get('eligibility_criteria')
        
        if not name:
            messages.error(request, "Name is required.")
            return redirect('hr_modules:examination_type_create')
        
        examination_type = ExaminationType.objects.create(
            name=name,
            description=description,
            eligibility_criteria=eligibility_criteria
        )
        
        messages.success(request, f"Examination type '{name}' created successfully.")
        return redirect('hr_modules:examination_type_list')
    
    return render(request, 'hr_modules/examination/examination_type_form.html')


@login_required
def examination_type_update(request, pk):
    """Update an examination type"""
    examination_type = get_object_or_404(ExaminationType, pk=pk)
    
    if not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to update examination types.")
        return redirect('hr_modules:examination_type_list')
    
    if request.method == 'POST':
        examination_type.name = request.POST.get('name')
        examination_type.description = request.POST.get('description')
        examination_type.eligibility_criteria = request.POST.get('eligibility_criteria')
        
        if not examination_type.name:
            messages.error(request, "Name is required.")
            return redirect('hr_modules:examination_type_update', pk=pk)
        
        examination_type.save()
        
        messages.success(request, f"Examination type '{examination_type.name}' updated successfully.")
        return redirect('hr_modules:examination_type_list')
    
    context = {
        'examination_type': examination_type,
    }
    
    return render(request, 'hr_modules/examination/examination_type_form.html', context)


@login_required
def examination_type_delete(request, pk):
    """Delete an examination type"""
    examination_type = get_object_or_404(ExaminationType, pk=pk)
    
    if not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to delete examination types.")
        return redirect('hr_modules:examination_type_list')
    
    if request.method == 'POST':
        name = examination_type.name
        
        # Check if this type is used in any examinations
        if Examination.objects.filter(examination_type=examination_type).exists():
            messages.error(request, f"Cannot delete examination type '{name}' because it is used in existing examinations.")
            return redirect('hr_modules:examination_type_list')
        
        examination_type.delete()
        messages.success(request, f"Examination type '{name}' deleted successfully.")
        return redirect('hr_modules:examination_type_list')
    
    context = {
        'examination_type': examination_type,
    }
    
    return render(request, 'hr_modules/examination/examination_type_confirm_delete.html', context)


@login_required
def examination_summary_report(request):
    """Generate examination summary report"""
    # Check if user can view reports
    if not request.user.user_permissions.get('can_view_reports', False) and not request.user.user_permissions.get('can_manage_examinations', False):
        messages.error(request, "You don't have permission to view summary reports.")
        return redirect('hr_modules:examination_list')
    
    # Get filter parameters
    year = request.GET.get('year', str(timezone.now().year))
    examination_type_id = request.GET.get('examination_type', '')
    
    # Get examinations for the given year
    examinations = Examination.objects.filter(
        scheduled_date__year=year,
        status='COMPLETED'
    ).select_related('examination_type').order_by('scheduled_date')
    
    # Apply examination type filter
    if examination_type_id:
        examinations = examinations.filter(examination_type_id=examination_type_id)
    
    # Get examination summary data
    examination_data = []
    for examination in examinations:
        # Get participant statistics
        stats = ExaminationParticipant.objects.filter(
            examination=examination
        ).aggregate(
            registered=Count('id'),
            attended=Count('id', filter=Q(status__in=['ATTENDED', 'PASSED', 'FAILED'])),
            passed=Count('id', filter=Q(status='PASSED')),
            failed=Count('id', filter=Q(status='FAILED')),
            avg_score=Avg('score', filter=Q(score__isnull=False))
        )
        
        # Calculate pass rate
        if stats['attended'] > 0:
            pass_rate = (stats['passed'] / stats['attended']) * 100
        else:
            pass_rate = 0
        
        examination_data.append({
            'examination': examination,
            'registered': stats['registered'],
            'attended': stats['attended'],
            'passed': stats['passed'],
            'failed': stats['failed'],
            'avg_score': stats['avg_score'] or 0,
            'pass_rate': pass_rate
        })
    
    # Get total statistics
    total_registered = sum(ed['registered'] for ed in examination_data)
    total_attended = sum(ed['attended'] for ed in examination_data)
    total_passed = sum(ed['passed'] for ed in examination_data)
    total_failed = sum(ed['failed'] for ed in examination_data)
    
    if total_attended > 0:
        total_pass_rate = (total_passed / total_attended) * 100
        avg_score_all = sum(ed['avg_score'] * ed['attended'] for ed in examination_data) / total_attended if total_attended > 0 else 0
    else:
        total_pass_rate = 0
        avg_score_all = 0
    
    # Get examination types for filter
    examination_types = ExaminationType.objects.all()
    
    # Get years for filter
    current_year = timezone.now().year
    years = range(current_year - 2, current_year + 3)
    
    context = {
        'examination_data': examination_data,
        'total_registered': total_registered,
        'total_attended': total_attended,
        'total_passed': total_passed,
        'total_failed': total_failed,
        'total_pass_rate': total_pass_rate,
        'avg_score_all': avg_score_all,
        'examination_types': examination_types,
        'years': years,
        'selected_year': year,
        'selected_examination_type': examination_type_id,
    }
    
    return render(request, 'hr_modules/examination/examination_summary_report.html', context)