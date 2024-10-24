from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from products.models import Product
from .models import Cart, CartItem

# Added 10/18 middleware for cart update and attach to objects
def cart_middleware(get_response):
    def middleware(request):
        request.cart = get_or_create_cart(request)
        response = get_response(request)
        return response
    return middleware

    
#updated 10/23 /expanded to include tax
def cart_context_processor(request):
    cart = getattr(request, 'cart', None)
    if cart:
        return {
            'cart_item_count': cart.item_count,
            'cart_total': cart.cart_total,
            'cart_tax': cart.tax,
            'cart_total_with_tax': cart.total_with_tax,
        }
    return {
        'cart_item_count': 0,
        'cart_total': 0,
        'cart_tax': 0,
        'cart_total_with_tax': 0
    }

#10/23 updated to reflect changes
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

@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    
    cart_item, created = CartItem.objects.get_or_create(cart=request.cart, product=product)
    
    if not created:
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity
    cart_item.update_quantity(cart_item.quantity)

    messages.success(request, f"{quantity} {product.name}(s) added to your cart.")
    return redirect('product_detail', category_slug=product.category.slug, product_slug=product.slug)

def cart_detail(request):
    cart = get_or_create_cart(request)
    cart_items = cart.items.all()
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'cart_total': cart.cart_total,  # Added cart_total explicitly
        'item_count': cart.item_count
    }
    return render(request, 'cart/cart_detail.html', context)

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