from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from products.models import Product
from .models import Cart, CartItem

import logging
logger = logging.getLogger(__name__)

def cart_context_processor(request):
    """
    Context processor to provide cart information to all templates
    """
    try:
        cart = getattr(request, 'cart', None)
        if cart:
            cart_items = cart.items.all()
            return {
                'cart_item_count': sum(item.quantity for item in cart_items),
                'cart_total': cart.cart_total,
                'cart_tax': cart.tax,
                'cart_total_with_tax': cart.total_with_tax,
            }
    except Exception as e:
        logger.error(f"Error in cart context processor: {str(e)}")
    
    return {
        'cart_item_count': 0,
        'cart_total': 0,
        'cart_tax': 0,
        'cart_total_with_tax': 0
    }
    
def cart_middleware(get_response):
    def middleware(request):
        # Attach cart to request
        request.cart = get_or_create_cart(request)
        response = get_response(request)
        return response
    return middleware

#10/23 updated to reflect changes
def get_or_create_cart(request):
    """
    Get existing cart or create new one
    """
    try:
        if request.user.is_authenticated:
            cart, created = Cart.objects.get_or_create(user=request.user)
            if 'cart_id' in request.session:
                del request.session['cart_id']
            return cart
            
        cart_id = request.session.get('cart_id')
        if cart_id:
            try:
                return Cart.objects.get(id=cart_id)
            except Cart.DoesNotExist:
                pass
                
        cart = Cart.objects.create()
        request.session['cart_id'] = cart.id
        return cart
        
    except Exception as e:
        logger.error(f"Error creating cart: {str(e)}")
        cart = Cart.objects.create()
        request.session['cart_id'] = cart.id
        return cart

@require_POST
def add_to_cart(request, product_id):
    """
    Add product to cart with proper messages
    """
    try:
        product = get_object_or_404(Product, id=product_id)
        cart = get_or_create_cart(request)
        
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            messages.error(request, "Please enter a valid quantity.")
            return redirect('product_detail', category_slug=product.category.slug, product_slug=product.slug)

        if not product.is_digital and quantity > product.stock:
            messages.error(request, f"Sorry, only {product.stock} items available.")
            return redirect('product_detail', category_slug=product.category.slug, product_slug=product.slug)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': 0}
        )

        cart_item.quantity += quantity
        cart_item.save()

        messages.success(request, f"{quantity} {product.name}(s) added to your cart.")
        
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        messages.error(request, "Sorry, there was an error adding the item to your cart.")
        
    return redirect('product_detail', category_slug=product.category.slug, product_slug=product.slug)
    
def cart_detail(request):
    """View cart with logging"""
    try:
        cart = request.cart
        logger.debug(f"Cart detail view - User: {request.user.email if request.user.is_authenticated else 'Guest'}")
        logger.debug(f"Cart ID: {cart.id if cart else 'No cart'}")
        logger.debug(f"Cart items: {cart.items.count() if cart else 0}")
        
        context = {
            'cart': cart,
            'cart_items': cart.items.all() if cart else [],
        }
        return render(request, 'cart/cart_detail.html', context)
        
    except Exception as e:
        logger.error(f"Error in cart detail: {str(e)}", exc_info=True)
        messages.error(request, "Sorry, there was an error displaying your cart.")
        return redirect('home')

@require_POST
def update_cart(request, item_id):
    cart = get_or_create_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    quantity = int(request.POST.get('quantity', 0))
    if quantity > 0:
        cart_item.update_quantity(quantity)
    else:
        cart_item.delete()
    return redirect('cart_detail')

def remove_from_cart(request, item_id):
    cart = get_or_create_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f"{product_name} removed from your cart.")
    return redirect('cart_detail')

@login_required
def merge_carts(request):
    session_cart_id = request.session.get('cart_id')
    if session_cart_id:
        try:
            session_cart = Cart.objects.get(id=session_cart_id)
            user_cart = get_or_create_cart(request)
            
            if session_cart != user_cart:
                for item in session_cart.items.all():
                    user_item, created = CartItem.objects.get_or_create(cart=user_cart, product=item.product)
                    if not created:
                        user_item.quantity += item.quantity
                    else:
                        user_item.quantity = item.quantity
                    user_item.update_quantity(user_item.quantity)
                session_cart.delete()
                del request.session['cart_id']
            
            messages.success(request, "Your guest cart has been merged with your account.")
        except Cart.DoesNotExist:
            pass
    
    return redirect('cart_detail')