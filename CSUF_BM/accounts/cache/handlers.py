from django.core.cache import cache
from django.shortcuts import render
from functools import wraps
from ..models import Account
from checkout.models import Order
from .keys import CacheKeyBuilder
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

from django.core.cache import cache
from django.conf import settings
from functools import wraps
import logging
import copy
from django.core.serializers.json import DjangoJSONEncoder
import json

logger = logging.getLogger(__name__)

class CacheHandler:
    """
    Handles all cache-related operations with proper serialization
    """
    
    @staticmethod
    def get_or_set(cache_key, data_func, timeout=3600):
        """
        Get data from cache or set it if not present
        
        Args:
            cache_key: Key to store/retrieve cache data
            data_func: Callable that returns the data if not in cache
            timeout: Cache timeout in seconds
            
        Returns:
            The cached or newly generated data
        """
        try:
            data = cache.get(cache_key)
            
            if data is None:
                data = data_func()
                if data:
                    # Make a copy to avoid modifying the original
                    cacheable_data = copy.copy(data)
                    
                    # Remove non-serializable items
                    if isinstance(cacheable_data, dict):
                        # Remove request object and other non-serializable items
                        cacheable_data.pop('request', None)
                        cacheable_data.pop('view', None)
                        
                        # Handle form instances
                        form_keys = [k for k in cacheable_data.keys() if 'form' in k.lower()]
                        for key in form_keys:
                            if hasattr(cacheable_data[key], 'initial'):
                                cacheable_data[key] = cacheable_data[key].initial
                        
                        # Handle model instances by converting to dict
                        for key, value in cacheable_data.items():
                            if hasattr(value, '_meta'):  # Django model instance
                                cacheable_data[key] = {
                                    'id': value.id,
                                    'str': str(value)
                                }
                    
                    # Try to cache the cleaned data
                    try:
                        # Verify data is serializable
                        json.dumps(cacheable_data, cls=DjangoJSONEncoder)
                        cache.set(cache_key, cacheable_data, timeout)
                    except (TypeError, ValueError) as e:
                        logger.warning(f"Could not serialize cache data: {str(e)}")
                        
                return data
            
            return data
            
        except Exception as e:
            logger.error(f"Cache error for key {cache_key}: {str(e)}")
            # Return fresh data if caching fails
            return data_func()

    @staticmethod
    def check_rate_limit(user_id, action, limit=10, period=60):
        """Check rate limit for an action"""
        cache_key = CacheKeyBuilder.rate_limit(user_id, action)
        try:
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
    def invalidate_user_caches(user_id):
        """Invalidate all user-related caches"""
        keys = [
            CacheKeyBuilder.user_profile(user_id),
            CacheKeyBuilder.dashboard_data(user_id),
            CacheKeyBuilder.user_orders(user_id),
            CacheKeyBuilder.user_data(user_id)
        ]
        cache.delete_many(keys)

