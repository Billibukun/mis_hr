from django.db import models
from django.contrib.auth.models import User
from datetime import date
from core.models import EmployeeProfile, Department, Unit, Zone, State


# Training Management
class TrainingType(models.Model):
    """Training type categorization"""
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name


class Training(models.Model):
    """Training program details"""
    STATUS_CHOICES = [
        ('UPCOMING', 'Upcoming'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=100)
    description = models.TextField()
    training_type = models.ForeignKey(TrainingType, on_delete=models.SET_NULL, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    location = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()
    organizer = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='UPCOMING')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_trainings')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='modified_trainings')
    modified_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({self.start_date} to {self.end_date})"
    
    @property
    def is_upcoming(self):
        return date.today() < self.start_date
    
    @property
    def is_ongoing(self):
        today = date.today()
        return self.start_date <= today <= self.end_date
    
    @property
    def is_completed(self):
        return date.today() > self.end_date


class TrainingParticipant(models.Model):
    """Employees participating in training programs"""
    STATUS_CHOICES = [
        ('NOMINATED', 'Nominated'),
        ('CONFIRMED', 'Confirmed'),
        ('ATTENDED', 'Attended'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
    ]
    
    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='participants')
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='trainings')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='NOMINATED')
    nomination_date = models.DateField(auto_now_add=True)
    nomination_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='training_nominations')
    attendance_record = models.FloatField(blank=True, null=True, help_text="Percentage of attendance")
    performance_score = models.FloatField(blank=True, null=True, help_text="Performance score (0-100)")
    certificate_issued = models.BooleanField(default=False)
    comments = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.training.title}"
    
    class Meta:
        unique_together = ('training', 'employee')


# Leave Management
class LeaveType(models.Model):
    """Types of leave available to employees"""
    name = models.CharField(max_length=50)
    max_days = models.PositiveIntegerField(help_text="Maximum days allowed per year")
    description = models.TextField(blank=True, null=True)
    requires_approval = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class LeaveBalance(models.Model):
    """Leave balance for each employee by leave type and year"""
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    initial_balance = models.PositiveIntegerField()
    used_days = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.leave_type.name} - {self.year}"
    
    @property
    def remaining_balance(self):
        return self.initial_balance - self.used_days
    
    class Meta:
        unique_together = ('employee', 'leave_type', 'year')


class LeaveRequest(models.Model):
    """Leave requests submitted by employees"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.PositiveIntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approved_date = models.DateField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.leave_type.name} ({self.start_date} to {self.end_date})"


class LeaveApprovalLevel(models.Model):
    """Approval levels for leave requests"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    level = models.PositiveIntegerField(help_text="1 for first level, 2 for second level, etc.")
    approver_roles = models.JSONField(help_text="List of role names that can approve at this level")
    
    def __str__(self):
        return f"{self.department.name} - {self.leave_type.name} - Level {self.level}"
    
    class Meta:
        unique_together = ('department', 'leave_type', 'level')


# Examination Tracking
class ExaminationType(models.Model):
    """Types of examinations available for employees"""
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    eligibility_criteria = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name


class Examination(models.Model):
    """Scheduled examinations for employees"""
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=100)
    examination_type = models.ForeignKey(ExaminationType, on_delete=models.CASCADE)
    scheduled_date = models.DateField()
    registration_deadline = models.DateField()
    venue = models.CharField(max_length=100)
    max_participants = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SCHEDULED')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_examinations')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({self.scheduled_date})"


class ExaminationParticipant(models.Model):
    """Employees registered for examinations"""
    STATUS_CHOICES = [
        ('REGISTERED', 'Registered'),
        ('APPROVED', 'Approved'),
        ('ATTENDED', 'Attended'),
        ('PASSED', 'Passed'),
        ('FAILED', 'Failed'),
        ('ABSENT', 'Absent'),
    ]
    
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, related_name='participants')
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='examinations')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='REGISTERED')
    registration_date = models.DateField(auto_now_add=True)
    score = models.FloatField(blank=True, null=True)
    position = models.PositiveIntegerField(blank=True, null=True, help_text="Ranking position")
    comments = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.examination.title}"
    
    class Meta:
        unique_together = ('examination', 'employee')


# Promotion Processing
class PromotionCycle(models.Model):
    """Promotion cycles for the organization"""
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('NOMINATIONS_OPEN', 'Nominations Open'),
        ('REVIEWS_IN_PROGRESS', 'Reviews In Progress'),
        ('APPROVALS_IN_PROGRESS', 'Approvals In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PLANNED')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_promotion_cycles')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({self.year})"


class PromotionCriteria(models.Model):
    """Criteria for promotions"""
    promotion_cycle = models.ForeignKey(PromotionCycle, on_delete=models.CASCADE, related_name='criteria')
    name = models.CharField(max_length=50)
    description = models.TextField()
    weight = models.PositiveIntegerField(help_text="Weight of this criteria in percentage")
    
    def __str__(self):
        return f"{self.promotion_cycle.title} - {self.name}"
    
    class Meta:
        unique_together = ('promotion_cycle', 'name')


class PromotionNomination(models.Model):
    """Nominations for promotion"""
    STATUS_CHOICES = [
        ('NOMINATED', 'Nominated'),
        ('SHORTLISTED', 'Shortlisted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    promotion_cycle = models.ForeignKey(PromotionCycle, on_delete=models.CASCADE, related_name='nominations')
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='promotion_nominations')
    current_level = models.PositiveIntegerField()
    proposed_level = models.PositiveIntegerField()
    nomination_date = models.DateField(auto_now_add=True)
    nominated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='submitted_nominations')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='NOMINATED')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_promotions')
    approved_date = models.DateField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.promotion_cycle.title}"
    
    class Meta:
        unique_together = ('promotion_cycle', 'employee')


class PromotionAssessment(models.Model):
    """Assessment scores for promotion criteria"""
    nomination = models.ForeignKey(PromotionNomination, on_delete=models.CASCADE, related_name='assessments')
    criteria = models.ForeignKey(PromotionCriteria, on_delete=models.CASCADE)
    score = models.FloatField(help_text="Score out of 100")
    comments = models.TextField(blank=True, null=True)
    assessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='conducted_assessments')
    assessment_date = models.DateField(auto_now=True)
    
    def __str__(self):
        return f"{self.nomination.employee.user.get_full_name()} - {self.criteria.name}"
    
    class Meta:
        unique_together = ('nomination', 'criteria')


# Transfer Management
class TransferRequest(models.Model):
    """Transfer requests for employees"""
    REQUEST_TYPES = [
        ('EMPLOYEE_REQUESTED', 'Employee Requested'),
        ('MANAGEMENT_INITIATED', 'Management Initiated'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='transfer_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    
    # Current placement
    current_department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='transfer_from_requests')
    current_unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_from_requests')
    current_zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_from_requests')
    current_state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_from_requests')
    
    # Requested placement
    requested_department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='transfer_to_requests')
    requested_unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_to_requests')
    requested_zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_to_requests')
    requested_state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_to_requests')
    
    reason = models.TextField()
    supporting_document_reference = models.CharField(max_length=100, blank=True, null=True)
    
    request_date = models.DateField(auto_now_add=True)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='initiated_transfers')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='DRAFT')
    
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    approved_date = models.DateField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    effective_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.current_department.name} to {self.requested_department.name}"


# Educational Upgrade
class EducationalUpgrade(models.Model):
    """Educational qualification upgrades for employees"""
    STATUS_CHOICES = [
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]
    
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='educational_upgrades')
    qualification_type = models.CharField(max_length=4, choices=EmployeeProfile.CADRE_CHOICES)
    course_of_study = models.CharField(max_length=100)
    institution = models.CharField(max_length=100)
    year_of_graduation = models.PositiveIntegerField()
    certificate_reference = models.CharField(max_length=100)
    
    submission_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='SUBMITTED')
    
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_upgrades')
    review_date = models.DateField(null=True, blank=True)
    review_comments = models.TextField(blank=True, null=True)
    
    approval_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_upgrades')
    
    effective_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.get_qualification_type_display()} in {self.course_of_study}"


# Retirement Processing
class RetirementPlan(models.Model):
    """Retirement planning for employees"""
    STATUS_CHOICES = [
        ('UPCOMING', 'Upcoming'),
        ('NOTIFIED', 'Employee Notified'),
        ('IN_PROGRESS', 'Processing In Progress'),
        ('COMPLETED', 'Processing Completed'),
        ('RETIRED', 'Employee Retired'),
    ]
    
    employee = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE, related_name='retirement_plan')
    expected_retirement_date = models.DateField()
    notification_date = models.DateField(null=True, blank=True, help_text="Date employee was notified of upcoming retirement")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='UPCOMING')
    
    exit_interview_date = models.DateField(null=True, blank=True)
    exit_interview_conducted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='conducted_exit_interviews')
    
    clearance_completed = models.BooleanField(default=False)
    clearance_date = models.DateField(null=True, blank=True)
    
    pension_processed = models.BooleanField(default=False)
    pension_processing_date = models.DateField(null=True, blank=True)
    
    final_payout_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    final_payout_date = models.DateField(null=True, blank=True)
    
    comments = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - Retirement on {self.expected_retirement_date}"


class RetirementChecklistItem(models.Model):
    """Checklist items for retirement processing"""
    retirement_plan = models.ForeignKey(RetirementPlan, on_delete=models.CASCADE, related_name='checklist_items')
    item_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_retirement_items')
    comments = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.retirement_plan.employee.user.get_full_name()} - {self.item_name}"