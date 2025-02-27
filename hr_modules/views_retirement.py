from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, F, ExpressionWrapper, fields
from django.http import HttpResponse

from .models import RetirementPlan, RetirementChecklistItem
from core.models import EmployeeProfile, Department
from task_management.models import Task, TaskStatus

from datetime import timedelta, date
import csv


@login_required
def retirement_list(request):
    """List all retirement plans with filters"""
    # Get filter parameters
    status = request.GET.get('status', '')
    year = request.GET.get('year', str(timezone.now().year))
    department_id = request.GET.get('department', '')
    search = request.GET.get('search', '')
    
    # Check if user can manage retirements
    can_manage = request.user.user_permissions.get('can_manage_retirements', False)
    
    if not can_manage:
        messages.error(request, "You don't have permission to access retirement management.")
        return redirect('dashboard')
    
    # Base queryset
    retirement_plans = RetirementPlan.objects.all().select_related(
        'employee', 'employee__user', 'employee__current_department',
        'exit_interview_conducted_by'
    )
    
    # Order by expected retirement date
    retirement_plans = retirement_plans.order_by('expected_retirement_date')
    
    # Apply filters
    if status:
        retirement_plans = retirement_plans.filter(status=status)
    
    if year:
        retirement_plans = retirement_plans.filter(expected_retirement_date__year=year)
    
    if department_id:
        retirement_plans = retirement_plans.filter(employee__current_department_id=department_id)
    
    if search:
        retirement_plans = retirement_plans.filter(
            Q(employee__user__first_name__icontains=search) |
            Q(employee__user__last_name__icontains=search) |
            Q(employee__file_number__icontains=search)
        )
    
    # Calculate days to retirement
    today = timezone.now().date()
    for plan in retirement_plans:
        plan.days_to_retirement = (plan.expected_retirement_date - today).days
    
    # Get upcoming retirements (next 90 days)
    upcoming_retirements = RetirementPlan.objects.filter(
        expected_retirement_date__gte=today,
        expected_retirement_date__lte=today + timedelta(days=90),
        status__in=['UPCOMING', 'NOTIFIED']
    ).select_related('employee', 'employee__user').order_by('expected_retirement_date')
    
    # Get counts for dashboard
    total_count = retirement_plans.count()
    upcoming_count = RetirementPlan.objects.filter(
        expected_retirement_date__gte=today,
        expected_retirement_date__lte=today + timedelta(days=90)
    ).count()
    processing_count = RetirementPlan.objects.filter(
        status__in=['NOTIFIED', 'IN_PROGRESS']
    ).count()
    completed_count = RetirementPlan.objects.filter(
        status='COMPLETED'
    ).count()
    
    # Get departments for filter
    departments = Department.objects.all()
    
    # Get years for filter
    current_year = timezone.now().year
    years = range(current_year - 2, current_year + 5)
    
    context = {
        'retirement_plans': retirement_plans,
        'upcoming_retirements': upcoming_retirements,
        'total_count': total_count,
        'upcoming_count': upcoming_count,
        'processing_count': processing_count,
        'completed_count': completed_count,
        'departments': departments,
        'years': years,
        'filter_status': status,
        'filter_year': year,
        'filter_department': department_id,
        'search': search,
    }
    
    return render(request, 'hr_modules/retirement/retirement_list.html', context)


@login_required
def retirement_detail(request, pk):
    """View retirement plan details"""
    retirement_plan = get_object_or_404(RetirementPlan, pk=pk)
    
    # Check if user can manage retirements
    can_manage = request.user.user_permissions.get('can_manage_retirements', False)
    
    # Check if user is the retiring employee
    is_self = retirement_plan.employee == request.user.employee_profile
    
    if not (can_manage or is_self):
        messages.error(request, "You don't have permission to view this retirement plan.")
        return redirect('dashboard')
    
    # Get checklist items
    checklist_items = RetirementChecklistItem.objects.filter(
        retirement_plan=retirement_plan
    ).order_by('id')
    
    # Calculate completion percentage
    if checklist_items.exists():
        completed_items = checklist_items.filter(is_completed=True).count()
        total_items = checklist_items.count()
        completion_percentage = int((completed_items / total_items) * 100)
    else:
        completion_percentage = 0
    
    # Calculate days to retirement
    today = timezone.now().date()
    days_to_retirement = (retirement_plan.expected_retirement_date - today).days
    
    context = {
        'retirement_plan': retirement_plan,
        'checklist_items': checklist_items,
        'completion_percentage': completion_percentage,
        'days_to_retirement': days_to_retirement,
        'can_manage': can_manage,
        'is_self': is_self,
    }
    
    return render(request, 'hr_modules/retirement/retirement_detail.html', context)


@login_required
def retirement_create(request):
    """Create a new retirement plan"""
    # Check if user can manage retirements
    if not request.user.user_permissions.get('can_manage_retirements', False):
        messages.error(request, "You don't have permission to create retirement plans.")
        return redirect('hr_modules:retirement_list')
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        expected_retirement_date = request.POST.get('expected_retirement_date')
        
        # Validate form data
        if not all([employee_id, expected_retirement_date]):
            messages.error(request, "Please fill all required fields.")
            return redirect('hr_modules:retirement_create')
        
        # Check if retirement plan already exists for this employee
        if RetirementPlan.objects.filter(employee_id=employee_id).exists():
            messages.error(request, "A retirement plan already exists for this employee.")
            return redirect('hr_modules:retirement_list')
        
        # Create retirement plan
        retirement_plan = RetirementPlan.objects.create(
            employee_id=employee_id,
            expected_retirement_date=expected_retirement_date,
            status='UPCOMING'
        )
        
        # Create default checklist items
        default_items = [
            "Documentation review",
            "Exit interview scheduling",
            "Badge/access card collection",
            "Equipment return",
            "Final payment calculation",
            "Pension processing",
            "Clearance from all departments",
            "Farewell arrangements"
        ]
        
        for item in default_items:
            RetirementChecklistItem.objects.create(
                retirement_plan=retirement_plan,
                item_name=item,
                description="",
                is_completed=False
            )
        
        messages.success(request, "Retirement plan created successfully.")
        return redirect('hr_modules:retirement_detail', pk=retirement_plan.pk)
    
    # Get eligible employees (close to retirement age)
    today = timezone.now().date()
    
    # Find employees within 5 years of retirement
    # In a real system, we would use date_of_birth and date_of_assumption to calculate
    employees = EmployeeProfile.objects.filter(
        user__is_active=True
    ).select_related('user', 'current_department').order_by('user__last_name')
    
    # Exclude employees with existing retirement plans
    existing_plans = RetirementPlan.objects.values_list('employee_id', flat=True)
    employees = employees.exclude(id__in=existing_plans)
    
    context = {
        'employees': employees,
    }
    
    return render(request, 'hr_modules/retirement/retirement_form.html', context)


@login_required
def retirement_update(request, pk):
    """Update a retirement plan"""
    retirement_plan = get_object_or_404(RetirementPlan, pk=pk)
    
    # Check if user can manage retirements
    if not request.user.user_permissions.get('can_manage_retirements', False):
        messages.error(request, "You don't have permission to update retirement plans.")
        return redirect('hr_modules:retirement_detail', pk=retirement_plan.pk)
    
    if request.method == 'POST':
        # Process form data
        expected_retirement_date = request.POST.get('expected_retirement_date')
        status = request.POST.get('status')
        notification_date = request.POST.get('notification_date') or None
        exit_interview_date = request.POST.get('exit_interview_date') or None
        clearance_completed = request.POST.get('clearance_completed') == 'on'
        clearance_date = request.POST.get('clearance_date') or None
        pension_processed = request.POST.get('pension_processed') == 'on'
        pension_processing_date = request.POST.get('pension_processing_date') or None
        final_payout_amount = request.POST.get('final_payout_amount') or None
        final_payout_date = request.POST.get('final_payout_date') or None
        comments = request.POST.get('comments')
        
        # Update retirement plan
        retirement_plan.expected_retirement_date = expected_retirement_date
        retirement_plan.status = status
        retirement_plan.notification_date = notification_date
        retirement_plan.exit_interview_date = exit_interview_date
        retirement_plan.clearance_completed = clearance_completed
        retirement_plan.clearance_date = clearance_date
        retirement_plan.pension_processed = pension_processed
        retirement_plan.pension_processing_date = pension_processing_date
        
        if final_payout_amount:
            retirement_plan.final_payout_amount = final_payout_amount
        
        retirement_plan.final_payout_date = final_payout_date
        retirement_plan.comments = comments
        
        # If status changed to NOTIFIED, record notification date
        if retirement_plan.status == 'NOTIFIED' and not retirement_plan.notification_date:
            retirement_plan.notification_date = timezone.now().date()
            
            # Create task notification for employee
            Task.objects.create(
                title="Retirement Notification",
                description=f"You have been notified of your upcoming retirement scheduled for {retirement_plan.expected_retirement_date}.",
                status=TaskStatus.objects.get(name='Completed'),
                assigned_to=retirement_plan.employee,
                creator=request.user,
                completed_by=request.user,
                completed_at=timezone.now()
            )
        
        # If status changed to RETIRED, update employee status
        if retirement_plan.status == 'RETIRED':
            employee = retirement_plan.employee
            employee.user.is_active = False
            employee.user.save()
        
        retirement_plan.save()
        
        messages.success(request, "Retirement plan updated successfully.")
        return redirect('hr_modules:retirement_detail', pk=retirement_plan.pk)
    
    context = {
        'retirement_plan': retirement_plan,
    }
    
    return render(request, 'hr_modules/retirement/retirement_form.html', context)


@login_required
def retirement_checklist_manage(request, plan_pk):
    """Manage retirement checklist items"""
    retirement_plan = get_object_or_404(RetirementPlan, pk=plan_pk)
    
    # Check if user can manage retirements
    if not request.user.user_permissions.get('can_manage_retirements', False):
        messages.error(request, "You don't have permission to manage retirement checklists.")
        return redirect('hr_modules:retirement_detail', pk=retirement_plan.pk)
    
    if request.method == 'POST':
        # Process form data for existing items
        for key, value in request.POST.items():
            if key.startswith('completed_'):
                item_id = key.split('_')[1]
                is_completed = value == 'on'
                comments = request.POST.get(f'comments_{item_id}', '')
                
                try:
                    checklist_item = RetirementChecklistItem.objects.get(
                        id=item_id,
                        retirement_plan=retirement_plan
                    )
                    
                    checklist_item.is_completed = is_completed
                    checklist_item.comments = comments
                    
                    if is_completed and not checklist_item.completed_date:
                        checklist_item.completed_date = timezone.now().date()
                        checklist_item.completed_by = request.user
                    
                    checklist_item.save()
                
                except RetirementChecklistItem.DoesNotExist:
                    continue
        
        # Process new items
        new_item_name = request.POST.get('new_item_name')
        new_item_description = request.POST.get('new_item_description', '')
        
        if new_item_name:
            RetirementChecklistItem.objects.create(
                retirement_plan=retirement_plan,
                item_name=new_item_name,
                description=new_item_description,
                is_completed=False
            )
        
        # Check if all items are completed and update retirement plan status
        all_items = RetirementChecklistItem.objects.filter(retirement_plan=retirement_plan)
        all_completed = all_items.exists() and all(item.is_completed for item in all_items)
        
        if all_completed and retirement_plan.status in ['IN_PROGRESS', 'NOTIFIED']:
            retirement_plan.status = 'COMPLETED'
            retirement_plan.save()
            
            messages.success(request, "All checklist items completed. Retirement plan status updated to COMPLETED.")
        else:
            messages.success(request, "Checklist items updated successfully.")
        
        return redirect('hr_modules:retirement_detail', pk=retirement_plan.pk)
    
    # Get existing checklist items
    checklist_items = RetirementChecklistItem.objects.filter(
        retirement_plan=retirement_plan
    ).order_by('id')
    
    context = {
        'retirement_plan': retirement_plan,
        'checklist_items': checklist_items,
    }
    
    return render(request, 'hr_modules/retirement/retirement_checklist.html', context)


@login_required
def retirement_checklist_item_delete(request, item_pk):
    """Delete a retirement checklist item"""
    checklist_item = get_object_or_404(RetirementChecklistItem, pk=item_pk)
    retirement_plan = checklist_item.retirement_plan
    
    # Check if user can manage retirements
    if not request.user.user_permissions.get('can_manage_retirements', False):
        messages.error(request, "You don't have permission to delete checklist items.")
        return redirect('hr_modules:retirement_detail', pk=retirement_plan.pk)
    
    if request.method == 'POST':
        checklist_item.delete()
        messages.success(request, "Checklist item deleted successfully.")
        
        return redirect('hr_modules:retirement_detail', pk=retirement_plan.pk)
    
    context = {
        'checklist_item': checklist_item,
        'retirement_plan': retirement_plan,
    }
    
    return render(request, 'hr_modules/retirement/checklist_item_confirm_delete.html', context)


@login_required
def retirement_exit_interview(request, pk):
    """Record retirement exit interview"""
    retirement_plan = get_object_or_404(RetirementPlan, pk=pk)
    
    # Check if user can manage retirements
    if not request.user.user_permissions.get('can_manage_retirements', False):
        messages.error(request, "You don't have permission to conduct exit interviews.")
        return redirect('hr_modules:retirement_detail', pk=retirement_plan.pk)
    
    if request.method == 'POST':
        # Process form data
        exit_interview_date = request.POST.get('exit_interview_date')
        comments = request.POST.get('comments')
        
        if not exit_interview_date:
            messages.error(request, "Please provide an exit interview date.")
            return redirect('hr_modules:retirement_exit_interview', pk=retirement_plan.pk)
        
        # Update retirement plan
        retirement_plan.exit_interview_date = exit_interview_date
        retirement_plan.exit_interview_conducted_by = request.user
        
        if comments:
            retirement_plan.comments = comments
        
        retirement_plan.save()
        
        # Update checklist item if exists
        try:
            checklist_item = RetirementChecklistItem.objects.get(
                retirement_plan=retirement_plan,
                item_name__icontains="exit interview"
            )
            
            checklist_item.is_completed = True
            checklist_item.completed_date = timezone.now().date()
            checklist_item.completed_by = request.user
            checklist_item.comments = "Exit interview conducted on " + exit_interview_date
            checklist_item.save()
        
        except RetirementChecklistItem.DoesNotExist:
            pass
        
        messages.success(request, "Exit interview recorded successfully.")
        return redirect('hr_modules:retirement_detail', pk=retirement_plan.pk)
    
    context = {
        'retirement_plan': retirement_plan,
    }
    
    return render(request, 'hr_modules/retirement/exit_interview_form.html', context)


@login_required
def retirement_export(request):
    """Export retirement data to CSV"""
    # Check if user can export data
    if not request.user.user_permissions.get('can_export_data', False) and not request.user.user_permissions.get('can_manage_retirements', False):
        messages.error(request, "You don't have permission to export retirement data.")
        return redirect('hr_modules:retirement_list')
    
    # Get filter parameters
    year = request.GET.get('year', str(timezone.now().year))
    status = request.GET.get('status', '')
    
    # Base queryset
    retirement_plans = RetirementPlan.objects.all().select_related(
        'employee', 'employee__user', 'employee__current_department',
        'exit_interview_conducted_by'
    ).order_by('expected_retirement_date')
    
    # Apply filters
    if year:
        retirement_plans = retirement_plans.filter(expected_retirement_date__year=year)
    
    if status:
        retirement_plans = retirement_plans.filter(status=status)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="retirement_plans_{year}.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    writer.writerow(['Employee', 'File Number', 'Department', 'Retirement Date', 'Status',
                    'Notification Date', 'Exit Interview Date', 'Clearance Completed',
                    'Pension Processed', 'Final Payout Amount', 'Final Payout Date'])
    
    # Add data rows
    for plan in retirement_plans:
        writer.writerow([
            plan.employee.user.get_full_name(),
            plan.employee.file_number,
            plan.employee.current_department.name if plan.employee.current_department else '',
            plan.expected_retirement_date,
            plan.get_status_display(),
            plan.notification_date if plan.notification_date else '',
            plan.exit_interview_date if plan.exit_interview_date else '',
            'Yes' if plan.clearance_completed else 'No',
            'Yes' if plan.pension_processed else 'No',
            plan.final_payout_amount if plan.final_payout_amount else '',
            plan.final_payout_date if plan.final_payout_date else ''
        ])
    
    return response


@login_required
def retirement_forecast(request):
    """Generate retirement forecast report"""
    # Check if user can view reports
    if not request.user.user_permissions.get('can_view_reports', False) and not request.user.user_permissions.get('can_manage_retirements', False):
        messages.error(request, "You don't have permission to view forecast reports.")
        return redirect('hr_modules:retirement_list')
    
    # Get filter parameters
    years_ahead = int(request.GET.get('years_ahead', '5'))
    department_id = request.GET.get('department', '')
    
    # Base date for calculations
    today = timezone.now().date()
    end_date = today + timedelta(days=365 * years_ahead)
    
    # Get all retirement plans within the forecast period
    retirement_plans = RetirementPlan.objects.filter(
        expected_retirement_date__gte=today,
        expected_retirement_date__lte=end_date
    ).select_related('employee', 'employee__user', 'employee__current_department')
    
    # Apply department filter
    if department_id:
        retirement_plans = retirement_plans.filter(employee__current_department_id=department_id)
    
    # Group by year and department
    year_data = {}
    department_data = {}
    
    for plan in retirement_plans:
        # Group by year
        year = plan.expected_retirement_date.year
        if year not in year_data:
            year_data[year] = []
        year_data[year].append(plan)
        
        # Group by department
        dept_name = plan.employee.current_department.name if plan.employee.current_department else "No Department"
        if dept_name not in department_data:
            department_data[dept_name] = []
        department_data[dept_name].append(plan)
    
    # Sort departments by number of retirees
    department_counts = {dept: len(plans) for dept, plans in department_data.items()}
    sorted_departments = sorted(department_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Get departments for filter
    departments = Department.objects.all()
    
    context = {
        'retirement_plans': retirement_plans,
        'year_data': year_data.items(),
        'department_data': department_data,
        'sorted_departments': sorted_departments,
        'departments': departments,
        'years_ahead': years_ahead,
        'filter_department': department_id,
        'today': today,
        'end_date': end_date,
    }
    
    return render(request, 'hr_modules/retirement/retirement_forecast.html', context)


@login_required
def identify_upcoming_retirements(request):
    """Automatic identification of employees approaching retirement"""
    # Check if user can manage retirements
    if not request.user.user_permissions.get('can_manage_retirements', False):
        messages.error(request, "You don't have permission to identify upcoming retirements.")
        return redirect('hr_modules:retirement_list')
    
    if request.method == 'POST':
        # Process retirement identification
        upcoming_years = int(request.POST.get('upcoming_years', '1'))
        department_id = request.POST.get('department', '')
        
        today = timezone.now().date()
        cutoff_date = today + timedelta(days=365 * upcoming_years)
        
        # Get all employees with age or service approaching retirement
        # In a real implementation, this would use date_of_birth for age-based retirement
        # and date_of_assumption for service-based retirement
        
        employees = EmployeeProfile.objects.filter(
            user__is_active=True,
            date_of_retirement__isnull=False,
            date_of_retirement__lte=cutoff_date
        ).select_related('user', 'current_department')
        
        # Apply department filter
        if department_id:
            employees = employees.filter(current_department_id=department_id)
        
        # Exclude employees with existing retirement plans
        existing_plans = RetirementPlan.objects.values_list('employee_id', flat=True)
        employees = employees.exclude(id__in=existing_plans)
        
        # Create retirement plans for identified employees
        count = 0
        for employee in employees:
            retirement_plan = RetirementPlan.objects.create(
                employee=employee,
                expected_retirement_date=employee.date_of_retirement,
                status='UPCOMING'
            )
            
            # Create default checklist items
            default_items = [
                "Documentation review",
                "Exit interview scheduling",
                "Badge/access card collection",
                "Equipment return",
                "Final payment calculation",
                "Pension processing",
                "Clearance from all departments",
                "Farewell arrangements"
            ]
            
            for item in default_items:
                RetirementChecklistItem.objects.create(
                    retirement_plan=retirement_plan,
                    item_name=item,
                    description="",
                    is_completed=False
                )
            
            count += 1
        
        if count > 0:
            messages.success(request, f"Successfully identified {count} employees approaching retirement.")
        else:
            messages.info(request, "No new employees approaching retirement were identified.")
        
        return redirect('hr_modules:retirement_list')
    
    # Get departments for filter
    departments = Department.objects.all()
    
    context = {
        'departments': departments,
    }
    
    return render(request, 'hr_modules/retirement/identify_retirements.html', context)