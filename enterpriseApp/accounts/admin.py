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

    """
    Fieldsets for the add view.
    """

    def full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}' #Returns the full name of the account holder.
    
    full_name.short_description = 'Full Name' # Add a human-readable description to the full_name method

    # Define a custom action to activate selected accounts
    def activate_accounts(modeladmin, request, queryset):
        queryset.update(is_active=True)
    
    # Define a custom action to deactivate selected accounts
    def deactivate_accounts(modeladmin, request, queryset):
        queryset.update(is_active=False)

    # Add a human-readable description to the deactivate_accounts action
    activate_accounts.short_description = 'Activate selected accounts'
    deactivate_accounts.short_description = 'Deactivate selected accounts'

    # Define a list of custom actions that will be available in the admin interface
    actions = [activate_accounts, deactivate_accounts] 

    # Customize the title and header of the admin interface
    admin.site.site_title = 'Your Site Title'
    admin.site.site_header = "Your Site Header"  

admin.site.register(Account, AccountAdmin)
admin.site.register(OrderHistory)
