# models/account.py

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from django.db import models, transaction
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator  # Added correct import
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class UserManager(ABC):
    """
    Abstract base class defining the interface for user management operations.
    """
    @abstractmethod
    def create_user(self, first_name: str, last_name: str, 
                   username: str, email: str, password: Optional[str] = None) -> 'Account':
        pass

    @abstractmethod
    def create_superuser(self, first_name: str, last_name: str, 
                        email: str, username: str, password: str) -> 'Account':
        pass

class MyAccountManager(BaseUserManager):
    """
    Custom account manager implementing the UserManager interface with extended functionality.
    """
    def validate_user_type(self, **kwargs) -> bool:
        """
        Validate that a user can only have one role.
        
        Args:
            **kwargs: Keyword arguments containing role flags
            
        Returns:
            bool: True if validation passes
            
        Raises:
            ValidationError: If multiple roles are detected
        """
        role_count = sum([
            kwargs.get('is_student', False),
            kwargs.get('is_faculty', False),
            kwargs.get('is_admin', False)
        ])
        
        if role_count > 1:
            raise ValidationError("User cannot have multiple roles (student, faculty, or admin)")
        
        return True

    @transaction.atomic
    def create_user(self, username: str, email: str, 
                   password: Optional[str] = None, **extra_fields) -> 'Account':
        """
        Create and save a new user account.
        
        Args:
            username: Unique username
            email: User's email address
            password: Optional password
            **extra_fields: Additional fields for the user
            
        Returns:
            Account: The created user account
            
        Raises:
            ValueError: If required fields are missing
            ValidationError: If user type validation fails
        """
        if not email:
            raise ValueError('Users must have an email address')
        if not username:
            raise ValueError('Users must have a username')
        
        # Validate user type
        self.validate_user_type(**extra_fields)
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        
        # Handle admin assignment by superuser
        if extra_fields.get('is_admin', False):
            from threading import local
            _thread_locals = local()
            current_user = getattr(_thread_locals, 'current_user', None)
            
            if current_user and current_user.is_superuser:
                user.assigned_by_superuser = True
                user.is_staff = True
        
        try:
            user.full_clean()
            user.save(using=self._db)
            
            logger.info(
                f"Created new user: {email} | Roles: {self.get_user_roles(user)}"
            )
            
            return user
            
        except ValidationError as e:
            logger.error(f"User creation failed for {email}: {str(e)}")
            raise
    
    @transaction.atomic
    def create_superuser(self, username: str, email: str, 
                        password: str, **extra_fields) -> 'Account':
        """
        Create and save a new superuser account.
        
        Args:
            username: Unique username
            email: User's email address
            password: Required password
            **extra_fields: Additional fields for the user
            
        Returns:
            Account: The created superuser account
            
        Raises:
            ValueError: If required superuser flags are not set
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_admin', True)
        extra_fields.setdefault('assigned_by_superuser', True)
        
        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser must have is_superuser=True.')
            
        return self.create_user(username, email, password, **extra_fields)
    
    def get_user_roles(self, user: 'Account') -> list:
        """
        Get list of user's active roles.
        
        Args:
            user: The user account to check
            
        Returns:
            list: List of active role names
        """
        roles = []
        if user.is_superuser:
            roles.append('Superuser')
        if user.is_admin:
            roles.append('Admin')
        if user.is_student:
            roles.append('Student')
        if user.is_faculty:
            roles.append('Faculty')
        return roles if roles else ['Regular User']

class Account(AbstractBaseUser, PermissionsMixin):
    """
    Custom user account model with role-based permissions and profile data.
    """
    # Basic user information
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    username = models.CharField(max_length=50, unique=True, db_index=True)
    email = models.EmailField(max_length=100, unique=True, db_index=True)
    
    # Contact information
    phone_regex = RegexValidator(  # Fixed: Using correctly imported RegexValidator
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    
    # Profile picture
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        default='static/profile_pics/200x200.png',
        null=True,
        blank=True
    )
    
    # Security fields
    security_question = models.CharField(max_length=255, blank=True, default='')
    security_answer = models.CharField(max_length=255, blank=True, default='')
    
    # Role and status flags
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)
    is_faculty = models.BooleanField(default=False)
    registration_complete = models.BooleanField(default=False)
    assigned_by_superuser = models.BooleanField(default=False)
    
    # Timestamps
    date_joined = models.DateTimeField(auto_now_add=True, db_index=True)
    last_login = models.DateTimeField(auto_now=True)
    
    # Model configuration
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    objects = MyAccountManager()
    
    class Meta:
        indexes = [
            models.Index(fields=['email', 'username']),
            models.Index(fields=['is_active', 'is_staff']),
        ]
        verbose_name = 'account'
        verbose_name_plural = 'accounts'
    
    def clean(self) -> None:
        """
        Validate the model instance.
        
        Raises:
            ValidationError: If validation fails
        """
        super().clean()
        
        # Validate user type
        role_count = sum([
            self.is_student,
            self.is_faculty,
            self.is_admin
        ])
        
        if role_count > 1:
            raise ValidationError({
                'user_type': "User cannot have multiple roles (student, faculty, or admin)"
            })
        
        # Validate superuser-related fields
        if self.is_superuser:
            self.is_staff = True
            self.is_admin = True
            self.assigned_by_superuser = True
        
        # Validate staff status for admin users
        if self.is_admin and self.assigned_by_superuser:
            self.is_staff = True
    
    def save(self, *args, **kwargs) -> None:
        """
        Save the model instance after validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        return self.email
    
    def get_full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'
    
    def get_short_name(self) -> str:
        return self.first_name
    
    @property
    def role(self) -> str:
        """Get the user's primary role."""
        if self.is_superuser:
            return 'Superuser'
        elif self.is_admin:
            return 'Admin'
        elif self.is_student:
            return 'Student'
        elif self.is_faculty:
            return 'Faculty'
        return 'Regular User'
    
    def has_perm(self, perm: str, obj: Optional[Any] = None) -> bool:
        """Check if user has a specific permission."""
        return self.is_superuser or self.is_admin
    
    def has_module_perms(self, app_label: str) -> bool:
        """Check if user has permissions to view the app 'app_label'."""
        return self.is_superuser or self.is_admin
    
    @property
    def is_superuser_or_admin(self) -> bool:
        """Check if user is either superuser or admin."""
        return self.is_superuser or self.is_admin