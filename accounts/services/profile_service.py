from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.core.files.storage import default_storage
from PIL import Image
from pathlib import Path
import uuid
import logging
from ..models import UserProfile, Address

logger = logging.getLogger(__name__)

class ProfileService:
    @staticmethod
    @transaction.atomic
    def update_profile(user, profile_data, files=None):
        """Update user profile and related information"""
        try:
            # Update user basic info
            user.first_name = profile_data['first_name']
            user.last_name = profile_data['last_name']
            if 'phone_number' in profile_data:
                user.phone_number = profile_data['phone_number']
            user.save()

            # Update or create address
            ProfileService._update_address(user, profile_data)

            # Update role-specific information
            ProfileService._update_role_specific_info(user, profile_data)

            # Handle profile picture
            profile = ProfileService._get_or_create_profile(user)
            if files and 'profile_picture' in files:
                ProfileService._update_profile_picture(profile, files['profile_picture'])

            return profile

        except Exception as e:
            logger.error(f"Profile update error: {str(e)}")
            raise

    @staticmethod
    def validate_image(image_file):
        """Validate image file format, dimensions, and integrity"""
        try:
            # Verify file is a valid image
            img = Image.open(image_file)
            img.verify()
            
            # Rewind the file
            image_file.seek(0)
            
            # Open again to check dimensions
            img = Image.open(image_file)
            
            # Check dimensions
            max_size = (2000, 2000)
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

    @staticmethod
    def safe_profile_picture_upload(uploaded_file, user_id):
        """Safely handle profile picture uploads"""
        try:
            # Get file extension
            original_name = uploaded_file.name
            ext = Path(original_name).suffix.lower()
            
            # Validate extension
            allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif'}
            if ext not in allowed_extensions:
                raise ValueError(f"Invalid file extension. Allowed: {', '.join(allowed_extensions)}")
            
            # Create a safe filename
            filename = f"user_{user_id}_{uuid.uuid4()}{ext}"
            save_path = f"profile_pics/{filename}"
            
            # Save using Django's storage system
            saved_name = default_storage.save(save_path, uploaded_file)
            
            return saved_name
            
        except Exception as e:
            raise ValueError(f"Error saving file: {str(e)}")

    @staticmethod
    def rate_limit_uploads(user_id, limit=10, period=60):
        """Rate limit uploads per user"""
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

    @staticmethod
    def _get_or_create_profile(user):
        """Get or create user profile"""
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def _update_profile_picture(profile, picture):
        """Update profile picture with proper cleanup"""
        try:
            # Delete old picture if it exists
            if profile.profile_picture:
                old_path = profile.profile_picture.path
                if old_path and default_storage.exists(old_path):
                    default_storage.delete(old_path)

            # Save new picture
            profile.profile_picture = picture
            profile.save()

        except Exception as e:
            logger.error(f"Profile picture update error: {str(e)}")
            raise

    @staticmethod
    def _update_address(user, profile_data):
        """Update or create user address"""
        address_data = {
            'address_line1': profile_data.get('address_line1', ''),
            'address_line2': profile_data.get('address_line2', ''),
            'city': profile_data.get('city', ''),
            'state': profile_data.get('state', ''),
            'country': profile_data.get('country', ''),
            'zipcode': profile_data.get('zipcode', '')
        }
        
        Address.objects.update_or_create(
            user=user,
            defaults=address_data
        )

    @staticmethod
    def _update_role_specific_info(user, profile_data):
        """Update role-specific information"""
        if hasattr(user, 'student') and 'major' in profile_data:
            user.student.major = profile_data['major']
            user.student.year = int(profile_data['year'])
            user.student.save()

        if hasattr(user, 'faculty'):
            if 'department' in profile_data:
                user.faculty.department = profile_data['department']
            if 'position' in profile_data:
                user.faculty.position = profile_data['position']
            user.faculty.save()