from django.shortcuts import render, HttpResponse
#from .models import LoginItem

# Create your views here.
def login(request):
    return render(request,"loginMenu.html")
