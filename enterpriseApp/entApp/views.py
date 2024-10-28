from django.shortcuts import render, HttpResponse
from .models import CategoryItem

# Create your views here.
def home(request):
    return render(request,"home.html")

def login(request):
    return render(request,"login.html")

def aboutUs(request):
    return render(request, "aboutUs.html")

def contact_us(request):
    return render(request, "contact_us.html")