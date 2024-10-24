from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from abc import ABC, abstractmethod
from django.conf import settings
from django.dispatch import receiver
import os
from django.db.models.signals import pre_save

class UserManager(ABC):
    @abstractmethod
    def create_user(self, first_name, last_name, username, email, password=None):
        pass

    @abstractmethod
    def create_superuser(self, first_name, last_name, email, username, password):
        pass
    
class MyAccountManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        if not username:
            raise ValueError('Users must have a username')
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_admin', True)  # Add this line
        return self.create_user(username, email, password, **extra_fields)


# LSP: MyAccountManager can be used wherever UserManager is expected
class Account(AbstractBaseUser, PermissionsMixin):
    first_name      = models.CharField(max_length=50)
    last_name       = models.CharField(max_length=50)
    username        = models.CharField(max_length=50, unique=True)
    email           = models.EmailField(max_length=100, unique=True)
    phone_regex     = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone_number    = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='users/profile_pics/80x80.png', null=True, blank=True)
    security_question = models.CharField(max_length=255)
    security_answer = models.CharField(max_length=255)
    
    # User type fields
    is_admin        = models.BooleanField(default=False)
    is_active       = models.BooleanField(default=True)
    is_staff        = models.BooleanField(default=False)
    is_student      = models.BooleanField(default=False)
    is_faculty      = models.BooleanField(default=False)
    
    # Timestamps
    date_joined     = models.DateTimeField(auto_now_add=True)
    last_login      = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
   
    objects = MyAccountManager()
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def get_short_name(self):
        return self.first_name
    
    # modified 10/22
    # def has_perm(self, perm, obj=None):
    #     return self.is_superuser
    def has_perm(self, perm, obj=None):
    #Check if user has a specific permission.
        if self.is_superuser:
            return True
        if self.is_admin:
            return True
        return False
    
    # modified 10/22
    # def has_module_perms(self, add_label):
    #     return True
    def has_module_perms(self, app_label):
    #Check if user has permissions to view the app `app_label`
        if self.is_superuser:
            return True
        if self.is_admin:
            return True
        return False
    # 10/22 added
    @property
    def is_superuser_or_admin(self):
    #Check if user is either superuser or admin.
        return self.is_superuser or self.is_admin


class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    student_id = models.CharField(max_length=20, unique=True)
    major = models.CharField(max_length=100)
    year = models.IntegerField()

    def __str__(self):
        return f"Student: {self.user.get_full_name()}"

class Faculty(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    faculty_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)
    position = models.CharField(max_length=100)

    def __str__(self):
        return f"Faculty: {self.user.get_full_name()}"

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
    profile_picture = models.ImageField(upload_to='users/profile_pictures', default='users/profile_pics/300x150.png', blank=True)
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
            # Get the current profile picture
            old_image = UserProfile.objects.get(pk=self.pk).profile_picture
            # Check if there is an existing file and if it's different from the current one
            if old_image and old_image != self.profile_picture:
                if os.path.isfile(old_image.path):
                    os.remove(old_image.path)
        except UserProfile.DoesNotExist:
            pass  # If it's a new profile, there's no old picture to delete
        
@receiver(pre_save, sender=UserProfile)
def delete_old_image_on_update(sender, instance, **kwargs):
    if instance.pk:
        instance.delete_old_image()

class OrderHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='order_history')
    order_number = models.CharField(max_length=20)
    order_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"Order {self.order_number} for {self.user.username}"

    class Meta:
        ordering = ['-order_date']
    
