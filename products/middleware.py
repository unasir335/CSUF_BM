# middleware.py
import time
from django.core.cache import cache
from django.conf import settings
import logging
logger = logging.getLogger(__name__)


class EnhancedCacheMonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.stats_timeout = 86400  # 24 hours

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time
        
        if not settings.DEBUG:
            self.update_cache_stats(request.path, duration, hasattr(response, '_cache_hit'))
        
        return response
    
    def update_cache_stats(self, path, duration, is_hit):
        """Update cache statistics with pipeline"""
        cache_key = f"cache_stats:{path}"
        
        pipeline = cache.client.pipeline(transaction=True)
        try:
            # Get current stats
            stats = cache.get(cache_key, {
                'hits': 0,
                'misses': 0,
                'avg_time': 0,
                'min_time': duration,
                'max_time': duration,
                'total_requests': 0
            })
            
            # Update stats
            stats['total_requests'] += 1
            if is_hit:
                stats['hits'] += 1
            else:
                stats['misses'] += 1
            
            stats['avg_time'] = (
                (stats['avg_time'] * (stats['total_requests'] - 1) + duration) / 
                stats['total_requests']
            )
            stats['min_time'] = min(stats['min_time'], duration)
            stats['max_time'] = max(stats['max_time'], duration)
            
            # Store updated stats
            pipeline.set(cache_key, stats, self.stats_timeout)
            pipeline.execute()
            
        except Exception as e:
            logger.error(f"Error updating cache stats: {e}")