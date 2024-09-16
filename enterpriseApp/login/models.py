from django.db import models

# Create your models here.
class LoginItem(models.Model):
    userID = models.CharField(max_length=20)