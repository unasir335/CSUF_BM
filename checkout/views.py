from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from decimal import Decimal
from accounts.models.address import Address
from products.models import Product
from cart.models import Cart, CartItem
from .models import Order, OrderProduct
from .forms import OrderForm, GuestOrderForm, CreditCardForm, FakePaymentGateway
import datetime
import uuid
#10/23 added
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.core.exceptions import PermissionDenied
from django.db import transaction, DatabaseError
from time import sleep
from functools import wraps
import random
from django.http import JsonResponse
from django.template.loader import render_to_string

# Create your views here.
# updated 10/23
# Helper function to get initial data from user and related models
def get_user_initial_data(user):
    initial_data = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'phone': user.phone_number,  # Get phone from user if it exists
    }
    
    # Get Address data
    try:
        address = user.address  # Using the related_name from your Address model
        
        # Map the address fields to order form fields
        address_data = {
            # Shipping address fields
            'address_line_1': address.address_line1,  # Note the difference in naming
            'address_line_2': address.address_line2,
            'city': address.city,
            'state': address.state,
            'country': address.country,
            'zipcode': address.zipcode,
            
            # Billing address fields - copy shipping address by default
            'billing_first_name': user.first_name,
            'billing_last_name': user.last_name,
            'billing_address_line_1': address.address_line1,
            'billing_address_line_2': address.address_line2,
            'billing_city': address.city,
            'billing_state': address.state,
            'billing_country': address.country,
            'billing_zipcode': address.zipcode,
        }
        
        initial_data.update(address_data)
        
        # Debug print
        # print("Found address data:", address_data)
        
    except Exception as e:
        # More detailed error handling
        print(f"Error getting address data: {str(e)}")
        # Log the error details for debugging
        print(f"User has address attribute: {hasattr(user, 'address')}")
        if hasattr(user, 'address'):
            print(f"User address object: {user.address}")
    
    return initial_data

# Helper function to get or create cart based on user authentication status
def get_or_create_cart(request):

    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        cart_id = request.session.get('cart_id')
        if cart_id:
            try:
                cart = Cart.objects.get(id=cart_id)
            except Cart.DoesNotExist:
                cart = Cart.objects.create()
        else:
            cart = Cart.objects.create()
        request.session['cart_id'] = cart.id
    return cart

# 10/23
# Decorator to retry a function on deadlock with exponential backoff
def retry_on_deadlock(max_retries=3, initial_delay=0.1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retry_count = 0
            delay = initial_delay
            
            while retry_count < max_retries:
                try:
                    return func(*args, **kwargs)
                except DatabaseError as e:
                    if 'Deadlock found' in str(e) and retry_count < max_retries - 1:
                        retry_count += 1
                        # Add random jitter to prevent multiple retries from deadlocking again
                        sleep_time = delay + (random.random() * 0.1)
                        sleep(sleep_time)
                        delay *= 2  # Exponential backoff
                        continue
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Process order items with optimized locking
def process_order_items(cart_items, order):
    insufficient_stock_items = []
    
    # First, validate all stock levels
    products_to_update = []
    for cart_item in cart_items:
        product = cart_item.product
        if cart_item.quantity > product.stock:
            insufficient_stock_items.append(product.name)
        else:
            products_to_update.append((product, cart_item.quantity))
    
    if insufficient_stock_items:
        raise ValueError(f"Insufficient stock for: {', '.join(insufficient_stock_items)}")
    
    # Then create order items and update stock in a single transaction
    order_products = []
    for product, quantity in products_to_update:
        order_products.append(
            OrderProduct(
                order=order,
                product=product,
                quantity=quantity,
                product_price=product.price,
                ordered=True
            )
        )
        product.stock -= quantity
        
    # Bulk create order products
    OrderProduct.objects.bulk_create(order_products)
    
    # Bulk update products
    products = [p for p, _ in products_to_update]
    Product.objects.bulk_update(products, ['stock'])

@retry_on_deadlock()
@transaction.atomic
def checkout(request):
    try:
        cart = get_or_create_cart(request)
        cart_items = CartItem.objects.filter(cart=cart)
        
        if not cart_items.exists():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Your cart is empty.',
                    'redirect_url': reverse('cart_detail')
                })
            messages.warning(request, 'Your cart is empty.')
            return redirect('cart_detail')
        
        # Initialize forms
        if request.user.is_authenticated:
            initial_data = get_user_initial_data(request.user)
            order_form = OrderForm(initial=initial_data)
        else:
            order_form = GuestOrderForm()
        payment_form = CreditCardForm()
        
        if request.method == 'POST':
            # Re-initialize forms with POST data
            order_form = OrderForm(request.POST) if request.user.is_authenticated else GuestOrderForm(request.POST)
            payment_form = CreditCardForm(request.POST)
            
            if order_form.is_valid() and payment_form.is_valid():
                try:
                    with transaction.atomic():
                        # Save order
                        order = order_form.save(commit=False)
                        if request.user.is_authenticated:
                            order.user = request.user
                        
                        order.order_total = cart.cart_total
                        order.tax = cart.tax
                        order.ip = request.META.get('REMOTE_ADDR')
                        order.order_number = str(uuid.uuid4())[:10].upper()
                        
                        # Process payment
                        payment_gateway = FakePaymentGateway()
                        payment_result = payment_gateway.process_payment(order, payment_form.cleaned_data)
                        
                        if not payment_result['success']:
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': False,
                                    'error': "Payment processing failed"
                                })
                            raise ValueError("Payment processing failed")
                            
                        # If payment successful, proceed with order creation
                        order.payment_status = 'PAID'
                        order.transaction_id = payment_result['transaction_id']
                        order.payment_method = f"{payment_form.cleaned_data['card_type'].upper()} **** **** **** {payment_form.cleaned_data['card_number'][-4:]}"
                        order.last_four = payment_form.cleaned_data['card_number'][-4:]
                        order.save()
                        
                        # Validate stock
                        insufficient_stock_items = []
                        for cart_item in cart_items:
                            if cart_item.quantity > cart_item.product.stock:
                                insufficient_stock_items.append(cart_item.product.name)
                        
                        if insufficient_stock_items:
                            error_msg = f"Insufficient stock for: {', '.join(insufficient_stock_items)}"
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': False,
                                    'error': error_msg
                                })
                            raise ValueError(error_msg)
                        
                        # Create order products and update stock
                        for cart_item in cart_items:
                            OrderProduct.objects.create(
                                order=order,
                                product=cart_item.product,
                                quantity=cart_item.quantity,
                                product_price=cart_item.product.price,
                                ordered=True
                            )
                            
                            cart_item.product.stock -= cart_item.quantity
                            cart_item.product.save()
                        
                        # Clear cart
                        cart_items.delete()
                        
                        # Store order number in session
                        request.session['completed_order'] = order.order_number
                        
                        success_url = reverse('order_complete', kwargs={'order_number': order.order_number})
                        
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': True,
                                'redirect_url': success_url
                            })
                            
                        messages.success(request, 'Payment successful! Order placed successfully.')
                        return redirect(success_url)
                        
                except (ValueError, Exception) as e:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': str(e)
                        })
                    messages.error(request, str(e))
                    
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'errors': {
                            **{f'{k}': v for k, v in order_form.errors.items()},
                            **{f'{k}': v for k, v in payment_form.errors.items()}
                        }
                    })
                messages.error(request, 'Please correct the errors in the form.')
        
        # Handle GET request or form errors for regular submission
        context = {
            'order_form': order_form,
            'payment_form': payment_form,
            'cart': cart,
            'cart_items': cart_items,
            'cart_total': cart.cart_total,
            'tax': cart.tax,
            'total_with_tax': cart.total_with_tax,
        }
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Invalid request method',
                'html': render_to_string('checkout/checkout.html', context, request)
            })
            
        return render(request, 'checkout/checkout.html', context)
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        messages.error(request, f'An error occurred: {str(e)}')
        return redirect('cart_detail')

@never_cache
def order_complete(request, order_number):
    try:
        order = get_object_or_404(Order, order_number=order_number)
        
        # Verify ownership or session
        completed_order = request.session.get('completed_order')
        if not request.user.is_authenticated and completed_order != order_number:
            raise PermissionDenied("Invalid order access")
        elif request.user.is_authenticated and order.user != request.user:
            raise PermissionDenied("Invalid order access")

        context = {
            'order': order,
            'order_items': order.items.all(),
            'subtotal': order.get_subtotal(),
            'tax': order.get_tax_amount(),
            'total': order.get_total_with_tax()
        }
        
        response = render(request, 'checkout/order_complete.html', context)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response
        
    except PermissionDenied:
        messages.error(request, 'Invalid order access.')
        return redirect('home')
    except Order.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('home')


def track_order(request):
    if request.method == 'POST':
        order_number = request.POST.get('order_number')
        email = request.POST.get('email')
        try:
            order = Order.objects.get(order_number=order_number, email=email)
            return redirect('order_status', order_number=order.order_number)
        except Order.DoesNotExist:
            messages.error(request, 'No order found with the given details.')
    return render(request, 'checkout/track_order.html')

def order_status(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    order_products = OrderProduct.objects.filter(order=order)
    context = {
        'order': order,
        'order_products': order_products,
    }
    return render(request, 'checkout/order_status.html', context)