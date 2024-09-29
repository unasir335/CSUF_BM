from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from products.models import Product
from .models import Cart, CartItem

# Create your views here.
def get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_or_create_cart(request)
    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)
    
    if not item_created:
        cart_item.quantity += 1
    cart_item.update_quantity(cart_item.quantity)

    messages.success(request, f"{product.name} added to your cart.")
    return redirect('product_detail', category_slug=product.category.slug, product_slug=product.slug)

def cart_detail(request):
    cart = get_or_create_cart(request)
    return render(request, 'cart/cart_detail.html', {'cart': cart})

def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart=get_or_create_cart(request))
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 0))
        if quantity > 0:
            cart_item.update_quantity(quantity)
        else:
            cart_item.delete()
    return redirect('cart_detail')

def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart=get_or_create_cart(request))
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f"{product_name} removed from your cart.")
    return redirect('cart_detail')

@login_required
def merge_carts(request):
    session_cart = Cart.objects.filter(session_key=request.session.session_key).first()
    user_cart, created = Cart.objects.get_or_create(user=request.user)
    
    if session_cart:
        for item in session_cart.items.all():
            user_item, created = CartItem.objects.get_or_create(cart=user_cart, product=item.product)
            if not created:
                user_item.quantity += item.quantity
            else:
                user_item.quantity = item.quantity
            user_item.update_quantity(user_item.quantity)
        session_cart.delete()
    
    messages.success(request, "Your guest cart has been merged with your account.")
    return redirect('cart_detail')