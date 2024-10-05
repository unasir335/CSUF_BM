from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account, OrderHistory
# Register your models here.

class AccountAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'username', 'last_login', 'date_joined', 'is_active')
    list_display_links = ('email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('-date_joined',)

    filter_horizontal = ()
    list_filter = ('is_active', 'is_staff', 'is_superadmin')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'username', 'phone_number')}),
        ('Address', {'fields': ('address_line1', 'address_line2', 'city', 'state', 'country', 'zipcode')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superadmin', 'is_student', 'is_faculty')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'username', 'phone_number'),
        }),
    )

admin.site.register(Account, AccountAdmin)
admin.site.register(OrderHistory)
