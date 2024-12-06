from django.core.cache import cache
from django.conf import settings
import time
import logging
from django.http import JsonResponse
from .cache.handlers import CacheHandler
from .cache.keys import CacheKeyBuilder

logger = logging.getLogger(__name__)


class RequestRateLimitMiddleware:
    def __call__(self, request):
        if request.user.is_authenticated:
            if not CacheHandler.check_rate_limit(
                request.user.id, 
                limit=settings.MAX_REQUESTS_PER_MINUTE,
                period=60
            ):
                return JsonResponse({
                    'error': 'Too many requests. Please try again later.'
                }, status=429)
            response = self.get_response(request)
        else:
            response = self.get_response(request)
        return response

class ResponseTimeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time
        
        if duration > 1.0:  # Log slow requests
            logger.warning(
                f'Slow request: {request.method} {request.path} '
                f'({duration:.2f}s)'
            )
            
        return response