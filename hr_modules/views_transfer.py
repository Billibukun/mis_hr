from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.http import HttpResponse, JsonResponse

from .models import TransferRequest
from core.models import EmployeeProfile, Department, Unit, Zone, State
from task_management.models import Task, TaskStatus

from datetime import timedelta
import csv


@login_required
def transfer_list(request):
    """List all transfer requests with filters"""
    # Get filter parameters
    status = request.GET.get('status', '')
    request_type = request.GET.get('request_type', '')
    department_id = request.GET.get('department', '')
    search = request.GET.get('search', '')
    
    employee_profile = request.user.employee_profile
    
    # Check if user can manage transfers
    can_manage = request.user.user_permissions.get('can_manage_transfers', False)
    
    # Base queryset - if can manage, show all transfers, otherwise show only user's transfers
    if can_manage:
        transfers = TransferRequest.objects.all().select_related(
            'employee', 'employee__user',
            'current_department', 'requested_department',
            'current_zone', 'requested_zone',
            'current_state', 'requested_state',
            'approved_by'
        )
    else:
        transfers = TransferRequest.objects.filter(
            employee=employee_profile
        ).select_related(
            'employee', 'employee__user',
            'current_department', 'requested_department',
            'current_zone', 'requested_zone',
            'current_state', 'requested_state',
            'approved_by'
        )
    
    # Order by recency
    transfers = transfers.order_by('-created_at')
    
    # Apply filters
    if status:
        transfers = transfers.filter(status=status)
    
    if request_type:
        transfers = transfers.filter(request_type=request_type)
    
    if department_id:
        transfers = transfers.filter(
            Q(current_department_id=department_id) |
            Q(requested_department_id=department_id)
        )
    
    if search:
        if can_manage:
            transfers = transfers.filter(
                Q(employee__user__first_name__icontains=search) |
                Q(employee__user__last_name__icontains=search) |
                Q(employee__file_number__icontains=search) |
                Q(reason__icontains=search)
            )
        else:
            transfers = transfers.filter(reason__icontains=search)
    
    # Get pending approvals if user can approve
    can_approve = request.user.user_permissions.get('can_approve_transfers', False)
    if can_approve:
        # Department heads can only approve transfers in their department
        if request.user.user_permissions.get('is_department_head', False) and employee_profile.current_department:
            pending_approvals = TransferRequest.objects.filter(
                status='UNDER_REVIEW',
                current_department=employee_profile.current_department
            ).select_related('employee', 'employee__user')
        else:
            pending_approvals = TransferRequest.objects.filter(
                status='UNDER_REVIEW'
            ).select_related('employee', 'employee__user')
    else:
        pending_approvals = None
    
    # Get departments for filter
    departments = Department.objects.all()
    
    context = {
        'transfers': transfers,
        'pending_approvals': pending_approvals,
        'can_manage': can_manage,
        'can_approve': can_approve,
        'departments': departments,
        'filter_status': status,
        'filter_request_type': request_type,
        'filter_department': department_id,
        'search': search,
    }
    
    return render(request, 'hr_modules/transfer/transfer_list.html', context)


@login_required
def transfer_detail(request, pk):
    """View transfer request details"""
    transfer_request = get_object_or_404(TransferRequest, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if user is authorized to view this transfer
    is_owner = transfer_request.employee == employee_profile
    can_manage = request.user.user_permissions.get('can_manage_transfers', False)
    can_approve = request.user.user_permissions.get('can_approve_transfers', False)
    
    if not (is_owner or can_manage or can_approve):
        messages.error(request, "You don't have permission to view this transfer request.")
        return redirect('hr_modules:transfer_list')
    
    # Check if user is authorized to approve this transfer
    can_approve_this = False
    if can_approve:
        if request.user.user_permissions.get('is_department_head', False):
            # Department heads can only approve transfers from their department
            user_department = employee_profile.current_department
            request_department = transfer_request.current_department
            can_approve_this = user_department == request_department
        else:
            can_approve_this = True
    
    context = {
        'transfer_request': transfer_request,
        'is_owner': is_owner,
        'can_manage': can_manage,
        'can_approve_this': can_approve_this,
    }
    
    return render(request, 'hr_modules/transfer/transfer_detail.html', context)


@login_required
def transfer_create(request):
    """Create a new transfer request"""
    employee_profile = request.user.employee_profile
    
    if request.method == 'POST':
        # Process form data
        request_type = request.POST.get('request_type')
        requested_department_id = request.POST.get('requested_department')
        requested_unit_id = request.POST.get('requested_unit')
        requested_zone_id = request.POST.get('requested_zone')
        requested_state_id = request.POST.get('requested_state')
        reason = request.POST.get('reason')
        
        # Validate form data
        if not all([request_type, requested_department_id, reason]):
            messages.error(request, "Please fill all required fields.")
            return redirect('hr_modules:transfer_create')
        
        # Check current placements
        if not employee_profile.current_department:
            messages.error(request, "Your current department information is not set. Please contact HR.")
            return redirect('hr_modules:transfer_list')
        
        # Create transfer request
        transfer_request = TransferRequest.objects.create(
            employee=employee_profile,
            request_type=request_type,
            current_department=employee_profile.current_department,
            current_unit=employee_profile.current_unit,
            current_zone=employee_profile.current_zone,
            current_state=employee_profile.current_state,
            requested_department_id=requested_department_id,
            requested_unit_id=requested_unit_id or None,
            requested_zone_id=requested_zone_id or None,
            requested_state_id=requested_state_id or None,
            reason=reason,
            status='DRAFT',
            requested_by=request.user
        )
        
        # Check if submitting immediately
        if 'submit' in request.POST:
            transfer_request.status = 'SUBMITTED'
            transfer_request.save()
            
            # Create task for department head
            if employee_profile.current_department:
                department_heads = EmployeeProfile.objects.filter(
                    current_department=employee_profile.current_department,
                    current_employee_type='HOD'
                )
                
                for head in department_heads:
                    Task.objects.create(
                        title=f"Transfer Request: {employee_profile.user.get_full_name()}",
                        description=f"New transfer request from {employee_profile.user.get_full_name()} ({employee_profile.file_number}) to {transfer_request.requested_department.name}.",
                        status=TaskStatus.objects.get(name='Pending'),
                        assigned_to=head,
                        creator=request.user,
                        due_date=timezone.now() + timedelta(days=5)
                    )
            
            messages.success(request, "Transfer request submitted successfully.")
        else:
            messages.success(request, "Transfer request saved as draft.")
        
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Get departments, zones, and states for the form
    departments = Department.objects.all()
    zones = Zone.objects.all()
    states = State.objects.all()
    
    context = {
        'departments': departments,
        'zones': zones,
        'states': states,
        'employee': employee_profile,
    }
    
    return render(request, 'hr_modules/transfer/transfer_form.html', context)


@login_required
def transfer_edit(request, pk):
    """Edit a transfer request"""
    transfer_request = get_object_or_404(TransferRequest, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if user is authorized to edit this transfer
    if transfer_request.employee != employee_profile:
        messages.error(request, "You can only edit your own transfer requests.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Check if transfer request can be edited (must be in DRAFT status)
    if transfer_request.status != 'DRAFT':
        messages.error(request, "Only draft transfer requests can be edited.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    if request.method == 'POST':
        # Process form data
        transfer_request.request_type = request.POST.get('request_type')
        transfer_request.requested_department_id = request.POST.get('requested_department')
        transfer_request.requested_unit_id = request.POST.get('requested_unit') or None
        transfer_request.requested_zone_id = request.POST.get('requested_zone') or None
        transfer_request.requested_state_id = request.POST.get('requested_state') or None
        transfer_request.reason = request.POST.get('reason')
        
        transfer_request.save()
        
        # Check if submitting
        if 'submit' in request.POST:
            transfer_request.status = 'SUBMITTED'
            transfer_request.save()
            
            # Create task for department head
            if employee_profile.current_department:
                department_heads = EmployeeProfile.objects.filter(
                    current_department=employee_profile.current_department,
                    current_employee_type='HOD'
                )
                
                for head in department_heads:
                    Task.objects.create(
                        title=f"Transfer Request: {employee_profile.user.get_full_name()}",
                        description=f"New transfer request from {employee_profile.user.get_full_name()} ({employee_profile.file_number}) to {transfer_request.requested_department.name}.",
                        status=TaskStatus.objects.get(name='Pending'),
                        assigned_to=head,
                        creator=request.user,
                        due_date=timezone.now() + timedelta(days=5)
                    )
            
            messages.success(request, "Transfer request submitted successfully.")
        else:
            messages.success(request, "Transfer request updated successfully.")
        
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Get departments, zones, and states for the form
    departments = Department.objects.all()
    zones = Zone.objects.all()
    states = State.objects.all()
    
    # Get units for the selected department
    if transfer_request.requested_department:
        units = Unit.objects.filter(department=transfer_request.requested_department)
    else:
        units = []
    
    context = {
        'transfer_request': transfer_request,
        'departments': departments,
        'zones': zones,
        'states': states,
        'units': units,
        'employee': employee_profile,
    }
    
    return render(request, 'hr_modules/transfer/transfer_form.html', context)


@login_required
def transfer_submit(request, pk):
    """Submit a draft transfer request"""
    transfer_request = get_object_or_404(TransferRequest, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if user is authorized to submit this transfer
    if transfer_request.employee != employee_profile:
        messages.error(request, "You can only submit your own transfer requests.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Check if transfer request can be submitted (must be in DRAFT status)
    if transfer_request.status != 'DRAFT':
        messages.error(request, "Only draft transfer requests can be submitted.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Submit the transfer request
    transfer_request.status = 'SUBMITTED'
    transfer_request.save()
    
    # Create task for department head
    if employee_profile.current_department:
        department_heads = EmployeeProfile.objects.filter(
            current_department=employee_profile.current_department,
            current_employee_type='HOD'
        )
        
        for head in department_heads:
            Task.objects.create(
                title=f"Transfer Request: {employee_profile.user.get_full_name()}",
                description=f"New transfer request from {employee_profile.user.get_full_name()} ({employee_profile.file_number}) to {transfer_request.requested_department.name}.",
                status=TaskStatus.objects.get(name='Pending'),
                assigned_to=head,
                creator=request.user,
                due_date=timezone.now() + timedelta(days=5)
            )
    
    messages.success(request, "Transfer request submitted successfully.")
    return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)


@login_required
def transfer_cancel(request, pk):
    """Cancel a transfer request"""
    transfer_request = get_object_or_404(TransferRequest, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if user is authorized to cancel this transfer
    is_owner = transfer_request.employee == employee_profile
    can_manage = request.user.user_permissions.get('can_manage_transfers', False)
    
    if not (is_owner or can_manage):
        messages.error(request, "You don't have permission to cancel this transfer request.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Check if transfer request can be cancelled (must not be COMPLETED or CANCELLED)
    if transfer_request.status in ['COMPLETED', 'CANCELLED']:
        messages.error(request, "This transfer request cannot be cancelled.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    if request.method == 'POST':
        # Cancel the transfer request
        transfer_request.status = 'CANCELLED'
        transfer_request.save()
        
        messages.success(request, "Transfer request cancelled successfully.")
        return redirect('hr_modules:transfer_list')
    
    context = {
        'transfer_request': transfer_request,
    }
    
    return render(request, 'hr_modules/transfer/transfer_cancel.html', context)


@login_required
def transfer_review(request, pk):
    """Review a transfer request (department head)"""
    transfer_request = get_object_or_404(TransferRequest, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if user can review transfers
    if not request.user.user_permissions.get('can_manage_transfers', False):
        messages.error(request, "You don't have permission to review transfer requests.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Check if user is department head of the current department
    is_dept_head = (
        request.user.user_permissions.get('is_department_head', False) and
        employee_profile.current_department == transfer_request.current_department
    )
    
    if not is_dept_head and not request.user.user_permissions.get('can_approve_transfers', False):
        messages.error(request, "You can only review transfer requests from your department.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Check if transfer request can be reviewed (must be SUBMITTED)
    if transfer_request.status != 'SUBMITTED':
        messages.error(request, "Only submitted transfer requests can be reviewed.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    if request.method == 'POST':
        # Get review action
        action = request.POST.get('action')
        comments = request.POST.get('comments', '')
        
        if action == 'approve':
            # Move to next stage
            transfer_request.status = 'UNDER_REVIEW'
            transfer_request.save()
            
            # Create task for HR department
            hr_department = Department.objects.filter(code='HR').first()
            if hr_department:
                hr_heads = EmployeeProfile.objects.filter(
                    current_department=hr_department,
                    current_employee_type='HOD'
                )
                
                for hr_head in hr_heads:
                    Task.objects.create(
                        title=f"Transfer Request for Review: {transfer_request.employee.user.get_full_name()}",
                        description=f"Transfer request from {transfer_request.employee.user.get_full_name()} ({transfer_request.employee.file_number}) to {transfer_request.requested_department.name} needs review.",
                        status=TaskStatus.objects.get(name='Pending'),
                        assigned_to=hr_head,
                        creator=request.user,
                        due_date=timezone.now() + timedelta(days=5)
                    )
            
            messages.success(request, "Transfer request approved for further review.")
        
        elif action == 'reject':
            # Reject the transfer request
            transfer_request.status = 'REJECTED'
            transfer_request.rejection_reason = comments
            transfer_request.save()
            
            # Create task notification for employee
            Task.objects.create(
                title="Transfer Request Rejected",
                description=f"Your transfer request to {transfer_request.requested_department.name} has been rejected by your department head. Reason: {comments}",
                status=TaskStatus.objects.get(name='Completed'),
                assigned_to=transfer_request.employee,
                creator=request.user,
                completed_by=request.user,
                completed_at=timezone.now()
            )
            
            messages.success(request, "Transfer request rejected successfully.")
        
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    context = {
        'transfer_request': transfer_request,
    }
    
    return render(request, 'hr_modules/transfer/transfer_review.html', context)


@login_required
def transfer_approve(request, pk):
    """Approve a transfer request (HR/management)"""
    transfer_request = get_object_or_404(TransferRequest, pk=pk)
    
    # Check if user can approve transfers
    if not request.user.user_permissions.get('can_approve_transfers', False):
        messages.error(request, "You don't have permission to approve transfer requests.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Check if transfer request can be approved (must be UNDER_REVIEW)
    if transfer_request.status != 'UNDER_REVIEW':
        messages.error(request, "Only transfer requests under review can be approved.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    if request.method == 'POST':
        # Get approval data
        effective_date = request.POST.get('effective_date')
        
        if not effective_date:
            messages.error(request, "Please provide an effective date.")
            return redirect('hr_modules:transfer_approve', pk=transfer_request.pk)
        
        # Approve the transfer request
        transfer_request.status = 'APPROVED'
        transfer_request.approved_by = request.user
        transfer_request.approved_date = timezone.now().date()
        transfer_request.effective_date = effective_date
        transfer_request.save()
        
        # Create task notification for employee
        Task.objects.create(
            title="Transfer Request Approved",
            description=f"Your transfer request to {transfer_request.requested_department.name} has been approved. Effective date: {effective_date}",
            status=TaskStatus.objects.get(name='Completed'),
            assigned_to=transfer_request.employee,
            creator=request.user,
            completed_by=request.user,
            completed_at=timezone.now()
        )
        
        messages.success(request, "Transfer request approved successfully.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    context = {
        'transfer_request': transfer_request,
    }
    
    return render(request, 'hr_modules/transfer/transfer_approve.html', context)


@login_required
def transfer_reject(request, pk):
    """Reject a transfer request (HR/management)"""
    transfer_request = get_object_or_404(TransferRequest, pk=pk)
    
    # Check if user can approve/reject transfers
    if not request.user.user_permissions.get('can_approve_transfers', False):
        messages.error(request, "You don't have permission to reject transfer requests.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Check if transfer request can be rejected (must be UNDER_REVIEW)
    if transfer_request.status != 'UNDER_REVIEW':
        messages.error(request, "Only transfer requests under review can be rejected.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    if request.method == 'POST':
        # Get rejection reason
        rejection_reason = request.POST.get('rejection_reason')
        
        if not rejection_reason:
            messages.error(request, "Please provide a reason for rejection.")
            return redirect('hr_modules:transfer_reject', pk=transfer_request.pk)
        
        # Reject the transfer request
        transfer_request.status = 'REJECTED'
        transfer_request.rejection_reason = rejection_reason
        transfer_request.approved_by = request.user  # Record who rejected it
        transfer_request.approved_date = timezone.now().date()
        transfer_request.save()
        
        # Create task notification for employee
        Task.objects.create(
            title="Transfer Request Rejected",
            description=f"Your transfer request to {transfer_request.requested_department.name} has been rejected. Reason: {rejection_reason}",
            status=TaskStatus.objects.get(name='Completed'),
            assigned_to=transfer_request.employee,
            creator=request.user,
            completed_by=request.user,
            completed_at=timezone.now()
        )
        
        messages.success(request, "Transfer request rejected successfully.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    context = {
        'transfer_request': transfer_request,
    }
    
    return render(request, 'hr_modules/transfer/transfer_reject.html', context)


@login_required
def transfer_complete(request, pk):
    """Mark a transfer as completed"""
    transfer_request = get_object_or_404(TransferRequest, pk=pk)
    
    # Check if user can manage transfers
    if not request.user.user_permissions.get('can_manage_transfers', False):
        messages.error(request, "You don't have permission to complete transfer requests.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    # Check if transfer request can be completed (must be APPROVED)
    if transfer_request.status != 'APPROVED':
        messages.error(request, "Only approved transfer requests can be completed.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    if request.method == 'POST':
        # Complete the transfer
        transfer_request.status = 'COMPLETED'
        transfer_request.completion_date = timezone.now().date()
        transfer_request.save()
        
        # Update employee's placement
        employee = transfer_request.employee
        employee.current_department = transfer_request.requested_department
        employee.current_unit = transfer_request.requested_unit
        employee.current_zone = transfer_request.requested_zone
        employee.current_state = transfer_request.requested_state
        employee.save()
        
        # Create task notification for employee
        Task.objects.create(
            title="Transfer Completed",
            description=f"Your transfer to {transfer_request.requested_department.name} has been completed.",
            status=TaskStatus.objects.get(name='Completed'),
            assigned_to=employee,
            creator=request.user,
            completed_by=request.user,
            completed_at=timezone.now()
        )
        
        messages.success(request, "Transfer completed successfully.")
        return redirect('hr_modules:transfer_detail', pk=transfer_request.pk)
    
    context = {
        'transfer_request': transfer_request,
    }
    
    return render(request, 'hr_modules/transfer/transfer_complete.html', context)


@login_required
def transfer_export(request):
    """Export transfer data to CSV"""
    # Check if user can export data
    if not request.user.user_permissions.get('can_export_data', False) and not request.user.user_permissions.get('can_manage_transfers', False):
        messages.error(request, "You don't have permission to export transfer data.")
        return redirect('hr_modules:transfer_list')
    
    # Get filter parameters
    year = request.GET.get('year', str(timezone.now().year))
    status = request.GET.get('status', '')
    department_id = request.GET.get('department', '')
    
    # Base queryset
    transfers = TransferRequest.objects.filter(
        created_at__year=year
    ).select_related(
        'employee', 'employee__user', 'employee__current_department',
        'current_department', 'requested_department',
        'current_zone', 'requested_zone',
        'current_state', 'requested_state',
        'approved_by'
    ).order_by('created_at')
    
    # Apply filters
    if status:
        transfers = transfers.filter(status=status)
    
    if department_id:
        transfers = transfers.filter(
            Q(current_department_id=department_id) |
            Q(requested_department_id=department_id)
        )
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transfer_records_{year}.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    writer.writerow(['Employee', 'File Number', 'Current Department', 'Requested Department', 
                     'Request Type', 'Status', 'Requested Date', 'Approved By', 'Effective Date',
                     'Completion Date', 'Reason'])
    
    # Add data rows
    for transfer in transfers:
        writer.writerow([
            transfer.employee.user.get_full_name(),
            transfer.employee.file_number,
            transfer.current_department.name,
            transfer.requested_department.name,
            transfer.get_request_type_display(),
            transfer.get_status_display(),
            transfer.request_date,
            transfer.approved_by.get_full_name() if transfer.approved_by else '',
            transfer.effective_date if transfer.effective_date else '',
            transfer.completion_date if transfer.completion_date else '',
            transfer.reason
        ])
    
    return response


@login_required
def transfer_summary_report(request):
    """Generate transfer summary report"""
    # Check if user can view reports
    if not request.user.user_permissions.get('can_view_reports', False) and not request.user.user_permissions.get('can_manage_transfers', False):
        messages.error(request, "You don't have permission to view summary reports.")
        return redirect('hr_modules:transfer_list')
    
    # Get filter parameters
    year = request.GET.get('year', str(timezone.now().year))
    status = request.GET.get('status', '')
    
    # Base queryset
    transfers = TransferRequest.objects.filter(
        created_at__year=year
    )
    
    # Apply status filter if provided
    if status:
        transfers = transfers.filter(status=status)
    
    # Get department data
    department_data = {}
    
    # Count transfers by source department
    from_counts = transfers.values('current_department__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for item in from_counts:
        dept_name = item['current_department__name']
        if dept_name not in department_data:
            department_data[dept_name] = {'name': dept_name, 'from_count': 0, 'to_count': 0}
        department_data[dept_name]['from_count'] = item['count']
    
    # Count transfers by destination department
    to_counts = transfers.values('requested_department__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for item in to_counts:
        dept_name = item['requested_department__name']
        if dept_name not in department_data:
            department_data[dept_name] = {'name': dept_name, 'from_count': 0, 'to_count': 0}
        department_data[dept_name]['to_count'] = item['count']
    
    # Calculate net gain/loss
    for dept in department_data.values():
        dept['net'] = dept['to_count'] - dept['from_count']
    
    # Sort by net gain/loss
    departments_sorted = sorted(department_data.values(), key=lambda x: x['net'], reverse=True)
    
    # Get status counts
    status_counts = transfers.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    status_data = {}
    for item in status_counts:
        status_code = item['status']
        status_display = dict(TransferRequest.STATUS_CHOICES).get(status_code, status_code)
        status_data[status_code] = {
            'name': status_display,
            'count': item['count']
        }
    
    # Get request type counts
    type_counts = transfers.values('request_type').annotate(
        count=Count('id')
    ).order_by('request_type')
    
    type_data = {}
    for item in type_counts:
        type_code = item['request_type']
        type_display = dict(TransferRequest.REQUEST_TYPES).get(type_code, type_code)
        type_data[type_code] = {
            'name': type_display,
            'count': item['count']
        }
    
    # Get years for filter
    current_year = timezone.now().year
    years = range(current_year - 2, current_year + 1)
    
    context = {
        'departments': departments_sorted,
        'status_data': status_data.values(),
        'type_data': type_data.values(),
        'total_transfers': transfers.count(),
        'years': years,
        'selected_year': year,
        'selected_status': status,
    }
    
    return render(request, 'hr_modules/transfer/transfer_summary_report.html', context)


@login_required
def get_units_for_department(request):
    """AJAX endpoint to get units for a department"""
    department_id = request.GET.get('department_id')
    
    if not department_id:
        return JsonResponse({'units': []})
    
    units = Unit.objects.filter(department_id=department_id).values('id', 'name')
    
    return JsonResponse({'units': list(units)})