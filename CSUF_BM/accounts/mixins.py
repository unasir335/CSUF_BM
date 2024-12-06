from django.core.cache import cache
import logging
from django.views.generic.base import ContextMixin
from typing import Optional, Dict, Any
from .cache.handlers import CacheHandler
from .cache.keys import CacheKeyBuilder

logger = logging.getLogger(__name__)

class UserTypeMixin:
    """Mixin to handle user type determination"""
    
    def get_user_type(self):
        user = self.request.user
        if user.is_superuser:
            return 'Superuser'
        elif user.is_admin:
            return 'Admin'
        elif hasattr(user, 'student'):
            return 'Student'
        elif hasattr(user, 'faculty'):
            return 'Faculty'
        return 'Regular User'

class RateLimitMixin:
    """Mixin to handle rate limiting"""
    
    def check_rate_limit(self, key_prefix, limit=100, period=60):
        return CacheHandler.check_rate_limit(
            user_id=self.request.user.id,
            action=key_prefix,
            limit=limit,
            period=period
        )

class CacheMixin:
    """Mixin to handle view data caching"""
    
    cache_timeout = 3600  # Default cache timeout
    _context_in_progress = False  # Flag to prevent recursion
    
    def get_cache_key(self) -> Optional[str]:
        """Get the appropriate cache key for the current request"""
        if not hasattr(self, 'request') or not self.request.user.is_authenticated:
            return None
            
        return CacheKeyBuilder.user_profile(self.request.user.id)
    
    def get_cached_data(
        self,
        cache_key: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> dict:
        """Get cached data or generate new data"""
        key = cache_key or self.get_cache_key()
        if not key:
            return self.get_context_data()
            
        # Check if we're already generating context
        if getattr(self, '_context_in_progress', False):
            return super().get_context_data()
            
        try:
            self._context_in_progress = True
            # Fix the lambda to properly pass kwargs
            return CacheHandler.get_or_set(
                cache_key=key,
                data_func=lambda: super(CacheMixin, self).get_context_data(**self.kwargs),
                timeout=timeout or self.cache_timeout
            )
        finally:
            self._context_in_progress = False
    
    def get_context_data(self, **kwargs):
        """Get context data with caching support"""
        if getattr(self, '_context_in_progress', False):
            return super().get_context_data(**kwargs)
            
        cache_key = self.get_cache_key()
        if not cache_key:
            return super().get_context_data(**kwargs)
            
        return self.get_cached_data(cache_key)
    
    