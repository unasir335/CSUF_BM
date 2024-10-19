# Django imports
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.contrib import messages, auth
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.views.generic import TemplateView
from django.db.models import Count, Sum
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic.edit import UpdateView

# Local imports
from .forms import (
    RegistrationForm, LoginForm, UserProfileForm,
    StudentRegistrationForm, FacultyRegistrationForm,
    CustomPasswordChangeForm,
)
from .models import Account, Student, Faculty, OrderHistory, UserProfile
from cart.models import Cart

# Python standard library imports
from abc import ABC, abstractmethod
import logging
import time
logger = logging.getLogger(__name__)

# ISP: AuthenticationService defines a focused interface for authentication
# OCP: New authentication methods can be added by implementing this interface
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

# LSP: DjangoAuthenticationService can be used wherever AuthenticationService is expected
class DjangoAuthenticationService(AuthenticationService):
    def authenticate(self, email, password):
        return auth.authenticate(email=email, password=password)

    def login(self, request, user):
        return auth_login(request, user)

    def logout(self, request):
        return auth_logout(request)

# ISP: UserCreationService defines a focused interface for user creation
# OCP: New user creation methods can be added by implementing this interface
class UserCreationService(ABC):
    @abstractmethod
    def create_user(self, form_data):
        pass

# SRP: AccountCreationService is responsible only for creating basic user accounts
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

# SRP: StudentCreationService is responsible only for creating student accounts
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

# SRP: FacultyCreationService is responsible only for creating faculty accounts
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

# SRP: RegisterView is responsible for handling user registration
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

# SRP: LoginView is responsible for handling user login
# DIP: Depends on AuthenticationService abstraction, not concrete implementation    
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

# SRP: LogoutView is responsible for handling user logout
# DIP: Depends on AuthenticationService abstraction, not concrete implementation
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

# SRP: LogoutSuccessView is responsible for displaying logout success message
class LogoutSuccessView(View):
    template_name = 'accounts/logout_success.html'

    def get(self, request):
        return render(request, self.template_name)

# SRP: DashboardView is responsible for displaying user dashboard
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        orders = OrderHistory.objects.filter(user=user).order_by('-order_date')  # Changed from '-created_at' to '-order_date'
        
        context.update({
            'user': user,
            'full_name': user.get_full_name(),
            'email': user.email,
            'phone_number': getattr(user, 'phone_number', ''),
            'date_joined': user.date_joined,
            'last_login': user.last_login,
            'orders_count': orders.count(),
            'total_spent': orders.aggregate(total=Sum('total_amount'))['total'] or 0,
        })

        #user type-specific information
        if hasattr(user, 'student'):
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

# SRP: UserProfileView is responsible for handling user profile updates
class UserProfileView(LoginRequiredMixin, UpdateView):
    form_class = UserProfileForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('user_profile')

    def get_object(self, queryset=None):
        return UserProfile.objects.get_or_create(user=self.request.user)[0]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['password_form'] = CustomPasswordChangeForm(self.request.user)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        user_profile = self.get_object()
        initial.update({
            'first_name': self.request.user.first_name,
            'last_name': self.request.user.last_name,
            'phone_number': user_profile.phone_number,
            'address_line1': user_profile.address_line1,
            'address_line2': user_profile.address_line2,
            'city': user_profile.city,
            'state': user_profile.state,
            'country': user_profile.country,
            'zipcode': user_profile.zipcode,
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

# @login_required
# def update_profile(request):
#     if request.method == 'POST':
#         form = UserProfileForm(request.POST, request.FILES, instance=request.user)
#         if form.is_valid():
#             user = form.save(commit=False)
#             if 'profile_picture' in request.FILES:
#                 user.profile_picture = request.FILES['profile_picture']
#             user.save()
            
#             # Force refresh of the user object in the session
#             request.session['_auth_user_id'] = user.id
#             request.session.modified = True
            
#             return redirect('user_profile')
#     else:
#         form = UserProfileForm(instance=request.user)
    
#     return render(request, 'edit_profile.html', {'form': form})  

  
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

