from django.urls import path
from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("categories/", views.categories, name='Categories'),
    path("", views.login, name="Login")
]
