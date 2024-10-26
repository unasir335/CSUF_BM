from django.db import models

# Create your models here. (Updated: 10/26)
class User(models.Model):
    username = models.CharField(max_length=255)
    email = models.EmailField(unique=True)

class CategoryItem(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
