from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('logout/success/', views.logout_success, name='logout_success'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # TO - DO - possibly will just need 2 of them, reset and done. 
    
    # path('password_reset/',views.password_reset,name='password_reset'),
    # path('password_reset/done/',views.password_reset_done,name='password_reset_done'),
    # path('reset/<uidb64>/<token>/',views.password_reset_confirm,name='password_reset_confirm'),
    # path('reset/done/',views.password_reset_complete,name='password_reset_complete'),
]