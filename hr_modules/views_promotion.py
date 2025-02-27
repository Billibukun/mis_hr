from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Avg, Sum, Count, F
from django.http import HttpResponse

from .models import (
    PromotionCycle, PromotionCriteria, PromotionNomination, 
    PromotionAssessment
)
from core.models import EmployeeProfile, Department, Designation
from task_management.models import Task, TaskStatus

from datetime import timedelta
import csv


@login_required
def promotion_list(request):
    """List all promotion cycles"""
    # Get filter parameters
    status = request.GET.get('status', '')
    year = request.GET.get('year', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    promotion_cycles = PromotionCycle.objects.all().order_by('-year', '-start_date')
    
    # Apply filters
    if status:
        promotion_cycles = promotion_cycles.filter(status=status)
    
    if year:
        promotion_cycles = promotion_cycles.filter(year=year)
    
    if search:
        promotion_cycles = promotion_cycles.filter(title__icontains=search)
    
    # Get current user's employee profile
    employee_profile = request.user.employee_profile
    
    # Get promotions for the current user
    my_nominations = PromotionNomination.objects.filter(
        employee=employee_profile
    ).select_related('promotion_cycle').order_by('-promotion_cycle__year')
    
    # Check if user can manage promotions
    can_manage = request.user.user_permissions.get('can_manage_promotions', False)
    
    # If user can manage, get active cycles that need attention
    if can_manage:
        active_cycles = PromotionCycle.objects.filter(
            Q(status='NOMINATIONS_OPEN') | 
            Q(status='REVIEWS_IN_PROGRESS') | 
            Q(status='APPROVALS_IN_PROGRESS')
        ).order_by('end_date')
    else:
        active_cycles = None
    
    # Get years for filter
    current_year = timezone.now().year
    years = range(current_year - 5, current_year + 2)
    
    context = {
        'promotion_cycles': promotion_cycles,
        'my_nominations': my_nominations,
        'active_cycles': active_cycles,
        'can_manage': can_manage,
        'filter_status': status,
        'filter_year': year,
        'search': search,
        'years': years,
    }
    
    return render(request, 'hr_modules/promotion/promotion_list.html', context)


@login_required
def promotion_cycle_detail(request, pk):
    """View promotion cycle details"""
    promotion_cycle = get_object_or_404(PromotionCycle, pk=pk)
    
    # Get criteria for this cycle
    criteria = PromotionCriteria.objects.filter(
        promotion_cycle=promotion_cycle
    ).order_by('weight')
    
    # Get nominations for this cycle
    nominations = PromotionNomination.objects.filter(
        promotion_cycle=promotion_cycle
    ).select_related('employee', 'employee__user', 'nominated_by')
    
    # Filter nominations by status if specified
    status_filter = request.GET.get('status', '')
    if status_filter:
        nominations = nominations.filter(status=status_filter)
    
    # Get current user's nomination if exists
    employee_profile = request.user.employee_profile
    try:
        my_nomination = PromotionNomination.objects.get(
            promotion_cycle=promotion_cycle,
            employee=employee_profile
        )
    except PromotionNomination.DoesNotExist:
        my_nomination = None
    
    # Check if user can manage promotions
    can_manage = request.user.user_permissions.get('can_manage_promotions', False)
    
    # Check if user can approve promotions
    can_approve = request.user.user_permissions.get('can_approve_promotions', False)
    
    # Calculate statistics
    stats = {
        'total_nominations': nominations.count(),
        'approved': nominations.filter(status='APPROVED').count(),
        'rejected': nominations.filter(status='REJECTED').count(),
        'pending': nominations.filter(Q(status='NOMINATED') | Q(status='SHORTLISTED')).count(),
    }
    
    context = {
        'promotion_cycle': promotion_cycle,
        'criteria': criteria,
        'nominations': nominations,
        'my_nomination': my_nomination,
        'can_manage': can_manage,
        'can_approve': can_approve,
        'stats': stats,
        'status_filter': status_filter,
    }
    
    return render(request, 'hr_modules/promotion/promotion_cycle_detail.html', context)


@login_required
def promotion_cycle_create(request):
    """Create a new promotion cycle"""
    # Check if user can manage promotions
    if not request.user.user_permissions.get('can_manage_promotions', False):
        messages.error(request, "You don't have permission to create promotion cycles.")
        return redirect('hr_modules:promotion_list')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        year = request.POST.get('year')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # Validate form data
        if not all([title, year, start_date, end_date]):
            messages.error(request, "Please fill all required fields.")
            return redirect('hr_modules:promotion_cycle_create')
        
        # Create promotion cycle
        promotion_cycle = PromotionCycle.objects.create(
            title=title,
            year=year,
            start_date=start_date,
            end_date=end_date,
            status='PLANNED',
            created_by=request.user
        )
        
        messages.success(request, f"Promotion cycle '{title}' created successfully.")
        return redirect('hr_modules:promotion_cycle_detail', pk=promotion_cycle.pk)
    
    # Get current year for default value
    current_year = timezone.now().year
    years = range(current_year - 1, current_year + 3)
    
    context = {
        'years': years,
        'current_year': current_year,
    }
    
    return render(request, 'hr_modules/promotion/promotion_cycle_form.html', context)


@login_required
def promotion_cycle_update(request, pk):
    """Update an existing promotion cycle"""
    promotion_cycle = get_object_or_404(PromotionCycle, pk=pk)
    
    # Check if user can manage promotions
    if not request.user.user_permissions.get('can_manage_promotions', False):
        messages.error(request, "You don't have permission to update promotion cycles.")
        return redirect('hr_modules:promotion_cycle_detail', pk=promotion_cycle.pk)
    
    if request.method == 'POST':
        promotion_cycle.title = request.POST.get('title')
        promotion_cycle.year = request.POST.get('year')
        promotion_cycle.start_date = request.POST.get('start_date')
        promotion_cycle.end_date = request.POST.get('end_date')
        promotion_cycle.status = request.POST.get('status')
        
        promotion_cycle.save()
        
        messages.success(request, f"Promotion cycle '{promotion_cycle.title}' updated successfully.")
        return redirect('hr_modules:promotion_cycle_detail', pk=promotion_cycle.pk)
    
    # Get years for the form
    current_year = timezone.now().year
    years = range(current_year - 1, current_year + 3)
    
    context = {
        'promotion_cycle': promotion_cycle,
        'years': years,
    }
    
    return render(request, 'hr_modules/promotion/promotion_cycle_form.html', context)


@login_required
def promotion_criteria_manage(request, cycle_pk):
    """Manage criteria for a promotion cycle"""
    promotion_cycle = get_object_or_404(PromotionCycle, pk=cycle_pk)
    
    # Check if user can manage promotions
    if not request.user.user_permissions.get('can_manage_promotions', False):
        messages.error(request, "You don't have permission to manage promotion criteria.")
        return redirect('hr_modules:promotion_cycle_detail', pk=promotion_cycle.pk)
    
    if request.method == 'POST':
        # Process criteria form data
        criteria_ids = request.POST.getlist('criteria_id')
        criteria_names = request.POST.getlist('criteria_name')
        criteria_descriptions = request.POST.getlist('criteria_description')
        criteria_weights = request.POST.getlist('criteria_weight')
        
        # Validate total weight should be 100%
        total_weight = sum(int(w) for w in criteria_weights if w)
        if total_weight != 100:
            messages.error(request, f"Total weight must be 100%. Current total: {total_weight}%")
            return redirect('hr_modules:promotion_criteria_manage', cycle_pk=promotion_cycle.pk)
        
        # Process existing criteria (update or delete)
        existing_criteria = PromotionCriteria.objects.filter(promotion_cycle=promotion_cycle)
        for criteria in existing_criteria:
            if str(criteria.id) in criteria_ids:
                # Update existing criteria
                index = criteria_ids.index(str(criteria.id))
                criteria.name = criteria_names[index]
                criteria.description = criteria_descriptions[index]
                criteria.weight = criteria_weights[index]
                criteria.save()
            else:
                # Delete criteria not in the form
                criteria.delete()
        
        # Add new criteria
        for i, name in enumerate(criteria_names):
            if not criteria_ids[i]:  # No ID means new criteria
                PromotionCriteria.objects.create(
                    promotion_cycle=promotion_cycle,
                    name=name,
                    description=criteria_descriptions[i],
                    weight=criteria_weights[i]
                )
        
        messages.success(request, "Promotion criteria updated successfully.")
        return redirect('hr_modules:promotion_cycle_detail', pk=promotion_cycle.pk)
    
    # Get existing criteria
    criteria = PromotionCriteria.objects.filter(
        promotion_cycle=promotion_cycle
    ).order_by('id')
    
    context = {
        'promotion_cycle': promotion_cycle,
        'criteria': criteria,
    }
    
    return render(request, 'hr_modules/promotion/promotion_criteria_form.html', context)


@login_required
def promotion_nominate(request, cycle_pk):
    """Nominate employees for promotion"""
    promotion_cycle = get_object_or_404(PromotionCycle, pk=cycle_pk)
    
    # Check if nominations are open
    if promotion_cycle.status != 'NOMINATIONS_OPEN':
        messages.error(request, "Nominations are not currently open for this promotion cycle.")
        return redirect('hr_modules:promotion_cycle_detail', pk=promotion_cycle.pk)
    
    # Check if user can nominate (managers, department heads)
    can_nominate = (
        request.user.user_permissions.get('can_manage_promotions', False) or
        request.user.user_permissions.get('is_department_head', False) or
        request.user.user_permissions.get('is_supervisor', False)
    )
    
    if not can_nominate:
        messages.error(request, "You don't have permission to nominate employees for promotion.")
        return redirect('hr_modules:promotion_cycle_detail', pk=promotion_cycle.pk)
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        current_level = request.POST.get('current_level')
        proposed_level = request.POST.get('proposed_level')
        
        # Validate form data
        if not all([employee_id, current_level, proposed_level]):
            messages.error(request, "Please fill all required fields.")
            return redirect('hr_modules:promotion_nominate', cycle_pk=promotion_cycle.pk)
        
        # Check if employee already nominated
        if PromotionNomination.objects.filter(
            promotion_cycle=promotion_cycle,
            employee_id=employee_id
        ).exists():
            messages.error(request, "This employee is already nominated for this promotion cycle.")
            return redirect('hr_modules:promotion_nominate', cycle_pk=promotion_cycle.pk)
        
        # Create nomination
        nomination = PromotionNomination.objects.create(
            promotion_cycle=promotion_cycle,
            employee_id=employee_id,
            current_level=current_level,
            proposed_level=proposed_level,
            status='NOMINATED',
            nominated_by=request.user
        )
        
        # Notify employee
        employee = EmployeeProfile.objects.get(id=employee_id)
        Task.objects.create(
            title=f"Promotion Nomination: {promotion_cycle.title}",
            description=f"You have been nominated for promotion from GL-{current_level} to GL-{proposed_level} in the {promotion_cycle.title} cycle.",
            status=TaskStatus.objects.get(name='Pending'),
            assigned_to=employee,
            creator=request.user,
            due_date=timezone.now() + timedelta(days=3)
        )
        
        messages.success(request, "Employee nominated successfully.")
        return redirect('hr_modules:promotion_cycle_detail', pk=promotion_cycle.pk)
    
    # Get eligible employees
    # If user is a department head, only show employees in their department
    employee_profile = request.user.employee_profile
    if request.user.user_permissions.get('is_department_head', False) and employee_profile.current_department:
        employees = EmployeeProfile.objects.filter(
            user__is_active=True,
            current_department=employee_profile.current_department
        )
    else:
        employees = EmployeeProfile.objects.filter(user__is_active=True)
    
    # Select related fields and order
    employees = employees.select_related(
        'user', 'current_department', 'current_designation'
    ).order_by('user__last_name')
    
    # Exclude already nominated employees
    nominated_ids = PromotionNomination.objects.filter(
        promotion_cycle=promotion_cycle
    ).values_list('employee_id', flat=True)
    
    employees = employees.exclude(id__in=nominated_ids)
    
    context = {
        'promotion_cycle': promotion_cycle,
        'employees': employees,
    }
    
    return render(request, 'hr_modules/promotion/promotion_nominate.html', context)


@login_required
def promotion_nomination_detail(request, pk):
    """View promotion nomination details"""
    nomination = get_object_or_404(PromotionNomination, pk=pk)
    
    # Get the employee profile and check permissions
    employee_profile = request.user.employee_profile
    
    # Check if user is authorized to view this nomination
    is_nominee = nomination.employee == employee_profile
    is_nominator = nomination.nominated_by == request.user
    can_manage = request.user.user_permissions.get('can_manage_promotions', False)
    can_approve = request.user.user_permissions.get('can_approve_promotions', False)
    
    if not (is_nominee or is_nominator or can_manage or can_approve):
        messages.error(request, "You don't have permission to view this nomination.")
        return redirect('hr_modules:promotion_list')
    
    # Get assessments for this nomination
    assessments = PromotionAssessment.objects.filter(
        nomination=nomination
    ).select_related('criteria', 'assessed_by')
    
    # Calculate total score if assessments exist
    total_score = 0
    criteria_weights = {}
    
    if assessments.exists():
        for assessment in assessments:
            weight = assessment.criteria.weight / 100.0  # Convert percentage to decimal
            weighted_score = assessment.score * weight
            total_score += weighted_score
            criteria_weights[assessment.criteria.id] = weight
    
    context = {
        'nomination': nomination,
        'assessments': assessments,
        'total_score': total_score,
        'is_nominee': is_nominee,
        'is_nominator': is_nominator,
        'can_manage': can_manage,
        'can_approve': can_approve,
    }
    
    return render(request, 'hr_modules/promotion/promotion_nomination_detail.html', context)


@login_required
def promotion_assessment(request, nomination_pk):
    """Assess a promotion nomination"""
    nomination = get_object_or_404(PromotionNomination, pk=nomination_pk)
    
    # Check if reviews are in progress
    if nomination.promotion_cycle.status != 'REVIEWS_IN_PROGRESS':
        messages.error(request, "Assessments are not currently open for this promotion cycle.")
        return redirect('hr_modules:promotion_nomination_detail', pk=nomination.pk)
    
    # Check if user can assess
    if not request.user.user_permissions.get('can_manage_promotions', False):
        messages.error(request, "You don't have permission to assess nominations.")
        return redirect('hr_modules:promotion_nomination_detail', pk=nomination.pk)
    
    if request.method == 'POST':
        # Process assessment form data
        for key, value in request.POST.items():
            if key.startswith('score_'):
                criteria_id = key.split('_')[1]
                score = value
                comments = request.POST.get(f'comments_{criteria_id}', '')
                
                # Validate score
                try:
                    score = float(score)
                    if score < 0 or score > 100:
                        raise ValueError("Score must be between 0 and 100")
                except ValueError:
                    messages.error(request, f"Invalid score for criteria {criteria_id}. Score must be between 0 and 100.")
                    return redirect('hr_modules:promotion_assessment', nomination_pk=nomination.pk)
                
                # Get or create assessment
                assessment, created = PromotionAssessment.objects.get_or_create(
                    nomination=nomination,
                    criteria_id=criteria_id,
                    defaults={
                        'score': score,
                        'comments': comments,
                        'assessed_by': request.user
                    }
                )
                
                if not created:
                    # Update existing assessment
                    assessment.score = score
                    assessment.comments = comments
                    assessment.save()
        
        # Update nomination status if all criteria assessed
        criteria_count = PromotionCriteria.objects.filter(
            promotion_cycle=nomination.promotion_cycle
        ).count()
        
        assessment_count = PromotionAssessment.objects.filter(
            nomination=nomination
        ).count()
        
        if assessment_count >= criteria_count:
            nomination.status = 'SHORTLISTED'
            nomination.save()
        
        messages.success(request, "Assessment saved successfully.")
        return redirect('hr_modules:promotion_nomination_detail', pk=nomination.pk)
    
    # Get criteria for this promotion cycle
    criteria = PromotionCriteria.objects.filter(
        promotion_cycle=nomination.promotion_cycle
    ).order_by('weight')
    
    # Get existing assessments
    assessments = {}
    for assessment in PromotionAssessment.objects.filter(nomination=nomination):
        assessments[assessment.criteria.id] = assessment
    
    context = {
        'nomination': nomination,
        'criteria': criteria,
        'assessments': assessments,
    }
    
    return render(request, 'hr_modules/promotion/promotion_assessment_form.html', context)


@login_required
def promotion_approve(request, nomination_pk):
    """Approve a promotion nomination"""
    nomination = get_object_or_404(PromotionNomination, pk=nomination_pk)
    
    # Check if approvals are in progress
    if nomination.promotion_cycle.status != 'APPROVALS_IN_PROGRESS':
        messages.error(request, "Approvals are not currently open for this promotion cycle.")
        return redirect('hr_modules:promotion_nomination_detail', pk=nomination.pk)
    
    # Check if user can approve
    if not request.user.user_permissions.get('can_approve_promotions', False):
        messages.error(request, "You don't have permission to approve nominations.")
        return redirect('hr_modules:promotion_nomination_detail', pk=nomination.pk)
    
    if request.method == 'POST':
        # Update nomination
        nomination.status = 'APPROVED'
        nomination.approved_by = request.user
        nomination.approved_date = timezone.now().date()
        nomination.save()
        
        # Update employee grade level
        employee = nomination.employee
        employee.current_grade_level = nomination.proposed_level
        employee.current_step = 1  # Reset step to 1 on promotion
        employee.last_promotion_date = timezone.now().date()
        employee.save()
        
        # Create task notification for employee
        Task.objects.create(
            title="Promotion Approved",
            description=f"Your promotion to Grade Level {nomination.proposed_level} has been approved.",
            status=TaskStatus.objects.get(name='Completed'),
            assigned_to=employee,
            creator=request.user,
            completed_by=request.user,
            completed_at=timezone.now()
        )
        
        messages.success(request, f"Promotion for {employee.user.get_full_name()} approved successfully.")
        return redirect('hr_modules:promotion_nomination_detail', pk=nomination.pk)
    
    context = {
        'nomination': nomination,
    }
    
    return render(request, 'hr_modules/promotion/promotion_approve.html', context)


@login_required
def promotion_reject(request, nomination_pk):
    """Reject a promotion nomination"""
    nomination = get_object_or_404(PromotionNomination, pk=nomination_pk)
    
    # Check if approvals are in progress
    if nomination.promotion_cycle.status != 'APPROVALS_IN_PROGRESS':
        messages.error(request, "Approvals are not currently open for this promotion cycle.")
        return redirect('hr_modules:promotion_nomination_detail', pk=nomination.pk)
    
    # Check if user can approve/reject
    if not request.user.user_permissions.get('can_approve_promotions', False):
        messages.error(request, "You don't have permission to reject nominations.")
        return redirect('hr_modules:promotion_nomination_detail', pk=nomination.pk)
    
    if request.method == 'POST':
        # Get rejection reason
        rejection_reason = request.POST.get('rejection_reason')
        
        if not rejection_reason:
            messages.error(request, "Please provide a reason for rejection.")
            return redirect('hr_modules:promotion_reject', nomination_pk=nomination.pk)
        
        # Update nomination
        nomination.status = 'REJECTED'
        nomination.rejection_reason = rejection_reason
        nomination.approved_by = request.user  # Using this field to track who rejected
        nomination.approved_date = timezone.now().date()
        nomination.save()
        
        # Create task notification for employee
        Task.objects.create(
            title="Promotion Not Approved",
            description=f"Your promotion nomination to Grade Level {nomination.proposed_level} was not approved. Reason: {rejection_reason}",
            status=TaskStatus.objects.get(name='Completed'),
            assigned_to=nomination.employee,
            creator=request.user,
            completed_by=request.user,
            completed_at=timezone.now()
        )
        
        messages.success(request, f"Promotion for {nomination.employee.user.get_full_name()} has been rejected.")
        return redirect('hr_modules:promotion_nomination_detail', pk=nomination.pk)
    
    context = {
        'nomination': nomination,
    }
    
    return render(request, 'hr_modules/promotion/promotion_reject.html', context)


@login_required
def promotion_export(request, cycle_pk):
    """Export promotion data to CSV"""
    promotion_cycle = get_object_or_404(PromotionCycle, pk=cycle_pk)
    
    # Check if user can export data
    if not request.user.user_permissions.get('can_export_data', False) and not request.user.user_permissions.get('can_manage_promotions', False):
        messages.error(request, "You don't have permission to export promotion data.")
        return redirect('hr_modules:promotion_cycle_detail', pk=promotion_cycle.pk)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{promotion_cycle.title}_promotions.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    writer.writerow(['Employee', 'File Number', 'Department', 'Current Level', 'Proposed Level', 
                     'Status', 'Nominated By', 'Approved By', 'Total Score'])
    
    # Get nominations for this cycle
    nominations = PromotionNomination.objects.filter(
        promotion_cycle=promotion_cycle
    ).select_related(
        'employee', 'employee__user', 'employee__current_department',
        'nominated_by', 'approved_by'
    )
    
    # Add data rows
    for nomination in nominations:
        # Calculate total score
        assessments = PromotionAssessment.objects.filter(nomination=nomination).select_related('criteria')
        total_score = 0
        
        for assessment in assessments:
            weight = assessment.criteria.weight / 100.0
            total_score += assessment.score * weight
        
        writer.writerow([
            nomination.employee.user.get_full_name(),
            nomination.employee.file_number,
            nomination.employee.current_department.name if nomination.employee.current_department else '',
            nomination.current_level,
            nomination.proposed_level,
            nomination.get_status_display(),
            nomination.nominated_by.get_full_name() if nomination.nominated_by else '',
            nomination.approved_by.get_full_name() if nomination.approved_by else '',
            f"{total_score:.2f}"
        ])
    
    return response


@login_required
def promotion_summary_report(request):
    """Generate promotion summary report"""
    # Check if user can view reports
    if not request.user.user_permissions.get('can_view_reports', False) and not request.user.user_permissions.get('can_manage_promotions', False):
        messages.error(request, "You don't have permission to view summary reports.")
        return redirect('hr_modules:promotion_list')
    
    # Get filter parameters
    year = request.GET.get('year', '')
    department_id = request.GET.get('department', '')
    
    # Base queryset
    promotion_cycles = PromotionCycle.objects.filter(status='COMPLETED')
    
    if year:
        promotion_cycles = promotion_cycles.filter(year=year)
    
    # Get all departments for the filter
    departments = Department.objects.all()
    
    # Prepare department summary data
    department_data = {}
    for department in departments:
        department_data[department.id] = {
            'department': department,
            'nominated': 0,
            'approved': 0,
            'rejected': 0,
            'approval_rate': 0
        }
    
    # Add entry for employees without department
    department_data[0] = {
        'department': {'name': 'No Department'},
        'nominated': 0,
        'approved': 0,
        'rejected': 0,
        'approval_rate': 0
    }
    
    # Get level distribution data
    level_data = {}
    for level in range(1, 18):  # GL-1 to GL-17
        level_data[level] = {
            'from': 0,
            'to': 0
        }
    
    # Get nominations data
    nominations = PromotionNomination.objects.filter(
        promotion_cycle__in=promotion_cycles
    ).select_related('employee', 'employee__current_department')
    
    # Apply department filter if specified
    if department_id:
        nominations = nominations.filter(employee__current_department_id=department_id)
    
    # Process nominations
    for nomination in nominations:
        dept_id = nomination.employee.current_department_id if nomination.employee.current_department_id else 0
        
        if dept_id not in department_data:
            # Should not happen with our initialization, but just in case
            department_data[dept_id] = {
                'department': nomination.employee.current_department if nomination.employee.current_department else {'name': 'No Department'},
                'nominated': 0,
                'approved': 0,
                'rejected': 0,
                'approval_rate': 0
            }
        
        # Update department stats
        department_data[dept_id]['nominated'] += 1
        
        if nomination.status == 'APPROVED':
            department_data[dept_id]['approved'] += 1
            
            # Update level stats
            level_data[nomination.current_level]['from'] += 1
            level_data[nomination.proposed_level]['to'] += 1
        
        elif nomination.status == 'REJECTED':
            department_data[dept_id]['rejected'] += 1
    
    # Calculate approval rates
    for dept_id, data in department_data.items():
        if data['nominated'] > 0:
            data['approval_rate'] = (data['approved'] / data['nominated']) * 100
    
    # Calculate totals
    total_nominated = sum(d['nominated'] for d in department_data.values())
    total_approved = sum(d['approved'] for d in department_data.values())
    total_rejected = sum(d['rejected'] for d in department_data.values())
    
    if total_nominated > 0:
        total_approval_rate = (total_approved / total_nominated) * 100
    else:
        total_approval_rate = 0
    
    # Get years for filter
    all_years = PromotionCycle.objects.values_list('year', flat=True).distinct().order_by('-year')
    
    context = {
        'department_data': [d for d in department_data.values() if d['nominated'] > 0],
        'level_data': level_data.items(),
        'total_nominated': total_nominated,
        'total_approved': total_approved,
        'total_rejected': total_rejected,
        'total_approval_rate': total_approval_rate,
        'departments': departments,
        'years': all_years,
        'selected_year': year,
        'selected_department': department_id,
    }
    
    return render(request, 'hr_modules/promotion/promotion_summary_report.html', context)