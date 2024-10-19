from django.contrib import admin
from .models import Account, Address, Student, Faculty

class AddressInline(admin.StackedInline):
    model = Address
    can_delete = False
    verbose_name_plural = 'Address'

class AccountAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'username', 'last_login', 'date_joined', 'is_active')
    list_display_links = ('email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('-date_joined',)

    filter_horizontal = ()
    list_filter = ()
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'username', 'phone_number', 'profile_picture')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superadmin')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    inlines = (AddressInline,)

admin.site.register(Account, AccountAdmin)
admin.site.register(Student)
admin.site.register(Faculty)