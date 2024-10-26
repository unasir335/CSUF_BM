from django.test import TestCase
from django.urls import reverse
from .models import CategoryItem, OrderHistory
from django.contrib.auth import get_user_model

# Create your tests here. (Updated 10/26)
from django.test import TestCase
from django.urls import reverse
from .models import CategoryItem, OrderHistory
from django.contrib.auth import get_user_model

User = get_user_model()

class CheckoutViewTests(TestCase):
    def setUp(self):
        """
        Create a test user and a test category item.
        """
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='password')
        self.category_item = CategoryItem.objects.create(title='Sample Item', available=True)
        self.client.login(username='testuser', password='password')

    def test_checkout_view_status_code(self):
        """
        Check that the checkout page returns a status code 200 when accessed by a logged-in user.
        """
        response = self.client.get(reverse('checkout'))  # Adjust 'checkout' to your actual URL name
        self.assertEqual(response.status_code, 200)

    def test_checkout_view_redirects_if_not_logged_in(self):
        """
        Check that the checkout page redirects to the login page if the user is not logged in.
        """
        self.client.logout()
        response = self.client.get(reverse('checkout'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('checkout')}")  # Adjust 'login' as necessary

    def test_checkout_view_template_used(self):
        """
        Check that the correct template is used for the checkout page.
        """
        response = self.client.get(reverse('checkout'))
        self.assertTemplateUsed(response, 'checkout/checkout.html')  # Adjust the template name as necessary

    def test_category_item_in_checkout_context(self):
        """
        Ensure the category item is included in the context of the checkout view.
        """
        response = self.client.get(reverse('checkout'))
        self.assertIn('category_item', response.context)  # Check context variable as per your view
        self.assertEqual(response.context['category_item'], self.category_item)

