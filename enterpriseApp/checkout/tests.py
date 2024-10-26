from django.test import TestCase
from django.urls import reverse
from .models import CategoryItem, OrderHistory
from django.contrib.auth import get_user_model

# Create your tests here. (Updated 10/26)

User = get_user_model()

class CheckoutViewTests(TestCase):
    def setUp(self):
        """
        Create a test user and a test category item.
        """
        
        self.user = User.objects.create_user(username = 'testuser', email = 'test@example.com')
        self.category_item = CategoryItem.objects.create(title = 'Sample Item', available=True)
        self.client.login(username = 'testuser', password = 'password')

    def test_checkout_view_status_code():
        """
        Check that the checkout page returns a status code
        """
        pass
