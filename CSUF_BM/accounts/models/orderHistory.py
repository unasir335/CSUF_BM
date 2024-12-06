from django.db import models
from django.conf import settings

class OrderHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='order_history')
    order_number = models.CharField(max_length=20)
    order_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"Order {self.order_number} for {self.user.username}"

    class Meta:
        ordering = ['-order_date']