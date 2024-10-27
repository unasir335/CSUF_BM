from django.urls import path
from . import views
from accounts import views as account_views

urlpatterns = [
    path("", views.home, name="home"),
    path("about-us/", views.aboutUs, name="about"),

]
