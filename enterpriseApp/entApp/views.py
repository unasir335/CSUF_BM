from django.shortcuts import render, HttpResponse
from .models import CategoryItem
from django.contrib.auth.forms import AuthenticationForm

# Create your views here. (Updated: 10/26)
def home(request):
    featured_items = CategoryItem.objects.filter(available=True)[:5] # Get first 5 available items
    return render(request,"home.html") 

def login(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
    if form.is_valid:
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
    if username is not None:
        login(request, username)
        return HttpResponse("Login successful!")
    else:
        form = AuthenticationForm()
    return render(request,"login.html", {'form': form})
         
def categories(request):
    catItems = CategoryItem.objects.all()
    return render(request, "categories.html", {"categories": catItems})

def aboutUs(request):
    return render(request, "aboutUs.html")
