from datetime import timedelta, date
from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from .models import *


# ====== Permission and Role Management ======

class Role(models.Model):
    """
    Custom role model for RBAC implementation
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    
    def __str__(self):
        return self.name


class UserRole(models.Model):
    """
    Associates users with roles and departments/units for contextual access
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)
    unit = models.ForeignKey('Unit', on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='role_assignments')
    assigned_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'role', 'department', 'unit')
        
    def __str__(self):
        context = f" in {self.department.name}" if self.department else ""
        context += f" - {self.unit.name}" if self.unit else ""
        return f"{self.user.username} as {self.role.name}{context}"


# ====== Task Management ======

class Task(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    title = models.CharField(max_length=100)
    description = models.TextField()
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks')
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)
    unit = models.ForeignKey('Unit', on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    def is_overdue(self):
        from django.utils import timezone
        return self.due_date < timezone.now() and self.status not in ['COMPLETED', 'CANCELLED']


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment on {self.task.title} by {self.user.username}"


# ====== Promotions ======

class PromotionCycle(models.Model):
    """
    Represents a promotion cycle/period
    """
    title = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_promotion_cycles')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.year}"
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date cannot be before start date")


class PromotionApplication(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('UNDER_REVIEW', 'Under Review'),
        ('SHORTLISTED', 'Shortlisted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('WITHDRAWN', 'Withdrawn'),
    ]
    
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promotion_applications')
    promotion_cycle = models.ForeignKey(PromotionCycle, on_delete=models.CASCADE)
    current_designation = models.ForeignKey('Designation', on_delete=models.CASCADE, related_name='promotion_from')
    target_designation = models.ForeignKey('Designation', on_delete=models.CASCADE, related_name='promotion_to')
    application_date = models.DateField(auto_now_add=True)
    last_promotion_date = models.DateField(null=True, blank=True)
    years_in_position = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    remarks = models.TextField(blank=True, null=True)
    is_eligible = models.BooleanField(default=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_promotions')
    processed_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"Promotion application for {self.employee.username} - {self.promotion_cycle.year}"
    
    def save(self, *args, **kwargs):
        # Calculate years in position if last promotion date exists
        if self.last_promotion_date:
            today = date.today()
            delta = today - self.last_promotion_date
            self.years_in_position = delta.days // 365
        super().save(*args, **kwargs)


class PromotionApproval(models.Model):
    APPROVAL_CHOICES = [
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('DEFERRED', 'Deferred'),
    ]
    
    promotion_application = models.ForeignKey(PromotionApplication, on_delete=models.CASCADE, related_name='approvals')
    approved_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promotion_approvals')
    approval_date = models.DateField(auto_now_add=True)
    decision = models.CharField(max_length=10, choices=APPROVAL_CHOICES)
    comments = models.TextField(blank=True, null=True)
    level = models.CharField(max_length=50, help_text="Level of approval (e.g., Supervisor, HOD, Director)")
    
    def __str__(self):
        return f"{self.get_decision_display()} by {self.approved_by.username} for {self.promotion_application.employee.username}"


# ====== Exams ======

class Examination(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    exam_date = models.DateField()
    registration_start_date = models.DateField()
    registration_end_date = models.DateField()
    eligible_grade_level_min = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    eligible_grade_level_max = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_exams')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    def clean(self):
        if self.registration_start_date > self.registration_end_date:
            raise ValidationError("Registration end date cannot be before start date")
        if self.registration_end_date > self.exam_date:
            raise ValidationError("Exam date must be after registration period")
        if self.eligible_grade_level_min > self.eligible_grade_level_max:
            raise ValidationError("Minimum eligible grade level cannot be greater than maximum")


class ExamRegistration(models.Model):
    STATUS_CHOICES = [
        ('REGISTERED', 'Registered'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ATTENDED', 'Attended'),
        ('ABSENT', 'Absent'),
    ]
    
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name='registrations')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_registrations')
    registration_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='REGISTERED')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_exam_registrations')
    approval_date = models.DateField(null=True, blank=True)
    attendance_marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='marked_exam_attendance')
    
    class Meta:
        unique_together = ('examination', 'employee')
    
    def __str__(self):
        return f"{self.employee.username} registered for {self.examination.title}"


class ExamResult(models.Model):
    registration = models.OneToOneField(ExamRegistration, on_delete=models.CASCADE, related_name='result')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    passing_score = models.DecimalField(max_digits=5, decimal_places=2)
    passed = models.BooleanField()
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_exam_results')
    recorded_date = models.DateField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        self.passed = self.score >= self.passing_score
        super().save(*args, **kwargs)
    
    def __str__(self):
        status = "Passed" if self.passed else "Failed"
        return f"{self.registration.employee.username} {status} {self.registration.examination.title}"


# ====== Transfers ======

class TransferRequest(models.Model):
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]
    
    TYPE_CHOICES = [
        ('DEPARTMENT', 'Inter-Department'),
        ('UNIT', 'Inter-Unit'),
        ('LOCATION', 'Location Change'),
    ]
    
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transfer_requests')
    request_type = models.CharField(max_length=15, choices=TYPE_CHOICES)
    current_department = models.ForeignKey('Department', on_delete=models.CASCADE, related_name='transfer_from_dept')
    current_unit = models.ForeignKey('Unit', on_delete=models.CASCADE, related_name='transfer_from_unit', null=True, blank=True)
    current_state = models.ForeignKey('State', on_delete=models.CASCADE, related_name='transfer_from_state', null=True, blank=True)
    
    target_department = models.ForeignKey('Department', on_delete=models.CASCADE, related_name='transfer_to_dept', null=True, blank=True)
    target_unit = models.ForeignKey('Unit', on_delete=models.CASCADE, related_name='transfer_to_unit', null=True, blank=True)
    target_state = models.ForeignKey('State', on_delete=models.CASCADE, related_name='transfer_to_state', null=True, blank=True)
    
    reason = models.TextField()
    request_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='REQUESTED')
    
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    approval_date = models.DateField(null=True, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"Transfer request by {self.employee.username} - {self.get_request_type_display()}"
    
    def clean(self):
        # Validate based on request type
        if self.request_type == 'DEPARTMENT' and not self.target_department:
            raise ValidationError("Target department is required for inter-department transfers")
        elif self.request_type == 'UNIT' and not self.target_unit:
            raise ValidationError("Target unit is required for inter-unit transfers")
        elif self.request_type == 'LOCATION' and not self.target_state:
            raise ValidationError("Target state is required for location changes")


class TransferApproval(models.Model):
    LEVEL_CHOICES = [
        ('SUPERVISOR', 'Supervisor'),
        ('HOD', 'Head of Department'),
        ('HOD_TARGET', 'Target Department Head'),
        ('HR', 'Human Resources'),
        ('DIRECTOR', 'Director'),
    ]
    
    STATUS_CHOICES = [
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PENDING', 'Pending'),
    ]
    
    transfer_request = models.ForeignKey(TransferRequest, on_delete=models.CASCADE, related_name='approvals')
    approval_level = models.CharField(max_length=15, choices=LEVEL_CHOICES)
    approver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transfer_approvals')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    comments = models.TextField(blank=True, null=True)
    approval_date = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ('transfer_request', 'approval_level')
    
    def __str__(self):
        return f"{self.get_approval_level_display()} approval for {self.transfer_request.employee.username}'s transfer"


# ====== Retirement and Pension Management ======

class RetirementApplication(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
    ]
    
    TYPE_CHOICES = [
        ('STATUTORY', 'Statutory'),
        ('VOLUNTARY', 'Voluntary'),
        ('MEDICAL', 'Medical'),
        ('COMPULSORY', 'Compulsory'),
    ]
    
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='retirement_applications')
    retirement_type = models.CharField(max_length=15, choices=TYPE_CHOICES)
    application_date = models.DateField(auto_now_add=True)
    planned_retirement_date = models.DateField()
    years_of_service = models.PositiveIntegerField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    reason = models.TextField(blank=True, null=True)
    
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_retirements')
    processed_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.employee.username} - {self.get_retirement_type_display()} Retirement"
    
    def save(self, *args, **kwargs):
        # Calculate years of service if not provided
        if not self.years_of_service and hasattr(self.employee, 'employee_profile'):
            profile = self.employee.employee_profile
            if profile.date_of_assumption:
                today = date.today()
                delta = today - profile.date_of_assumption
                self.years_of_service = delta.days // 365
        super().save(*args, **kwargs)


class PensionDetail(models.Model):
    employee = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pension_details')
    retirement_date = models.DateField()
    last_salary = models.DecimalField(max_digits=12, decimal_places=2)
    pension_amount = models.DecimalField(max_digits=12, decimal_places=2)
    gratuity_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    years_of_service = models.PositiveIntegerField()
    pfa = models.ForeignKey('PFA', on_delete=models.CASCADE)
    pension_number = models.CharField(max_length=20)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_pension_records')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_pension_records')
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Pension details for {self.employee.username}"


# ====== Nominal Roll ======

class NominalRoll(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PENDING', 'Pending Verification'),
        ('LEAVE', 'On Leave'),
        ('SUSPENDED', 'Suspended'),
        ('TRANSFERRED', 'Transferred'),
        ('RETIRED', 'Retired'),
        ('TERMINATED', 'Terminated'),
    ]
    
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nominal_roll_entries')
    department = models.ForeignKey('Department', on_delete=models.CASCADE)
    unit = models.ForeignKey('Unit', on_delete=models.CASCADE, null=True, blank=True)
    designation = models.ForeignKey('Designation', on_delete=models.CASCADE)
    location = models.ForeignKey('State', on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    
    effective_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_nominal_rolls')
    created_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_nominal_rolls')
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-effective_date']
    
    def __str__(self):
        return f"{self.employee.username} - {self.department.name} - {self.effective_date}"


# ====== Leave Management ======

class LeaveType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    days_allowed = models.PositiveIntegerField()
    requires_approval = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class LeaveBalance(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    total_days = models.PositiveIntegerField()
    days_taken = models.PositiveIntegerField(default=0)
    days_remaining = models.PositiveIntegerField()
    
    class Meta:
        unique_together = ('employee', 'leave_type', 'year')
    
    def __str__(self):
        return f"{self.employee.username} - {self.leave_type.name} - {self.year}"
    
    def save(self, *args, **kwargs):
        self.days_remaining = self.total_days - self.days_taken
        super().save(*args, **kwargs)


class LeaveApplication(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]
    
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_applications')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.PositiveIntegerField()
    reason = models.TextField()
    contact_address = models.CharField(max_length=200, blank=True, null=True)
    contact_phone = models.CharField(max_length=15, blank=True, null=True)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    application_date = models.DateField(auto_now_add=True)
    
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approval_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.employee.username} - {self.leave_type.name} - {self.start_date} to {self.end_date}"
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date cannot be before start date")
        
        # Calculate days
        delta = self.end_date - self.start_date
        self.days_requested = delta.days + 1
        
        # Check leave balance
        try:
            current_year = date.today().year
            balance = LeaveBalance.objects.get(
                employee=self.employee,
                leave_type=self.leave_type,
                year=current_year
            )
            
            if balance.days_remaining < self.days_requested:
                raise ValidationError(f"Insufficient leave balance. Available: {balance.days_remaining}, Requested: {self.days_requested}")
                
        except LeaveBalance.DoesNotExist:
            pass  # Skip validation if no balance exists


class LeaveApproval(models.Model):
    LEVEL_CHOICES = [
        ('SUPERVISOR', 'Supervisor'),
        ('HOD', 'Head of Department'),
        ('HR', 'Human Resources'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    leave_application = models.ForeignKey(LeaveApplication, on_delete=models.CASCADE, related_name='approvals')
    approval_level = models.CharField(max_length=15, choices=LEVEL_CHOICES)
    approver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_approvals')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    comments = models.TextField(blank=True, null=True)
    approval_date = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ('leave_application', 'approval_level')
    
    def __str__(self):
        return f"{self.get_approval_level_display()} approval for {self.leave_application.employee.username}'s leave"


# ====== Training Management ======

class TrainingProgram(models.Model):
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    TYPE_CHOICES = [
        ('INDUCTION', 'Induction'),
        ('SKILL', 'Skill Development'),
        ('MANDATORY', 'Mandatory'),
        ('PROMOTION', 'Promotion-based'),
        ('LEADERSHIP', 'Leadership'),
        ('TECHNICAL', 'Technical'),
    ]
    
    title = models.CharField(max_length=100)
    description = models.TextField()
    training_type = models.CharField(max_length=15, choices=TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    location = models.CharField(max_length=100)
    max_participants = models.PositiveIntegerField()
    eligibility_criteria = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PLANNED')
    
    provider = models.CharField(max_length=100, blank=True, null=True)
    cost_per_participant = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_trainings')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date cannot be before start date")


class TrainingApplication(models.Model):
    STATUS_CHOICES = [
        ('APPLIED', 'Applied'),
        ('SHORTLISTED', 'Shortlisted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ATTENDED', 'Attended'),
        ('COMPLETED', 'Completed'),
        ('NO_SHOW', 'No Show'),
    ]
    
    training_program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name='applications')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_applications')
    application_date = models.DateField(auto_now_add=True)
    justification = models.TextField()
    supervisor_recommendation = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='APPLIED')
    
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_training_applications')
    approval_date = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ('training_program', 'employee')
    
    def __str__(self):
        return f"{self.employee.username} - {self.training_program.title}"


class TrainingFeedback(models.Model):
    RATING_CHOICES = [
        (1, 'Poor'),
        (2, 'Fair'),
        (3, 'Average'),
        (4, 'Good'),
        (5, 'Excellent'),
    ]
    
    training_application = models.OneToOneField(TrainingApplication, on_delete=models.CASCADE, related_name='feedback')
    content_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    instructor_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    facility_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    relevance_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    overall_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comments = models.TextField(blank=True, null=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Feedback for {self.training_application.training_program.title} by {self.training_application.employee.username}"


# ====== Document Management ======

class DocumentType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    is_required = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name


class EmployeeDocument(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE)
    document = models.FileField(upload_to='employee_documents/')
    upload_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return self.document
    
    
