from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.core.files.storage import default_storage
import logging
logger = logging.getLogger(__name__)

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='userprofile')
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to='users/profile_pictures/',
        default='profile_pictures/200x200.png',
        blank=True
    )
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
        """Delete old profile picture if it exists and isn't the default"""
        try:
            if self.pk:
                old_profile = UserProfile.objects.get(pk=self.pk)
                if (old_profile.profile_picture and 
                    old_profile.profile_picture != self.profile_picture and 
                    'defaults/default_profile.png' not in old_profile.profile_picture.name):
                    # Get the full path to verify it's within media root
                    file_path = default_storage.path(old_profile.profile_picture.name)
                    if default_storage.exists(file_path):
                        default_storage.delete(old_profile.profile_picture.name)
        except UserProfile.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error deleting old image: {e}")

    def save(self, *args, **kwargs):
        if self.pk:
            self.delete_old_image()
        super().save(*args, **kwargs)