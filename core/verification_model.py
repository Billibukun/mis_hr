from django.db import models
from django.contrib.auth.models import User
from datetime import date


class EmployeeVerification(models.Model):
    """Model to track verification of employee profiles by HR"""
    
    VERIFICATION_STATUS_CHOICES = [
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
        ('FLAGGED', 'Issues Flagged'),
        ('RESOLVED', 'Issues Resolved'),
        ('REJECTED', 'Verification Rejected'),
    ]
    
    FLAG_CATEGORY_CHOICES = [
        ('AGE', 'Age Discrepancy'),
        ('EDUCATION', 'Educational Qualification Issue'),
        ('DOCS', 'Missing Documents'),
        ('IDENTIFICATION', 'Identification Mismatch'),
        ('EMPLOYMENT', 'Employment Details Issue'),
        ('OTHER', 'Other Issues'),
    ]
    
    employee_profile = models.ForeignKey('EmployeeProfile', on_delete=models.CASCADE, related_name='verifications')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_profiles')
    verified_date = models.DateField(null=True, blank=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='PENDING')
    verification_notes = models.TextField(blank=True, null=True)
    
    # Issue flagging
    flag_category = models.CharField(max_length=20, choices=FLAG_CATEGORY_CHOICES, null=True, blank=True)
    issue_description = models.TextField(blank=True, null=True)
    flagged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='flagged_profiles')
    flagged_date = models.DateField(null=True, blank=True)
    
    # Resolution tracking
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_profiles')
    resolved_date = models.DateField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, null=True)
    
    # Automated checks
    has_age_flag = models.BooleanField(default=False, help_text="Flagged for age inconsistency")
    has_education_flag = models.BooleanField(default=False, help_text="Flagged for education timeline issues")
    has_employment_flag = models.BooleanField(default=False, help_text="Flagged for employment date issues")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Verification of {self.employee_profile.user.get_full_name()} - {self.get_verification_status_display()}"
    
    def verify(self, verified_by, notes=None):
        """Mark this verification as completed"""
        self.verified_by = verified_by
        self.verified_date = date.today()
        self.verification_status = 'VERIFIED'
        
        if notes:
            self.verification_notes = notes
        
        self.save()
    
    def flag_issues(self, flagged_by, category, description):
        """Flag issues with the employee profile"""
        self.flagged_by = flagged_by
        self.flagged_date = date.today()
        self.verification_status = 'FLAGGED'
        self.flag_category = category
        self.issue_description = description
        self.save()
    
    def resolve_issues(self, resolved_by, notes):
        """Mark flagged issues as resolved"""
        self.resolved_by = resolved_by
        self.resolved_date = date.today()
        self.verification_status = 'RESOLVED'
        self.resolution_notes = notes
        self.save()
    
    def reject(self, verified_by, notes):
        """Reject verification"""
        self.verified_by = verified_by
        self.verified_date = date.today()
        self.verification_status = 'REJECTED'
        self.verification_notes = notes
        self.save()
    

class AutomatedCheck(models.Model):
    """Model for storing automated verification check rules"""
    
    CHECK_TYPE_CHOICES = [
        ('AGE_PRIMARY', 'Minimum Age for Primary Education'),
        ('AGE_SECONDARY', 'Minimum Age for Secondary Education'),
        ('AGE_TERTIARY', 'Minimum Age for Tertiary Education'),
        ('EMPLOYMENT_AGE', 'Minimum Age for Employment'),
        ('MAX_AGE', 'Maximum Age for Employment'),
        ('EDUCATION_GAP', 'Maximum Gap Between Education Levels'),
        ('EDUCATION_OVERLAP', 'Education Timeline Overlap'),
    ]
    
    check_name = models.CharField(max_length=100)
    check_type = models.CharField(max_length=20, choices=CHECK_TYPE_CHOICES)
    description = models.TextField()
    
    # Parameters for different check types
    min_value = models.IntegerField(null=True, blank=True, help_text="Minimum value for age checks (in years)")
    max_value = models.IntegerField(null=True, blank=True, help_text="Maximum value for age or gap checks (in years)")
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_checks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.check_name} ({self.get_check_type_display()})"


class VerificationLog(models.Model):
    """Model for logging verification activities"""
    
    ACTION_CHOICES = [
        ('CREATED', 'Verification Created'),
        ('VERIFIED', 'Profile Verified'),
        ('FLAGGED', 'Issues Flagged'),
        ('RESOLVED', 'Issues Resolved'),
        ('REJECTED', 'Verification Rejected'),
        ('UPDATED', 'Profile Updated'),
        ('AUTO_CHECK', 'Automated Check Performed'),
    ]
    
    verification = models.ForeignKey(EmployeeVerification, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.verification.employee_profile.user.get_full_name()} - {self.get_action_display()} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"