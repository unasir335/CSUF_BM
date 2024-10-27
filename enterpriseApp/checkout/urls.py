from django.urls import path
from . import views

urlpatterns = [
    path('', views.checkout, name='checkout'),
    path('order_complete/<str:order_number>/', views.order_complete, name='order_complete'),  # Make sure this name matches
    path('track_order/', views.track_order, name='track_order'),
    path('order_status/<str:order_number>/', views.order_status, name='order_status'),
]