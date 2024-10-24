from django.db import models
from django.conf import settings
from products.models import Product
from decimal import Decimal

class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        if self.user:
            return f"Cart for {self.user.username}"
        return f"Guest Cart {self.session_key}"
    #10/24 update
    @property
    def cart_total(self):
        return sum(item.subtotal for item in self.items.all()) 
    #10/24 update
    @property
    def tax_rate(self):
        return Decimal('10.0')  # 10% tax rate
    #10/24 update
    @property
    def tax(self):
        return (self.cart_total * Decimal('0.1')).quantize(Decimal('0.01'))
    #10/24 update
    @property
    def total_with_tax(self):
        return self.cart_total + self.tax

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} of {self.product.name}"

    #10/23 revised to product.price instead of discounted
    @property
    def subtotal(self):
        return self.product.price * self.quantity


    def update_quantity(self, quantity):
        self.quantity = max(1, min(quantity, self.product.stock))
        self.save()