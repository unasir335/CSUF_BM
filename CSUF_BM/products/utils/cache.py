from django.conf import settings
from django.core.cache import cache
from functools import wraps

class CacheKeyBuilder:
    """Centralized cache key management"""
    
    @staticmethod
    def _sanitize_key(key):
        """Convert characters that might cause issues with memcached"""
        return key.replace(' ', '_').replace(':', '_').replace('/', '_')
    
    @staticmethod
    def product_key(product_id):
        return f"product_{product_id}"
    
    @staticmethod
    def product_recommendations_key(product_id):
        return f"recommendations_product_{product_id}"
    
    @staticmethod
    def department_recommendations_key(department):
        department = CacheKeyBuilder._sanitize_key(department)
        return f"recommendations_department_{department}"
    
    @staticmethod
    def faculty_recommendations_key(faculty_id):
        return f"recommendations_faculty_{faculty_id}"
    
    @staticmethod
    def store_page_key(category_slug=None, params=None):
        base = "store_page"
        if category_slug:
            base += f"_{category_slug}"
        if params:
            param_hash = hash(frozenset(params.items()))
            base += f"_{param_hash}"
        return base

def get_or_set_cache(key, func, timeout=3600):
    """Get from cache or compute and cache value"""
    result = cache.get(key)
    if result is None:
        result = func()
        cache.set(key, result, timeout=timeout)
    return result

def make_versioned_key(key, key_prefix, version):
    """Create a versioned cache key"""
    if version is None:
        version = cache.get('global_version', 1)
    return f'{key_prefix}:v{version}:{key}'

def cache_with_version(timeout=None):
    """Decorator for version-aware caching"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = func.__name__ + ':' + ':'.join(str(arg) for arg in args)
            version = cache.get('global_version', 1)
            result = cache.get(key, version=version)
            
            if result is None:
                result = func(*args, **kwargs)
                cache.set(key, result, timeout=timeout, version=version)
            
            return result
        return wrapper
    return decorator

def bulk_cache_delete(keys):
    """Delete multiple cache keys efficiently"""
    pipeline = cache.client.pipeline(transaction=True)
    for key in keys:
        pipeline.delete(key)
    pipeline.execute()
    
    
def get_or_set_cache(key, func, timeout=3600):
    """Get from cache or compute and cache value"""
    result = cache.get(key)
    if result is None:
        result = func()
        cache.set(key, result, timeout=timeout)
    return result