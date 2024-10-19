from django.urls import path
from .views import (
    RegisterView, 
    LoginView, 
    LogoutView, 
    LogoutSuccessView, 
    DashboardView, 
    UserProfileView,
    change_password,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('logout/success/', LogoutSuccessView.as_view(), name='logout_success'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('change-password/', change_password, name='change_password'),
   
]