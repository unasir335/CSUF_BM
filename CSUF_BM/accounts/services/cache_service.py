from django.core.cache import cache
from django.conf import settings
from functools import wraps
from django.shortcuts import render
from ..models import Account
from checkout.models import Order
import logging

logger = logging.getLogger(__name__)

class CacheKeyBuilder:
    VERSION = 'v1'
    
    @staticmethod
    def _build_key(prefix, identifier):
        return f"{prefix}:{identifier}:{CacheKeyBuilder.VERSION}"
    
    @staticmethod
    def user_profile(user_id):
        return CacheKeyBuilder._build_key('user:profile', user_id)
    
    @staticmethod
    def dashboard_data(user_id):
        return CacheKeyBuilder._build_key('user:dashboard', user_id)
    
    @staticmethod
    def user_orders(user_id):
        return CacheKeyBuilder._build_key('user:orders', user_id)

class CacheService:
    @staticmethod
    def get_cached_profile(user_id, timeout=3600):
        """Get cached user profile data"""
        cache_key = CacheKeyBuilder.user_profile(user_id)
        data = cache.get(cache_key)
        
        if data is None:
            try:
                user = Account.objects.select_related(
                    'student', 
                    'faculty', 
                    'address', 
                    'userprofile'
                ).get(id=user_id)
                
                data = {
                    'user': user,
                    'full_name': user.get_full_name(),
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'role': user.role,
                }
                
                cache.set(cache_key, data, timeout)
            except Exception as e:
                logger.error(f"Error getting cached profile: {str(e)}")
                return None
        
        return data

    @staticmethod
    def get_cached_dashboard_data(user_id, timeout=1800):
        """Get cached dashboard data"""
        cache_key = CacheKeyBuilder.dashboard_data(user_id)
        data = cache.get(cache_key)
        
        if data is None:
            try:
                user = Account.objects.get(id=user_id)
                orders = Order.objects.filter(user=user).order_by('-created_at')
                
                data = {
                    'orders_count': orders.count(),
                    'total_spent': sum(order.get_total_with_tax() for order in orders),
                    'recent_orders': list(orders[:5].values())
                }
                cache.set(cache_key, data, timeout)
            except Exception as e:
                logger.error(f"Error getting dashboard data: {str(e)}")
                return None
        
        return data

    @staticmethod
    def get_cached_user_data(user_id, timeout=1800):
        """Get comprehensive cached user data"""
        cache_key = f'user:data:{user_id}'
        data = cache.get(cache_key)
        
        if data is None:
            try:
                user = Account.objects.select_related(
                    'student',
                    'faculty',
                    'address'
                ).get(id=user_id)
                
                data = {
                    'user': user,
                    'full_name': user.get_full_name(),
                    'email': user.email,
                    'phone_number': getattr(user, 'phone_number', ''),
                    'date_joined': user.date_joined,
                    'last_login': user.last_login,
                    'user_type': CacheService._get_user_type(user)
                }
                
                CacheService._add_role_specific_data(data, user)
                CacheService._add_address_data(data, user)
                
                cache.set(cache_key, data, timeout)
            except Account.DoesNotExist:
                logger.error(f"User {user_id} not found")
                return {}
            except Exception as e:
                logger.error(f"Error getting user data: {str(e)}")
                return {}
        
        return data

    @staticmethod
    def invalidate_user_caches(user_id):
        """Invalidate all user-related caches"""
        keys = [
            CacheKeyBuilder.user_profile(user_id),
            CacheKeyBuilder.dashboard_data(user_id),
            CacheKeyBuilder.user_orders(user_id)
        ]
        cache.delete_many(keys)

    @staticmethod
    def _get_user_type(user):
        if user.is_superuser:
            return 'Superuser'
        elif user.is_admin:
            return 'Admin'
        elif hasattr(user, 'student'):
            return 'Student'
        elif hasattr(user, 'faculty'):
            return 'Faculty'
        return 'General User'

    @staticmethod
    def _add_role_specific_data(data, user):
        if hasattr(user, 'student'):
            data.update({
                'student_id': user.student.student_id,
                'major': user.student.major,
                'year': user.student.year,
            })
        elif hasattr(user, 'faculty'):
            data.update({
                'faculty_id': user.faculty.faculty_id,
                'department': user.faculty.department,
                'position': user.faculty.position,
            })

    @staticmethod
    def _add_address_data(data, user):
        if hasattr(user, 'address'):
            data.update({
                'address_line1': user.address.address_line1,
                'address_line2': user.address.address_line2,
                'city': user.address.city,
                'state': user.address.state,
                'country': user.address.country,
                'zipcode': user.address.zipcode,
            })

def cache_profile(timeout=3600):
    """Decorator for caching profile views"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            
            cache_key = CacheKeyBuilder.user_profile(request.user.id)
            data = cache.get(cache_key)
            
            if data is None:
                response = view_func(request, *args, **kwargs)
                if hasattr(response, 'context_data'):
                    cache.set(cache_key, response.context_data, timeout)
                return response
            
            return render(request, 'accounts/profile.html', data)
        return wrapper
    return decorator