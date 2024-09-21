from django.db import models

# Create Users model & credentials

class Person(models.Model):
    username    =   models.EmailField(max_length=50, required = True, unique = True)
    password    =   models.CharField(max_length=25, required = True)
    first_name  =   models.CharField(max_length=50, required = False)
    last_name   =   models.CharField(max_length=50, required = False)
    
    is_student  =   models.BooleanField(default=False)
    is_faculty  =   models.BooleanField(default=False)
    is_admin    =   models.BooleanField(default=False)
    
    created_on  =   models.DateTimeField(auto_now=True, auto_now_add=True)
    

class Person_Details(models.Model):
    pass



