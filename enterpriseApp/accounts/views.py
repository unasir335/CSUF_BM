from django.shortcuts import render, redirect
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .forms import RegistrationForm, LoginForm
from .models import Account


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            phone_number = form.cleaned_data['phone_number']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            username = email.split("@")[0]
            user = Account.objects.create_user(first_name=first_name, last_name=last_name, email=email, username=username, password=password)
            user.phone_number = phone_number
            user.save()
            messages.success(request, 'Registration successful.')
            return redirect('login')
    else:
        form = RegistrationForm()
    context = {
        'form': form,
    }
    return render(request, 'accounts/register.html', context)


def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = auth.authenticate(email=email, password=password)
            if user is not None:
                auth_login(request, user)
                #messages.success(request, 'You are now logged in.')
                return redirect('home')  # or 'dashboard'
            else:
                messages.error(request, 'Invalid login credentials')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    return redirect('logout_success')

def logout_success(request):
    #messages.success(request, 'You are logged out.')
    return render(request, 'accounts/logout_success.html')

# - THINKING ABOUT USER DASHBOARD THAT LISTS THEIR SHOPPING STUFF
@login_required(login_url='login')
def dashboard(request):
    return render(request, 'accounts/dashboard.html')