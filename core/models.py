from datetime import timedelta, date
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


class Department(models.Model):
    TYPE_CHOICES = [
        ('SYS', 'System Admin'),
        ('DG_O', 'Director General Office'),
        ('SERV', 'Service Deparment'),
        ('PROG', 'Programme Department'),
        ('ZONAL', 'Zonal Office'),
        ('BRANCH', 'Branch'),
        ('UTILITY', 'Utility Unit'),
    ]
    name = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=150, blank=True, null=True)
    code = models.CharField(max_length=5, unique=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')

    def __str__(self):
        return self.name
    
class Unit(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=150, blank=True, null=True)
    department = models.ForeignKey('Department', on_delete=models.CASCADE, related_name='units')

    def __str__(self):
        return self.name
    
class Zone(models.Model):
    code = models.CharField(max_length=2, unique=True)
    name = models.CharField(max_length=30, unique=True)
    
    def __str__(self):
        return self.name
    
class State(models.Model):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=30,)
    zone = models.ForeignKey('Zone', on_delete=models.CASCADE, related_name='states')
    
    def __str__(self):
        return self.name
    
class LGA(models.Model):
    code = models.CharField(max_length=5, unique=True)
    name = models.CharField(max_length=30)
    state = models.ForeignKey('State', on_delete=models.CASCADE, related_name='lgas')
    
    def __str__(self):
        return self.name
    
class Bank(models.Model):
    code = models.CharField(max_length=5, unique=True)
    name = models.CharField(max_length=30, unique=True)
    
    def __str__(self):
        return self.name
    
class PFA(models.Model):
    code = models.CharField(max_length=5, unique=True)
    name = models.CharField(max_length=30, unique=True)
    
    def __str__(self):
        return self.name
    
class Designation(models.Model):
    code = models.CharField(max_length=5, unique=True)
    grade_level = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)])
    name = models.CharField(max_length=30, unique=True)
    department = models.ForeignKey('Department', on_delete=models.CASCADE, related_name='designations')
    
    def __str__(self):
        return self.name

# Helper Functions
def get_current_year():
    return date.today().year

class EmployeeProfile(models.Model):
    EMPLOYEE_TYPE_CHOICES = [
        ('SYS', 'System Admin'),
        ('DG', 'Director General'),
        ('DIR', 'Director'),
        ('ZD', 'Zonal Driector'),
        ('HOD', 'Head of Department'),
        ('HOU', 'Head of Unit'),
        ('SC', 'State Coordinator'),
        ('STAFF', 'Staff'),
    ]
    CADRE_CHOICES = [
        ('O', 'Officer'),
        ('E','Executive'),
        ('S', 'Secretariat'),
        ('C', 'Clerical'),
        ('D', 'Driver')
    ]
    
    MARITAL_STATUS_CHOICES = [
        ('S', 'Single'),
        ('M', 'Married'),
        ('D', 'Divorced'),
        ('W', 'Widowed'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    current_employee_type = models.CharField(max_length=5, choices=EMPLOYEE_TYPE_CHOICES, default='STAFF')
    profile_picture = models.ImageField(upload_to='employee_pics/', blank=True, null=True)
    file_number = models.CharField(max_length=7, verbose_name='File Number')
    ippis_number = models.CharField(max_length=10, blank=True, null=True, unique=True, verbose_name='IPPIS Number')
    
    # Personal Information
    middle_name = models.CharField(max_length=30, blank=True, null=True, verbose_name='Middle Name')
    sex = models.CharField(max_length=1, choices=([('M', 'Male'),('F', 'Female')]), blank=True, null=True, verbose_name= 'Sex')
    marital_status = models.CharField(max_length=1, choices=MARITAL_STATUS_CHOICES, blank=True, null=True, verbose_name='Marital Status')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Date of Birth')
    phone_number = models.CharField(max_length=11, blank=True, verbose_name= 'Phone Number')
    contact_address = models.CharField(max_length=100, blank=True, verbose_name='Contact Address')
    lga_of_residence = models.ForeignKey('LGA', on_delete=models.SET_NULL, null=True, blank=True, related_name='residents')
    state_of_residence = models.ForeignKey('State', on_delete=models.SET_NULL, null=True, blank=True, related_name='residents')
    lga_of_origin = models.ForeignKey('LGA', on_delete=models.SET_NULL, null=True, blank=True, related_name='origins')
    state_of_origin = models.ForeignKey('State', on_delete=models.SET_NULL, null=True, blank=True, related_name='origins')
    nin = models.CharField(max_length=11, blank=True, null=True, unique=True, verbose_name='National Identification Number')
    brn = models.CharField(max_length=18, blank=True, null=True, unique=True, verbose_name='Birth Registration Number')
    
    # Current Employment Details
    date_of_appointment = models.DateField(null=True, blank=True, verbose_name='Date on Appointment Letter')
    date_of_present_appointment = models.DateField(null=True, blank=True, verbose_name='Date of Present Appointment')
    date_of_documentation = models.DateField(null=True, blank=True, verbose_name='Date of Documentation')
    date_of_assumption = models.DateField(null=True, blank=True, verbose_name='Date of Assumption of Duty')
    date_of_confirmation = models.DateField(null=True, blank=True, verbose_name='Date of Confirmation')
    date_of_retirement = models.DateField(null=True, blank=True, verbose_name='Date of Retirement')
    
    current_zone = models.ForeignKey('Zone', on_delete=models.SET_NULL, null=True, blank=True, related_name='current_employees')
    current_state = models.ForeignKey('State', on_delete=models.SET_NULL, null=True, blank=True, related_name='current_employees')
    current_grade_level = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(18)], blank=True, null=True, verbose_name='Current Grade Level')
    current_step = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(15)], blank=True, null=True, verbose_name='Current Step')
    current_department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='current_employees')
    current_unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, null=True, blank=True, related_name='current_employees')
    current_designation = models.ForeignKey('Designation', on_delete=models.SET_NULL, null=True, blank=True, related_name='current_employees')
    current_cadre = models.CharField(max_length=1, choices=CADRE_CHOICES, blank=True, null=True, verbose_name='Current Cadre')
    
    last_promotion_date = models.DateField(null=True, blank=True, verbose_name='Last Promotion Date')
    last_examination_date = models.DateField(null=True, blank=True, verbose_name='Last Examination Date')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_profiles')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_profiles')
    modified_at = models.DateTimeField(auto_now=True)
    
    is_profile_completed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Profile for {self.user.username}"
    
    def clean(self):
        if self.current_grade_level == 11:
            raise ValidationError('Grade level 11 is not allowed.')
        
        # calculate retirement automatically based on 35 years in service or 60 years of age
        if self.date_of_assumption and self.date_of_birth: # Corrected condition: check for date_of_birth
            years_in_service_date = self.date_of_assumption + timedelta(days=35*365)
            years_from_birth_date = self.date_of_birth + timedelta(days=60*365)

            retirement_date = min(years_in_service_date, years_from_birth_date) # Get the minimum date

            # Assign the calculated retirement date to the field (if in a model or form)
            self.date_of_retirement = retirement_date

        else:
            # Handle cases where date_of_assumption or date_of_birth is missing
            # 1. Set date_of_retirement to None
            # 2. Raise a ValidationError if these dates are required
            self.date_of_retirement = None # Or handle as appropriate
            # raise ValidationError("Date of assumption and date of birth are required to calculate retirement date.")
            
        # If retirement date = today turn is active in user model to false
        if self.date_of_retirement == date.today():
            self.user.is_active = False
            self.user.save()

    class Meta:
        verbose_name = "Employee Profile"
        verbose_name_plural = "Employee Profiles"

class EmployeeDetail(models.Model):
    employee_profile = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE, related_name='details')
    
    QUALIFICATION_TYPE_CHOICES = [
        ('FSLC', 'First School Leaving Certificate'),
        ('JSCE', 'Junior School Certificate'),
        ('SSCE', 'Secondary School Certificate'),
        ('OND', 'Ordinary National Diploma'),
        ('HND', 'Higher National Diploma'),
        ('BAC', 'Bachelors'),
        ('MAS', 'Masters'),
        ('DOR', 'Doctorate'),
        ('PRO', 'Professional'),
    ]
    
    # Educational Information
    highest_formal_eduation = models.CharField(max_length=4, choices=QUALIFICATION_TYPE_CHOICES, blank=True, null=True, verbose_name='Highest Formal Education')
    course_of_study = models.CharField(max_length=50, blank=True, null=True, verbose_name='Course of Study')
    area_of_study = models.CharField(max_length=50, blank=True, null=True, verbose_name='Area of Study', help_text="Commerce, Arts, Science, etc.")
    year_of_graduation = models.PositiveIntegerField(validators=[MinValueValidator(1960), MaxValueValidator(get_current_year)], blank=True, null=True, verbose_name='Year of Graduation')    
    
    ACCOUNT_TYPE_CHOICES = [
        ('SAV', 'Savings'),
        ('CUR', 'Current'),
    ]
    
    # Financial Informaiton
    bank = models.ForeignKey('Bank', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    account_number = models.CharField(max_length=10, blank=True, null=True, unique=True, verbose_name='Account Number')
    account_type = models.CharField(max_length=3, choices=ACCOUNT_TYPE_CHOICES, blank=True, null=True, verbose_name='Account Type')
    pfa = models.ForeignKey('PFA', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')
    pfa_number = models.CharField(max_length=10, blank=True, null=True, unique=True, verbose_name='PFA Number')
    
    LEAVE_STATUS_CHOICES = [
        ('A', 'Active'),
        ('I', 'On Leave'),
        ('S', 'Suspended'),
        ('R', 'Resigned'),
        ('T', 'Terminated'),
        ('D', 'Deceased'),
    ]
    
    leave_status = models.CharField(max_length=1, choices=LEAVE_STATUS_CHOICES, default='A', verbose_name='Leave Status')   
    
    # Spouse Details
    spouse_name = models.CharField(max_length=50, blank=True, null=True, verbose_name='Spouse Name')
    spouse_phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='Spouse Phone Number')
    spouse_email = models.EmailField(blank=True, null=True, verbose_name='Spouse Email')
    spouse_address = models.CharField(max_length=100, blank=True, null=True, verbose_name='Spouse Address')
    
    
    NOK_RELARIOINSHIP_CHOICES = [
        ('SPO', 'Spouse'),
        ('PRT', 'Parent'),
        ('CHD', 'Child'),
        ('SIB', 'Sibling'),
        ('REL', 'Relative'),
        ('OTH', 'Others'),
    ]
    
    # Next of Kin Information
    nok1_name = models.CharField(max_length=50, blank=True, null=True, verbose_name='Next of Kin 1 Name')
    nok1_phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='Next of Kin 1 Phone Number')
    nok1_email = models.EmailField(blank=True, null=True, verbose_name='Next of Kin 1 Email')
    nok1_relationship = models.CharField(max_length=3, choices=NOK_RELARIOINSHIP_CHOICES, blank=True, null=True, verbose_name='Next of Kin 1 Relationship')
    nok1_address = models.CharField(max_length=100, blank=True, null=True, verbose_name='Next of Kin 1 Address')
    
    nok2_name = models.CharField(max_length=50, blank=True, null=True, verbose_name='Next of Kin 2 Name')
    nok2_phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='Next of Kin 2 Phone Number')
    nok2_email = models.EmailField(blank=True, null=True, verbose_name='Next of Kin 2 Email')
    nok2_relationship = models.CharField(max_length=3, choices=NOK_RELARIOINSHIP_CHOICES, blank=True, null=True, verbose_name='Next of Kin 2 Relationship')
    nok2_address = models.CharField(max_length=100, blank=True, null=True, verbose_name='Next of Kin 2 Address')


    def __str__(self):
        return f"Details for {self.employee_profile.user.username}"

    class Meta:
        verbose_name = "Employee Detail"
        verbose_name_plural = "Employee Details"

@receiver(post_save, sender=User)
def create_employee_profile(sender, instance, created, **kwargs):
    if created:
        EmployeeProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_employee_profile(sender, instance, **kwargs):
    instance.employee_profile.save()
    
    
class EducationalQualification(models.Model):
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='qualifications')
    qualification_type = models.CharField(max_length=4, choices=EmployeeDetail.QUALIFICATION_TYPE_CHOICES, verbose_name='Qualification Type')
    course_of_study = models.CharField(max_length=50, verbose_name='Course of Study')
    area_of_study = models.CharField(max_length=50, null=True, blank=True, verbose_name='Area of Study')
    institution = models.CharField(max_length=50, verbose_name='Institution')
    year_of_graduation = models.PositiveIntegerField(validators=[MinValueValidator(1960), MaxValueValidator(get_current_year)], verbose_name='Year of Graduation')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_qualifications')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_qualifications')
    modified_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.qualification_type} - {self.course_of_study} - {self.employee_profile.user.username}"

    class Meta:
        verbose_name = "Educational Qualification"
        verbose_name_plural = "Educational Qualifications"
        
class Newsletter(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    publish_date = models.DateField(auto_now_add=True)  # Automatically set the publication date
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) # Link to author

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-publish_date']  