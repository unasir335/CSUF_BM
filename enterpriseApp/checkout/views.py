from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from cart.models import Cart, CartItem
from .models import Order, OrderProduct
from .forms import OrderForm, GuestOrderForm
import datetime
import uuid

# Create your views here.

def checkout(request):
    cart = Cart.objects.get(session_key=request.session.session_key) if not request.user.is_authenticated else Cart.objects.get(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)
    
    if request.method == 'POST':
        form = OrderForm(request.POST) if request.user.is_authenticated else GuestOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            order.order_total = cart.total
            order.tax = cart.total * 0.1  # Assuming 10% tax/change if you feel like it.
            order.ip = request.META.get('REMOTE_ADDR')
            order.order_number = str(uuid.uuid4())[:10].upper()  # Generate a unique order number
            order.save()

            # Create order products
            for cart_item in cart_items:
                OrderProduct.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    product_price=cart_item.product.price,
                    ordered=True
                )
                
                # Reduce the quantity of the sold products
                product = cart_item.product
                product.stock -= cart_item.quantity
                product.save()

            # Clear cart
            cart_items.delete()
            
            # TODO: PAYMENT GATEWAY GOES HERE / WE'LL FIGURE THIS ONE OUT LATER. IGNORE THIS BIT FOR NOW
            
            messages.success(request, 'Order placed successfully.')
            return redirect('order_complete')
    else:
        initial_data = {}
        if request.user.is_authenticated:
            initial_data = {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': request.user.phone_number,
                'address_line_1': request.user.address_line1,
                'address_line_2': request.user.address_line2,
                'city': request.user.city,
                'state': request.user.state,
                'country': request.user.country,
                'zipcode': request.user.zipcode,
            }
        form = OrderForm(initial=initial_data) if request.user.is_authenticated else GuestOrderForm() 
    
    context = {
        'form': form,
        'cart_items': cart_items,
        'total': cart.total,
        'tax': cart.total * 0.1,
        'grand_total': cart.total * 1.1,
    }
    return render(request, 'checkout/checkout.html', context)

def order_complete(request):
    return render(request, 'checkout/order_complete.html')

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