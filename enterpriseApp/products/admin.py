from django.contrib import admin
from .models import Category, Product, ProductImage, ProductReview

# Register your models here.

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductReviewInline(admin.TabularInline):
    model = ProductReview
    extra = 0
    readonly_fields = ('user', 'rating', 'review', 'created_at')

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'is_available', 'modified_date')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('category', 'is_available')
    list_editable = ('is_available', 'stock')
    inlines = [ProductImageInline, ProductReviewInline]

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

admin.site.register(Category, CategoryAdmin)
admin.site.register(Product, ProductAdmin)