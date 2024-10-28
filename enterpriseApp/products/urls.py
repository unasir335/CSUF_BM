from django.urls import path
from . import views

urlpatterns = [
    # Management URLs
    path('manage/fetch-sorted-data/', views.fetch_sorted_data, name='fetch_sorted_data'),
    path('manage/category/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    path('manage/product/<int:product_id>/delete/', views.delete_product, name='delete_product'),
    path('manage/category/<int:category_id>/', views.manage_category, name='edit_category'),
    path('manage/category/', views.manage_category, name='add_category'),
    path('manage/product/<int:product_id>/', views.manage_product, name='edit_product'),
    path('manage/product/', views.manage_product, name='add_product'),
    path('manage/', views.manage_items, name='manage_items'),
    
    # Store front URLs
    path('', views.store, name='store'),
    path('<slug:category_slug>/', views.store, name='products_by_category'),
    path('<slug:category_slug>/<slug:product_slug>/', views.product_detail, name='product_detail'),
    
# Faculty recommendation endpoints
    path('recommendations/toggle/<int:product_id>/', views.toggle_recommendation, name='toggle_recommendation'),
    path('recommendations/remove/<int:product_id>/', views.remove_recommendation, name='remove_recommendation'),
    path('recommendations/<int:product_id>/', views.get_product_recommendations, name='get_recommendations'),
]
