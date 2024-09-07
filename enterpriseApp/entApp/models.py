from django.db import models

# Create your models here.

class CategoryItem(models.Model):
    title = models.CharField(max_length=200)
    available = models.BooleanField(default=True)
