from django.db import models
from django.conf import settings

class Address(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='address')
    address_line1 = models.CharField(max_length=100, blank=True)
    address_line2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, blank=True)
    zipcode = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f'{self.address_line1}, {self.city}, {self.state}, {self.country}'

# class OrderHistory(models.Model):
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='order_history')
#     order_number = models.CharField(max_length=20)
#     order_date = models.DateTimeField(auto_now_add=True)
#     total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
#     def __str__(self):
#         return f"Order {self.order_number} for {self.user.username}"

#     class Meta:
#         ordering = ['-order_date']