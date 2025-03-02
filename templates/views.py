# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from .forms import *
from .models import *
from django.contrib.auth.models import Group
from django.http import HttpResponseForbidden
from django.contrib.auth import logout

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from .models import EmployeeProfile, Department, Unit
from hr_modules.models import (
    Training, TrainingParticipant, 
    LeaveRequest, LeaveBalance, 
    Examination, ExaminationParticipant,
    PromotionCycle, PromotionNomination,
    TransferRequest, EducationalUpgrade, RetirementPlan
)
from task_management.models import Task, TaskStatus, TaskPriority
from file_management.models import File


@login_required
def dashboard(request):
    """Main dashboard view showing key metrics and recent activities"""
    today = timezone.now().date()
    user = request.user
    employee_profile = user.employee_profile
    
    # Employee stats
    employee_count = EmployeeProfile.objects.filter(user__is_active=True).count()
    new_employees = EmployeeProfile.objects.filter(
        date_of_assumption__gte=today - timedelta(days=30),
        user__is_active=True
    ).count()
    
    # Leave stats
    pending_leaves = LeaveRequest.objects.filter(status='PENDING').count()
    approved_leaves = LeaveRequest.objects.filter(
        status='APPROVED',
        approved_date__gte=today - timedelta(days=30)
    ).count()
    
    # My tasks
    my_tasks = Task.objects.filter(
        assigned_to=employee_profile,
        status__is_completed=False
    ).select_related('status', 'priority').order_by('due_date')[:5]
    
    my_tasks_count = Task.objects.filter(
        assigned_to=employee_profile,
        status__is_completed=False
    ).count()
    
    overdue_tasks = Task.objects.filter(
        assigned_to=employee_profile,
        status__is_completed=False,
        due_date__lt=today
    ).count()
    
    # Training stats
    upcoming_trainings = Training.objects.filter(
        start_date__gte=today,
        status='UPCOMING'
    ).count()
    
    ongoing_trainings = Training.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        status='ONGOING'
    ).count()
    
    # Available trainings
    available_trainings = Training.objects.filter(
        Q(status='UPCOMING') | Q(status='ONGOING'),
        start_date__gte=today - timedelta(days=7)
    ).order_by('start_date')[:3]
    
    # My leave balances
    leave_balances = LeaveBalance.objects.filter(
        employee=employee_profile,
        year=today.year
    ).select_related('leave_type')
    
    # Recent files
    recent_files = File.objects.filter(
        status='ACTIVE'
    ).select_related('created_by').order_by('-created_at')[:5]
    
    # Upcoming events - combine trainings, exams, etc.
    upcoming_events = []
    
    # Add trainings
    for training in Training.objects.filter(
        start_date__gte=today,
        start_date__lte=today + timedelta(days=30)
    ).order_by('start_date')[:3]:
        upcoming_events.append({
            'title': f"Training: {training.title}",
            'description': f"Location: {training.location}",
            'date': training.start_date,
        })
    
    # Add exams
    for exam in Examination.objects.filter(
        scheduled_date__gte=today,
        scheduled_date__lte=today + timedelta(days=30)
    ).order_by('scheduled_date')[:3]:
        upcoming_events.append({
            'title': f"Exam: {exam.title}",
            'description': f"Venue: {exam.venue}",
            'date': exam.scheduled_date,
        })
    
    # Add approved leave dates
    for leave in LeaveRequest.objects.filter(
        employee=employee_profile,
        status='APPROVED',
        start_date__gte=today
    ).order_by('start_date')[:3]:
        upcoming_events.append({
            'title': f"Leave: {leave.leave_type.name}",
            'description': f"{leave.start_date} to {leave.end_date}",
            'date': leave.start_date,
        })
    
    # Sort all events by date
    upcoming_events.sort(key=lambda x: x['date'])
    
    # Get only the next 5 events
    upcoming_events = upcoming_events[:5]
    
    context = {
        'employee_count': employee_count,
        'new_employees': new_employees,
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        'my_tasks': my_tasks,
        'my_tasks_count': my_tasks_count,
        'overdue_tasks': overdue_tasks,
        'upcoming_trainings': upcoming_trainings,
        'ongoing_trainings': ongoing_trainings,
        'available_trainings': available_trainings,
        'leave_balances': leave_balances,
        'recent_files': recent_files,
        'upcoming_events': upcoming_events,
    }
    
    return render(request, 'dashboard.html', context)


@login_required
def profile(request):
    """User profile view"""
    user = request.user
    employee_profile = user.employee_profile
    
    # Get related records
    trainings = TrainingParticipant.objects.filter(
        employee=employee_profile
    ).select_related('training').order_by('-training__start_date')[:5]
    
    leave_requests = LeaveRequest.objects.filter(
        employee=employee_profile
    ).order_by('-created_at')[:5]
    
    examinations = ExaminationParticipant.objects.filter(
        employee=employee_profile
    ).select_related('examination').order_by('-examination__scheduled_date')[:5]
    
    promotions = PromotionNomination.objects.filter(
        employee=employee_profile
    ).select_related('promotion_cycle').order_by('-promotion_cycle__year')[:5]
    
    transfers = TransferRequest.objects.filter(
        employee=employee_profile
    ).order_by('-created_at')[:5]
    
    educational_upgrades = EducationalUpgrade.objects.filter(
        employee=employee_profile
    ).order_by('-submission_date')[:5]
    
    # Try to get retirement plan
    try:
        retirement_plan = RetirementPlan.objects.get(employee=employee_profile)
    except RetirementPlan.DoesNotExist:
        retirement_plan = None
    
    context = {
        'employee_profile': employee_profile,
        'trainings': trainings,
        'leave_requests': leave_requests,
        'examinations': examinations,
        'promotions': promotions,
        'transfers': transfers,
        'educational_upgrades': educational_upgrades,
        'retirement_plan': retirement_plan,
    }
    
    return render(request, 'profile.html', context)


@login_required
def profile_edit(request):
    """Edit user profile"""
    user = request.user
    employee_profile = user.employee_profile
    
    if request.method == 'POST':
        # Handle form submission - update profile fields that are editable by the user
        employee_profile.phone_number = request.POST.get('phone_number', employee_profile.phone_number)
        employee_profile.contact_address = request.POST.get('contact_address', employee_profile.contact_address)
        
        # Update user fields
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        
        # Save changes
        employee_profile.save()
        user.save()
        
        messages.success(request, 'Profile updated successfully')
        return redirect('profile')
    
    context = {
        'employee_profile': employee_profile,
    }
    
    return render(request, 'profile_edit.html', context)


@login_required
def department_detail(request, pk):
    """View department details including employees"""
    department = get_object_or_404(Department, pk=pk)
    
    # Get employees in this department
    employees = EmployeeProfile.objects.filter(
        current_department=department,
        user__is_active=True
    ).select_related('user', 'current_designation')
    
    # Get units in this department
    units = Unit.objects.filter(department=department)
    
    # Get child departments
    child_departments = Department.objects.filter(parent=department)
    
    context = {
        'department': department,
        'employees': employees,
        'units': units,
        'child_departments': child_departments,
    }
    
    return render(request, 'department_detail.html', context)


@login_required
def employee_detail(request, pk):
    """View employee details"""
    employee_profile = get_object_or_404(EmployeeProfile, pk=pk)
    
    # Check if user has permission to view this employee
    # This would use the permission system we defined
    
    context = {
        'employee_profile': employee_profile,
    }
    
    return render(request, 'employee_detail.html', context) 