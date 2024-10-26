from django.db import models

# Create your models here. (Updated: 10/26)

# The User model represents a user in the system.
class User(models.Model):
    username = models.CharField(max_length=255) # The username field stores a unique name for each user.
    email = models.EmailField(unique=True) # The email field stores the user's email address and must be unique.

    def __str__(self):
        return self.username # The str method will return a human-readable representation of the object.

# The CategoryItem model represents an item that can be categorized.
class CategoryItem(models.Model):
    title = models.CharField(max_length=200) 
    description = models.TextField(blank=True)
    available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
