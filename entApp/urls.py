from django.urls import path
from . import views
from accounts import views as account_views

urlpatterns = [
    path("", views.home, name="home"),
    path("about-us/", views.aboutUs, name="about"),
    path("contact-us/", views.contact_us, name ="contact-us"),
    path("walkthrough/", views.sys_walkthrough, name="sys_walkthrough"),
    path("walkthrough/1/", views.sys_arch, name="sys_arch"),
    path("walkthrough/2/", views.sys_arch2, name="sys_arch2"),
    path("walkthrough/3/", views.sys_arch3, name="sys_arch3"),
    path("walkthrough/4/", views.sys_arch4, name="sys_arch4"),
    path("walkthrough/5/", views.sys_arch5, name="sys_arch5"),
    path("walkthrough/6/", views.security_flow, name="security_flow"),
    

]
