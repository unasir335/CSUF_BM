from django.db import models
from django.conf import settings
from products.models import Product #notice, this module is dependent on products models.py content of Product
from decimal import Decimal # added 10/23
# Create your models here.

# Updated 10/23
class Order(models.Model):
    ORDER_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    order_number = models.CharField(max_length=20, unique=True)
    
    # Shipping Information
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(max_length=50)
    phone = models.CharField(max_length=15)
    address_line_1 = models.CharField(max_length=50)
    address_line_2 = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    zipcode = models.CharField(max_length=10)
    
    # Billing Information - Making these nullable for existing orders
    billing_first_name = models.CharField(max_length=50, null=True, blank=True)
    billing_last_name = models.CharField(max_length=50, null=True, blank=True)
    billing_address_line_1 = models.CharField(max_length=50, null=True, blank=True)
    billing_address_line_2 = models.CharField(max_length=50, blank=True)
    billing_city = models.CharField(max_length=50, null=True, blank=True)
    billing_state = models.CharField(max_length=50, null=True, blank=True)
    billing_country = models.CharField(max_length=50, null=True, blank=True)
    billing_zipcode = models.CharField(max_length=10, null=True, blank=True)
    
    # Order Information
    order_total = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default='PENDING')
    ip = models.CharField(blank=True, max_length=20)
    is_ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    order_note = models.CharField(max_length=100, blank=True)

    # Payment fields
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PAID', 'Paid'),
            ('FAILED', 'Failed'),
            ('REFUNDED', 'Refunded')
        ],
        default='PENDING'
    )
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True)
    last_four = models.CharField(max_length=4, blank=True)

    def full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def billing_full_name(self):
        if self.billing_first_name and self.billing_last_name:
            return f'{self.billing_first_name} {self.billing_last_name}'
        return self.full_name()  # Fall back to shipping name if billing name not set

    def full_address(self):
        return f'{self.address_line_1} {self.address_line_2}'
    
    def billing_full_address(self):
        if self.billing_address_line_1:
            return f'{self.billing_address_line_1} {self.billing_address_line_2}'
        return self.full_address()  # Fall back to shipping address if billing address not set
    
    # Added 10/23
    # Calculate order subtotal before tax
    def get_subtotal(self):
        return self.order_total

    # Get tax amount
    def get_tax_amount(self):
        return self.tax

    # Calculate total including tax
    def get_total_with_tax(self):
        return self.order_total + self.tax

    # Calculate total from order items
    def get_items_total(self):
        return sum(item.get_total() for item in self.items.all())
   
    def __str__(self):
        return self.order_number

class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product.name
    
    #10/23 Added
    def get_total(self):
        return self.product_price * self.quantity