from django.db import models, transaction
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from abc import ABC, abstractmethod
from django.conf import settings
from django.dispatch import receiver
from django.core.files.storage import default_storage

import os
from django.db.models.signals import pre_save
import logging

logger = logging.getLogger(__name__)

class UserManager(ABC):
    @abstractmethod
    def create_user(self, first_name, last_name, username, email, password=None):
        pass

    @abstractmethod
    def create_superuser(self, first_name, last_name, email, username, password):
        pass

# Updated 10/25 Validate that a user can only have one role
class MyAccountManager(BaseUserManager):
    def validate_user_type(self, **kwargs):
        role_count = sum([
            kwargs.get('is_student', False),
            kwargs.get('is_faculty', False),
            kwargs.get('is_admin', False)
        ])
        
        if role_count > 1:
            raise ValidationError("User cannot have multiple roles (student, faculty, or admin)")
        
        return True

    @transaction.atomic
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        if not username:
            raise ValueError('Users must have a username')
        
        # Validate user type
        self.validate_user_type(**extra_fields)
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        
        # If the user is being made an admin, check if it's being done by a superuser
        if extra_fields.get('is_admin', False):
            from threading import local
            _thread_locals = local()
            current_user = getattr(_thread_locals, 'current_user', None)
            
            if current_user and current_user.is_superuser:
                user.assigned_by_superuser = True
                user.is_staff = True  # Automatically set staff status for superuser-assigned admins
        
        try:
            user.full_clean()  # Run model validation
            user.save(using=self._db)
            
            logger.info(
                f"Created new user: {email} | Roles: {self.get_user_roles(user)}"
            )
            
            return user
            
        except ValidationError as e:
            logger.error(f"User creation failed for {email}: {str(e)}")
            raise
    
    @transaction.atomic
    def create_superuser(self, username, email, password=None, **extra_fields):
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
    
    def get_user_roles(self, user):
        """Get list of user's active roles"""
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
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$', 
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/', 
        default='users/profile_pics/80x80.png', 
        null=True, 
        blank=True
    )
    
    security_question = models.CharField(max_length=255, blank=True, default='')
    security_answer = models.CharField(max_length=255, blank=True, default='')
    
    # User type fields
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)
    is_faculty = models.BooleanField(default=False)
    registration_complete = models.BooleanField(default=False)
    assigned_by_superuser = models.BooleanField(default=False)  # Added this field
    
    # Timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
   
    objects = MyAccountManager()
    
    def clean(self):
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
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def get_short_name(self):
        return self.first_name
    
    @property
    def role(self):
        if self.is_superuser:
            return 'Superuser'
        elif self.is_admin:
            return 'Admin'
        elif self.is_student:
            return 'Student'
        elif self.is_faculty:
            return 'Faculty'
        return 'Regular User'
    
    def has_perm(self, perm, obj=None):
        return self.is_superuser or self.is_admin
    
    def has_module_perms(self, app_label):
        return self.is_superuser or self.is_admin
    
    @property
    def is_superuser_or_admin(self):
        return self.is_superuser or self.is_admin

class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student',
        primary_key=True
    )
    student_id = models.CharField(max_length=20, unique=True)
    major = models.CharField(max_length=100)
    year = models.IntegerField()

    class Meta:
        db_table = 'accounts_student'
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.student_id}"
    
class Faculty(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='faculty',
        primary_key=True
    )
    faculty_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    research_areas = models.TextField(blank=True)

    class Meta:
        db_table = 'accounts_faculty'
        verbose_name = 'Faculty Profile'
        verbose_name_plural = 'Faculty Profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.faculty_id}"

class Address(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='address')
    address_line1 = models.CharField(max_length=100, blank=True)
    address_line2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, blank=True)
    zipcode = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f'{self.address_line1}, {self.city}, {self.state}, {self.country}'

class UserActivity(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50)  # e.g., 'login', 'password_change', etc.
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.activity_type}"

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='userprofile')
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='users/profile_pictures', default='/profile_pics/300x150.png', blank=True)
    address_line1 = models.CharField(max_length=100, blank=True)
    address_line2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, blank=True)
    zipcode = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"{self.user.email}'s profile"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self):
        return self.first_name
    
    def delete_old_image(self):
        try:
            if self.pk:  # Only if the instance exists in DB
                old_profile = UserProfile.objects.get(pk=self.pk)
                if (old_profile.profile_picture and 
                    old_profile.profile_picture != self.profile_picture and 
                    old_profile.profile_picture.name != 'profile_pics/300x150.png'):
                    # Delete the old file from storage
                    default_storage.delete(old_profile.profile_picture.name)
        except UserProfile.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error deleting old image: {e}")

    def save(self, *args, **kwargs):
        if self.pk:
            self.delete_old_image()
        super().save(*args, **kwargs)

class OrderHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='order_history')
    order_number = models.CharField(max_length=20)
    order_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"Order {self.order_number} for {self.user.username}"

    class Meta:
        ordering = ['-order_date']
    
