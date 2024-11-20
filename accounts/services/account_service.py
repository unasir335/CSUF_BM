from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.shortcuts import redirect, render
from ..models import Account, Student, Faculty
from ..forms import CustomPasswordChangeForm
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class AccountService:
    @staticmethod
    @transaction.atomic
    def create_user(data):
        """Create a new user with associated role-specific profile"""
        try:
            user = Account.objects.create_user(**data)
            
            if data.get('is_student'):
                Student.objects.create(user=user, **data.get('student_data', {}))
            elif data.get('is_faculty'):
                Faculty.objects.create(user=user, **data.get('faculty_data', {}))
                
            return user
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise

    @staticmethod
    def change_password(request):
        """Handle password change request"""
        if request.method == 'POST':
            form = CustomPasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password was successfully updated!')
                return redirect('user_profile')
            else:
                messages.error(request, 'Please correct the error below.')
        else:
            form = CustomPasswordChangeForm(request.user)
            
        return render(request, 'accounts/change_password.html', {
            'form': form
        })

    @staticmethod
    @transaction.atomic
    def change_password_service(user, old_password, new_password):
        """Service method for password changes"""
        try:
            # Verify old password
            if not user.check_password(old_password):
                raise ValidationError("Current password is incorrect")
            
            # Set and save new password
            user.set_password(new_password)
            user.save()
            
            return True
        except Exception as e:
            logger.error(f"Password change error for user {user.id}: {str(e)}")
            raise

    @staticmethod
    @transaction.atomic
    def update_user(user, data):
        """Update user account information"""
        try:
            for field, value in data.items():
                if hasattr(user, field):
                    setattr(user, field, value)
            user.save()
            return user
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            raise

class UserCreationService(ABC):
    @abstractmethod
    def create_user(self, form_data):
        pass
    
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

