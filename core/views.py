# core/views.py
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView  # Import LoginView and LogoutView
from django.urls import reverse_lazy  # Import reverse_lazy for redirect URLs
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect # Import HttpResponseRedirect for cleaner redirects

from .forms import CustomLoginForm, EmployeeProfileForm, UserUploadForm  # Import CustomLoginForm
from .models import LGA, EmployeeProfile, Department, Designation, State

import json # Import json module
from django.core.serializers import serialize 


class CustomLoginView(LoginView):
    """
    Custom login view using the CustomLoginForm and rendering the login.html template.
    """
    form_class = CustomLoginForm
    template_name = 'login.html'  # Use your login.html template
    redirect_authenticated_user = True # Redirect logged in users away from login page

    def get_success_url(self):
        # Customize the redirect URL after successful login if needed
        return reverse_lazy('update_employee_profile') # Example: Redirect to admin index page

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login') # Redirect to login page after logout


@login_required
def update_employee_profile(request):
    employee_profile = get_object_or_404(EmployeeProfile, user=request.user)
    if request.method == 'POST':
        form = EmployeeProfileForm(request.POST, request.FILES, instance=employee_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!") # Success message
            return HttpResponseRedirect(reverse_lazy('profile_updated_success')) # Use HttpResponseRedirect
    else:
        form = EmployeeProfileForm(instance=employee_profile)
    return render(request, 'core/employee_profile_form.html', {'form': form})

def profile_updated_success(request):
    return render(request, 'core/profile_updated_success.html')

def upload_users_csv(request):
    if request.method == 'POST':
        form = UserUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            for row in reader:
                username = row.get('file_number')
                if not username:
                    messages.error(request, "Row missing 'file_number' which is used as username. Skipping row.")
                    continue

                password = row.get('password') or 'defaultpassword'
                first_name = row.get('first_name', '')
                last_name = row.get('last_name', '')
                middle_name = row.get('middle_name', '')
                email = row.get('email', '')
                file_number = row.get('file_number')
                ippis_number = row.get('ippis_number', '')
                date_of_birth_str = row.get('date_of_birth', '')
                sex = row.get('sex', '')
                marital_status = row.get('marital_status', '')
                department_name = row.get('staff_location/department', '')
                designation_name = row.get('current_designation', '')
                date_of_first_appointment_str = row.get('date_of_first_appointment', '')
                date_of_present_appointment_str = row.get('date_of_present_appointment', '')
                current_grade_level = row.get('current_grade_level', '')
                current_step = row.get('current_step', '')
                phone_number = row.get('phone_number', '')
                nin = row.get('nin', '')


                try:
                    with transaction.atomic():
                        user, created = User.objects.get_or_create(username=username, defaults={
                            'password': password,
                            'first_name': first_name,
                            'last_name': last_name,
                            'email': email,
                            'is_active': False,
                        })

                        if created:
                            user.set_password(password)
                            user.save()
                            messages.success(request, f"User {username} created successfully.")
                        else:
                            messages.warning(request, f"User {username} already exists. Profile will be updated.")


                        employee_profile, profile_created = EmployeeProfile.objects.get_or_create(user=user, defaults={'file_number': file_number})

                        employee_profile.file_number = file_number
                        employee_profile.ippis_number = ippis_number
                        employee_profile.middle_name = middle_name
                        employee_profile.sex = sex.upper() if sex else None
                        employee_profile.marital_status = marital_status.upper() if marital_status else None
                        employee_profile.phone_number = phone_number
                        employee_profile.nin = nin

                        employee_profile.date_of_birth = parse_date(date_of_birth_str) if date_of_birth_str else None
                        employee_profile.date_of_appointment = parse_date(date_of_first_appointment_str) if date_of_first_appointment_str else None
                        employee_profile.date_of_assumption = parse_date(date_of_present_appointment_str) if date_of_present_appointment_str else None

                        try:
                            department = Department.objects.get(name__iexact=department_name.strip())
                            employee_profile.current_department = department
                        except Department.DoesNotExist:
                            messages.warning(request, f"Department '{department_name}' not found for user {username}. Please create it in Departments.")
                            employee_profile.current_department = None

                        try:
                            designation = Designation.objects.get(name__iexact=designation_name.strip())
                            employee_profile.current_designation = designation
                        except Designation.DoesNotExist:
                            messages.warning(request, f"Designation '{designation_name}' not found for user {username}. Please create it in Designations.")
                            employee_profile.current_designation = None

                        employee_profile.current_grade_level = int(current_grade_level) if current_grade_level and current_grade_level.isdigit() else None
                        employee_profile.current_step = int(current_step) if current_step and current_step.isdigit() else None


                        employee_profile.save()

                except IntegrityError as e:
                    messages.error(request, f"Database Integrity Error for user {username}: {e}. Possibly duplicate file_number or NIN.")
                except ValueError as e:
                    messages.error(request, f"Value Error for user {username}: {e}. Check data types (e.g., dates, numbers).")
                except Exception as e:
                    messages.error(request, f"Error processing row for user {username}: {e}")

            messages.success(request, "CSV file processed successfully.") # General success message for CSV upload
            return HttpResponseRedirect(reverse_lazy('upload_users_success')) # Use HttpResponseRedirect
    else:
        form = UserUploadForm()
    context = {
        'form': form,
        'all_states': State.objects.all(),
        'all_lgas': LGA.objects.all(),
        'all_lgas_json': serialize('json', LGA.objects.all(), fields=('name', 'state')), # Serialize LGAs to JSON
    }
    return render(request, 'core/employee_profile_form.html', context)


def upload_users_success(request):
    return render(request, 'core/upload_success.html', {'upload_type': 'users'})