from django.contrib import admin

# Register your models here. (Updated: 10/26)

class OrderHistoryAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'order_date', 'total_amount')
    list_filter = ('user', 'order_date')
    search_fields = ('order_number', 'user__username')
    ordering = ('__order_date')

admin.site.register(OrderHistoryAdmin)
