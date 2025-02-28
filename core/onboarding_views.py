from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.utils.crypto import get_random_string
import csv
import io
from datetime import date

from .models import EmployeeProfile, Department, Unit, State, LGA
from .forms import ProfileCompleteForm, StaffOnboardingForm, EmployeeVerificationForm
from .verification_model import EmployeeVerification, AutomatedCheck, VerificationLog


def is_hr_admin(user):
    """Check if user is HR admin"""
    if not user.is_authenticated:
        return False
    
    # Check if user has admin permissions or HR role
    if user.is_staff or user.is_superuser:
        return True
    
    # Check employee type for HR roles
    if hasattr(user, 'employee_profile'):
        employee_type = user.employee_profile.current_employee_type
        if employee_type in ['HOD', 'HOU'] and user.employee_profile.current_department.code == 'HR':
            return True
    
    return False


@login_required
def profile_complete(request):
    """View for employees to complete their profile"""
    user = request.user
    
    # Check if profile is already completed
    if hasattr(user, 'employee_profile') and user.employee_profile.is_profile_completed:
        messages.info(request, "Your profile is already completed.")
        return redirect('dashboard')
    
    # Get the existing employee profile
    try:
        profile = user.employee_profile
    except EmployeeProfile.DoesNotExist:
        # This should not happen since the post_save signal should create a profile
        # But just in case, create one now
        profile = EmployeeProfile.objects.create(user=user)
    
    if request.method == 'POST':
        # Pass the existing profile instance to the form
        form = ProfileCompleteForm(request.POST, request.FILES, user=user, instance=profile)
        if form.is_valid():
            # Save profile data
            profile = form.save(commit=False)
            profile.is_profile_completed = True
            profile.save()
            
            # Create verification record if it doesn't exist
            verification, created = EmployeeVerification.objects.get_or_create(
                employee_profile=profile,
                defaults={'verification_status': 'PENDING'}
            )
            
            # Log the event
            VerificationLog.objects.create(
                verification=verification,
                action='CREATED' if created else 'UPDATED',
                performed_by=user,
                details="Employee completed profile"
            )
            
            # Run automated checks
            run_automated_checks(profile, verification)
            
            messages.success(request, "Your profile has been completed successfully. It is now pending verification by HR.")
            return redirect('dashboard')
    else:
        # Initialize form with existing profile data
        form = ProfileCompleteForm(user=user, instance=profile)
    
    return render(request, 'core/profile_complete.html', {
        'form': form,
        'user': user,
    })


@login_required
@user_passes_test(is_hr_admin)
def staff_onboarding(request):
    """View for HR to onboard new staff"""
    if request.method == 'POST':
        form = StaffOnboardingForm(request.POST)
        if form.is_valid():
            # Create user and profile
            user, profile, password = form.save()
            
            # Create verification record (automatically verified since HR created it)
            verification = EmployeeVerification.objects.create(
                employee_profile=profile,
                verification_status='VERIFIED',
                verified_by=request.user,
                verified_date=date.today(),
                verification_notes="Verified during onboarding by HR."
            )
            
            # Log the verification
            VerificationLog.objects.create(
                verification=verification,
                action='VERIFIED',
                performed_by=request.user,
                details="Verified during onboarding"
            )
            
            # Send welcome email with credentials
            send_welcome_email(user, password, request)
            
            messages.success(request, f"Employee {user.get_full_name()} has been successfully onboarded. Login credentials have been sent to their email.")
            return redirect('staff_list')
    else:
        form = StaffOnboardingForm()
    
    return render(request, 'core/staff_onboarding.html', {
        'form': form,
    })


@login_required
@user_passes_test(is_hr_admin)
def staff_bulk_upload(request):
    """View for HR to upload multiple staff via CSV"""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, "Please upload a CSV file.")
            return redirect('staff_bulk_upload')
        
        # Check file type
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "File must be a CSV.")
            return redirect('staff_bulk_upload')
        
        # Process CSV file
        try:
            # Read CSV file
            csv_data = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(csv_data))
            
            # Track results
            success_count = 0
            error_count = 0
            errors = []
            
            for row in csv_reader:
                try:
                    # Basic validation
                    required_fields = ['username', 'first_name', 'last_name', 'email', 'file_number']
                    missing_fields = [field for field in required_fields if not row.get(field)]
                    
                    if missing_fields:
                        errors.append(f"Row {csv_reader.line_num}: Missing required fields: {', '.join(missing_fields)}")
                        error_count += 1
                        continue
                    
                    # Check for existing users/profiles
                    if User.objects.filter(username=row['username']).exists():
                        errors.append(f"Row {csv_reader.line_num}: Username '{row['username']}' already exists.")
                        error_count += 1
                        continue
                    
                    if User.objects.filter(email=row['email']).exists():
                        errors.append(f"Row {csv_reader.line_num}: Email '{row['email']}' already exists.")
                        error_count += 1
                        continue
                    
                    if EmployeeProfile.objects.filter(file_number=row['file_number']).exists():
                        errors.append(f"Row {csv_reader.line_num}: File number '{row['file_number']}' already exists.")
                        error_count += 1
                        continue
                    
                    # Create user
                    password = get_random_string(10)
                    user = User.objects.create_user(
                        username=row['username'],
                        email=row['email'],
                        password=password,
                        first_name=row['first_name'],
                        last_name=row['last_name']
                    )
                    
                    # Get employee profile (created automatically by signal)
                    try:
                        profile = user.employee_profile
                    except EmployeeProfile.DoesNotExist:
                        # If profile wasn't created by signal, create it now
                        profile = EmployeeProfile.objects.create(user=user)
                    
                    # Update profile with basic info
                    profile.file_number = row['file_number']
                    profile.ippis_number = row.get('ippis_number', '')
                    
                    # Get department if provided
                    department_code = row.get('department_code')
                    if department_code:
                        try:
                            department = Department.objects.get(code=department_code)
                            profile.current_department = department
                        except Department.DoesNotExist:
                            errors.append(f"Row {csv_reader.line_num}: Department code '{department_code}' not found.")
                    
                    # Save profile
                    profile.save()
                    
                    # Create verification record
                    verification = EmployeeVerification.objects.create(
                        employee_profile=profile,
                        verification_status='PENDING',
                        verification_notes="Bulk uploaded by HR."
                    )
                    
                    # Log the verification
                    VerificationLog.objects.create(
                        verification=verification,
                        action='CREATED',
                        performed_by=request.user,
                        details="Created through bulk upload"
                    )
                    
                    # Send welcome email with credentials
                    send_welcome_email(user, password, request)
                    
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {csv_reader.line_num}: Error - {str(e)}")
                    error_count += 1
            
            # Show results
            if success_count > 0:
                messages.success(request, f"Successfully created {success_count} employee accounts.")
            
            if error_count > 0:
                error_message = f"Encountered {error_count} errors during import:<br>"
                error_message += "<br>".join(errors[:10])
                if len(errors) > 10:
                    error_message += f"<br>...and {len(errors) - 10} more errors."
                messages.error(request, error_message)
            
            return redirect('staff_list')
            
        except Exception as e:
            messages.error(request, f"Error processing CSV file: {str(e)}")
            return redirect('staff_bulk_upload')
    
    # Show CSV template fields
    template_fields = [
        'username', 'first_name', 'last_name', 'email', 'file_number',
        'ippis_number', 'department_code'
    ]
    
    return render(request, 'core/staff_bulk_upload.html', {
        'template_fields': template_fields,
    })


@login_required
@user_passes_test(is_hr_admin)
def staff_list(request):
    """View to list all staff"""
    # Get filter parameters
    department_id = request.GET.get('department', '')
    is_verified = request.GET.get('verified', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    employees = EmployeeProfile.objects.filter(
        user__is_active=True
    ).select_related('user', 'current_department')
    
    # Apply filters
    if department_id:
        employees = employees.filter(current_department_id=department_id)
    
    if is_verified == 'yes':
        # Get verified profiles
        verified_ids = EmployeeVerification.objects.filter(
            verification_status='VERIFIED'
        ).values_list('employee_profile_id', flat=True)
        employees = employees.filter(id__in=verified_ids)
    elif is_verified == 'no':
        # Get unverified profiles
        verified_ids = EmployeeVerification.objects.filter(
            verification_status='VERIFIED'
        ).values_list('employee_profile_id', flat=True)
        employees = employees.exclude(id__in=verified_ids)
    elif is_verified == 'flagged':
        # Get flagged profiles
        flagged_ids = EmployeeVerification.objects.filter(
            verification_status='FLAGGED'
        ).values_list('employee_profile_id', flat=True)
        employees = employees.filter(id__in=flagged_ids)
    
    if search:
        employees = employees.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(file_number__icontains=search) |
            Q(ippis_number__icontains=search)
        )
    
    # Get departments for filter
    departments = Department.objects.all()
    
    # Get verification statistics
    total_count = EmployeeProfile.objects.filter(user__is_active=True).count()
    verified_count = EmployeeVerification.objects.filter(verification_status='VERIFIED').count()
    pending_count = EmployeeVerification.objects.filter(verification_status='PENDING').count()
    flagged_count = EmployeeVerification.objects.filter(verification_status='FLAGGED').count()
    
    return render(request, 'core/staff_list.html', {
        'employees': employees,
        'departments': departments,
        'filter_department': department_id,
        'filter_verified': is_verified,
        'search': search,
        'total_count': total_count,
        'verified_count': verified_count,
        'pending_count': pending_count,
        'flagged_count': flagged_count,
    })


@login_required
@user_passes_test(is_hr_admin)
def verify_employee(request, employee_id):
    """View for HR to verify an employee's profile"""
    employee = get_object_or_404(EmployeeProfile, pk=employee_id)
    
    # Get or create verification record
    verification, created = EmployeeVerification.objects.get_or_create(
        employee_profile=employee,
        defaults={
            'verification_status': 'PENDING'
        }
    )
    
    # Run automated checks if they haven't been run yet
    if created or (not verification.has_age_flag and not verification.has_education_flag and not verification.has_employment_flag):
        run_automated_checks(employee, verification)
    
    if request.method == 'POST':
        form = EmployeeVerificationForm(request.POST)
        if form.is_valid():
            is_verified = form.cleaned_data.get('is_verified')
            verification_notes = form.cleaned_data.get('verification_notes')
            flag_issues = form.cleaned_data.get('flag_issues')
            issue_description = form.cleaned_data.get('issue_description')
            
            if is_verified:
                # Mark as verified
                verification.verify(request.user, verification_notes)
                
                # Log the verification
                VerificationLog.objects.create(
                    verification=verification,
                    action='VERIFIED',
                    performed_by=request.user,
                    details=verification_notes
                )
                
                messages.success(request, f"Profile for {employee.user.get_full_name()} has been verified.")
            
            elif flag_issues:
                # Flag issues
                verification.flag_issues(
                    request.user,
                    'OTHER',  # Default category
                    issue_description
                )
                
                # Log the flagging
                VerificationLog.objects.create(
                    verification=verification,
                    action='FLAGGED',
                    performed_by=request.user,
                    details=issue_description
                )
                
                messages.warning(request, f"Issues have been flagged for {employee.user.get_full_name()}'s profile.")
            
            return redirect('staff_list')
    else:
        form = EmployeeVerificationForm()
    
    # Get verification history
    verification_logs = VerificationLog.objects.filter(
        verification=verification
    ).order_by('-timestamp')
    
    return render(request, 'core/verify_employee.html', {
        'employee': employee,
        'verification': verification,
        'form': form,
        'verification_logs': verification_logs,
    })


@login_required
@user_passes_test(is_hr_admin)
def resolve_verification_issues(request, verification_id):
    """View for HR to resolve issues with an employee's verification"""
    verification = get_object_or_404(EmployeeVerification, pk=verification_id)
    
    if request.method == 'POST':
        resolution_notes = request.POST.get('resolution_notes')
        verify_after_resolution = request.POST.get('verify_after_resolution') == 'on'
        
        if not resolution_notes:
            messages.error(request, "Please provide resolution notes.")
            return redirect('resolve_verification_issues', verification_id=verification.id)
        
        # Update verification status
        if verify_after_resolution:
            verification.verify(request.user, f"Issues resolved: {resolution_notes}")
            
            # Log the verification
            VerificationLog.objects.create(
                verification=verification,
                action='VERIFIED',
                performed_by=request.user,
                details=f"Verified after resolving issues: {resolution_notes}"
            )
            
            messages.success(request, f"Issues resolved and profile verified for {verification.employee_profile.user.get_full_name()}.")
        else:
            verification.resolve_issues(request.user, resolution_notes)
            
            # Log the resolution
            VerificationLog.objects.create(
                verification=verification,
                action='RESOLVED',
                performed_by=request.user,
                details=resolution_notes
            )
            
            messages.success(request, f"Issues resolved for {verification.employee_profile.user.get_full_name()}.")
        
        return redirect('staff_list')
    
    return render(request, 'core/resolve_verification.html', {
        'verification': verification,
    })


def get_lgas_for_state(request):
    """AJAX view to get LGAs for a state"""
    state_id = request.GET.get('state_id')
    if state_id:
        lgas = LGA.objects.filter(state_id=state_id).values('id', 'name')
        return JsonResponse({'lgas': list(lgas)})
    return JsonResponse({'lgas': []})


def get_units_for_department(request):
    """AJAX view to get units for a department"""
    department_id = request.GET.get('department_id')
    if department_id:
        units = Unit.objects.filter(department_id=department_id).values('id', 'name')
        return JsonResponse({'units': list(units)})
    return JsonResponse({'units': []})


# Helper Functions

def send_welcome_email(user, password, request):
    """Send welcome email with login credentials"""
    subject = "Welcome to the HR Management System"
    login_url = request.build_absolute_uri(reverse('login'))
    
    message = f"""
    Dear {user.get_full_name()},
    
    Welcome to the HR Management System. Your account has been created successfully.
    
    Here are your login credentials:
    Username: {user.username}
    Password: {password}
    
    Please login at {login_url} and complete your profile information.
    
    For security reasons, we recommend changing your password after the first login.
    
    Best regards,
    HR Department
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def run_automated_checks(employee_profile, verification):
    """Run automated checks on an employee profile"""
    # Reset flags
    verification.has_age_flag = False
    verification.has_education_flag = False
    verification.has_employment_flag = False
    
    # Get active checks
    checks = AutomatedCheck.objects.filter(is_active=True)
    
    # Collect issues
    issues = []
    
    for check in checks:
        # Skip checks that don't apply (e.g., education checks for profiles without education data)
        if check.check_type.startswith('AGE_') and not employee_profile.date_of_birth:
            continue
        
        # Age checks
        if check.check_type == 'EMPLOYMENT_AGE' and employee_profile.date_of_birth and employee_profile.date_of_assumption:
            # Calculate age at employment
            employment_date = employee_profile.date_of_assumption
            birth_date = employee_profile.date_of_birth
            age_at_employment = employment_date.year - birth_date.year
            
            # Adjust for month/day
            if (employment_date.month, employment_date.day) < (birth_date.month, birth_date.day):
                age_at_employment -= 1
            
            if age_at_employment < check.min_value:
                verification.has_age_flag = True
                issues.append(f"Employee was {age_at_employment} years old at employment, which is below the minimum age of {check.min_value}")
    
    # If any issues were found, update the verification
    if issues:
        verification.issue_description = "\n".join(issues)
    
    verification.save()
    
    # Log the automated check
    VerificationLog.objects.create(
        verification=verification,
        action='AUTO_CHECK',
        performed_by=None,  # System check
        details=f"Automated checks run. Issues found: {len(issues)}"
    )
    
    return issues