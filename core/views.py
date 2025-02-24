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

class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('home')

def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "You have been logged out successfully.")
    return redirect('login')


class HomeView(LoginRequiredMixin, View):  # Require login for the home view
    def get(self, request):
        # Get the latest 3 newsletters for the homepage
        newsletters = Newsletter.objects.all()[:3]
        context = {
            'newsletters': newsletters,
        }
        return render(request, 'home.html', context)



class EmployeeProfileUpdateView(LoginRequiredMixin, View):
    def get(self, request):
        profile = get_object_or_404(EmployeeProfile, user=request.user)
        profile_form = EmployeeProfileForm(instance=profile)
        detail, created = EmployeeDetail.objects.get_or_create(employee_profile=profile)
        detail_form = EmployeeDetailForm(instance=detail)
        education_formset = EducationFormSet(instance=profile)

        context = {
            'profile_form': profile_form,
            'detail_form': detail_form,
            'education_formset': education_formset,
        }
        return render(request, 'core/employee_profile_form.html', context)


    def post(self, request):
        profile = get_object_or_404(EmployeeProfile, user=request.user)
        profile_form = EmployeeProfileForm(request.POST, request.FILES, instance=profile)
        detail, created = EmployeeDetail.objects.get_or_create(employee_profile=profile)
        detail_form = EmployeeDetailForm(request.POST, instance=detail)
        education_formset = EducationFormSet(request.POST, instance=profile)

        if profile_form.is_valid() and detail_form.is_valid() and education_formset.is_valid():
            profile_form.save()
            detail_form.save()
            education_formset.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('home')  # Or redirect to a profile view
        else:
            messages.error(request, "Please correct the errors below.")
            context = {
                'profile_form': profile_form,
                'detail_form': detail_form,
                'education_formset': education_formset
            }
            return render(request, 'core/employee_profile_form.html', context)


# --- Newsletter Views ---
class NewsletterListView(LoginRequiredMixin,  ListView):
    model = Newsletter
    template_name = 'core/newsletter_list.html'
    context_object_name = 'newsletters'
    paginate_by = 10

class NewsletterCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Newsletter
    form_class = NewsletterForm
    template_name = 'core/newsletter_form.html'
    success_url = reverse_lazy('newsletter_list')

    def form_valid(self, form):
        form.instance.author = self.request.user  # Set the author
        messages.success(self.request, "Newsletter created successfully!")
        return super().form_valid(form)

    def test_func(self):
        return self.request.user.groups.filter(name='Information and Publications').exists() or self.request.user.is_superuser
    
    def handle_no_permission(self):
        return HttpResponseForbidden("You do not have permission to view this page.")


class NewsletterUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Newsletter
    form_class = NewsletterForm
    template_name = 'core/newsletter_form.html'
    success_url = reverse_lazy('newsletter_list')

    def form_valid(self, form):
        messages.success(self.request, "Newsletter updated successfully!")
        return super().form_valid(form)
    
    def test_func(self):
        return self.request.user.groups.filter(name='Information and Publications').exists() or self.request.user.is_superuser

    def handle_no_permission(self):
        return HttpResponseForbidden("You do not have permission to view this page.")


class NewsletterDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Newsletter
    template_name = 'core/newsletter_confirm_delete.html'  # You'll need this template
    success_url = reverse_lazy('newsletter_list')

    def form_valid(self, form):
        messages.success(self.request, "Newsletter Deleted successfully!")
        return super().form_valid(form)

    def test_func(self):
        return self.request.user.groups.filter(name='Information and Publications').exists() or self.request.user.is_superuser
    
    def handle_no_permission(self):
        return HttpResponseForbidden("You do not have permission to view this page.")

class NewsletterDetailView(LoginRequiredMixin, DetailView):
    model=Newsletter
    template_name = 'core/newsletter_detail.html'