from django.urls import path
from .views import (
    # Authentication views
    LoginView,
    LogoutView,
    LogoutSuccessView,
    RegisterView,
    StudentRegistrationView,
    FacultyRegistrationView,
    
    # Password management views
    PasswordRecoveryView,
    SecurityQuestionView,
    ResetPasswordView,
    
    # Profile and dashboard views
    DashboardView,
    UserProfileView,
    AdminDashboardView,
    
    # Function-based views
    change_password,
    update_profile_picture,
)

# Authentication URLs
auth_patterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('register/student/', StudentRegistrationView.as_view(), name='student_registration'),
    path('register/faculty/', FacultyRegistrationView.as_view(), name='faculty_registration'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('logout/success/', LogoutSuccessView.as_view(), name='logout_success'),
]

# Password management URLs
password_patterns = [
    path('password-recovery/', PasswordRecoveryView.as_view(), name='password_recovery'),
    path('security-question/', SecurityQuestionView.as_view(), name='security_question'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('change-password/', change_password, name='change_password'),
]

# User dashboard and profile URLs
user_patterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('profile/update-picture/', update_profile_picture, name='update_profile_picture'),
]

# Admin URLs
admin_patterns = [
    path('admin/dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),
    
]

# Combine all URL patterns
urlpatterns = [
    *auth_patterns,
    *password_patterns,
    *user_patterns,
    *admin_patterns,
]