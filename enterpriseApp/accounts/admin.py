from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import Account, Address, Student, Faculty

class AddressInline(admin.StackedInline):
    model = Address
    can_delete = False
    verbose_name_plural = 'Address'

class AccountAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'username', 'last_login', 'is_active')
    list_display_links = ('email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('-date_joined',)
    
    filter_horizontal = ()
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'is_student', 'is_faculty')
    
    fieldsets = (
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'username', 'email', 'password', 'profile_picture')
        }),
        ('Security Info', {
            'fields': ('security_question', 'security_answer')
        }),
        ('Contact Info', {
            'fields': ('phone_number',)
        }),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser', 'is_admin',
                'is_student', 'is_faculty', 'groups', 'user_permissions'
            )
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'username', 'password1', 'password2',
                'first_name', 'last_name', 'phone_number',
                'security_question', 'security_answer',
                'is_active', 'is_staff', 'is_superuser',
                'is_admin', 'is_student', 'is_faculty'
            ),
        }),
    )

    def get_profile_picture(self, obj):
        if obj.profile_picture:
            return format_html('<img src="{}" width="30" style="border-radius: 50%;">', obj.profile_picture.url)
        return format_html('<img src="/media/profile_pics/80x80.png" width="30" style="border-radius: 50%;">')
    get_profile_picture.short_description = 'Profile Picture'

    search_fields = ('email', 'first_name', 'last_name', 'username')
    ordering = ('email',)

admin.site.register(Account, AccountAdmin)
admin.site.register(Student)
admin.site.register(Faculty)