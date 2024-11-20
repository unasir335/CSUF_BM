from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Product, Category, DigitalProduct, ProductReview, ProductRecommendation
from django.contrib import messages #added 10/22
from .forms import ProductSortForm, CategoryForm, ProductForm, DigitalProductForm, ProductReviewForm # Added 10/22 CategoryForm and ProductForm, 10/26 digital product
from django.db.models import Q, Count
from accounts.models.faculty import Faculty
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.http import Http404
# Create your views here.
from django.core.cache import cache
import logging
from django.views.decorators.http import require_http_methods, require_POST
from functools import wraps
from django.db import transaction
from datetime import datetime
from .utils.cache import CacheKeyBuilder, get_or_set_cache
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie

logger = logging.getLogger(__name__)

def get_cached_data(key):
    cache_version = cache.get('product_cache_version', 1)
    return cache.get(f'{key}_v{cache_version}')

def rate_limit(key_prefix, limit, period=60):
    """Generic rate limiting decorator"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            user_id = request.user.faculty.user_id
            cache_key = f"rate_limit_{key_prefix}_{user_id}"
            
            try:
                # Get current count
                count = cache.get(cache_key, 0)
                
                # Check limit
                if count >= limit:
                    logger.warning(f'Rate limit exceeded for {key_prefix} by faculty {user_id}')
                    return JsonResponse({
                        'error': f'Too many attempts. Please wait {period} seconds.'
                    }, status=429)
                
                # Increment count
                cache.set(cache_key, count + 1, period)
                
                return view_func(request, *args, **kwargs)
                
            except Exception as e:
                logger.error(f'Rate limiting error: {str(e)}')
                return view_func(request, *args, **kwargs)
                
        return wrapped
    return decorator


def rate_limit_faculty_delete(view_func):
    """Rate limiting decorator specifically for delete operations"""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        faculty_id = request.user.faculty.user_id  # or request.user.faculty.pk
        cache_key = f'faculty_delete_{faculty_id}'
        
        # Allow 10 deletions per minute
        if cache.get(cache_key, 0) >= 10:
            logger.warning(f'Delete rate limit exceeded for faculty {faculty_id}')
            return JsonResponse({
                'error': 'Too many deletion attempts. Please wait a minute.'
            }, status=429)
            
        cache.incr(cache_key, 1)
        # Set expiry to 60 seconds if not set
        if not cache.ttl(cache_key):
            cache.expire(cache_key, 60)
        
        return view_func(request, *args, **kwargs)
    return wrapped

def is_faculty(user):
    """Check if user is authenticated faculty member"""
    return user.is_authenticated and hasattr(user, 'faculty') and user.is_faculty

@login_required
@user_passes_test(is_faculty)
@require_POST
def remove_recommendation(request, product_id):
    """Remove a faculty recommendation"""
    try:
        logger.debug(f"Attempting to remove recommendation - Product: {product_id}, User: {request.user.id}")
        
        with transaction.atomic():
            # Get the recommendation
            recommendation = ProductRecommendation.objects.select_for_update().filter(
                product_id=product_id,
                faculty=request.user.faculty
            ).first()
            
            if not recommendation:
                logger.warning(f"Recommendation not found - Product: {product_id}, Faculty: {request.user.faculty.user_id}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Recommendation not found'
                }, status=404)
            
            # Store cache info before deletion
            cache_keys = [
                f"recommendations_product_{product_id}",
                f"recommendations_faculty_{request.user.faculty.user_id}",
                "store_page_*",
                f"product_{product_id}_*"
            ]
            
            if request.user.faculty.department:
                cache_keys.append(
                    f"recommendations_department_{request.user.faculty.department.replace(' ', '_')}"
                )
            
            # Delete recommendation
            recommendation.delete()
            
            # Clear caches
            for key in cache_keys:
                try:
                    cache.delete(key)
                except Exception as e:
                    logger.warning(f"Error deleting cache key {key}: {str(e)}")
            
            logger.info(
                f'Recommendation removed successfully - Product: {product_id}, '
                f'Faculty: {request.user.faculty.user_id}'
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Recommendation removed successfully'
            })
            
    except Exception as e:
        logger.error(f'Error removing recommendation: {str(e)}', exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e) if settings.DEBUG else 'An error occurred'
        }, status=500)          
            
def get_product_recommendations(request, product_id):
    def fetch_recommendations():
        product = get_object_or_404(Product, id=product_id)
        recommendations = product.recommendations.select_related(
            'faculty', 
            'faculty__user'
        ).all()
        
        return [
            {
                'faculty_name': rec.faculty.user.get_full_name(),
                'department': rec.faculty.department,
                'recommendation_text': rec.recommendation_text,
                'is_essential': rec.is_essential,
                'created_at': rec.created_at.strftime('%B %d, %Y')
            }
            for rec in recommendations
        ]
    
    cache_key = CacheKeyBuilder.product_recommendations_key(product_id)
    recommendations_data = get_or_set_cache(cache_key, fetch_recommendations, timeout=1800)
    
    return JsonResponse({'recommendations': recommendations_data})

@login_required
@user_passes_test(is_faculty)
@rate_limit('faculty_action', 30)
@require_POST
def toggle_recommendation(request, product_id):
    """
    Toggle or update a faculty recommendation for a product
    """
    try:
        # Add debugging information
        logger.debug(f"User ID: {request.user.id}")
        logger.debug(f"Request method: {request.method}")
        logger.debug(f"POST data: {request.POST}")
        
        # Verify faculty exists
        if not hasattr(request.user, 'faculty'):
            logger.error(f'Faculty profile missing for user {request.user.id}')
            return JsonResponse({
                'status': 'error',
                'message': 'Faculty profile not found'
            }, status=404)

        faculty = request.user.faculty
        logger.debug(f"Faculty user_id: {faculty.user_id}")
        logger.debug(f"Faculty department: {faculty.department}")

        # Validate request data
        recommendation_text = request.POST.get('recommendation_text', '').strip()
        is_essential = request.POST.get('is_essential') == 'true'
        
        if not recommendation_text:
            return JsonResponse({
                'status': 'error',
                'message': 'Recommendation text is required'
            }, status=400)

        with transaction.atomic():
            # Get or create product with select_for_update
            try:
                product = Product.objects.select_for_update().get(id=product_id)
            except Product.DoesNotExist:
                logger.error(f"Product not found: {product_id}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Product not found'
                }, status=404)

            # Update or create recommendation
            recommendation, created = ProductRecommendation.objects.update_or_create(
                product=product,
                faculty=faculty,
                defaults={
                    'recommendation_text': recommendation_text,
                    'is_essential': is_essential
                }
            )
            
            # Clear ALL related caches
            cache_keys = [
                CacheKeyBuilder.product_recommendations_key(product_id),
                CacheKeyBuilder.faculty_recommendations_key(faculty.user_id),
                "store_page_*",  # Clear all store view caches
                f"product_{product_id}_*",  # Clear product detail caches
            ]
            
            if faculty.department:
                cache_keys.append(
                    CacheKeyBuilder.department_recommendations_key(faculty.department)
                )
            
            # Log cache operations
            logger.debug(f"Clearing cache keys: {cache_keys}")
            
            for key in cache_keys:
                try:
                    cache.delete(key)
                except Exception as e:
                    logger.warning(f"Error deleting cache key {key}: {str(e)}")
            
            # Log successful operation
            logger.info(
                f'Recommendation {"created" if created else "updated"} - '
                f'Product: {product_id}, Faculty: {faculty.user_id}'  # Changed from faculty.id
            )
            
            return JsonResponse({
                'status': 'success',
                'message': f'Recommendation {"created" if created else "updated"} successfully',
                'recommendation': {
                    'id': recommendation.id,
                    'faculty_name': faculty.user.get_full_name(),
                    'department': faculty.department,
                    'recommendation_text': recommendation.recommendation_text,
                    'is_essential': recommendation.is_essential,
                    'created_at': recommendation.created_at.strftime('%B %d, %Y')
                }
            })
            
    except Exception as e:
        logger.error(f'Error in toggle_recommendation: {str(e)}', exc_info=True)
        if settings.DEBUG:
            # In development, return the actual error message
            return JsonResponse({
                'status': 'error',
                'message': str(e),
                'type': type(e).__name__
            }, status=500)
        else:
            # In production, return a generic error message
            return JsonResponse({
                'status': 'error',
                'message': 'An error occurred while processing your request'
            }, status=500)
    
def warmup_store_cache():
    """Warm up cache for frequently accessed store data"""
    try:
        # Warm up categories with products
        categories = Category.objects.all().order_by('name')
        cache.set('all_categories', categories, timeout=3600)  # 1 hour

        # Warm up featured and popular products
        products = Product.objects.select_related('category').prefetch_related(
            'recommendations', 
            'recommendations__faculty', 
            'recommendations__faculty__user'
        ).filter(is_available=True)
        
        # Cache featured products
        featured_products = products.filter(featured=True)
        cache.set('featured_products', featured_products, timeout=3600)

        # Cache popular products (those with most recommendations)
        popular_products = products.annotate(
            rec_count=Count('recommendations')
        ).filter(rec_count__gt=0).order_by('-rec_count')[:20]
        cache.set('popular_products', popular_products, timeout=3600)

        # Warm up department recommendations
        departments = Faculty.objects.values_list('department', flat=True).distinct()
        for dept in departments:
            recommendations = ProductRecommendation.objects.select_related(
                'faculty', 
                'faculty__user', 
                'product'
            ).filter(
                faculty__department=dept,
                product__is_available=True
            ).order_by('-is_essential', '-created_at')
            cache.set(f'department_recommendations_{dept}', recommendations, timeout=3600)

        logger.info("Store cache warmup completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error during cache warmup: {str(e)}")
        return False

# Modify your store view to use the warmup
def store(request, category_slug=None):    
    try:
        # Get filter parameters
        filters = {
            'department': request.GET.get('department', ''),
            'faculty_search': request.GET.get('faculty_search', ''),
            'essential_only': request.GET.get('essential_only') == 'on',
            'recommended_only': request.GET.get('recommended_only') == 'on',
        }
        
        # Handle sorting separately
        sort_form = ProductSortForm(request.GET)
        sort_by = request.GET.get('sort_by', '')

        # Create cache key based on all parameters
        cache_params = {
            **filters,
            'sort_by': sort_by,
            'category_slug': category_slug
        }
        cache_key = f"store_view:{hash(frozenset(cache_params.items()))}"

        def get_cached_data():
            """Get or compute filtered products"""
            # Base queryset with related fields
            queryset = Product.objects.select_related('category').prefetch_related(
                'recommendations', 
                'recommendations__faculty', 
                'recommendations__faculty__user'
            ).filter(is_available=True)

            # Apply category filter
            if category_slug:
                queryset = queryset.filter(category__slug=category_slug)

            # Apply faculty filters
            if filters['essential_only']:
                queryset = queryset.filter(recommendations__is_essential=True)
            
            if filters['recommended_only']:
                queryset = queryset.filter(recommendations__isnull=False)
            
            if filters['department']:
                queryset = queryset.filter(
                    recommendations__faculty__department=filters['department']
                )
            
            if filters['faculty_search']:
                queryset = queryset.filter(
                    Q(recommendations__faculty__user__first_name__icontains=filters['faculty_search']) |
                    Q(recommendations__faculty__user__last_name__icontains=filters['faculty_search'])
                )

            # Apply sorting
            if sort_form.is_valid() and sort_by:
                if sort_by == 'recommendations':
                    queryset = queryset.annotate(
                        recommendation_count=Count('recommendations')
                    ).order_by('-recommendation_count')
                else:
                    queryset = queryset.order_by(sort_by)

            return queryset.distinct()

        # Get cached data or compute it
        products = get_or_set_cache(cache_key, get_cached_data, timeout=900)
        departments = get_or_set_cache(
            'all_departments',
            lambda: list(Faculty.objects.values_list('department', flat=True).distinct()),
            timeout=3600
        )
        categories = get_or_set_cache(
            'all_categories',
            lambda: list(Category.objects.all().order_by('name')),
            timeout=3600
        )

        # Get current category
        current_category = None
        if category_slug:
            current_category = get_or_set_cache(
                f'category_{category_slug}',
                lambda: Category.objects.get(slug=category_slug),
                timeout=3600
            )

        context = {
            'products': products,
            'categories': categories,
            'departments': departments,
            'sort_form': sort_form,
            'selected_department': filters['department'],
            'faculty_search': filters['faculty_search'],
            'essential_only': filters['essential_only'],
            'recommended_only': filters['recommended_only'],
            'category': current_category,
            # Add these for the template
            'department': filters['department'],
            'sort_by': sort_by,
        }
        
        response = render(request, 'store/store.html', context)
        
        # Monitor performance
        if settings.DEBUG:
            from django.db import connection
            query_count = len(connection.queries)
            logger.debug(f'Store view queries: {query_count}')
            
        return response
        
    except Category.DoesNotExist:
        messages.error(request, f'Category "{category_slug}" not found.')
        return redirect('store')
    except Exception as e:
        logger.error(f'Error in store view: {str(e)}')
        messages.error(request, 'An error occurred while loading the store.')
        return redirect('home')

def periodic_cache_warmup(request):
    """Check and perform cache warmup if needed"""
    last_warmup = cache.get('last_cache_warmup')
    now = datetime.now()
    
    if not last_warmup or (now - last_warmup).total_seconds() > 3600:  # 1 hour
        warmup_store_cache()
        cache.set('last_cache_warmup', now)
        
def product_detail(request, category_slug, product_slug):
    try:
        # First check if the category exists
        category = get_object_or_404(Category, slug=category_slug)
        
        # Then try to get the product
        try:
            single_product = Product.objects.get(
                category=category,
                slug=product_slug
            )
        except Product.DoesNotExist:
            # Check if it's a digital product
            single_product = get_object_or_404(
                DigitalProduct,
                category=category,
                slug=product_slug
            )

        # Handle review submission - enforce authentication
        if request.method == 'POST':
            if not request.user.is_authenticated:
                messages.error(request, 'Please log in to submit a review.')
                return redirect('login')  # Redirect to login page with next parameter
            
            rating = request.POST.get('rating')
            review_text = request.POST.get('review')
            
            if not rating or not review_text:
                messages.error(request, 'Both rating and review are required.')
            else:
                try:
                    # Try to get existing review
                    review = ProductReview.objects.get(
                        product=single_product,
                        user=request.user
                    )
                    review.rating = rating
                    review.review = review_text
                    review.save()
                    messages.success(request, 'Your review has been updated.')
                except ProductReview.DoesNotExist:
                    # Create new review
                    ProductReview.objects.create(
                        product=single_product,
                        user=request.user,
                        rating=rating,
                        review=review_text
                    )
                    messages.success(request, 'Your review has been submitted.')
                
                return redirect('product_detail', 
                              category_slug=category_slug, 
                              product_slug=product_slug)
        
        # Get user's existing review if any
        user_review = None
        user_recommendation = None
        review_form = None
        
        if request.user.is_authenticated:
            user_review = ProductReview.objects.filter(
                product=single_product,
                user=request.user
            ).first()
            
            # Initialize form only for authenticated users
            review_form = ProductReviewForm(instance=user_review) if user_review else ProductReviewForm()
            
            # Get faculty recommendation if user is faculty
            if hasattr(request.user, 'faculty'):
                user_recommendation = ProductRecommendation.objects.filter(
                    product=single_product,
                    faculty=request.user.faculty
                ).first()
        
        # Get all reviews ordered by most recent
        reviews = single_product.reviews.all().order_by('-created_at')
        
        # Get all faculty recommendations
        recommendations = single_product.recommendations.select_related(
            'faculty', 
            'faculty__user'
        ).order_by('-created_at')

        context = {
            'single_product': single_product,
            'product_id': single_product.id,
            'review_form': review_form,
            'user_review': user_review,
            'reviews': reviews,
            'recommendations': recommendations,
            'user_recommendation': user_recommendation,
            'is_faculty': request.user.is_faculty if request.user.is_authenticated else False,
        }
        return render(request, 'store/product_detail.html', context)
        
    except Http404:
        messages.error(request, "The requested product was not found.")
        return redirect('store')
        
    except Exception as e:
        logger.error(f"Error in product_detail view: {str(e)}")
        messages.error(request, "An error occurred while loading the product.")
        return redirect('store')

def categories_processor(request):
    return {
        'categories': Category.objects.all()
    }

@login_required
def manage_category(request, category_id=None):
    category = None
    if category_id:
        category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 
                           f'Category {"updated" if category else "added"} successfully!')
            return redirect('manage_items')
    else:
        form = CategoryForm(instance=category)
    
    context = {
        'form': form,
        'title': 'Edit Category' if category else 'Add New Category',
        'category': category,
        'is_edit': bool(category)
    }
    return render(request, 'admin/category_form.html', context)

@login_required
def manage_product(request, product_id=None):
    product = None
    if product_id:
        try:
            product = DigitalProduct.objects.get(id=product_id)
        except DigitalProduct.DoesNotExist:
            product = get_object_or_404(Product, id=product_id)
    
    # Determine which form to use based on the product type
    product_type = request.GET.get('type', 'physical')
    if product_type == 'digital' or (product and isinstance(product, DigitalProduct)):
        form_class = DigitalProductForm
    else:
        form_class = ProductForm
    
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, 
                           f'Product {"updated" if product_id else "added"} successfully!')
            return redirect('manage_items')
    else:
        form = form_class(instance=product)
    
    context = {
        'form': form,
        'title': 'Edit Product' if product else 'Add New Product',
        'product': product,
        'is_edit': bool(product),
        'is_digital': product_type == 'digital' if not product else isinstance(product, DigitalProduct)
    }
    return render(request, 'admin/product_form.html', context)

@login_required
def manage_items(request):
    def convert_wildcard_to_regex(search_term):
        return '^' + search_term.replace('*', '.*') + '$'
    
    search_term = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'name')  # Default sort by name
    sort_dir = request.GET.get('dir', 'asc')   # Default ascending
    
    # Initialize querysets with sorting
    categories = Category.objects.all()
    
    # Get both regular products and digital products
    base_products = Product.objects.select_related('category').filter(digitalproduct__isnull=True)
    digital_products = DigitalProduct.objects.select_related('category')
    
    # Handle category sorting
    if sort_by == 'name':
        categories = categories.order_by('name' if sort_dir == 'asc' else '-name')
    elif sort_by == 'description':
        categories = categories.order_by('description' if sort_dir == 'asc' else '-description')
    
    # Calculate counts before filtering
    digital_count = digital_products.count()
    physical_count = base_products.count()
    out_of_stock = base_products.filter(stock=0).count()
    
    if search_term:
        # Handle wildcard searches
        if '*' in search_term:
            regex_pattern = convert_wildcard_to_regex(search_term)
            categories = categories.filter(
                Q(name__iregex=regex_pattern) |
                Q(description__iregex=regex_pattern)
            )
            
            # Filter both querysets separately
            base_products = base_products.filter(
                Q(name__iregex=regex_pattern) |
                Q(description__iregex=regex_pattern) |
                Q(category__name__iregex=regex_pattern) |
                Q(brand__iregex=regex_pattern)
            )
            digital_products = digital_products.filter(
                Q(name__iregex=regex_pattern) |
                Q(description__iregex=regex_pattern) |
                Q(category__name__iregex=regex_pattern) |
                Q(brand__iregex=regex_pattern)
            )
        else:
            # Regular search
            categories = categories.filter(
                Q(name__icontains=search_term) |
                Q(description__icontains=search_term)
            )
            
            # Filter both querysets separately
            base_products = base_products.filter(
                Q(name__icontains=search_term) |
                Q(description__icontains=search_term) |
                Q(category__name__icontains=search_term) |
                Q(brand__icontains=search_term)
            )
            digital_products = digital_products.filter(
                Q(name__icontains=search_term) |
                Q(description__icontains=search_term) |
                Q(category__name__icontains=search_term) |
                Q(brand__icontains=search_term)
            )

    # Convert to lists and add digital_type flag
    base_products = list(base_products)
    digital_products = list(digital_products)
    
    for product in base_products:
        product.digital_type = False
        
    for product in digital_products:
        product.digital_type = True
    
    # Combine the lists
    products = base_products + digital_products
    
    # Sort products
    def get_sort_key(product):
        if sort_by == 'name':
            return product.name.lower()
        elif sort_by == 'type':
            return str(product.digital_type)
        elif sort_by == 'category':
            return product.category.name.lower()
        elif sort_by == 'price':
            return float(product.price)
        return product.name.lower()  # default
    
    products.sort(
        key=get_sort_key,
        reverse=(sort_dir == 'desc')
    )
    
    # Calculate total after filtering
    total_products = len(products)
    
    # Sort combined products by created date for recent products
    products.sort(key=lambda x: x.created_date, reverse=True)
    recent_products = products[:5]
    
    context = {
        'categories': categories,
        'products': products,
        'search_term': search_term,
        'title': 'Manage Items',
        'sort_by': sort_by,
        'sort_dir': sort_dir,
        # Statistics
        'total_products': total_products,
        'digital_products': digital_count,
        'physical_products': physical_count,
        'out_of_stock': out_of_stock,
    }
    
    return render(request, 'admin/manage_items.html', context)

@login_required
def fetch_sorted_data(request):
    sort_by = request.GET.get('sort', 'name')
    sort_dir = request.GET.get('dir', 'asc')
    search_term = request.GET.get('search', '').strip()
    
    # Get both regular products and digital products
    base_products = Product.objects.select_related('category').filter(digitalproduct__isnull=True)
    digital_products = DigitalProduct.objects.select_related('category')
    categories = Category.objects.all()
    
    # Handle category sorting
    if sort_by == 'name':
        categories = categories.order_by('name' if sort_dir == 'asc' else '-name')
    elif sort_by == 'description':
        categories = categories.order_by('description' if sort_dir == 'asc' else '-description')
        
    # Convert to lists and add digital_type flag
    base_products = list(base_products)
    digital_products = list(digital_products)
    
    for product in base_products:
        product.digital_type = False
        
    for product in digital_products:
        product.digital_type = True
    
    # Combine the lists
    products = base_products + digital_products
    
    # Sort products
    def get_sort_key(product):
        if sort_by == 'name':
            return product.name.lower()
        elif sort_by == 'type':
            return str(product.digital_type)
        elif sort_by == 'category':
            return product.category.name.lower()
        elif sort_by == 'price':
            return float(product.price)
        elif sort_by == 'stock':
            if product.digital_type:
                # For digital products, sort by version
                # Convert version string to tuple of numbers for proper sorting
                # Example: "1.2.3" becomes (1, 2, 3)
                try:
                    return tuple(map(int, product.version.split('.')))
                except (AttributeError, ValueError):
                    return (0,)  # Default if version is invalid
            else:
                # For physical products, sort by stock number
                return product.stock
        return product.name.lower()  # default
    
    try:
        products.sort(
            key=get_sort_key,
            reverse=(sort_dir == 'desc')
        )
    except TypeError:
        # Fallback sorting if there's an error comparing different types
        products.sort(
            key=lambda x: str(get_sort_key(x)),
            reverse=(sort_dir == 'desc')
        )
    
    # Render just the table contents
    categories_html = render_to_string('admin/partials/categories_table.html', {
        'categories': categories,
        'sort_by': sort_by,
        'sort_dir': sort_dir,
        'search_term': search_term
    }, request)
    
    products_html = render_to_string('admin/partials/products_table.html', {
        'products': products,
        'sort_by': sort_by,
        'sort_dir': sort_dir,
        'search_term': search_term
    }, request)
    
    return JsonResponse({
        'categories_html': categories_html,
        'products_html': products_html
    })
    
@login_required
def delete_category(request, category_id):
    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id)
        category.delete()
        messages.success(request, f'Category "{category.name}" has been deleted.')
    return redirect('manage_items')

@login_required
def delete_product(request, product_id):
    if request.method == 'POST':
        try:
            product = DigitalProduct.objects.get(id=product_id)
        except DigitalProduct.DoesNotExist:
            product = get_object_or_404(Product, id=product_id)
        
        product_name = product.name
        product.delete()
        messages.success(request, f'Product "{product_name}" has been deleted.')
    return redirect('manage_items')
