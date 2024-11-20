from django.shortcuts import render, HttpResponse, get_object_or_404
from .models import CategoryItem
from products.models import Product, Category
from products.forms import ProductSortForm

# Create your views here.
def home(request, category_slug=None):
    categories = None
    products = None
    sort_form = ProductSortForm(request.GET)

    if category_slug != None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories, is_available=True)
    else:
        products = Product.objects.all().filter(is_available=True)


    if sort_form.is_valid():
        sort_by = sort_form.cleaned_data['sort_by']
        if sort_by:
            products = products.order_by(sort_by)

    context = {

        'products': products,
        'sort_form': sort_form,
    }
    return render(request, 'home.html', context)

def login(request):
    return render(request,"login.html")

def categories(request):
    catItems = CategoryItem.objects.all()
    return render(request, "categories.html", {"categories": catItems})

def aboutUs(request):
    return render(request, "aboutUs.html")

def contact_us(request):
    return render(request, "contact_us.html")