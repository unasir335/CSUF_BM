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
from PIL import Image

# Django core imports
from django.conf import settings
from django.contrib import messages, auth
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
    login
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.db.utils import OperationalError
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.views.generic.edit import UpdateView

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
from .models import Account, Student, Faculty, Address, UserProfile
from cart.models import Cart
from checkout.models import Order

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
  
# 10/25 transaction retry for race conditions (prevents Travelsal hack)
def retry_on_deadlock(func):
    def wrapper(*args, **kwargs):
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            try:
                return func(*args, **kwargs)
            except OperationalError as e:
                if 'deadlock' in str(e).lower():
                    attempt += 1
                    if attempt == max_attempts:
                        raise
                    time.sleep(0.1)
                else:
                    raise
    return wrapper

# 10/25 to prevent brute force hack attempts, limit keys passage/reset
def post(self, request, *args, **kwargs):
    # Rate limit key based on user and action
    rate_limit_key = f"admin_action_{request.user.id}"
    if cache.get(rate_limit_key, 0) >= 100:  # 100 actions per minute
        raise PermissionDenied("Too many actions. Please wait a minute before attempting again.")
    cache.incr(rate_limit_key, 1)
    cache.expire(rate_limit_key, 60)  # Reset after 1 minute
   
#10/25 added Validation that a user can only have one type (student, faculty, or admin)
class UserTypeValidator:
    @staticmethod
    def validate_user_type(user_data):
        user_types = [
            ('is_student', user_data.get('is_student', False)),
            ('is_faculty', user_data.get('is_faculty', False)),
            ('is_admin', user_data.get('is_admin', False))
        ]
        
        active_types = [utype for utype, value in user_types if value]
        
        if len(active_types) > 1:
            raise ValidationError(
                f"User cannot have multiple roles. Found: {', '.join(active_types)}"
            )
        
        return True

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

#10/25 Added to improve validation when accounts created by superuser
class AccountCreationService(UserCreationService):
    @transaction.atomic
    def create_user(self, form_data):
        # Validate user type before creation
        user_data = {
            'is_student': 'student_id' in form_data,
            'is_faculty': 'faculty_id' in form_data,
            'is_admin': form_data.get('is_admin', False)
        }
        
        UserTypeValidator.validate_user_type(user_data)
        
        username = form_data['email'].split("@")[0]
        user = Account.objects.create_user(
            first_name=form_data['first_name'],
            last_name=form_data['last_name'],
            email=form_data['email'],
            username=username,
            password=form_data['password']
        )
        
        # Set user type flags
        user.is_student = user_data['is_student']
        user.is_faculty = user_data['is_faculty']
        user.is_admin = user_data['is_admin']
        
        if user.is_admin and getattr(form_data, 'created_by_superuser', False):
            user.is_staff = True
        
        user.phone_number = form_data['phone_number']
        user.save()
        
        # Log user creation
        logger.info(
            f"Created new user: {user.email} | Type: {self.get_user_type(user_data)}"
        )
        
        return user
    
    @staticmethod
    def get_user_type(user_data):
        if user_data['is_student']:
            return 'Student'
        elif user_data['is_faculty']:
            return 'Faculty'
        elif user_data['is_admin']:
            return 'Admin'
        return 'Regular User'

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
            # Set user type based on email domain
            if email.endswith('@csu.fullerton.edu'):
                user.is_student = True
            elif email.endswith('@fullerton.edu'):
                user.is_faculty = True
            
            user.registration_complete = False
            user.save()
            
            # Log the user in
            login(request, user)
            
            # Redirect based on email domain
            if user.is_student:
                messages.info(request, 'Please complete your student profile to continue.')
                return redirect('student_registration')
            elif user.is_faculty:
                messages.info(request, 'Please complete your faculty profile to continue.')
                return redirect('faculty_registration')
            else:
                user.registration_complete = True
                user.save()
                messages.success(request, 'Registration successful. You can now login.')
                return redirect('home')
                
        return render(request, self.template_name, {'form': form})

#10/25 updated 
class StudentCreationService(UserCreationService):
    @transaction.atomic
    def create_user(self, form_data):
        # Add student flag to form data
        form_data['is_student'] = True
        
        account_service = AccountCreationService()
        user = account_service.create_user(form_data)
        
        student = Student.objects.create(
            user=user,
            student_id=form_data['student_id'],
            major=form_data['major'],
            year=form_data['year']
        )
        
        logger.info(f"Created new student profile for user: {user.email}")
        return student

#10/25 created
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
            
        # Get existing student profile data if it exists
        initial_data = {}
        if hasattr(request.user, 'student'):
            student = request.user.student
            initial_data = {
                'student_id': student.student_id if not student.student_id.startswith('STU') else '',
                'major': student.major,
                'year': student.year
            }
            
        form = StudentRegistrationForm(initial=initial_data)
        return render(request, self.template_name, {'form': form})
    
    @method_decorator(login_required)
    def post(self, request):
        if not request.user.is_student:
            messages.error(request, 'Access denied. This form is only for students.')
            return redirect('home')
        
        form = StudentRegistrationForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Get or update student profile
                    student, created = Student.objects.update_or_create(
                        user=request.user,
                        defaults={
                            'student_id': form.cleaned_data['student_id'],
                            'major': form.cleaned_data['major'],
                            'year': form.cleaned_data['year']
                        }
                    )
                    
                    # Mark registration as complete
                    request.user.registration_complete = True
                    request.user.save()
                    
                    messages.success(request, 'Student registration completed successfully.')
                    return redirect('home')
                    
            except Exception as e:
                logger.error(f"Student registration error: {str(e)}")
                messages.error(request, 'An error occurred during registration. Please try again.')
                return render(request, self.template_name, {'form': form})
                
        return render(request, self.template_name, {'form': form})

class FacultyRegistrationView(View):
    template_name = 'accounts/faculty_registration.html'
    
    @method_decorator(login_required)
    def get(self, request):
        if not request.user.is_faculty:
            messages.error(request, 'Access denied. This form is only for faculty members.')
            return redirect('home')
        
        if request.user.registration_complete:
            messages.info(request, 'Your registration is already complete.')
            return redirect('home')
            
        # Get existing faculty profile data if it exists
        initial_data = {}
        if hasattr(request.user, 'faculty'):
            faculty = request.user.faculty
            initial_data = {
                'faculty_id': faculty.faculty_id if not faculty.faculty_id.startswith('FAC') else '',
                'department': faculty.department,
                'position': faculty.position,
                'research_areas': faculty.research_areas,
            }
            
        form = FacultyRegistrationForm(initial=initial_data)
        return render(request, self.template_name, {'form': form})
    
    @method_decorator(login_required)
    def post(self, request):
        if not request.user.is_faculty:
            messages.error(request, 'Access denied. This form is only for faculty members.')
            return redirect('home')
        
        form = FacultyRegistrationForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Get or update faculty profile
                    faculty, created = Faculty.objects.update_or_create(
                        user=request.user,
                        defaults={
                            'faculty_id': form.cleaned_data['faculty_id'],
                            'department': form.cleaned_data['department'],
                            'position': form.cleaned_data['position'],
                            'research_areas': form.cleaned_data.get('research_areas', ''),
                        }
                    )
                    
                    # Mark registration as complete
                    request.user.registration_complete = True
                    request.user.save()
                    
                    messages.success(request, 'Faculty registration completed successfully.')
                    return redirect('home')
                    
            except Exception as e:
                logger.error(f"Faculty registration error: {str(e)}")
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
            
        form = FacultyRegistrationForm()
        return render(request, self.template_name, {'form': form})
    
    @method_decorator(login_required)
    def post(self, request):
        if not request.user.is_faculty:
            messages.error(request, 'Access denied. This form is only for faculty.')
            return redirect('home')
        
        form = FacultyRegistrationForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create faculty profile
                    Faculty.objects.create(
                        user=request.user,
                        faculty_id=form.cleaned_data['faculty_id'],
                        department=form.cleaned_data['department'],
                        position=form.cleaned_data['position']
                    )
                    
                    # Mark registration as complete
                    request.user.registration_complete = True
                    request.user.save()
                    
                    messages.success(request, 'Faculty registration completed successfully.')
                    return redirect('home')
                    
            except Exception as e:
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
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('user_profile')

    def get_form_class(self):
        # Return appropriate form class based on user type
        if hasattr(self.request.user, 'faculty'):
            return FacultyProfileForm
        elif hasattr(self.request.user, 'student'):
            return StudentProfileForm
        return UserProfileForm

    def get_object(self, queryset=None):
        return UserProfile.objects.get_or_create(user=self.request.user)[0]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['password_form'] = CustomPasswordChangeForm(self.request.user)
        
        # Add student information to context if user is a student
        if hasattr(self.request.user, 'student'):
            context['student'] = self.request.user.student  # Changed from student_info to student
        
        # Add faculty information to context if user is faculty
        if hasattr(self.request.user, 'faculty'):
            context['faculty'] = self.request.user.faculty  # Changed from faculty_info to faculty
        
        return context

    def get_initial(self):
        initial = super().get_initial()
        user = self.request.user
        user_profile = self.get_object()
        address = Address.objects.filter(user=user).first()
        
        initial.update({
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user_profile.phone_number,
            'address_line1': address.address_line1 if address else '',
            'address_line2': address.address_line2 if address else '',
            'city': address.city if address else '',
            'state': address.state if address else '',
            'country': address.country if address else '',
            'zipcode': address.zipcode if address else '',
        })

        # Add faculty information to initial data if user is faculty
        if hasattr(user, 'faculty'):
            initial.update({
                'faculty_id': user.faculty.faculty_id,
                'department': user.faculty.department,
                'position': user.faculty.position,
            })
        
        # Add student information to initial data if user is student
        elif hasattr(user, 'student'):
            initial.update({
                'student_id': user.student.student_id,
                'major': user.student.major,
                'year': str(user.student.year),
            })
            
        return initial

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user_profile = form.save(commit=False)
                user = self.request.user
                
                # Update basic user information
                user.first_name = form.cleaned_data['first_name']
                user.last_name = form.cleaned_data['last_name']
                if 'phone_number' in form.cleaned_data:
                    user.phone_number = form.cleaned_data['phone_number']
                user.save()

                # Update address
                address, created = Address.objects.get_or_create(user=user)
                address.address_line1 = form.cleaned_data.get('address_line1', '')
                address.address_line2 = form.cleaned_data.get('address_line2', '')
                address.city = form.cleaned_data.get('city', '')
                address.state = form.cleaned_data.get('state', '')
                address.country = form.cleaned_data.get('country', '')
                address.zipcode = form.cleaned_data.get('zipcode', '')
                address.save()

                # Update student information if user is a student
                if hasattr(user, 'student') and 'major' in form.cleaned_data:
                    student = user.student
                    student.major = form.cleaned_data['major']
                    student.year = int(form.cleaned_data['year'])
                    student.save()

                # Update faculty information if user is faculty
                if hasattr(user, 'faculty'):
                    faculty = user.faculty
                    faculty.department = form.cleaned_data.get('department')
                    faculty.position = form.cleaned_data.get('position')
                    faculty.save()

                # Handle profile picture
                if 'profile_picture' in self.request.FILES:
                    user_profile.delete_old_image()
                    user_profile.profile_picture = self.request.FILES['profile_picture']

                user_profile.save()

                messages.success(self.request, 'Your profile has been updated successfully.')
                return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f'Error updating profile: {str(e)}')
            return self.form_invalid(form)

    # Rest of your methods remain the same
    def post(self, request, *args, **kwargs):
        if 'password_change' in request.POST:
            return self.handle_password_change(request)
        elif 'security_update' in request.POST:
            return self.handle_security_update(request)
        return super().post(request, *args, **kwargs)

    def handle_password_change(self, request):
        password_form = CustomPasswordChangeForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
        else:
            for error in password_form.errors.values():
                messages.error(request, error)
        return self.render_to_response(self.get_context_data(password_form=password_form))

    def handle_security_update(self, request):
        security_question = request.POST.get('security_question')
        security_answer = request.POST.get('security_answer')
        
        if security_question and security_answer:
            user = request.user
            user.security_question = security_question
            user.security_answer = security_answer
            user.save()
            messages.success(request, 'Security settings updated successfully!')
        else:
            messages.error(request, 'Both security question and answer are required.')
        return redirect('user_profile')

    def form_invalid(self, form):
        print("Form errors:", form.errors)  # Debug: Print errors to console
        messages.error(self.request, 'Please correct the errors on this form.')
        return super().form_invalid(form)

# Rate limit uploads per user
def rate_limit_uploads(user_id, limit=10, period=60):
    cache_key = f"profile_upload_{user_id}"
    try:
        # Initialize the cache key if it doesn't exist
        if cache.get(cache_key) is None:
            cache.set(cache_key, 0, period)
        
        current = cache.get(cache_key, 0)
        if current >= limit:
            return False
            
        cache.incr(cache_key, 1)
        return True
    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        return True  # Fail open if cache is down

# Validate image file format, dimensions, and integrity
def validate_image(image_file):
    try:
        # Verify file is a valid image
        img = Image.open(image_file)
        img.verify()
        
        # Rewind the file
        image_file.seek(0)
        
        # Open again to check dimensions
        img = Image.open(image_file)
        
        # Check dimensions
        max_size = (2000, 2000)  # Maximum dimensions
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            raise ValidationError(f"Image dimensions must be no larger than {max_size[0]}x{max_size[1]} pixels")
            
        # Check if image format is supported
        if img.format.lower() not in ['jpeg', 'jpg', 'png', 'gif']:
            raise ValidationError("Unsupported image format. Use JPEG, PNG, or GIF")
            
        # Rewind file for future use
        image_file.seek(0)
        
        return True
        
    except (IOError, SyntaxError) as e:
        raise ValidationError("Invalid or corrupted image file")
    except Exception as e:
        raise ValidationError(f"Image validation error: {str(e)}")

# Handles profile picture updates with rate limiting and validation
@retry_on_deadlock
@login_required
@require_http_methods(["POST"])
def update_profile_picture(request):
    try:
        # Rate limiting check
        if not rate_limit_uploads(request.user.id):
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
            validate_image(file)
            
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
    
    # Create a new student role with temporary profile
    def setup_student_role(self, user):
        try:
            if not hasattr(user, 'student'):
                Student.objects.create(
                    user=user,
                    student_id=f"STU{user.id}",  # Temporary ID
                    major="",  # To be updated by user
                    year=2024  # Default year
                )
                messages.info(self.request, 
                    f'Student profile created for {user.email}. Additional details can be updated in Profile.')
            user.is_student = True
            user.save()
            return "Student"
        except Exception as e:
            messages.error(self.request, f'Error creating student profile: {str(e)}')
            raise

    # Create a new student role with temporary profile
    def setup_student_role(self, user):
        try:
            if hasattr(user, 'student'):
                user.student.delete()
            
            # Create new student profile with temporary data
            Student.objects.create(
                user=user,
                student_id=f"STU{user.id}",  # Temporary ID
                major="",  # To be updated by user
                year=2024  # Default year
            )
            
            # Set flags
            user.is_student = True
            user.registration_complete = False  # Reset registration status
            user.save()
            
            messages.info(self.request, 
                f'Student profile created for {user.email}. User will need to complete registration on next login.')
            return "Student"
            
        except Exception as e:
            messages.error(self.request, f'Error creating student profile: {str(e)}')
            raise

    # Create a new faculty role with temporary profile
    def setup_faculty_role(self, user):
        try:
            if hasattr(user, 'faculty'):
                user.faculty.delete()
            
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
            user.registration_complete = False  # Reset registration status
            user.save()
            
            messages.info(self.request, 
                f'Faculty profile created for {user.email}. User will need to complete registration on next login.')
            return "Faculty"
            
        except Exception as e:
            messages.error(self.request, f'Error creating faculty profile: {str(e)}')
            raise

    # Remove all role-specific data and permissions
    def clear_current_role(self, user):
        if hasattr(user, 'student'):
            user.student.delete()
        if hasattr(user, 'faculty'):
            user.faculty.delete()
        
        user.is_student = False
        user.is_faculty = False
        user.is_admin = False
        user.is_staff = False
        user.assigned_by_superuser = False
        user.registration_complete = True  # Regular users don't need registration
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


# Future
# TODO: User Profile, security question answer needs to be encrypted. - no need
