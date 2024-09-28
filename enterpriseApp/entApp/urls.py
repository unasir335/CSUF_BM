from django.urls import path
from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("categories/", views.categories, name='Categories'),
    path("about-us/", views.aboutUs, name="About Us"),
    path("", views.login, name="Login")
]
