from django.urls import path
from . import views
from accounts import views as account_views

urlpatterns = [
    path("", views.home, name="home"),
    path("categories/", views.categories, name='Categories'),
    path('login/', account_views.login, name='login'), 
    path('logout/', account_views.logout, name='logout'), 
    path("about-us/", views.aboutUs, name="About Us"),
    path("", views.login, name="Login")
]
