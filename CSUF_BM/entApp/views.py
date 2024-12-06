from django.shortcuts import render, HttpResponse
from products.models import Product, Category
from django.db.models import Avg


def home(request):
    # Get featured/active products
    products = Product.objects.filter(
        is_available=True
    ).annotate(
        avg_rating=Avg('reviews__rating')
    ).order_by('-created_date')
    
    # Get categories
    categories = Category.objects.all()
    
    context = {
        'products': products,
        'categories': categories,
    }
    
    return render(request, 'home.html', context)


def login(request):
    return render(request,"login.html")

def aboutUs(request):
    return render(request, "aboutUs.html")

def contact_us(request):
    return render(request, "contact_us.html")

def sys_arch(request):
    return render(request, "presentation/system_architecture.html")

def sys_arch2(request):
    return render(request, "presentation/system_architecture2.html")

def sys_arch3(request):
    return render(request, "presentation/system_architecture3.html")

def sys_arch4(request):
    return render(request, "presentation/system_architecture4.html")

def sys_arch5(request):
    return render(request, "presentation/system_architecture5.html")

def security_flow(request):
    return render(request, "presentation/security_flow.html")

def sys_walkthrough(request):
    return render(request, "presentation/system_walkthrough.html")