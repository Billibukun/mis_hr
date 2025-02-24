# core/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import *
from django.forms import inlineformset_factory


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent',
        'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent',
        'placeholder': 'Password'
    }))

class EmployeeProfileForm(forms.ModelForm):
    class Meta:
        model = EmployeeProfile
        # Exclude HR-only and automatically-set fields.  This is VERY important for security.
        exclude = ('user', 'is_hr_verified', 'verification_notes', 'verified_by', 'verification_date',
                   'created_by', 'created_at', 'modified_by', 'modified_at', 'is_profile_completed', 'date_of_retirement')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Tailwind CSS classes or other attributes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control' # Add a css class

class EmployeeDetailForm(forms.ModelForm):
    class Meta:
        model = EmployeeDetail
        exclude = ('employee_profile',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

EducationFormSet = inlineformset_factory(
    EmployeeProfile, EducationalQualification,
    fields=('qualification_type', 'course_of_study', 'area_of_study', 'institution', 'year_of_graduation'),
    extra=1,  # Number of extra forms to display
    can_delete=True,
    widgets={
        'qualification_type': forms.Select(attrs={'class': 'form-control'}),
        'course_of_study': forms.TextInput(attrs={'class': 'form-control'}),
        'area_of_study': forms.TextInput(attrs={'class': 'form-control'}),
        'institution': forms.TextInput(attrs={'class': 'form-control'}),
        'year_of_graduation': forms.NumberInput(attrs={'class': 'form-control'}),
    }
)


class NewsletterForm(forms.ModelForm):
    class Meta:
        model = Newsletter
        fields = ['title', 'content'] # author is set in the view
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control'}),
        }