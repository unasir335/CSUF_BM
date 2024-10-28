from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Product, Category, DigitalProduct, ProductReview, ProductRecommendation
from django.contrib import messages #added 10/22
from .forms import ProductSortForm, CategoryForm, ProductForm, DigitalProductForm, ProductReviewForm # Added 10/22 CategoryForm and ProductForm, 10/26 digital product
from django.db.models import Q, Count
from accounts.models import Faculty
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.http import Http404
# Create your views here.

import logging

logger = logging.getLogger(__name__)

def is_faculty(user):
    return user.is_authenticated and user.is_faculty

@login_required
@user_passes_test(is_faculty)
def toggle_recommendation(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    try:
        product = get_object_or_404(Product, id=product_id)
        faculty = request.user.faculty
        recommendation_text = request.POST.get('recommendation_text', '')
        is_essential = request.POST.get('is_essential', False) == 'true'
        
        recommendation, created = ProductRecommendation.objects.update_or_create(
            product=product,
            faculty=faculty,
            defaults={
                'recommendation_text': recommendation_text,
                'is_essential': is_essential
            }
        )
        
        action = 'created' if created else 'updated'
        return JsonResponse({
            'status': 'success',
            'message': f'Recommendation {action}',
            'recommendation_id': recommendation.id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@user_passes_test(is_faculty)
def remove_recommendation(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    try:
        recommendation = get_object_or_404(
            ProductRecommendation, 
            product_id=product_id, 
            faculty=request.user.faculty
        )
        recommendation.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Recommendation removed'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def get_product_recommendations(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    recommendations = product.recommendations.select_related('faculty', 'faculty__user').all()
    
    recommendations_data = []
    for rec in recommendations:
        recommendations_data.append({
            'faculty_name': rec.faculty.user.get_full_name(),
            'department': rec.faculty.department,
            'recommendation_text': rec.recommendation_text,
            'is_essential': rec.is_essential,
            'created_at': rec.created_at.strftime('%B %d, %Y')
        })
    
    return JsonResponse({
        'recommendations': recommendations_data
    })

#modified 10/26
def store(request, category_slug=None):    
    # Get filter parameters
    department = request.GET.get('department', '')
    faculty_search = request.GET.get('faculty_search', '')
    essential_only = request.GET.get('essential_only') == 'on'
    recommended_only = request.GET.get('recommended_only') == 'on'
    sort_form = ProductSortForm(request.GET)

    # Base queryset with related fields
    products = Product.objects.select_related('category').prefetch_related(
        'recommendations', 'recommendations__faculty', 'recommendations__faculty__user'
    ).filter(is_available=True)

    # Apply category filter
    if category_slug:
        categories = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=categories)

    # Apply faculty filters
    if essential_only:
        products = products.filter(recommendations__is_essential=True).distinct()
    
    if recommended_only:
        products = products.filter(recommendations__isnull=False).distinct()
    
    if department:
        products = products.filter(recommendations__faculty__department=department).distinct()
    
    if faculty_search:
        products = products.filter(
            Q(recommendations__faculty__user__first_name__icontains=faculty_search) |
            Q(recommendations__faculty__user__last_name__icontains=faculty_search)
        ).distinct()

    # Apply sorting
    if sort_form.is_valid():
        sort_by = sort_form.cleaned_data['sort_by']
        if sort_by == 'recommendations':
            products = products.annotate(
                recommendation_count=Count('recommendations')
            ).order_by('-recommendation_count')
        elif sort_by:
            products = products.order_by(sort_by)

    # Get unique departments for filter dropdown
    departments = Faculty.objects.values_list('department', flat=True).distinct()

    context = {
        'products': products,
        'categories': Category.objects.all(),
        'departments': departments,
        'sort_form': sort_form,
        'selected_department': department,
        'faculty_search': faculty_search,
        'essential_only': essential_only,
        'recommended_only': recommended_only,
        'category': categories if category_slug else None,
    }
    
    return render(request, 'store/store.html', context)

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
        
        # Get user's existing review if any
        user_review = None
        user_recommendation = None
        
        if request.user.is_authenticated:
            user_review = ProductReview.objects.filter(
                product=single_product,
                user=request.user
            ).first()
            
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
            'product_id': single_product.id,  # Explicitly add product_id to context
            'review_form': ProductReviewForm(instance=user_review) if user_review else ProductReviewForm(),
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

#added 10/18

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


    
    