def make_cache_key(key, key_prefix, version):
    """
    Django-compatible cache key function
    
    Args:
        key: The base key name
        key_prefix: The prefix to use
        version: The version number
        
    Returns:
        str: The formatted cache key
    """
    return f"{key_prefix}:{version}:{key}"


class CacheKeyBuilder:
    """
    Manages the construction of cache keys with versioning support
    """
    VERSION = 'v1'
    
    @staticmethod
    def _build_key(prefix, identifier):
        """
        Build a versioned cache key
        
        Args:
            prefix: Key prefix indicating the type of data
            identifier: Unique identifier (usually user_id)
            
        Returns:
            str: Formatted cache key
        """
        return f"{prefix}:{identifier}:{CacheKeyBuilder.VERSION}"
    
    @classmethod
    def user_profile(cls, user_id):
        """Get cache key for user profile"""
        return cls._build_key('user:profile', user_id)
    
    @classmethod
    def dashboard_data(cls, user_id):
        """Get cache key for dashboard data"""
        return cls._build_key('user:dashboard', user_id)
    
    @classmethod
    def user_orders(cls, user_id):
        """Get cache key for user orders"""
        return cls._build_key('user:orders', user_id)
    
    @classmethod
    def user_data(cls, user_id):
        """Get cache key for comprehensive user data"""
        return cls._build_key('user:data', user_id)
    
    @classmethod
    def request_rate(cls, user_id):
        """Get cache key for request rate limiting"""
        return cls._build_key('request_rate', user_id)
    
    @classmethod
    def profile_view(cls, user_id):
        """Get cache key for profile view rate limiting"""
        return cls._build_key('profile:view', user_id)
    
    @classmethod
    def profile_upload(cls, user_id):
        """Get cache key for profile upload rate limiting"""
        return cls._build_key('profile:upload', user_id)
    
    @classmethod
    def rate_limit(cls, user_id, action):
        """Get cache key for general rate limiting"""
        return cls._build_key(f'rate_limit:{action}', user_id)
    