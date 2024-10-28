from django.db import models
from django.urls import reverse
from django.utils.text import slugify

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(max_length=255, blank=True)
    image = models.ImageField(upload_to='photos/categories', blank=True)
    
    class Meta:
        verbose_name = 'category'
        verbose_name_plural = 'categories'
    
    def get_url(self):
        return reverse('products_by_category', args=[self.slug])

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(Category, self).save(*args, **kwargs)


class Product(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(max_length=500, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='photos/products')
    stock = models.IntegerField()
    is_available = models.BooleanField(default=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    
    brand = models.CharField(max_length=100, blank=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    featured = models.BooleanField(default=False)

    PRODUCT_TYPES = (
        ('physical', 'Physical Product'),
        ('digital', 'Digital Product'),
    )
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='physical')
    
    @property
    def is_digital(self):
        return False
    
    @property
    def discounted_price(self):
        return self.price * (1 - self.discount / 100)
    
    def get_url(self):
        return reverse('product_detail', args=[self.category.slug, self.slug])

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if self.product_type == 'digital':
            self.stock = -1  # Indicates unlimited stock
        super().save(*args, **kwargs)

    @property
    def discounted_price(self):
        return self.price * (1 - self.discount / 100)

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='photos/products')
    alt_text = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.product.name} - Image {self.id}"

class ProductReview(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey('accounts.Account', on_delete=models.CASCADE)
    rating = models.IntegerField()
    review = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.rating} stars"

    def save(self, *args, **kwargs):
        super(ProductReview, self).save(*args, **kwargs)
        # Update average rating
        self.product.average_rating = self.product.reviews.aggregate(models.Avg('rating'))['rating__avg']
        self.product.save()

class DigitalProduct(Product):
    version = models.CharField(max_length=50)
    download_link = models.URLField(max_length=500)
    file_size = models.CharField(max_length=50, help_text="e.g., '15 MB'")
    system_requirements = models.TextField(blank=True)
    release_notes = models.TextField(blank=True)
    
    def save(self, *args, **kwargs):
        self.stock = -1  # Indicates unlimited stock for digital products
        super().save(*args, **kwargs)
    
    @property
    def is_digital(self):
        return True
    
    
class ProductRecommendation(models.Model):
    product = models.ForeignKey(Product, related_name='recommendations', on_delete=models.CASCADE)
    faculty = models.ForeignKey('accounts.Faculty', related_name='recommended_products', on_delete=models.CASCADE)
    recommendation_text = models.TextField(help_text="Share why you recommend this product")
    is_essential = models.BooleanField(default=False, help_text="Mark if this is essential for your class")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['product', 'faculty']  # One recommendation per product per faculty
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} recommended by {self.faculty.user.get_full_name()}"
        
        