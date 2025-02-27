from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import PasswordResetRequestForm, SetPasswordForm
from .models import EmployeeProfile
import uuid
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse


def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Check if profile is completed
                if hasattr(user, 'employee_profile') and not user.employee_profile.is_profile_completed:
                    messages.info(request, "Please complete your profile information.")
                    return redirect('profile_complete')
                
                next_page = request.GET.get('next', 'dashboard')
                return redirect(next_page)
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    
    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')


@login_required
def change_password(request):
    """Allow users to change their password"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Updating the password logs out all sessions, so we need to re-login
            login(request, user)
            messages.success(request, "Your password was successfully updated!")
            return redirect('profile')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'auth/change_password.html', {'form': form})


def password_reset_request(request):
    """Handle password reset request"""
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            try:
                user = User.objects.get(email=email)
                token = str(uuid.uuid4())
                
                # In a real system, store this token in a model with an expiry time
                # For simplicity, we'll just use the session for now
                request.session['reset_token'] = token
                request.session['reset_email'] = email
                
                # Send email
                reset_url = request.build_absolute_uri(
                    reverse('password_reset_confirm') + f'?token={token}&email={email}'
                )
                
                send_mail(
                    'Password Reset Request',
                    f'Please click the following link to reset your password: {reset_url}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                
                messages.success(request, "Password reset instructions have been sent to your email.")
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, "No user is associated with this email.")
        else:
            messages.error(request, "Please enter a valid email.")
    else:
        form = PasswordResetRequestForm()
    
    return render(request, 'auth/password_reset_request.html', {'form': form})


def password_reset_confirm(request):
    """Handle password reset confirmation"""
    token = request.GET.get('token')
    email = request.GET.get('email')
    
    # In a real system, verify token from database
    if token != request.session.get('reset_token') or email != request.session.get('reset_email'):
        messages.error(request, "Invalid password reset link.")
        return redirect('login')
    
    if request.method == 'POST':
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(email=email)
                user.set_password(form.cleaned_data.get('new_password'))
                user.save()
                
                # Clear session data
                if 'reset_token' in request.session:
                    del request.session['reset_token']
                if 'reset_email' in request.session:
                    del request.session['reset_email']
                
                messages.success(request, "Your password has been reset successfully. You can now log in with your new password.")
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, "User not found.")
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = SetPasswordForm()
    
    return render(request, 'auth/password_reset_confirm.html', {'form': form})
