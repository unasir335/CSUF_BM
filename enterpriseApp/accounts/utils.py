# utils.py
from pathlib import Path
from django.conf import settings
import uuid
from django.core.files.storage import default_storage


def safe_profile_picture_upload(uploaded_file, user_id):
    """
    Safely handles profile picture uploads using Django's storage system.
    """
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