# core/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Department, Unit, Zone, State, LGA, Bank, PFA, Designation, EmployeeProfile, EmployeeDetail, EducationalQualification
from django.contrib.auth.models import User

class CustomLoginForm(AuthenticationForm):
    """
    A custom login form for user authentication.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Username'})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = '__all__' # Or specify fields if you don't want all
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'parent': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional Parent Department'}),
        }

class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = '__all__'
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'department': forms.Select(attrs={'class': 'form-control'}),
        }

class ZoneForm(forms.ModelForm):
    class Meta:
        model = Zone
        fields = '__all__'
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class StateForm(forms.ModelForm):
    class Meta:
        model = State
        fields = '__all__'
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'zone': forms.Select(attrs={'class': 'form-control'}),
        }

class LGAForm(forms.ModelForm):
    class Meta:
        model = LGA
        fields = '__all__'
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.Select(attrs={'class': 'form-control'}),
        }

class BankForm(forms.ModelForm):
    class Meta:
        model = Bank
        fields = '__all__'
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class PFAForm(forms.ModelForm):
    class Meta:
        model = PFA
        fields = '__all__'
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class DesignationForm(forms.ModelForm):
    class Meta:
        model = Designation
        fields = '__all__'
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'grade_level': forms.NumberInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
        }

class EmployeeProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'})) # Add User fields here
    last_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = EmployeeProfile
        # Exclude user and user-related fields from the default EmployeeProfile fields
        exclude = ['user'] # exclude user, we will handle it in the form explicitly
        fields = [ # List the fields you want, excluding user, but including user related fields defined above
            'profile_picture', 'file_number', 'ippis_number', 'current_employee_type',
            'middle_name', 'sex', 'marital_status', 'date_of_birth', 'phone_number',
            'contact_address', 'lga_of_residence', 'state_of_residence',
            'lga_of_origin', 'state_of_origin', 'nin', 'brn',
            'date_of_appointment', 'date_of_documentation', 'date_of_assumption',
            'date_of_confirmation', 'date_of_retirement',
            'current_department', 'current_unit', 'current_zone', 'current_state',
            'current_grade_level', 'current_step', 'current_designation', 'current_cadre',
            'last_promotion_date', 'last_examination_date', 'is_profile_completed'
        ]
        widgets = {
            'profile_picture': forms.FileInput(attrs={'class': 'form-control-file'}),
            'file_number': forms.TextInput(attrs={'class': 'form-control'}),
            'ippis_number': forms.TextInput(attrs={'class': 'form-control'}),
            'current_employee_type': forms.Select(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'sex': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'marital_status': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'contact_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional'}),
            'lga_of_residence': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'state_of_residence': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'lga_of_origin': forms.Select(attrs={'class': 'form-control appearance-none', 'placeholder': 'Optional'}),  
            'state_of_origin': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'brn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'date_of_appointment': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
            'date_of_documentation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
            'date_of_assumption': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
            'date_of_confirmation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
            'date_of_retirement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
            'current_department': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'current_unit': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'current_zone': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'current_state': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'current_grade_level': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'current_step': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'current_designation': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'current_cadre': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'last_promotion_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
            'last_examination_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'YYYY-MM-DD'}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user: # Check if employee profile and user exist
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        employee_profile = super().save(commit=False) # Get the EmployeeProfile object but don't save yet
        user = employee_profile.user # Get the related User instance

        user.first_name = self.cleaned_data['first_name'] # Update User fields from form data
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.save() # Save the User object

        if commit:
            employee_profile.save() # Now save the EmployeeProfile object
        return employee_profile

class EmployeeDetailForm(forms.ModelForm):
    class Meta:
        model = EmployeeDetail
        fields = '__all__' # Or specify fields
        widgets = {
            'highest_formal_eduation': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'course_of_study': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'area_of_study': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'year_of_graduation': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'bank': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'account_type': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'pfa': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'pfa_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'leave_status': forms.Select(attrs={'class': 'form-control'}),
            'spouse_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'spouse_phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'spouse_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'spouse_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok1_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok1_phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok1_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok1_relationship': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok1_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok2_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok2_phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok2_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok2_relationship': forms.Select(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'nok2_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
        }

class EducationalQualificationForm(forms.ModelForm):
    class Meta:
        model = EducationalQualification
        fields = ['qualification_type', 'course_of_study', 'area_of_study', 'institution', 'year_of_graduation']
        widgets = {
            'qualification_type': forms.Select(attrs={'class': 'form-control'}),
            'course_of_study': forms.TextInput(attrs={'class': 'form-control'}),
            'area_of_study': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'institution': forms.TextInput(attrs={'class': 'form-control'}),
            'year_of_graduation': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        

class UserUploadForm(forms.Form):
    """
    Form for uploading a CSV file to create users.
    """
    csv_file = forms.FileField(
        label='User CSV file',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )

class EmployeeDetailUploadForm(forms.Form):
    """
    Form for uploading a TSV file to update employee details.
    """
    tsv_file = forms.FileField(
        label='Employee Details TSV file',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )