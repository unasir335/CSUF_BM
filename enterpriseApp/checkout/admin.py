from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Order, OrderProduct

class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    extra = 1  # Number of empty forms to display
    fields = ('product', 'quantity', 'product_price', 'ordered')
    readonly_fields = ('product_price',)  # Optionally make product price read-only

class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'user', 'full_name', 'order_total', 
        'tax', 'status', 'created_at', 'payment_status'
    )
    search_fields = ('order_number', 'user__username', 'first_name', 'last_name', 'email')
    list_filter = ('status', 'payment_status', 'created_at')
    inlines = [OrderProductInline]  # Include the order products inline

    def full_name(self, obj):
        return obj.full_name()
    full_name.short_description = 'Customer Name'  # Custom label in admin

admin.site.register(Order, OrderAdmin)
