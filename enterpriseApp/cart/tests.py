from django.test import TestCase
from django.urls import reverse
from .models import Cart, CartItem
from products.models import Product  # Ensure you have a Product model to work with
from django.contrib.auth import get_user_model

User = get_user_model()

class CartViewTests(TestCase):
    def setUp(self):
        """
        Create a test user, a test product, and a test cart.
        """
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password'
        )
        self.product = Product.objects.create(
            name='Sample Product',
            price=10.00,
            stock=100  # Adjust based on your Product model
        )
        self.cart = Cart.objects.create(user=self.user)  # Create a cart for the user
        self.client.login(username='testuser', password='password')

    def test_cart_view_status_code(self):
        """
        Check that the cart page returns a status code 200 when accessed by a logged-in user.
        """
        response = self.client.get(reverse('cart'))  # Adjust 'cart' to your actual URL name
        self.assertEqual(response.status_code, 200)

    def test_cart_view_redirects_if_not_logged_in(self):
        """
        Check that the cart page redirects to the login page if the user is not logged in.
        """
        self.client.logout()
        response = self.client.get(reverse('cart'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('cart')}")  # Adjust as necessary

    def test_cart_items_displayed_in_cart_view(self):
        """
        Ensure items in the cart are displayed on the cart page.
        """
        cart_item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        response = self.client.get(reverse('cart'))
        self.assertContains(response, cart_item.product.name)
        self.assertContains(response, cart_item.quantity)

    def test_cart_empty_message(self):
        """
        Check that the cart displays an empty message if there are no items.
        """
        response = self.client.get(reverse('cart'))
        self.assertContains(response, "Your cart is empty")  # Adjust message as necessary

    def test_cart_total_calculation(self):
        """
        Ensure the cart total is calculated correctly.
        """
        cart_item1 = CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        cart_item2 = CartItem.objects.create(cart=self.cart, product=self.product, quantity=3)
        
        expected_total = (cart_item1.quantity + cart_item2.quantity) * self.product.price
        response = self.client.get(reverse('cart'))
        
        # Assuming you render the total in the cart template with a context variable 'cart_total'
        self.assertContains(response, f'Total: {expected_total:.2f}')  # Adjust the total message as necessary
