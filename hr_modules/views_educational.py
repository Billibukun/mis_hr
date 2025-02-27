from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.http import HttpResponse

from .models import EducationalUpgrade
from core.models import EmployeeProfile, Department
from task_management.models import Task, TaskStatus

from datetime import timedelta
import csv


@login_required
def educational_upgrade_list(request):
    """List all educational upgrade requests with filters"""
    # Get filter parameters
    status = request.GET.get('status', '')
    qualification_type = request.GET.get('qualification_type', '')
    year = request.GET.get('year', '')
    search = request.GET.get('search', '')
    
    employee_profile = request.user.employee_profile
    
    # Check if user can manage educational upgrades
    can_manage = request.user.user_permissions.get('can_manage_educational_upgrades', False)
    
    # Base queryset - if can manage, show all upgrades, otherwise show only user's upgrades
    if can_manage:
        upgrades = EducationalUpgrade.objects.all().select_related(
            'employee', 'employee__user', 'reviewed_by', 'approved_by'
        )
    else:
        upgrades = EducationalUpgrade.objects.filter(
            employee=employee_profile
        ).select_related(
            'employee', 'employee__user', 'reviewed_by', 'approved_by'
        )
    
    # Order by recency
    upgrades = upgrades.order_by('-submission_date')
    
    # Apply filters
    if status:
        upgrades = upgrades.filter(status=status)
    
    if qualification_type:
        upgrades = upgrades.filter(qualification_type=qualification_type)
    
    if year:
        upgrades = upgrades.filter(year_of_graduation=year)
    
    if search:
        if can_manage:
            upgrades = upgrades.filter(
                Q(employee__user__first_name__icontains=search) |
                Q(employee__user__last_name__icontains=search) |
                Q(employee__file_number__icontains=search) |
                Q(course_of_study__icontains=search) |
                Q(institution__icontains=search)
            )
        else:
            upgrades = upgrades.filter(
                Q(course_of_study__icontains=search) |
                Q(institution__icontains=search)
            )
    
    # Get pending reviews if user can review/approve
    can_review = request.user.user_permissions.get('can_manage_educational_upgrades', False)
    can_approve = request.user.user_permissions.get('can_approve_educational_upgrades', False)
    
    if can_review:
        pending_reviews = EducationalUpgrade.objects.filter(
            status='SUBMITTED'
        ).select_related('employee', 'employee__user')
    else:
        pending_reviews = None
    
    if can_approve:
        pending_approvals = EducationalUpgrade.objects.filter(
            status='UNDER_REVIEW'
        ).select_related('employee', 'employee__user')
    else:
        pending_approvals = None
    
    # Get qualification types for filter
    qualification_types = EducationalUpgrade.qualification_type.field.choices
    
    # Get years for filter (from 20 years ago to current year)
    current_year = timezone.now().year
    years = range(current_year - 20, current_year + 1)
    
    context = {
        'upgrades': upgrades,
        'pending_reviews': pending_reviews,
        'pending_approvals': pending_approvals,
        'can_manage': can_manage,
        'can_review': can_review,
        'can_approve': can_approve,
        'qualification_types': qualification_types,
        'years': years,
        'filter_status': status,
        'filter_qualification_type': qualification_type,
        'filter_year': year,
        'search': search,
    }
    
    return render(request, 'hr_modules/educational/educational_upgrade_list.html', context)


@login_required
def educational_upgrade_detail(request, pk):
    """View educational upgrade details"""
    upgrade = get_object_or_404(EducationalUpgrade, pk=pk)
    employee_profile = request.user.employee_profile
    
    # Check if user is authorized to view this upgrade
    is_owner = upgrade.employee == employee_profile
    can_manage = request.user.user_permissions.get('can_manage_educational_upgrades', False)
    can_approve = request.user.user_permissions.get('can_approve_educational_upgrades', False)
    
    if not (is_owner or can_manage or can_approve):
        messages.error(request, "You don't have permission to view this educational upgrade.")
        return redirect('hr_modules:educational_upgrade_list')
    
    context = {
        'upgrade': upgrade,
        'is_owner': is_owner,
        'can_manage': can_manage,
        'can_approve': can_approve,
    }
    
    return render(request, 'hr_modules/educational/educational_upgrade_detail.html', context)


@login_required
def educational_upgrade_create(request):
    """Create a new educational upgrade request"""
    employee_profile = request.user.employee_profile
    
    if request.method == 'POST':
        # Process form data
        qualification_type = request.POST.get('qualification_type')
        course_of_study = request.POST.get('course_of_study')
        institution = request.POST.get('institution')
        year_of_graduation = request.POST.get('year_of_graduation')
        certificate_reference = request.POST.get('certificate_reference')
        
        # Validate form data
        if not all([qualification_type, course_of_study, institution, year_of_graduation, certificate_reference]):
            messages.error(request, "Please fill all required fields.")
            return redirect('hr_modules:educational_upgrade_create')
        
        # Create educational upgrade request
        upgrade = EducationalUpgrade.objects.create(
            employee=employee_profile,
            qualification_type=qualification_type,
            course_of_study=course_of_study,
            institution=institution,
            year_of_graduation=year_of_graduation,
            certificate_reference=certificate_reference,
            status='SUBMITTED'
        )
        
        # Create task for HR
        hr_department = Department.objects.filter(code='HR').first()
        if hr_department:
            hr_officers = EmployeeProfile.objects.filter(
                current_department=hr_department,
                current_employee_type__in=['HOD', 'STAFF']
            )
            
            for officer in hr_officers[:2]:  # Limit to 2 notifications
                Task.objects.create(
                    title=f"Educational Upgrade Review: {employee_profile.user.get_full_name()}",
                    description=f"New educational upgrade request from {employee_profile.user.get_full_name()} ({employee_profile.file_number}) for {upgrade.get_qualification_type_display()} in {upgrade.course_of_study} from {upgrade.institution}.",
                    status=TaskStatus.objects.get(name='Pending'),
                    assigned_to=officer,
                    creator=request.user,
                    due_date=timezone.now() + timedelta(days=7)
                )
        
        messages.success(request, "Educational upgrade request submitted successfully.")
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    # Get qualification types for the form
    qualification_types = EducationalUpgrade.qualification_type.field.choices
    
    # Get years for the form (from 20 years ago to current year)
    current_year = timezone.now().year
    years = range(current_year - 20, current_year + 1)
    
    context = {
        'qualification_types': qualification_types,
        'years': years,
        'current_year': current_year,
    }
    
    return render(request, 'hr_modules/educational/educational_upgrade_form.html', context)


@login_required
def educational_upgrade_review(request, pk):
    """Review an educational upgrade request"""
    upgrade = get_object_or_404(EducationalUpgrade, pk=pk)
    
    # Check if user can review educational upgrades
    if not request.user.user_permissions.get('can_manage_educational_upgrades', False):
        messages.error(request, "You don't have permission to review educational upgrade requests.")
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    # Check if upgrade can be reviewed (must be SUBMITTED)
    if upgrade.status != 'SUBMITTED':
        messages.error(request, "Only submitted educational upgrades can be reviewed.")
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    if request.method == 'POST':
        # Get review data
        action = request.POST.get('action')
        comments = request.POST.get('comments', '')
        
        # Update upgrade
        upgrade.review_comments = comments
        upgrade.reviewed_by = request.user
        upgrade.review_date = timezone.now().date()
        
        if action == 'approve':
            upgrade.status = 'UNDER_REVIEW'
            
            # Create task for approvers
            approvers = EmployeeProfile.objects.filter(
                user__user_permissions__can_approve_educational_upgrades=True
            )
            
            for approver in approvers[:2]:  # Limit to 2 notifications
                Task.objects.create(
                    title=f"Educational Upgrade Approval: {upgrade.employee.user.get_full_name()}",
                    description=f"Educational upgrade request from {upgrade.employee.user.get_full_name()} for {upgrade.get_qualification_type_display()} in {upgrade.course_of_study} needs approval.",
                    status=TaskStatus.objects.get(name='Pending'),
                    assigned_to=approver,
                    creator=request.user,
                    due_date=timezone.now() + timedelta(days=5)
                )
            
            messages.success(request, "Educational upgrade request forwarded for approval.")
        else:
            upgrade.status = 'REJECTED'
            
            # Create task notification for employee
            Task.objects.create(
                title="Educational Upgrade Request Rejected",
                description=f"Your educational upgrade request for {upgrade.get_qualification_type_display()} in {upgrade.course_of_study} has been rejected during review. Comments: {comments}",
                status=TaskStatus.objects.get(name='Completed'),
                assigned_to=upgrade.employee,
                creator=request.user,
                completed_by=request.user,
                completed_at=timezone.now()
            )
            
            messages.success(request, "Educational upgrade request rejected.")
        
        upgrade.save()
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    context = {
        'upgrade': upgrade,
    }
    
    return render(request, 'hr_modules/educational/educational_upgrade_review.html', context)


@login_required
def educational_upgrade_approve(request, pk):
    """Approve an educational upgrade request"""
    upgrade = get_object_or_404(EducationalUpgrade, pk=pk)
    
    # Check if user can approve educational upgrades
    if not request.user.user_permissions.get('can_approve_educational_upgrades', False):
        messages.error(request, "You don't have permission to approve educational upgrade requests.")
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    # Check if upgrade can be approved (must be UNDER_REVIEW)
    if upgrade.status != 'UNDER_REVIEW':
        messages.error(request, "Only reviewed educational upgrades can be approved.")
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    if request.method == 'POST':
        # Get approval data
        effective_date = request.POST.get('effective_date')
        
        if not effective_date:
            messages.error(request, "Please provide an effective date.")
            return redirect('hr_modules:educational_upgrade_approve', pk=upgrade.pk)
        
        # Approve the upgrade
        upgrade.status = 'APPROVED'
        upgrade.approved_by = request.user
        upgrade.approval_date = timezone.now().date()
        upgrade.effective_date = effective_date
        upgrade.save()
        
        # Create task notification for employee
        Task.objects.create(
            title="Educational Upgrade Approved",
            description=f"Your educational upgrade request for {upgrade.get_qualification_type_display()} in {upgrade.course_of_study} has been approved. Effective date: {effective_date}",
            status=TaskStatus.objects.get(name='Completed'),
            assigned_to=upgrade.employee,
            creator=request.user,
            completed_by=request.user,
            completed_at=timezone.now()
        )
        
        messages.success(request, "Educational upgrade request approved successfully.")
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    context = {
        'upgrade': upgrade,
    }
    
    return render(request, 'hr_modules/educational/educational_upgrade_approve.html', context)


@login_required
def educational_upgrade_complete(request, pk):
    """Mark an educational upgrade as completed"""
    upgrade = get_object_or_404(EducationalUpgrade, pk=pk)
    
    # Check if user can manage educational upgrades
    if not request.user.user_permissions.get('can_manage_educational_upgrades', False):
        messages.error(request, "You don't have permission to complete educational upgrade requests.")
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    # Check if upgrade can be completed (must be APPROVED)
    if upgrade.status != 'APPROVED':
        messages.error(request, "Only approved educational upgrades can be completed.")
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    if request.method == 'POST':
        # Complete the upgrade
        upgrade.status = 'COMPLETED'
        upgrade.save()
        
        # Add educational qualification to employee profile
        from core.models import EducationalQualification
        
        qualification = EducationalQualification.objects.create(
            employee_profile=upgrade.employee,
            qualification_type=upgrade.qualification_type,
            course_of_study=upgrade.course_of_study,
            area_of_study='',  # Not provided in upgrade request
            institution=upgrade.institution,
            year_of_graduation=upgrade.year_of_graduation,
            created_by=request.user
        )
        
        # Create task notification for employee
        Task.objects.create(
            title="Educational Upgrade Completed",
            description=f"Your educational upgrade for {upgrade.get_qualification_type_display()} in {upgrade.course_of_study} has been processed and added to your profile.",
            status=TaskStatus.objects.get(name='Completed'),
            assigned_to=upgrade.employee,
            creator=request.user,
            completed_by=request.user,
            completed_at=timezone.now()
        )
        
        messages.success(request, "Educational upgrade completed and added to employee profile.")
        return redirect('hr_modules:educational_upgrade_detail', pk=upgrade.pk)
    
    context = {
        'upgrade': upgrade,
    }
    
    return render(request, 'hr_modules/educational/educational_upgrade_complete.html', context)


@login_required
def educational_upgrade_export(request):
    """Export educational upgrade data to CSV"""
    # Check if user can export data
    if not request.user.user_permissions.get('can_export_data', False) and not request.user.user_permissions.get('can_manage_educational_upgrades', False):
        messages.error(request, "You don't have permission to export educational upgrade data.")
        return redirect('hr_modules:educational_upgrade_list')
    
    # Get filter parameters
    year = request.GET.get('year', '')
    status = request.GET.get('status', '')
    qualification_type = request.GET.get('qualification_type', '')
    
    # Base queryset
    upgrades = EducationalUpgrade.objects.all().select_related(
        'employee', 'employee__user', 'employee__current_department',
        'reviewed_by', 'approved_by'
    ).order_by('-submission_date')
    
    # Apply filters
    if year:
        upgrades = upgrades.filter(year_of_graduation=year)
    
    if status:
        upgrades = upgrades.filter(status=status)
    
    if qualification_type:
        upgrades = upgrades.filter(qualification_type=qualification_type)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = f"educational_upgrades_{timezone.now().strftime('%Y%m%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create CSV writer
    writer = csv.writer(response)
    writer.writerow(['Employee', 'File Number', 'Department', 'Qualification Type', 
                     'Course', 'Institution', 'Year', 'Status', 'Submission Date',
                     'Reviewer', 'Review Date', 'Approver', 'Approval Date', 'Effective Date'])
    
    # Add data rows
    for upgrade in upgrades:
        writer.writerow([
            upgrade.employee.user.get_full_name(),
            upgrade.employee.file_number,
            upgrade.employee.current_department.name if upgrade.employee.current_department else '',
            upgrade.get_qualification_type_display(),
            upgrade.course_of_study,
            upgrade.institution,
            upgrade.year_of_graduation,
            upgrade.get_status_display(),
            upgrade.submission_date,
            upgrade.reviewed_by.get_full_name() if upgrade.reviewed_by else '',
            upgrade.review_date if upgrade.review_date else '',
            upgrade.approved_by.get_full_name() if upgrade.approved_by else '',
            upgrade.approval_date if upgrade.approval_date else '',
            upgrade.effective_date if upgrade.effective_date else ''
        ])
    
    return response


@login_required
def educational_upgrade_summary_report(request):
    """Generate educational upgrade summary report"""
    # Check if user can view reports
    if not request.user.user_permissions.get('can_view_reports', False) and not request.user.user_permissions.get('can_manage_educational_upgrades', False):
        messages.error(request, "You don't have permission to view summary reports.")
        return redirect('hr_modules:educational_upgrade_list')
    
    # Get filter parameters
    year_from = request.GET.get('year_from', str(timezone.now().year - 5))
    year_to = request.GET.get('year_to', str(timezone.now().year))
    
    # Base queryset
    upgrades = EducationalUpgrade.objects.filter(
        year_of_graduation__gte=year_from,
        year_of_graduation__lte=year_to
    )
    
    # Get qualification type counts
    qual_counts = upgrades.values('qualification_type').annotate(
        count=Count('id')
    ).order_by('qualification_type')
    
    qualification_data = []
    qualification_choices = dict(EducationalUpgrade.qualification_type.field.choices)
    
    for item in qual_counts:
        qual_type = item['qualification_type']
        qualification_data.append({
            'code': qual_type,
            'name': qualification_choices.get(qual_type, qual_type),
            'count': item['count']
        })
    
    # Get status counts
    status_counts = upgrades.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    status_data = []
    status_choices = dict(EducationalUpgrade.status.field.choices)
    
    for item in status_counts:
        status_code = item['status']
        status_data.append({
            'code': status_code,
            'name': status_choices.get(status_code, status_code),
            'count': item['count']
        })
    
    # Get yearly trends
    year_counts = upgrades.values('year_of_graduation').annotate(
        count=Count('id')
    ).order_by('year_of_graduation')
    
    year_data = {}
    for item in year_counts:
        year_data[item['year_of_graduation']] = item['count']
    
    # Fill in missing years
    year_range = range(int(year_from), int(year_to) + 1)
    year_series = []
    
    for year in year_range:
        year_series.append({
            'year': year,
            'count': year_data.get(year, 0)
        })
    
    # Get years for filter
    available_years = range(timezone.now().year - 20, timezone.now().year + 1)
    
    context = {
        'qualification_data': qualification_data,
        'status_data': status_data,
        'year_series': year_series,
        'total_upgrades': upgrades.count(),
        'available_years': available_years,
        'year_from': year_from,
        'year_to': year_to,
    }
    
    return render(request, 'hr_modules/educational/educational_upgrade_summary.html', context)