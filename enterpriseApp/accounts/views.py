# Django imports
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.contrib import messages, auth
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from django.db import transaction
from django.views.generic import TemplateView
from django.db.models import Count, Sum
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic.edit import UpdateView
from checkout.models import Order

# Local imports
from .forms import (
    RegistrationForm, LoginForm, UserProfileForm,
    StudentRegistrationForm, FacultyRegistrationForm,
    CustomPasswordChangeForm,
)
from .models import Account, Student, Faculty, Address, UserProfile
from cart.models import Cart

# Python standard library imports
from abc import ABC, abstractmethod
import logging
import time
logger = logging.getLogger(__name__)

class AuthenticationService(ABC):
    @abstractmethod
    def authenticate(self, email, password):
        pass

    @abstractmethod
    def login(self, request, user):
        pass

    @abstractmethod
    def logout(self, request):
        pass

class DjangoAuthenticationService(AuthenticationService):
    def authenticate(self, email, password):
        return auth.authenticate(email=email, password=password)

    def login(self, request, user):
        return auth_login(request, user)

    def logout(self, request):
        return auth_logout(request)

class UserCreationService(ABC):
    @abstractmethod
    def create_user(self, form_data):
        pass

class AccountCreationService(UserCreationService):
    def create_user(self, form_data):
        username = form_data['email'].split("@")[0]
        user = Account.objects.create_user(
            first_name=form_data['first_name'],
            last_name=form_data['last_name'],
            email=form_data['email'],
            username=username,
            password=form_data['password']
        )
        user.phone_number = form_data['phone_number']
        user.save()
        return user

class StudentCreationService(UserCreationService):
    def create_user(self, form_data):
        account_service = AccountCreationService()
        user = account_service.create_user(form_data)
        student = Student.objects.create(
            user=user,
            student_id=form_data['student_id'],
            major=form_data['major'],
            year=form_data['year']
        )
        return student

class FacultyCreationService(UserCreationService):
    def create_user(self, form_data):
        account_service = AccountCreationService()
        user = account_service.create_user(form_data)
        faculty = Faculty.objects.create(
            user=user,
            faculty_id=form_data['faculty_id'],
            department=form_data['department'],
            position=form_data['position']
        )
        return faculty

class RegisterView(View):
    template_name = 'accounts/register.html'

    def get(self, request):
        form = RegistrationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful. You can now login.')
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.capitalize()}: {error}')
        return render(request, self.template_name, {'form': form})

class LoginView(View):
    template_name = 'accounts/login.html'

    def get(self, request):
        form = LoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = auth.authenticate(email=email, password=password)
            if user is not None:
                auth_login(request, user)
                messages.success(request, 'You are now logged in.')
                return redirect('home') # or dashboard
            else:
                messages.error(request, 'Invalid login credentials')
        return render(request, self.template_name, {'form': form})

class LogoutView(View):
    @method_decorator(login_required(login_url='login'))
    def get(self, request):
        # Clear the cart
        if 'cart_id' in request.session:
            try:
                cart = Cart.objects.get(id=request.session['cart_id'])
                cart.delete()
            except Cart.DoesNotExist:
                pass
            del request.session['cart_id']
        
        auth_logout(request)
        messages.success(request, 'You have been logged out.')
        return redirect('home')

class LogoutSuccessView(View):
    template_name = 'accounts/logout_success.html'

    def get(self, request):
        return render(request, self.template_name)

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/dashboard.html'

    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get orders for the user
        orders = Order.objects.filter(user=user).order_by('-created_at')
        
        # Calculate total spent correctly
        total_spent = sum(order.get_total_with_tax() for order in orders)
        
        context.update({
            'user': user,
            'full_name': user.get_full_name(),
            'email': user.email,
            'phone_number': getattr(user, 'phone_number', ''),
            'date_joined': user.date_joined,
            'last_login': user.last_login,
            'orders': orders,
            'orders_count': orders.count(),
            'total_spent': total_spent,
        })

        # Check for superuser and admin first
        if user.is_superuser:
            context['user_type'] = 'Superuser'
        elif user.is_admin:
            context['user_type'] = 'Admin'
        # Then check for student and faculty
        elif hasattr(user, 'student'):
            context.update({
                'user_type': 'Student',
                'student_id': user.student.student_id,
                'major': user.student.major,
                'year': user.student.year,
            })
        elif hasattr(user, 'faculty'):
            context.update({
                'user_type': 'Faculty',
                'faculty_id': user.faculty.faculty_id,
                'department': user.faculty.department,
                'position': user.faculty.position,
            })
        else:
            context['user_type'] = 'General User'

        return context
    
    
class UserProfileView(LoginRequiredMixin, UpdateView):
    form_class = UserProfileForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('user_profile')

    def get_object(self, queryset=None):
        # Get or create UserProfile
        return UserProfile.objects.get_or_create(user=self.request.user)[0]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['password_form'] = CustomPasswordChangeForm(self.request.user)
        return context

    def form_valid(self, form):
        user_profile = form.save(commit=False)
        user = self.request.user
        user.first_name = form.cleaned_data['first_name']
        user.last_name = form.cleaned_data['last_name']
        user.save()

        # Also create or update Address instance
        address, created = Address.objects.get_or_create(user=user)
        address.address_line1 = form.cleaned_data.get('address_line1', '')
        address.address_line2 = form.cleaned_data.get('address_line2', '')
        address.city = form.cleaned_data.get('city', '')
        address.state = form.cleaned_data.get('state', '')
        address.country = form.cleaned_data.get('country', '')
        address.zipcode = form.cleaned_data.get('zipcode', '')
        address.save()

        if 'profile_picture' in self.request.FILES:
            user_profile.delete_old_image()
            user_profile.profile_picture = self.request.FILES['profile_picture']

        user_profile.save()

        messages.success(self.request, 'Your profile has been updated successfully.')
        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        user_profile = self.get_object()
        
        # Get user's address data if it exists
        address = Address.objects.filter(user=self.request.user).first()
        
        initial.update({
            'first_name': self.request.user.first_name,
            'last_name': self.request.user.last_name,
            'phone_number': user_profile.phone_number,
            'address_line1': address.address_line1 if address else '',
            'address_line2': address.address_line2 if address else '',
            'city': address.city if address else '',
            'state': address.state if address else '',
            'country': address.country if address else '',
            'zipcode': address.zipcode if address else '',
        })
        return initial

    def form_valid(self, form):
        user_profile = form.save(commit=False)
        user = self.request.user
        user.first_name = form.cleaned_data['first_name']
        user.last_name = form.cleaned_data['last_name']
        user.save()

        if 'profile_picture' in self.request.FILES:
            # Delete old image before saving new one
            user_profile.delete_old_image()
            user_profile.profile_picture = self.request.FILES['profile_picture']

        user_profile.save()

        # Force refresh of the user object in the session
        self.request.session['_auth_user_id'] = user.id
        self.request.session.modified = True

        messages.success(self.request, 'Your profile has been updated successfully.')
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        if 'password_change' in request.POST:
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Important!
                messages.success(request, 'Your password was successfully updated!')
            else:
                for error in password_form.errors.values():
                    messages.error(request, error)
            return self.render_to_response(self.get_context_data(password_form=password_form))
        else:
            return super().post(request, *args, **kwargs)

  
@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('user_profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = CustomPasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {
        'form': form
    })
    

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'admin/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_admin
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        raise PermissionDenied("You don't have permission to access this page.")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all users except superusers
        users = Account.objects.filter(is_superuser=False).order_by('-date_joined')
        
        context.update({
            'users': users,
            'total_users': users.count(),
            'admin_users': users.filter(is_admin=True).count(),
            'student_users': users.filter(is_student=True).count(),
            'faculty_users': users.filter(is_faculty=True).count(),
            'recent_users': users.order_by('-date_joined')[:5],
        })
        return context
    
    def post(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.is_admin):
            raise PermissionDenied("You don't have permission to perform this action.")
            
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        
        try:
            user = Account.objects.get(id=user_id)
            
            if action == 'toggle_admin':
                user.is_admin = not user.is_admin
                user.save()
                messages.success(request, f'Admin status for {user.email} has been {"granted" if user.is_admin else "revoked"}.')
            
            elif action == 'toggle_active':
                user.is_active = not user.is_active
                user.save()
                messages.success(request, f'Account for {user.email} has been {"activated" if user.is_active else "deactivated"}.')
                
        except Account.DoesNotExist:
            messages.error(request, 'User not found.')
            
        return redirect('admin_dashboard')
   

