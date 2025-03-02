from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import *


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=254)


class SetPasswordForm(forms.Form):
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput,
        min_length=8,
        help_text="Your password must be at least 8 characters and contain letters and numbers."
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError("Passwords don't match. Please enter both fields again.")
        
        return cleaned_data


class ProfileCompleteForm(forms.ModelForm):
    """Enhanced form for completing employee profile"""
    # User fields
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    
    # Profile personal information
    middle_name = forms.CharField(max_length=30, required=False)
    SEX_CHOICES = [('M', 'Male'), ('F', 'Female')]
    sex = forms.ChoiceField(choices=SEX_CHOICES, required=True)
    
    MARITAL_STATUS_CHOICES = [
        ('S', 'Single'),
        ('M', 'Married'),
        ('D', 'Divorced'),
        ('W', 'Widowed'),
    ]
    marital_status = forms.ChoiceField(choices=MARITAL_STATUS_CHOICES, required=True)
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    phone_number = forms.CharField(max_length=11, required=True)
    contact_address = forms.CharField(max_length=100, required=True, widget=forms.Textarea(attrs={'rows': 3}))
    
    # State and LGA fields
    state_of_residence = forms.ModelChoiceField(
        queryset=State.objects.all(),
        required=True,
        empty_label="Select State of Residence"
    )
    lga_of_residence = forms.ModelChoiceField(
        queryset=LGA.objects.none(),
        required=True,
        empty_label="Select LGA of Residence"
    )
    
    state_of_origin = forms.ModelChoiceField(
        queryset=State.objects.all(),
        required=True,
        empty_label="Select State of Origin"
    )
    lga_of_origin = forms.ModelChoiceField(
        queryset=LGA.objects.none(),
        required=True,
        empty_label="Select LGA of Origin"
    )
    
    # ID fields
    nin = forms.CharField(max_length=11, required=False, label="National Identification Number")
    brn = forms.CharField(max_length=18, required=False, label="Birth Registration Number")
    
    # Profile picture
    profile_picture = forms.ImageField(required=False)
    
    # Employment details
    CADRE_CHOICES = [
        ('O', 'Officer'),
        ('E','Executive'),
        ('S', 'Secretariat'),
        ('C', 'Clerical'),
        ('D', 'Driver')
    ]
    current_cadre = forms.ChoiceField(choices=CADRE_CHOICES, required=False)
    current_grade_level = forms.IntegerField(required=False, min_value=1, max_value=18)
    current_step = forms.IntegerField(required=False, min_value=1, max_value=15)
    
    # Employee Details - Education
    highest_formal_eduation = forms.ChoiceField(
        choices=EmployeeDetail.QUALIFICATION_TYPE_CHOICES,
        required=False,
        label="Highest Formal Education"
    )
    course_of_study = forms.CharField(max_length=50, required=False)
    area_of_study = forms.CharField(max_length=50, required=False, help_text="Commerce, Arts, Science, etc.")
    year_of_graduation = forms.IntegerField(required=False)
    
    # Employee Details - Bank Information
    bank = forms.ModelChoiceField(
        queryset=Bank.objects.all(),
        required=False,
        label="Bank"
    )
    account_number = forms.CharField(max_length=10, required=False)
    account_type = forms.ChoiceField(
        choices=EmployeeDetail.ACCOUNT_TYPE_CHOICES,
        required=False
    )
    pfa = forms.ModelChoiceField(
        queryset=PFA.objects.all(),
        required=False,
        label="Pension Fund Administrator"
    )
    pfa_number = forms.CharField(max_length=10, required=False, label="PFA Number")
    
    # Next of Kin Information
    nok1_name = forms.CharField(max_length=50, required=False, label="Next of Kin 1 Name")
    nok1_phone_number = forms.CharField(max_length=20, required=False, label="Next of Kin 1 Phone Number")
    nok1_email = forms.EmailField(required=False, label="Next of Kin 1 Email")
    nok1_relationship = forms.ChoiceField(
        choices=EmployeeDetail.NOK_RELARIOINSHIP_CHOICES,
        required=False,
        label="Next of Kin 1 Relationship"
    )
    nok1_address = forms.CharField(max_length=100, required=False, widget=forms.Textarea(attrs={'rows': 2}), label="Next of Kin 1 Address")
    
    nok2_name = forms.CharField(max_length=50, required=False, label="Next of Kin 2 Name")
    nok2_phone_number = forms.CharField(max_length=20, required=False, label="Next of Kin 2 Phone Number")
    nok2_email = forms.EmailField(required=False, label="Next of Kin 2 Email")
    nok2_relationship = forms.ChoiceField(
        choices=EmployeeDetail.NOK_RELARIOINSHIP_CHOICES,
        required=False,
        label="Next of Kin 2 Relationship"
    )
    nok2_address = forms.CharField(max_length=100, required=False, widget=forms.Textarea(attrs={'rows': 2}), label="Next of Kin 2 Address")
    
    # Multiple qualifications
    additional_qualifications = forms.BooleanField(required=False, initial=False, label="Add more qualifications")
    
    class Meta:
        model = EmployeeProfile
        fields = [
            'middle_name', 'sex', 'marital_status', 'date_of_birth',
            'phone_number', 'contact_address', 
            'state_of_residence', 'lga_of_residence',
            'state_of_origin', 'lga_of_origin',
            'nin', 'brn', 'profile_picture',
            'current_cadre', 'current_grade_level', 'current_step',
        ]
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        # Get instance if provided
        instance = kwargs.get('instance', None)
        super(ProfileCompleteForm, self).__init__(*args, **kwargs)
        
        # Initialize user fields if user is provided
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
            
        # Set initial values for state and LGA fields if instance exists
        if instance:
            if instance.state_of_residence:
                # Set LGA queryset for residence
                self.fields['lga_of_residence'].queryset = LGA.objects.filter(
                    state=instance.state_of_residence
                ).order_by('name')
            
            if instance.state_of_origin:
                # Set LGA queryset for origin
                self.fields['lga_of_origin'].queryset = LGA.objects.filter(
                    state=instance.state_of_origin
                ).order_by('name')
            
            # Try to get employee detail if it exists
            try:
                employee_detail = instance.details
                # Set initial values for employee detail fields
                for field_name in ['highest_formal_eduation', 'course_of_study', 'area_of_study', 
                                  'year_of_graduation', 'bank', 'account_number', 'account_type', 
                                  'pfa', 'pfa_number', 'nok1_name', 'nok1_phone_number', 'nok1_email',
                                  'nok1_relationship', 'nok1_address', 'nok2_name', 'nok2_phone_number',
                                  'nok2_email', 'nok2_relationship', 'nok2_address']:
                    if hasattr(employee_detail, field_name) and field_name in self.fields:
                        self.fields[field_name].initial = getattr(employee_detail, field_name)
            except EmployeeDetail.DoesNotExist:
                pass
        
        # Handle dynamic LGA selection from form data
        if 'state_of_residence' in self.data:
            try:
                state_id = int(self.data.get('state_of_residence'))
                self.fields['lga_of_residence'].queryset = LGA.objects.filter(state_id=state_id).order_by('name')
            except (ValueError, TypeError):
                pass
        
        if 'state_of_origin' in self.data:
            try:
                state_id = int(self.data.get('state_of_origin'))
                self.fields['lga_of_origin'].queryset = LGA.objects.filter(state_id=state_id).order_by('name')
            except (ValueError, TypeError):
                pass
    
    def clean_date_of_birth(self):
        """Validate date of birth is reasonable (not in future, not too old)"""
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            import datetime
            today = datetime.date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            
            if age < 18:
                raise ValidationError("Employee must be at least 18 years old.")
            
            if age > 100:
                raise ValidationError("Please check the date of birth and enter a valid date.")
            
            if dob > today:
                raise ValidationError("Date of birth cannot be in the future.")
        
        return dob
    
    def clean_nin(self):
        """Validate NIN format"""
        nin = self.cleaned_data.get('nin')
        if nin:
            # NIN should be 11 digits
            if not nin.isdigit() or len(nin) != 11:
                raise ValidationError("NIN must be 11 digits.")
            
            # Check if NIN is already used by another employee
            existing_profiles = EmployeeProfile.objects.filter(nin=nin)
            if self.instance and self.instance.pk:
                existing_profiles = existing_profiles.exclude(pk=self.instance.pk)
                
            if existing_profiles.exists():
                raise ValidationError("This NIN is already registered in the system.")
        
        return nin
    
    def clean_account_number(self):
        """Validate account number format if provided"""
        account_number = self.cleaned_data.get('account_number')
        if account_number:
            if not account_number.isdigit() or len(account_number) != 10:
                raise ValidationError("Account number must be 10 digits.")
        return account_number
    
    def clean_profile_picture(self):
        """Process and validate profile picture"""
        image = self.cleaned_data.get('profile_picture')
        if image:
            # Check file size (20KB = 20 * 1024 bytes)
            if image.size > 20 * 1024:
                from PIL import Image
                import io
                
                # Open the image
                img = Image.open(image)
                
                # If it's larger than 20KB, resize it while maintaining aspect ratio
                img.thumbnail((200, 200))  # Reasonable size for profile picture
                
                # Save to a BytesIO object
                output = io.BytesIO()
                img.save(output, format=img.format, quality=70)
                output.seek(0)
                
                # Replace the original file with the compressed version
                image.file = output
                image.size = output.getbuffer().nbytes
        
        return image
    
    def save(self, commit=True):
        """Save both user and employee profile data, including employee details"""
        # Update user data
        if self.user:
            self.user.first_name = self.cleaned_data.get('first_name')
            self.user.last_name = self.cleaned_data.get('last_name')
            self.user.email = self.cleaned_data.get('email')
            if commit:
                self.user.save()
        
        # Update profile
        profile = super().save(commit=False)
        
        # Ensure profile is linked to the user
        if self.user and not profile.user_id:
            profile.user = self.user
        
        # Mark profile as completed
        profile.is_profile_completed = True
        
        if commit:
            profile.save()
            
            # Create or update EmployeeDetail
            employee_detail, created = EmployeeDetail.objects.get_or_create(
                employee_profile=profile
            )
            
            # Update employee detail fields
            detail_fields = [
                'highest_formal_eduation', 'course_of_study', 'area_of_study', 
                'year_of_graduation', 'bank', 'account_number', 'account_type', 
                'pfa', 'pfa_number', 'nok1_name', 'nok1_phone_number', 'nok1_email',
                'nok1_relationship', 'nok1_address', 'nok2_name', 'nok2_phone_number',
                'nok2_email', 'nok2_relationship', 'nok2_address'
            ]
            
            for field in detail_fields:
                if field in self.cleaned_data:
                    setattr(employee_detail, field, self.cleaned_data.get(field))
            
            employee_detail.save()
            
            # Create educational qualification if data provided
            if (self.cleaned_data.get('highest_formal_eduation') and 
                self.cleaned_data.get('course_of_study') and
                self.cleaned_data.get('year_of_graduation')):
                
                # Check if this qualification already exists
                existing_qual = EducationalQualification.objects.filter(
                    employee_profile=profile,
                    qualification_type=self.cleaned_data.get('highest_formal_eduation'),
                    course_of_study=self.cleaned_data.get('course_of_study'),
                    year_of_graduation=self.cleaned_data.get('year_of_graduation')
                ).first()
                
                if not existing_qual:
                    EducationalQualification.objects.create(
                        employee_profile=profile,
                        qualification_type=self.cleaned_data.get('highest_formal_eduation'),
                        course_of_study=self.cleaned_data.get('course_of_study'),
                        area_of_study=self.cleaned_data.get('area_of_study', ''),
                        institution=self.cleaned_data.get('institution', ''),
                        year_of_graduation=self.cleaned_data.get('year_of_graduation'),
                        created_by=self.user
                    )
        
        return profile


class AdditionalQualificationForm(forms.ModelForm):
    """Form for adding additional qualifications"""
    class Meta:
        model = EducationalQualification
        fields = ['qualification_type', 'course_of_study', 'area_of_study', 'institution', 'year_of_graduation']
        widgets = {
            'year_of_graduation': forms.NumberInput(attrs={'min': 1960, 'max': lambda: get_current_year()})
        }
        

class StaffOnboardingForm(forms.Form):
    """Form for HR staff to onboard a new employee"""
    # User information
    username = forms.CharField(max_length=150, required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    
    # Employee profile basic information
    file_number = forms.CharField(max_length=7, required=True)
    ippis_number = forms.CharField(max_length=10, required=False)
    
    # Employee type
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
    current_employee_type = forms.ChoiceField(choices=EMPLOYEE_TYPE_CHOICES, required=True)
    
    # Department and designation
    current_department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=True,
        empty_label="Select Department"
    )
    current_unit = forms.ModelChoiceField(
        queryset=Unit.objects.none(),
        required=False,
        empty_label="Select Unit (Optional)"
    )
    current_designation = forms.CharField(max_length=100, required=True)
    
    # Grade level
    current_grade_level = forms.IntegerField(
        min_value=1, max_value=17, 
        required=True,
        help_text="Grade level (1-17, excluding 11)"
    )
    current_step = forms.IntegerField(
        min_value=1, max_value=15,
        required=True,
        help_text="Step within grade level (1-15)"
    )
    
    # Employment dates
    date_of_appointment = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True,
        help_text="Date on appointment letter"
    )
    date_of_assumption = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True,
        help_text="Date employee assumed duty"
    )
    
    def __init__(self, *args, **kwargs):
        super(StaffOnboardingForm, self).__init__(*args, **kwargs)
        
        # Set up dynamic unit choices based on department
        if 'current_department' in self.data:
            try:
                department_id = int(self.data.get('current_department'))
                self.fields['current_unit'].queryset = Unit.objects.filter(department_id=department_id).order_by('name')
            except (ValueError, TypeError):
                pass
    
    def clean_username(self):
        """Check if username already exists"""
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username already exists.")
        return username
    
    def clean_email(self):
        """Check if email already exists"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email already exists.")
        return email
    
    def clean_file_number(self):
        """Check if file number already exists"""
        file_number = self.cleaned_data.get('file_number')
        if EmployeeProfile.objects.filter(file_number=file_number).exists():
            raise ValidationError("File number already exists.")
        return file_number
    
    def clean_ippis_number(self):
        """Check if IPPIS number already exists"""
        ippis_number = self.cleaned_data.get('ippis_number')
        if ippis_number and EmployeeProfile.objects.filter(ippis_number=ippis_number).exists():
            raise ValidationError("IPPIS number already exists.")
        return ippis_number
    
    def clean_current_grade_level(self):
        """Validate grade level is not 11"""
        grade_level = self.cleaned_data.get('current_grade_level')
        if grade_level == 11:
            raise ValidationError("Grade level 11 is not allowed.")
        return grade_level
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        date_of_appointment = cleaned_data.get('date_of_appointment')
        date_of_assumption = cleaned_data.get('date_of_assumption')
        
        # Validate appointment and assumption dates
        if date_of_appointment and date_of_assumption:
            if date_of_assumption < date_of_appointment:
                raise ValidationError("Date of assumption cannot be earlier than date of appointment.")
            
            import datetime
            today = datetime.date.today()
            if date_of_appointment > today or date_of_assumption > today:
                raise ValidationError("Appointment and assumption dates cannot be in the future.")
        
        return cleaned_data
    
    def save(self):
        """
        Create a new user and employee profile
        Returns a tuple of (user, profile, password)
        """
        # Generate a random password
        from django.utils.crypto import get_random_string
        password = get_random_string(10)
        
        # Create user
        user = User.objects.create_user(
            username=self.cleaned_data.get('username'),
            email=self.cleaned_data.get('email'),
            password=password,
            first_name=self.cleaned_data.get('first_name'),
            last_name=self.cleaned_data.get('last_name')
        )
        
        # Get or create employee profile
        profile = EmployeeProfile.objects.get(user=user)
        
        # Update profile with form data
        profile.file_number = self.cleaned_data.get('file_number')
        profile.ippis_number = self.cleaned_data.get('ippis_number')
        profile.current_employee_type = self.cleaned_data.get('current_employee_type')
        profile.current_department = self.cleaned_data.get('current_department')
        profile.current_unit = self.cleaned_data.get('current_unit')
        profile.current_grade_level = self.cleaned_data.get('current_grade_level')
        profile.current_step = self.cleaned_data.get('current_step')
        profile.date_of_appointment = self.cleaned_data.get('date_of_appointment')
        profile.date_of_assumption = self.cleaned_data.get('date_of_assumption')
        
        # Save profile
        profile.save()
        
        return user, profile, password


class EmployeeVerificationForm(forms.Form):
    """Form for HR staff to verify employee profile"""
    is_verified = forms.BooleanField(
        required=False,
        label="Verify Profile",
        help_text="Check this box if profile information is correct and verified"
    )
    verification_notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Verification Notes",
        help_text="Add any notes regarding the verification process"
    )
    flag_issues = forms.BooleanField(
        required=False,
        label="Flag Issues",
        help_text="Check this box if there are issues with the profile that need attention"
    )
    issue_description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Issue Description",
        help_text="Describe the issues requiring attention"
    )
    
    def clean(self):
        """Ensure either verification or issue flagging is complete"""
        cleaned_data = super().clean()
        is_verified = cleaned_data.get('is_verified')
        flag_issues = cleaned_data.get('flag_issues')
        issue_description = cleaned_data.get('issue_description')
        
        if is_verified and flag_issues:
            raise ValidationError("Cannot both verify and flag issues at the same time.")
        
        if flag_issues and not issue_description:
            raise ValidationError("Please provide a description of the issues.")
        
        return cleaned_data