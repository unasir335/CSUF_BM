# Python standard library imports
import io
import json
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

# Third-party imports
from PIL import Image # type: ignore

# Django core imports
from django.conf import settings
from django.contrib import messages, auth
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.views.generic.edit import UpdateView
from functools import wraps
from django.utils.decorators import method_decorator
from .cache.handlers import CacheHandler

# Local application imports
from .forms import (
    CustomPasswordChangeForm,
    FacultyProfileForm,
    FacultyRegistrationForm,
    LoginForm,
    RegistrationForm,
    StudentProfileForm,
    StudentRegistrationForm,
    UserProfileForm,
)
from .models.account import Account
from .models.address import Address
from .models.faculty import Faculty
from .models.student import Student
from .models.profile import UserProfile
from .services.account_service import AccountCreationService, AccountService, UserCreationService, StudentCreationService
from .constants import Messages
from cart.models import Cart
from checkout.models import Order
from .decorators import (
    secure_upload,
    cache_profile
)
from .services.profile_service import ProfileService
from .services.account_service import AccountService
from .cache.handlers import CacheHandler
from .cache.keys import CacheKeyBuilder
from .mixins import UserTypeMixin, RateLimitMixin, CacheMixin
from typing import Optional, Dict, Any


logger = logging.getLogger(__name__)

# 10/25 for debugging.
class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        duration = time.time() - start_time
        logger.info(
            f'{request.method} {request.path} - {response.status_code} '
            f'[{duration:.2f}s]'
        )
        
        return response

# 10/25 to prevent brute force hack attempts, limit keys passage/reset
def post(self, request, *args, **kwargs):
    # Rate limit key based on user and action
    rate_limit_key = f"admin_action_{request.user.id}"
    if cache.get(rate_limit_key, 0) >= 100:  # 100 actions per minute
        raise PermissionDenied("Too many actions. Please wait a minute before attempting again.")
    cache.incr(rate_limit_key, 1)
    cache.expire(rate_limit_key, 60)  # Reset after 1 minute

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

class RegisterView(View):
    template_name = 'accounts/register.html'
    
    def get(self, request):
        form = RegistrationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
            
            # Create user account
            user = form.save(commit=False)
            
            # Check for existing profiles
            existing_student = Student.objects.filter(user__email=email).first()
            existing_faculty = Faculty.objects.filter(user__email=email).first()
            
            # Set user type based on email domain
            if email.endswith('@csu.fullerton.edu'):
                user.is_student = True
                if existing_student:  # If student profile exists
                    user.registration_complete = True
            elif email.endswith('@fullerton.edu'):
                user.is_faculty = True
                if existing_faculty:  # If faculty profile exists
                    user.registration_complete = True
            
            user.save()
            
            # Log the user in
            auth_login(request, user)
            
            # Handle redirection based on profile existence
            if user.is_student:
                if existing_student:
                    # Reattach existing student profile to new user
                    existing_student.user = user
                    existing_student.save()
                    messages.success(request, 'Welcome back! Your student profile has been restored.')
                    return redirect('home')
                else:
                    messages.info(request, 'Please complete your student profile to continue.')
                    return redirect('student_registration')
            elif user.is_faculty:
                if existing_faculty:
                    # Reattach existing faculty profile to new user
                    existing_faculty.user = user
                    existing_faculty.save()
                    messages.success(request, 'Welcome back! Your faculty profile has been restored.')
                    return redirect('home')
                else:
                    messages.info(request, 'Please complete your faculty profile to continue.')
                    return redirect('faculty_registration')
            else:
                user.registration_complete = True
                user.save()
                messages.success(request, 'Registration successful. You can now login.')
                return redirect('home')
                
        return render(request, self.template_name, {'form': form})

class StudentRegistrationView(View):
    template_name = 'accounts/student_registration.html'
    
    @method_decorator(login_required)
    def get(self, request):
        if not request.user.is_student:
            messages.error(request, 'Access denied. This form is only for students.')
            return redirect('home')
        
        if request.user.registration_complete:
            messages.info(request, 'Your registration is already complete.')
            return redirect('home')
            
        form = StudentRegistrationForm(user=request.user)
        return render(request, self.template_name, {'form': form})
    
    @method_decorator(login_required)
    def post(self, request):
        if not request.user.is_student:
            messages.error(request, 'Access denied. This form is only for students.')
            return redirect('home')
        
        form = StudentRegistrationForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Save student profile
                    student = form.save()
                    
                    # Mark registration as complete
                    request.user.registration_complete = True
                    request.user.save()
                    
                    # Clear stored profile data from cache after successful registration
                    cache_key = f"stored_profiles_{request.user.email}"
                    cache.delete(cache_key)
                    
                    messages.success(request, 'Student registration completed successfully.')
                    return redirect('home')
                    
            except Exception as e:
                logger.error(f"Student registration error: {str(e)}")
                messages.error(request, 'An error occurred during registration. Please try again.')
                return render(request, self.template_name, {'form': form})
                
        return render(request, self.template_name, {'form': form})

#10/25 created
class FacultyRegistrationView(View):
    template_name = 'accounts/faculty_registration.html'
    
    @method_decorator(login_required)
    def get(self, request):
        if not request.user.is_faculty:
            messages.error(request, 'Access denied. This form is only for faculty.')
            return redirect('home')
        
        if request.user.registration_complete:
            messages.info(request, 'Your registration is already complete.')
            return redirect('home')
            
        form = FacultyRegistrationForm(user=request.user)
        return render(request, self.template_name, {'form': form})
    
    @method_decorator(login_required)
    def post(self, request):
        if not request.user.is_faculty:
            messages.error(request, 'Access denied. This form is only for faculty.')
            return redirect('home')
        
        form = FacultyRegistrationForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create faculty profile
                    faculty = form.save(commit=False)
                    faculty.user = request.user
                    faculty.save()
                    
                    # Mark registration as complete
                    request.user.registration_complete = True
                    request.user.save()
                    
                    # Clear stored profile data from cache after successful registration
                    cache_key = f"stored_profiles_{request.user.email}"
                    cache.delete(cache_key)
                    
                    messages.success(request, 'Faculty registration completed successfully.')
                    return redirect('home')
                    
            except Exception as e:
                logger.error(f"Faculty registration error: {str(e)}")
                messages.error(request, 'An error occurred during registration. Please try again.')
                return render(request, self.template_name, {'form': form})
                
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
                
                # Check if registration is incomplete
                if not user.registration_complete:
                    if user.is_student:
                        messages.info(request, 'Please complete your student profile to continue.')
                        return redirect('student_registration')
                    elif user.is_faculty:
                        messages.info(request, 'Please complete your faculty profile to continue.')
                        return redirect('faculty_registration')
                
                messages.success(request, 'You are now logged in.')
                return redirect('home')
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

def dashboard(request):
    user_data = CacheHandler.get_cached_user_data(request.user.id)
    dashboard_data = CacheHandler.get_cached_dashboard_data(request.user.id)
    
    context = {**user_data, **dashboard_data}
    return render(request, 'accounts/dashboard.html', context)
    
class DashboardView(LoginRequiredMixin, CacheMixin, TemplateView):
    template_name = "accounts/dashboard.html"
    cache_timeout = 1800  # 30 minutes cache
    
    def get_cache_key(self) -> Optional[str]:
        """Override to provide dashboard-specific cache key"""
        if not self.request.user.is_authenticated:
            return None
        return CacheKeyBuilder.dashboard_data(self.request.user.id)
    
    def get_context_data(self, **kwargs):
        """Get dashboard context data"""
        if getattr(self, '_context_in_progress', False):
            # When generating fresh context
            context = super(CacheMixin, self).get_context_data(**kwargs)
        else:
            # Normal flow through caching
            context = super().get_context_data(**kwargs)
            
        user = self.request.user
        
        # Update order query to include all necessary related data
        orders = Order.objects.select_related('user').prefetch_related(
            'items',
            'items__product'
        ).filter(
            user=user,
            payment_status='PAID'
        ).order_by('-created_at')
        
        # Calculate total spent only for paid orders
        total_spent = sum(order.get_total_with_tax() for order in orders if order.payment_status == 'PAID')
        
        # Base context with user info
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

        # Add user type and role-specific information
        if user.is_superuser:
            context.update({
                'user_type': 'Superuser',
                'is_superuser': True
            })
        elif user.is_admin:
            context.update({
                'user_type': 'Admin',
                'is_admin': True
            })
        elif hasattr(user, 'student') and user.student:
            context.update({
                'user_type': 'Student',
                'student_id': user.student.student_id,
                'major': user.student.major,
                'year': user.student.year,
            })
        elif hasattr(user, 'faculty') and user.faculty:
            context.update({
                'user_type': 'Faculty',
                'faculty_id': user.faculty.faculty_id,
                'department': user.faculty.department,
                'position': user.faculty.position,
            })
        else:
            context['user_type'] = 'Regular User'
        
        # Debug logging to verify context data
        if settings.DEBUG:
            logger.debug(f"Dashboard context for user {user.id}: {context}")
        
        return context
 
class UserProfileView(LoginRequiredMixin, UserTypeMixin, RateLimitMixin, UpdateView):
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('user_profile')
    form_class = UserProfileForm
    
    @method_decorator(cache_profile(timeout=1800))
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add caching"""
        return super().dispatch(request, *args, **kwargs)
    
    def get_password_form(self):
        """Get the password change form"""
        return CustomPasswordChangeForm(self.request.user)
    
    def get_object(self):
        """Get or create the user profile"""
        if not hasattr(self, '_profile'):
            self._profile = UserProfile.objects.select_related(
                'user',
                'user__student',
                'user__faculty'
            ).get_or_create(user=self.request.user)[0]
        return self._profile

    def get_context_data(self, **kwargs):
        """Build context data"""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        try:
            profile = self.get_object()
            address = Address.objects.filter(user=user).select_related('user').first()
            
            context.update({
                'password_form': self.get_password_form(),
                'student': getattr(user, 'student', None),
                'faculty': getattr(user, 'faculty', None),
                'profile': profile,
                'address': address
            })
            
        except Exception as e:
            logger.error(f"Error building context data: {str(e)}")
            
        return context

    def get_form_class(self):
        """Get the appropriate form class based on user type"""
        user = self.request.user
        if hasattr(user, 'faculty'):
            return FacultyProfileForm
        elif hasattr(user, 'student'):
            return StudentProfileForm
        return UserProfileForm

    def get_form_kwargs(self):
        """Get form keyword arguments"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        """Get initial form data"""
        user = self.request.user
        profile = self.get_object()
        address = Address.objects.filter(user=user).select_related('user').first()
        
        initial = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': profile.phone_number if hasattr(profile, 'phone_number') else '',
            'address_line1': getattr(address, 'address_line1', ''),
            'address_line2': getattr(address, 'address_line2', ''),
            'city': getattr(address, 'city', ''),
            'state': getattr(address, 'state', ''),
            'country': getattr(address, 'country', ''),
            'zipcode': getattr(address, 'zipcode', ''),
        }
        
        if hasattr(user, 'faculty'):
            initial.update({
                'faculty_id': user.faculty.faculty_id,
                'department': user.faculty.department,
                'position': user.faculty.position,
            })
        elif hasattr(user, 'student'):
            initial.update({
                'student_id': user.student.student_id,
                'major': user.student.major,
                'year': str(user.student.year),
            })
            
        return initial

    @transaction.atomic
    def form_valid(self, form):
        """Handle valid form submission"""
        try:
            user = self.request.user
            profile_service = ProfileService()
            
            profile_service.update_profile(
                user=user,
                profile_data=form.cleaned_data,
                files=self.request.FILES
            )
            
            # Invalidate all user-related caches
            CacheHandler.invalidate_user_caches(user.id)
            messages.success(self.request, Messages.PROFILE_UPDATED)
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Profile update error for user {user.id}: {str(e)}")
            messages.error(self.request, 'Error updating profile. Please try again.')
            return self.form_invalid(form)

    def post(self, request, *args, **kwargs):
        """Handle POST requests"""
        try:
            if 'password_change' in request.POST:
                return self._handle_password_change()
            elif 'security_update' in request.POST:
                return self._handle_security_update()
            
            return super().post(request, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Post error for user {request.user.id}: {str(e)}")
            messages.error(request, 'An error occurred. Please try again.')
            return redirect('user_profile')

    def _handle_password_change(self):
        """Handle password change request"""
        response = AccountService.change_password(self.request)
        if 'success' in [m.level_tag for m in messages.get_messages(self.request)]:
            CacheHandler.invalidate_user_caches(self.request.user.id)
        return response

    def _handle_security_update(self):
        """Handle security question/answer update"""
        user = self.request.user
        question = self.request.POST.get('security_question')
        answer = self.request.POST.get('security_answer')
        
        if not (question and answer):
            messages.error(self.request, 'Both security question and answer are required.')
            return redirect('user_profile')
        
        try:
            with transaction.atomic():
                user.security_question = question
                user.security_answer = answer
                user.save()
                
                CacheHandler.invalidate_user_caches(user.id)
                messages.success(self.request, 'Security settings updated successfully!')
                
        except Exception as e:
            logger.error(f"Security update error for user {user.id}: {str(e)}")
            messages.error(self.request, 'Error updating security settings.')
            
        return redirect('user_profile')   
    
# Handles profile picture updates with rate limiting and validation
@secure_upload('profile_picture', limit=5, period=3600)
def update_profile_picture(request):
    try:
        # Update rate limiting check
        if not ProfileService.rate_limit_uploads(request.user.id):
            return JsonResponse({
                'error': 'Too many upload attempts. Please wait a minute and try again.'
            }, status=429)

        # Handle profile picture removal
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
                if data.get('clear'):
                    with transaction.atomic():
                        profile = request.user.userprofile
                        default_image = 'profile_pics/300x150.png'
                        
                        # Delete old picture if it exists and isn't the default
                        if profile.profile_picture and profile.profile_picture.name != default_image:
                            try:
                                default_storage.delete(profile.profile_picture.name)
                            except Exception as e:
                                logger.error(f"Error deleting file: {e}")
                        
                        # Set default image
                        profile.profile_picture = default_image
                        profile.save()
                        
                        # Construct the full URL for the default image
                        default_url = f"{settings.STATIC_URL}{default_image}"
                        
                        return JsonResponse({
                            'success': True,
                            'message': 'Profile picture removed',
                            'path': default_url
                        })
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Handle new profile picture upload
        if 'profile_picture' not in request.FILES:
            return JsonResponse({
                'error': 'No file uploaded'
            }, status=400)
            
        file = request.FILES['profile_picture']
        
        # Basic validations
        if file.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            return JsonResponse({
                'error': f'File size must be less than {settings.FILE_UPLOAD_MAX_MEMORY_SIZE // (1024*1024)}MB'
            }, status=400)

        allowed_types = ['image/jpeg', 'image/png', 'image/gif']
        if file.content_type not in allowed_types:
            return JsonResponse({
                'error': 'Please upload a JPG, PNG or GIF file'
            }, status=400)

        try:
            # Validate image file
            ProfileService.validate_image(file)

            
            with transaction.atomic():
                # Generate safe filename
                ext = Path(file.name).suffix.lower()
                filename = f"users/profile_pictures/user_{request.user.id}_{uuid.uuid4()}{ext}"
                
                # Save the new file
                saved_path = default_storage.save(filename, file)
                
                # Update user profile
                profile = request.user.userprofile
                old_picture = profile.profile_picture.name if profile.profile_picture else None
                
                profile.profile_picture = saved_path
                profile.save()

                # Delete old picture if it exists and isn't the default
                if old_picture and old_picture != 'profile_pics/300x150.png':
                    try:
                        default_storage.delete(old_picture)
                    except Exception as e:
                        logger.error(f"Error deleting old file: {e}")

                # Log the change
                LogEntry.objects.log_action(
                    user_id=request.user.id,
                    content_type_id=ContentType.objects.get_for_model(profile.__class__).pk,
                    object_id=profile.pk,
                    object_repr=str(profile),
                    action_flag=CHANGE,
                    change_message='Updated profile picture'
                )

                # Return the new URL
                url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
                return JsonResponse({
                    'success': True,
                    'message': 'Profile picture updated successfully',
                    'path': url
                })

        except ValidationError as ve:
            return JsonResponse({'error': str(ve)}, status=400)
        except Exception as e:
            logger.error(f"Error saving profile picture: {e}")
            return JsonResponse({
                'error': 'Error saving profile picture. Please try again.'
            }, status=500)

    except Exception as e:
        logger.error(f"Unexpected error in update_profile_picture: {e}")
        return JsonResponse({
            'error': 'An unexpected error occurred. Please try again.'
        }, status=500)

# User profile change password handler
@login_required
def change_password(request):
    """
    View function that handles password change requests by delegating to AccountService.
    Requires user to be logged in.
    
    View: Handles HTTP request/response cycle
    - Authentication check
    - Request handling
    - Logging
    - Cache invalidation
    - User messages
    - Redirects
    """
    if not request.user.is_authenticated:
        messages.error(request, 'You must be logged in to change your password.')
        return redirect('login')
        
    # Use the existing service method to handle the password change
    try:
        response = AccountService.change_password(request)
        
        # Log the successful password change
        if request.method == 'POST' and response.url == reverse_lazy('user_profile'):
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(request.user.__class__).pk,
                object_id=request.user.pk,
                object_repr=str(request.user),
                action_flag=CHANGE,
                change_message='Changed password via profile'
            )
            
            # Invalidate any cached user data
            CacheHandler.invalidate_user_caches(request.user.id)
            
        return response
        
    except Exception as e:
        logger.error(f"Password change error for user {request.user.id}: {str(e)}")
        messages.error(request, 'An error occurred while changing your password. Please try again.')
        return redirect('user_profile')

      
class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'admin/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_admin
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        raise PermissionDenied("You don't have permission to access this page.")

    # Helper method to convert wildcard search patterns to regex
    def convert_wildcard_to_regex(self, search_term):
        escaped = re.escape(search_term).replace('\\*', '.*')
        return f'^{escaped}$'
    
    # User search functionality
    def search_users(self, search_term):
        base_query = Account.objects.filter(is_superuser=False)
        
        if not search_term:
            return base_query
            
        if '*' in search_term:
            regex_pattern = self.convert_wildcard_to_regex(search_term)
            return base_query.filter(
                Q(email__iregex=regex_pattern) |
                Q(username__iregex=regex_pattern) |
                Q(first_name__iregex=regex_pattern) |
                Q(last_name__iregex=regex_pattern)
            )
        
        return base_query.filter(
            Q(email__icontains=search_term) |
            Q(username__icontains=search_term) |
            Q(first_name__icontains=search_term) |
            Q(last_name__icontains=search_term)
        )
    
    # Change role to admin
    def setup_admin_role(self, user):
        try:
            # Clear any existing role-specific attributes first
            if hasattr(user, 'student'):
                user.student.delete()
            if hasattr(user, 'faculty'):
                user.faculty.delete()
                
            # Set admin flags
            user.is_admin = True
            user.is_staff = True  # Staff status is typically needed for admin access
            user.assigned_by_superuser = self.request.user.is_superuser
            user.registration_complete = True  # Admins don't need additional registration
            user.save()
            
            messages.info(self.request, 
                f'Admin role granted to {user.email}. {"This admin was assigned by a superuser." if user.assigned_by_superuser else ""}')
            return "Admin"
            
        except Exception as e:
            messages.error(self.request, f'Error creating admin role: {str(e)}')
            raise
    
    # Create a new student role with temporary profile
    def setup_student_role(self, user):
        """Create a new student role with temporary profile or restore existing"""
        try:
            # Check for existing student profile
            existing_profile = Student.objects.filter(user__email=user.email).first()
            
            if existing_profile:
                # Reattach existing profile
                existing_profile.user = user
                existing_profile.save()
            else:
                # Create new student profile with temporary data
                Student.objects.create(
                    user=user,
                    student_id=f"STU{user.id}",  # Temporary ID
                    major="",  # To be updated by user
                    year=2024  # Default year
                )
                
            # Set flags
            user.is_student = True
            user.registration_complete = bool(existing_profile)  # Complete if profile exists
            user.save()
            
            messages.info(
                self.request, 
                'Student profile restored for {}'.format(user.email) if existing_profile else
                'Student profile created for {}. User will need to complete registration on next login.'.format(user.email)
            )
            return "Student"
                
        except Exception as e:
            messages.error(self.request, f'Error creating student profile: {str(e)}')
            raise

    def setup_faculty_role(self, user):
        """Create a new faculty role with temporary profile or restore existing"""
        try:
            # Check for existing faculty profile
            existing_profile = Faculty.objects.filter(user__email=user.email).first()
            
            if existing_profile:
                # Reattach existing profile
                existing_profile.user = user
                existing_profile.save()
            else:
                # Create new faculty profile with temporary data
                Faculty.objects.create(
                    user=user,
                    faculty_id=f"FAC{user.id}",  # Temporary ID
                    department="",  # To be updated by user
                    position="",  # To be updated by user
                    research_areas="",
                )
                
            # Set flags
            user.is_faculty = True
            user.registration_complete = bool(existing_profile)  # Complete if profile exists
            user.save()
            
            messages.info(
                self.request, 
                'Faculty profile restored for {}'.format(user.email) if existing_profile else
                'Faculty profile created for {}. User will need to complete registration on next login.'.format(user.email)
            )
            return "Faculty"
                
        except Exception as e:
            messages.error(self.request, f'Error creating faculty profile: {str(e)}')
            raise

    
    def clear_current_role(self, user):
        """Remove role but preserve profile data"""
        # Store existing profile data before removing roles
        stored_profiles = {}
        
        if hasattr(user, 'student'):
            stored_profiles['student'] = {
                'student_id': user.student.student_id,
                'major': user.student.major,
                'year': user.student.year
            }
            user.student.delete()
            
        if hasattr(user, 'faculty'):
            stored_profiles['faculty'] = {
                'faculty_id': user.faculty.faculty_id,
                'department': user.faculty.department,
                'position': user.faculty.position,
                'research_areas': getattr(user.faculty, 'research_areas', '')
            }
            user.faculty.delete()
        
        # Store the profiles in cache for future use
        cache_key = f"stored_profiles_{user.email}"
        cache.set(cache_key, stored_profiles, timeout=None)  # No timeout
        
        # Clear role flags
        user.is_student = False
        user.is_faculty = False
        user.is_admin = False
        user.is_staff = False
        user.assigned_by_superuser = False
        user.registration_complete = False  # Reset registration status
        user.save()
        
        return "Regular User"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_term = self.request.GET.get('search', '').strip()
        
        users = self.search_users(search_term)
        
        # Identify protected users that regular admins can't modify
        if not self.request.user.is_superuser:
            context['unmodifiable_users'] = users.filter(
                Q(is_superuser=True) |
                Q(is_admin=True, assigned_by_superuser=True)
            ).values_list('id', flat=True)
        
        context.update({
            'users': users,
            'total_users': users.count(),
            'admin_users': users.filter(is_admin=True).count(),
            'student_users': users.filter(is_student=True).count(),
            'faculty_users': users.filter(is_faculty=True).count(),
            'recent_users': users.order_by('-date_joined')[:5],
            'search_term': search_term,
            'is_superuser': self.request.user.is_superuser,
        })
        return context
    
    # Validate role changes
    def validate_role_change(self, user, new_role):
        # Check if user can be modified
        if user.is_superuser:
            return False, "Superuser accounts cannot be modified"
        
        if user.assigned_by_superuser and not self.request.user.is_superuser:
            return False, "Protected admin accounts can only be modified by superusers"
            
        # Validate that user won't have multiple roles
        role_count = sum([
            new_role == 'admin',
            new_role == 'faculty',
            new_role == 'student'
        ])
        if role_count > 1:
            return False, "User cannot have multiple roles"
        
        return True, ""

    # Handle role change process
    @transaction.atomic
    def handle_role_change(self, user, new_role):
        try:
            # Validate the role change
            is_valid, message = self.validate_role_change(user, new_role)
            if not is_valid:
                return False, message

            # Clear existing role first
            self.clear_current_role(user)
            
            # Set new role
            if new_role == 'admin':
                role_name = self.setup_admin_role(user)
            elif new_role == 'faculty':
                role_name = self.setup_faculty_role(user)
            elif new_role == 'student':
                role_name = self.setup_student_role(user)
            else:  # regular user
                role_name = "Regular User"
            
            return True, f"User role successfully changed to {role_name}"
            
        except Exception as e:
            return False, str(e)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # Check permissions
        if not (request.user.is_superuser or request.user.is_admin):
            raise PermissionDenied("You don't have permission to perform this action.")
        
        # Rate limiting with proper initialization
        rate_limit_key = f"admin_action_{request.user.id}"
        try:
            # Get current count or initialize to 0 if not exists
            current_count = cache.get(rate_limit_key, 0)
            
            # Check if limit exceeded
            if current_count >= 100:
                raise PermissionDenied("Too many actions. Please wait a minute.")
            
            # Increment and set with expiry if not exists
            cache.set(rate_limit_key, current_count + 1, 60)  # 60 seconds timeout
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Continue processing if cache fails
        
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        
        try:
            user = Account.objects.select_for_update().get(id=user_id)
            
            # Handle role changes
            if action in ['make_admin', 'make_faculty', 'make_student', 'make_regular']:
                success, message = self.handle_role_change(
                    user, 
                    action.replace('make_', '')
                )
                
                if success:
                    self.log_admin_action(request.user, message, user)
                    messages.success(request, message)
                else:
                    messages.error(request, f"Error changing role: {message}")
            
            # Handle account activation/deactivation
            elif action == 'toggle_active':
                if not request.user.is_superuser and user.assigned_by_superuser:
                    messages.error(request, "You cannot modify protected admin accounts.")
                    return redirect('admin_dashboard')
                
                user.is_active = not user.is_active
                user.save()
                
                status = "activated" if user.is_active else "deactivated"
                self.log_admin_action(
                    request.user,
                    f"Account {status}",
                    user
                )
                messages.success(request, f"User account has been {status}.")
            
            # Handle user deletion
            elif action == 'delete_user':
                if user.is_superuser:
                    messages.error(request, "Superuser accounts cannot be deleted.")
                elif user.assigned_by_superuser and not request.user.is_superuser:
                    messages.error(request, "Protected admin accounts can only be deleted by superusers.")
                else:
                    user_email = user.email
                    self.log_admin_action(request.user, "Deleted user account", user)
                    user.delete()
                    messages.success(request, f"User {user_email} has been deleted.")
            
        except Account.DoesNotExist:
            messages.error(request, "User not found.")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            
        return redirect('admin_dashboard')
    
    # Log administrative actions
    def log_admin_action(self, admin_user, action, affected_user):
        LogEntry.objects.create(
            user_id=admin_user.id,
            content_type_id=ContentType.objects.get_for_model(Account).id,
            object_id=affected_user.id,
            object_repr=str(affected_user),
            action_flag=CHANGE,
            change_message=f"Admin action: {action}"
        )
               
class PasswordRecoveryView(View):
    template_name = 'accounts/password_recovery.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email')
        try:
            user = Account.objects.get(email=email)
            # Store the email in session for the next step
            request.session['recovery_email'] = email
            return redirect('security_question')
        except Account.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
            return render(request, self.template_name)

class SecurityQuestionView(View):
    template_name = 'accounts/security_question.html'

    def get(self, request):
        if 'recovery_email' not in request.session:
            return redirect('password_recovery')
        
        email = request.session['recovery_email']
        try:
            user = Account.objects.get(email=email)
            return render(request, self.template_name, {
                'security_question': user.security_question
            })
        except Account.DoesNotExist:
            return redirect('password_recovery')

    def post(self, request):
        if 'recovery_email' not in request.session:
            return redirect('password_recovery')

        email = request.session['recovery_email']
        answer = request.POST.get('security_answer')
        
        try:
            user = Account.objects.get(email=email)
            if user.security_answer == answer:
                # Store user ID in session for password reset
                request.session['recovery_user_id'] = user.id
                return redirect('reset_password')
            else:
                messages.error(request, 'Incorrect answer.')
                return render(request, self.template_name, {
                    'security_question': user.security_question
                })
        except Account.DoesNotExist:
            return redirect('password_recovery')

class ResetPasswordView(View):
    template_name = 'accounts/reset_password.html'

    def get(self, request):
        if 'recovery_user_id' not in request.session:
            return redirect('password_recovery')
        return render(request, self.template_name)

    def post(self, request):
        if 'recovery_user_id' not in request.session:
            return redirect('password_recovery')

        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords don't match.")
            return render(request, self.template_name)

        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, self.template_name)

        try:
            user = Account.objects.get(id=request.session['recovery_user_id'])
            user.set_password(password1)
            user.save()
            
            # Clear recovery sessions
            del request.session['recovery_email']
            del request.session['recovery_user_id']
            
            messages.success(request, 'Password has been reset successfully. You can now login.')
            return redirect('login')
        except Account.DoesNotExist:
            return redirect('password_recovery')
        



# TODO: ADD Search for orders/order number, or product
# TODO: ADD search for entire website
# TODO: see all orders, do shipped, include shipper and tracking number. - admins
# TODO: SOME items should be digital, and those should be marked as DELIVERED upon processing. In details page provide 
# an activation code or some sort of content.
# TODO: Admin dashboard should also include sales statistics from all users- Pandas

