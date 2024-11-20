from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Account
from .cache.handlers import CacheHandler

@receiver(post_save, sender=Account)
def invalidate_profile_cache(sender, instance, **kwargs):
    """Invalidate all user-related caches when account is updated"""
    CacheHandler.invalidate_user_caches(instance.id)