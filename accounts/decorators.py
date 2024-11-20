from django.core.exceptions import PermissionDenied
from django.db.utils import OperationalError
from django.db import transaction
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.core.cache import cache
from functools import wraps
from typing import Callable, Any, Optional, Union
import logging
import time
from .cache.keys import CacheKeyBuilder


logger = logging.getLogger(__name__)

def retry_on_deadlock(max_attempts: int = 3, delay: float = 0.1) -> Callable:
    """
    Decorator to retry operations on database deadlocks
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Base delay between attempts in seconds
        
    Returns:
        Callable: Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    if 'deadlock' in str(e).lower():
                        attempt += 1
                        if attempt == max_attempts:
                            logger.error(
                                f"Max deadlock retries ({max_attempts}) reached for {func.__name__}"
                            )
                            raise
                        logger.warning(
                            f"Deadlock detected in {func.__name__}, "
                            f"attempt {attempt}/{max_attempts}"
                        )
                        time.sleep(delay * attempt)
                    else:
                        raise
            return None
        return wrapper
    return decorator

def require_role(role: str) -> Callable:
    """
    Decorator to enforce user role requirements
    
    Args:
        role: Required role (e.g., 'admin', 'student', 'faculty')
        
    Returns:
        Callable: Decorated view function
        
    Raises:
        PermissionDenied: If user doesn't have required role
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(
            request: HttpRequest,
            *args: Any,
            **kwargs: Any
        ) -> HttpResponse:
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
                
            if not getattr(request.user, f"is_{role}", False):
                logger.warning(
                    f"User {request.user.id} attempted to access {role}-only view"
                )
                raise PermissionDenied(f"This action requires {role} privileges")
                
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def secure_upload(
    upload_type: str,
    limit: int = 10,
    period: int = 3600,
    max_retries: int = 3
) -> Callable:
    """
    Combined security decorator for file uploads
    
    Handles:
    - Rate limiting
    - Deadlock retrying
    - Transaction management
    
    Args:
        upload_type: Type of upload for rate limiting
        limit: Maximum uploads per period
        period: Time period in seconds
        max_retries: Maximum retry attempts for deadlocks
        
    Returns:
        Callable: Decorated view function
        
    Raises:
        PermissionDenied: If rate limit exceeded
        OperationalError: If max retries reached
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(
            request: HttpRequest,
            *args: Any,
            **kwargs: Any
        ) -> HttpResponse:
            # Lazy import to avoid circular dependencies
            from .cache.handlers import CacheHandler
            
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Check rate limit
            if not CacheHandler.check_rate_limit(
                user_id=request.user.id,
                action=f'upload_{upload_type}',
                limit=limit,
                period=period
            ):
                logger.warning(
                    f"Rate limit exceeded for {upload_type} upload by user {request.user.id}"
                )
                raise PermissionDenied(
                    f"Maximum {limit} uploads allowed per {period//3600} hours"
                )
            
            # Retry logic with transaction
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        return view_func(request, *args, **kwargs)
                except OperationalError as e:
                    if 'deadlock' in str(e).lower() and attempt < max_retries - 1:
                        logger.warning(
                            f"Deadlock detected on attempt {attempt + 1}/{max_retries}"
                        )
                        time.sleep(0.1 * (attempt + 1))
                    else:
                        logger.error(f"Upload failed: {str(e)}")
                        raise
                except Exception as e:
                    logger.error(
                        f"Error in {upload_type} upload: {str(e)}",
                        exc_info=True
                    )
                    raise
        return wrapper
    return decorator

def cache_profile(timeout: int = 3600) -> Callable:
    """
    Decorator for caching profile views
    
    Args:
        timeout: Cache timeout in seconds
        
    Returns:
        Callable: Decorated class method
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(view_instance, *args, **kwargs):
            # Get request from args
            request = args[0] if args else kwargs.get('request')
            
            if not request or not request.user.is_authenticated:
                return view_func(view_instance, *args, **kwargs)
                
            # Only cache GET requests
            if request.method != 'GET':
                return view_func(view_instance, *args, **kwargs)
            
            from .cache.handlers import CacheHandler
            
            try:
                # Generate cache key
                from .cache.keys import CacheKeyBuilder
                cache_key = CacheKeyBuilder.user_profile(request.user.id)
                
                def get_fresh_data():
                    # Get the response from the view
                    response = view_func(view_instance, *args, **kwargs)
                    
                    if not hasattr(response, 'context_data'):
                        return None
                        
                    # Create a copy of context data for caching
                    context = response.context_data.copy()
                    
                    # Clean up context for caching
                    context.pop('request', None)
                    context.pop('view', None)
                    context.pop('form', None)
                    context.pop('password_form', None)
                    
                    # Convert model instances to dictionaries
                    if 'profile' in context:
                        profile = context['profile']
                        context['profile'] = {
                            'id': profile.id,
                            'phone_number': getattr(profile, 'phone_number', ''),
                            'user_id': profile.user_id,
                            'str': str(profile)
                        }
                    
                    if 'address' in context:
                        address = context['address']
                        if address:
                            context['address'] = {
                                'id': address.id,
                                'address_line1': address.address_line1,
                                'address_line2': address.address_line2,
                                'city': address.city,
                                'state': address.state,
                                'country': address.country,
                                'zipcode': address.zipcode,
                                'user_id': address.user_id,
                                'str': str(address)
                            }
                            
                    if 'student' in context:
                        student = context['student']
                        if student:
                            context['student'] = {
                                'id': student.id,
                                'student_id': student.student_id,
                                'major': student.major,
                                'year': student.year,
                                'str': str(student)
                            }
                            
                    if 'faculty' in context:
                        faculty = context['faculty']
                        if faculty:
                            context['faculty'] = {
                                'id': faculty.id,
                                'faculty_id': faculty.faculty_id,
                                'department': faculty.department,
                                'position': faculty.position,
                                'str': str(faculty)
                            }
                    
                    return context
                
                # Try to get cached data or generate fresh data
                cached_data = CacheHandler.get_or_set(cache_key, get_fresh_data, timeout)
                
                if cached_data:
                    # Get a fresh response to ensure forms and other dynamic content
                    response = view_func(view_instance, *args, **kwargs)
                    if hasattr(response, 'context_data'):
                        # Update the response's context with cached data
                        response.context_data.update(cached_data)
                    return response
                    
            except Exception as e:
                logger.error(f"Cache error in profile view: {str(e)}")
            
            # Fallback to uncached response
            return view_func(view_instance, *args, **kwargs)
            
        return wrapper
    return decorator



