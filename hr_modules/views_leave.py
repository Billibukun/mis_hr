from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum
from django.http import HttpResponse

from .models import LeaveType, LeaveBalance, LeaveRequest, LeaveApprovalLevel
from core.models import EmployeeProfile, Department
from task_management.models import Task, TaskStatus

from datetime import timedelta, datetime
import csv


@login_required
def leave_list(request):
    """List all leave requests with filters"""
    # Get filter parameters
    status = request.GET.get('status', '')
    type_id = request.GET.get('type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    employee_profile = request.user.employee_profile
    
    # Check if user can approve leaves
    can_approve = request.user.user_permissions.get('can_approve_leaves', False)
    
    # Base queryset - if can approve, show all leaves, otherwise show only user's leaves
    if can_approve:
        leaves = LeaveRequest.objects.all().select_related(
            'employee', 'employee__user', 'leave_type', 'approved_by'
        )
    else:
        leaves = LeaveRequest.objects.filter(
            employee=employee_profile
        ).select_related('employee', 'employee__user', 'leave_type', 'approved_by')
    
    # Order by recency and status
    leaves = leaves.order_by('-created_at')
    
    # Apply filters
    if status:
        leaves = leaves.filter(status=status)
    
    if type_id:
        leaves = leaves.filter(leave_type_id=type_id)
    
    if date_from:
        leaves = leaves.filter(start_date__gte=date_from)
    
    if date_to:
        leaves = leaves.filter(end_date__lte=date_to)
    
    if search:
        if can_approve:
            leaves = leaves.filter(
                Q(employee__user__first_name__icontains=search) |
                Q(employee__user__last_name__icontains=search) |
                Q(employee__file_number__icontains=search) |
                Q(reason__icontains=search)
            )
        else:
            leaves = leaves.filter(
                Q(reason__icontains=search)
            )
    
    # Get leave types for filter
    leave_types = LeaveType.objects.all()
    
    # Get leave balances for current user
    leave_balances = LeaveBalance.objects.filter(
        employee=employee_profile,
        year=timezone.now().year
    ).select_related('leave_type')
    
    # Get pending approvals for user if they can approve
    if can_approve:
        pending_approvals = LeaveRequest.objects.filter(
            status='PENDING'
        ).select_related('employee', 'employee__user', 'leave_type')
        
        # Filter based on department if user is a manager
        if request.user.user_permissions.get('is_department_head', False):
            user_department = employee_profile.current_department
            if user_department:
                pending_approvals = pending_approvals.filter(
                    employee__current_department=user_department
                )
    else:
        pending_approvals = None
    
    context = {
        'leaves': leaves,
        'leave_types': leave_types,
        'leave_balances': leave_balances,
        'pending_approvals': pending_approvals,
        'can_approve': can_approve,
        'filter_status': status,
        'filter_type': type_id,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
        'search': search,
    }
    
    return render(request, 'hr_modules/leave/leave_list.html', context)


@login_required
def leave_detail(request, pk):
    """View leave request details"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if user is authorized to view this leave
    is_owner = leave_request.employee == employee_profile
    can_approve = request.user.user_permissions.get('can_approve_leaves', False)
    
    if not (is_owner or can_approve):
        messages.error(request, "You don't have permission to view this leave request.")
        return redirect('hr_modules:leave_list')
    
    # Check if user is authorized to approve this leave
    can_approve_this = False
    if can_approve:
        # Department head can only approve for their department
        if request.user.user_permissions.get('is_department_head', False):
            user_department = employee_profile.current_department
            leave_department = leave_request.employee.current_department
            can_approve_this = user_department == leave_department
        else:
            can_approve_this = True
    
    context = {
        'leave_request': leave_request,
        'is_owner': is_owner,
        'can_approve_this': can_approve_this,
    }
    
    return render(request, 'hr_modules/leave/leave_detail.html', context)


@login_required
def leave_create(request):
    """Create a new leave request"""
    employee_profile = request.user.employee_profile
    
    if request.method == 'POST':
        # Process form data
        leave_type_id = request.POST.get('leave_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')
        
        # Validate form data
        if not all([leave_type_id, start_date, end_date, reason]):
            messages.error(request, "Please fill all required fields.")
            return redirect('hr_modules:leave_create')
        
        # Convert dates
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Calculate days
        days_requested = (end_date - start_date).days + 1
        
        if days_requested <= 0:
            messages.error(request, "End date must be after start date.")
            return redirect('hr_modules:leave_create')
        
        # Check leave balance
        try:
            leave_balance = LeaveBalance.objects.get(
                employee=employee_profile,
                leave_type_id=leave_type_id,
                year=timezone.now().year
            )
            
            if leave_balance.remaining_balance < days_requested:
                messages.error(request, f"Insufficient leave balance. You have {leave_balance.remaining_balance} days remaining.")
                return redirect('hr_modules:leave_create')
        
        except LeaveBalance.DoesNotExist:
            messages.error(request, "No leave balance found for this leave type.")
            return redirect('hr_modules:leave_create')
        
        # Create leave request
        leave_request = LeaveRequest.objects.create(
            employee=employee_profile,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            days_requested=days_requested,
            reason=reason,
            status='PENDING'
        )
        
        # Create notification task for HR
        hr_department = Department.objects.filter(code='HR').first()
        if hr_department:
            hr_heads = EmployeeProfile.objects.filter(
                current_department=hr_department,
                current_employee_type='HOD'
            )
            
            for hr_head in hr_heads:
                Task.objects.create(
                    title=f"Leave Request: {employee_profile.user.get_full_name()}",
                    description=f"New leave request from {employee_profile.user.get_full_name()} ({employee_profile.file_number}) for {days_requested} days from {start_date} to {end_date}. Reason: {reason}",
                    status=TaskStatus.objects.get(name='Pending'),
                    assigned_to=hr_head,
                    creator=request.user,
                    due_date=timezone.now() + timedelta(days=2)
                )
        
        messages.success(request, "Leave request submitted successfully.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    # Get available leave types with balances
    leave_balances = LeaveBalance.objects.filter(
        employee=employee_profile,
        year=timezone.now().year
    ).select_related('leave_type')
    
    context = {
        'leave_balances': leave_balances,
    }
    
    return render(request, 'hr_modules/leave/leave_form.html', context)


@login_required
def leave_cancel(request, pk):
    """Cancel a leave request"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if user is the owner of this leave request
    if leave_request.employee != employee_profile:
        messages.error(request, "You can only cancel your own leave requests.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    # Check if leave request can be cancelled (must be in PENDING or APPROVED status)
    if leave_request.status not in ['PENDING', 'APPROVED']:
        messages.error(request, "This leave request cannot be cancelled.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    # Check if leave has already started
    if leave_request.start_date <= timezone.now().date():
        messages.error(request, "Cannot cancel a leave that has already started.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    if request.method == 'POST':
        # Cancel the leave request
        leave_request.status = 'CANCELLED'
        leave_request.save()
        
        messages.success(request, "Leave request cancelled successfully.")
        return redirect('hr_modules:leave_list')
    
    context = {
        'leave_request': leave_request,
    }
    
    return render(request, 'hr_modules/leave/leave_reject.html', context)


@login_required
def leave_balance_admin(request):
    """Manage leave balances (admin view)"""
    # Check if user can manage leaves
    if not request.user.user_permissions.get('can_manage_leaves', False):
        messages.error(request, "You don't have permission to manage leave balances.")
        return redirect('hr_modules:leave_list')
    
    # Get filter parameters
    year = request.GET.get('year', str(timezone.now().year))
    department_id = request.GET.get('department', '')
    search = request.GET.get('search', '')
    
    # Get all employees with their leave balances
    employees = EmployeeProfile.objects.filter(
        user__is_active=True
    ).select_related('user', 'current_department').order_by('user__last_name')
    
    # Apply filters
    if department_id:
        employees = employees.filter(current_department_id=department_id)
    
    if search:
        employees = employees.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(file_number__icontains=search)
        )
    
    # Get leave types
    leave_types = LeaveType.objects.all()
    
    # Get leave balances for all employees
    leave_balances = LeaveBalance.objects.filter(
        year=year
    ).select_related('employee', 'leave_type')
    
    # Organize leave balances by employee and leave type
    employee_balances = {}
    for employee in employees:
        employee_balances[employee.id] = {
            'employee': employee,
            'balances': {}
        }
        
        # Initialize with zero balances for all leave types
        for leave_type in leave_types:
            employee_balances[employee.id]['balances'][leave_type.id] = {
                'initial': 0,
                'used': 0,
                'remaining': 0
            }
    
    # Fill in actual balances
    for balance in leave_balances:
        if balance.employee_id in employee_balances:
            employee_balances[balance.employee_id]['balances'][balance.leave_type_id] = {
                'initial': balance.initial_balance,
                'used': balance.used_days,
                'remaining': balance.remaining_balance
            }
    
    # Get departments for filter
    departments = Department.objects.all()
    
    # Get years for filter (from 2 years ago to 2 years in the future)
    current_year = timezone.now().year
    years = range(current_year - 2, current_year + 3)
    
    context = {
        'employee_balances': employee_balances.values(),
        'leave_types': leave_types,
        'departments': departments,
        'years': years,
        'selected_year': year,
        'selected_department': department_id,
        'search': search,
    }
    
    return render(request, 'hr_modules/leave/leave_balance_admin.html', context)


@login_required
def leave_balance_update(request, employee_id):
    """Update leave balance for an employee"""
    # Check if user can manage leaves
    if not request.user.user_permissions.get('can_manage_leaves', False):
        messages.error(request, "You don't have permission to update leave balances.")
        return redirect('hr_modules:leave_balance_admin')
    
    employee = get_object_or_404(EmployeeProfile, pk=employee_id)
    
    if request.method == 'POST':
        year = request.POST.get('year', str(timezone.now().year))
        
        # Process each leave type
        for leave_type in LeaveType.objects.all():
            initial_balance = request.POST.get(f'initial_{leave_type.id}', '0')
            
            if initial_balance and initial_balance != '0':
                # Get or create leave balance
                balance, created = LeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=leave_type,
                    year=year,
                    defaults={'initial_balance': int(initial_balance), 'used_days': 0}
                )
                
                if not created:
                    # Update existing balance
                    balance.initial_balance = int(initial_balance)
                    balance.save()
        
        messages.success(request, f"Leave balance for {employee.user.get_full_name()} updated successfully.")
        return redirect('hr_modules:leave_balance_admin')
    
    # Get current leave balances
    year = request.GET.get('year', str(timezone.now().year))
    leave_types = LeaveType.objects.all()
    
    balances = {}
    for leave_type in leave_types:
        try:
            balance = LeaveBalance.objects.get(
                employee=employee,
                leave_type=leave_type,
                year=year
            )
            balances[leave_type.id] = balance
        except LeaveBalance.DoesNotExist:
            balances[leave_type.id] = None
    
    # Get years for filter
    current_year = timezone.now().year
    years = range(current_year - 2, current_year + 3)
    
    context = {
        'employee': employee,
        'leave_types': leave_types,
        'balances': balances,
        'years': years,
        'selected_year': year,
    }
    
    return render(request, 'hr_modules/leave/leave_balance_update.html', context)


@login_required
def leave_export(request):
    """Export leave records to CSV"""
    # Check if user can export leaves
    if not request.user.user_permissions.get('can_export_data', False) and not request.user.user_permissions.get('can_manage_leaves', False):
        messages.error(request, "You don't have permission to export leave records.")
        return redirect('hr_modules:leave_list')
    
    # Get filter parameters
    year = request.GET.get('year', str(timezone.now().year))
    department_id = request.GET.get('department', '')
    leave_type_id = request.GET.get('leave_type', '')
    status = request.GET.get('status', '')
    
    # Base queryset
    leaves = LeaveRequest.objects.filter(
        start_date__year=year
    ).select_related(
        'employee', 'employee__user', 'employee__current_department', 
        'leave_type', 'approved_by'
    ).order_by('start_date')
    
    # Apply filters
    if department_id:
        leaves = leaves.filter(employee__current_department_id=department_id)
    
    if leave_type_id:
        leaves = leaves.filter(leave_type_id=leave_type_id)
    
    if status:
        leaves = leaves.filter(status=status)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leave_records_{year}.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    writer.writerow(['Employee', 'File Number', 'Department', 'Leave Type', 'Start Date', 'End Date', 
                    'Days', 'Status', 'Approved By', 'Approval Date', 'Reason'])
    
    # Add leave data
    for leave in leaves:
        writer.writerow([
            leave.employee.user.get_full_name(),
            leave.employee.file_number,
            leave.employee.current_department.name if leave.employee.current_department else '',
            leave.leave_type.name,
            leave.start_date,
            leave.end_date,
            leave.days_requested,
            leave.get_status_display(),
            leave.approved_by.get_full_name() if leave.approved_by else '',
            leave.approved_date if leave.approved_date else '',
            leave.reason
        ])
    
    return response


@login_required
def leave_summary_report(request):
    """Generate leave summary report"""
    # Check if user can view reports
    if not request.user.user_permissions.get('can_view_reports', False) and not request.user.user_permissions.get('can_manage_leaves', False):
        messages.error(request, "You don't have permission to view summary reports.")
        return redirect('hr_modules:leave_list')
    
    # Get filter parameters
    year = request.GET.get('year', str(timezone.now().year))
    department_id = request.GET.get('department', '')
    
    # Get leave types
    leave_types = LeaveType.objects.all()
    
    # Base queryset for approved leave requests
    approved_leaves = LeaveRequest.objects.filter(
        status='APPROVED',
        start_date__year=year
    ).select_related(
        'employee', 'employee__current_department', 'leave_type'
    )
    
    # Apply department filter
    if department_id:
        approved_leaves = approved_leaves.filter(employee__current_department_id=department_id)
    
    # Group by department and leave type
    department_summaries = {}
    
    # Get all departments first
    departments = Department.objects.all()
    for department in departments:
        department_summaries[department.id] = {
            'department': department,
            'leave_types': {lt.id: 0 for lt in leave_types},
            'total': 0
        }
    
    # Add department with no defined ID for employees without department
    department_summaries[0] = {
        'department': {'name': 'No Department'},
        'leave_types': {lt.id: 0 for lt in leave_types},
        'total': 0
    }
    
    # Aggregate leave data
    for leave in approved_leaves:
        dept_id = leave.employee.current_department_id if leave.employee.current_department_id else 0
        
        if dept_id not in department_summaries:
            # Should not happen with our initialization, but just in case
            department_summaries[dept_id] = {
                'department': leave.employee.current_department if leave.employee.current_department else {'name': 'No Department'},
                'leave_types': {lt.id: 0 for lt in leave_types},
                'total': 0
            }
        
        department_summaries[dept_id]['leave_types'][leave.leave_type_id] += leave.days_requested
        department_summaries[dept_id]['total'] += leave.days_requested
    
    # Get grand totals
    grand_totals = {lt.id: 0 for lt in leave_types}
    total_days = 0
    
    for dept_summary in department_summaries.values():
        for leave_type_id, days in dept_summary['leave_types'].items():
            grand_totals[leave_type_id] += days
            total_days += days
    
    # Get departments for filter
    departments = Department.objects.all()
    
    # Get years for filter
    current_year = timezone.now().year
    years = range(current_year - 2, current_year + 3)
    
    context = {
        'department_summaries': [ds for ds in department_summaries.values() if ds['total'] > 0],
        'leave_types': leave_types,
        'grand_totals': grand_totals,
        'total_days': total_days,
        'departments': departments,
        'years': years,
        'selected_year': year,
        'selected_department': department_id,
    }
    
    return render(request, 'hr_modules/leave/leave_summary_report.html', context)



@login_required
def leave_approve(request, pk):
    """Approve a leave request"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Check if user can approve leaves
    if not request.user.user_permissions.get('can_approve_leaves', False):
        messages.error(request, "You don't have permission to approve leave requests.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    # Check if leave request is pending
    if leave_request.status != 'PENDING':
        messages.error(request, "Only pending leave requests can be approved.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    if request.method == 'POST':
        # Update leave request
        leave_request.status = 'APPROVED'
        leave_request.approved_by = request.user
        leave_request.approved_date = timezone.now().date()
        leave_request.save()
        
        # Update leave balance
        try:
            leave_balance = LeaveBalance.objects.get(
                employee=leave_request.employee,
                leave_type=leave_request.leave_type,
                year=timezone.now().year
            )
            
            leave_balance.used_days += leave_request.days_requested
            leave_balance.save()
            
        except LeaveBalance.DoesNotExist:
            # If no balance exists, create one with negative balance
            LeaveBalance.objects.create(
                employee=leave_request.employee,
                leave_type=leave_request.leave_type,
                year=timezone.now().year,
                initial_balance=leave_request.days_requested,
                used_days=leave_request.days_requested
            )
        
        # Create notification task for employee
        Task.objects.create(
            title="Leave Request Approved",
            description=f"Your leave request for {leave_request.days_requested} days from {leave_request.start_date} to {leave_request.end_date} has been approved.",
            status=TaskStatus.objects.get(name='Completed'),
            assigned_to=leave_request.employee,
            creator=request.user,
            completed_by=request.user,
            completed_at=timezone.now()
        )
        
        messages.success(request, "Leave request approved successfully.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    context = {
        'leave_request': leave_request,
    }
    
    return render(request, 'hr_modules/leave/leave_approve.html', context)


@login_required
def leave_reject(request, pk):
    """Reject a leave request"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Check if user can approve leaves
    if not request.user.user_permissions.get('can_approve_leaves', False):
        messages.error(request, "You don't have permission to reject leave requests.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    # Check if leave request is pending
    if leave_request.status != 'PENDING':
        messages.error(request, "Only pending leave requests can be rejected.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    if request.method == 'POST':
        # Get rejection reason
        rejection_reason = request.POST.get('rejection_reason')
        
        if not rejection_reason:
            messages.error(request, "Please provide a reason for rejection.")
            return redirect('hr_modules:leave_reject', pk=leave_request.pk)
        
        # Update leave request
        leave_request.status = 'REJECTED'
        leave_request.rejection_reason = rejection_reason
        leave_request.approved_by = request.user  # Record who rejected it
        leave_request.approved_date = timezone.now().date()
        leave_request.save()
        
        # Create notification task for employee
        Task.objects.create(
            title="Leave Request Rejected",
            description=f"Your leave request for {leave_request.days_requested} days from {leave_request.start_date} to {leave_request.end_date} has been rejected. Reason: {rejection_reason}",
            status=TaskStatus.objects.get(name='Completed'),
            assigned_to=leave_request.employee,
            creator=request.user,
            completed_by=request.user,
            completed_at=timezone.now()
        )
        
        messages.success(request, "Leave request rejected successfully.")
        return redirect('hr_modules:leave_detail', pk=leave_request.pk)
    
    context = {
        'leave_request': leave_request,
    }
    
    return render(request, 'hr_modules/leave/leave_reject.html', context)