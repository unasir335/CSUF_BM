from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache, caches
from .models import Product, ProductRecommendation
from .utils.cache import CacheKeyBuilder

def bulk_cache_delete(keys):
    """Delete multiple cache keys efficiently"""
    pipeline = cache.client.pipeline(transaction=True)
    for key in keys:
        pipeline.delete(key)
    pipeline.execute()

@receiver([post_save, post_delete], sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    keys_to_delete = [
        CacheKeyBuilder.product_key(instance.id),
        CacheKeyBuilder.store_page_key(instance.category.slug),
        CacheKeyBuilder.store_page_key(),
    ]
    
    # Invalidate related recommendations
    if hasattr(instance, 'recommendations'):
        keys_to_delete.extend([
            CacheKeyBuilder.product_recommendations_key(instance.id),
            CacheKeyBuilder.department_recommendations_key(instance.category.name)
        ])
    
    bulk_cache_delete(keys_to_delete)
    cache.incr('global_version')

@receiver([post_save, post_delete], sender=ProductRecommendation)
def invalidate_recommendation_cache(sender, instance, **kwargs):
    keys_to_delete = [
        CacheKeyBuilder.product_recommendations_key(instance.product_id),
        CacheKeyBuilder.faculty_recommendations_key(instance.faculty_id),
        CacheKeyBuilder.department_recommendations_key(instance.faculty.department),
        CacheKeyBuilder.store_page_key()
    ]
    bulk_cache_delete(keys_to_delete)