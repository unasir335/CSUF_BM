from django.shortcuts import render, HttpResponse
from .models import CategoryItem

# Create your views here.
def home(request):
    return render(request,"home.html")

def categories(request):
    catItems = CategoryItem.objects.all()
    return render(request, "categories.html", {"categories": catItems})