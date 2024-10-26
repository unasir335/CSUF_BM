from django.test import TestCase
from .models import User, CategoryItem

class UserModelTests(TestCase):
    def setUp(self):
        """Create a test user."""
        self.user = User.objects.create(username='testuser', email='test@example.com')

    def test_user_string_representation(self):
        """Test the string representation of the user."""
        self.assertEqual(str(self.user), 'testuser')

    def test_user_email_unique(self):
        """Test that the email field must be unique."""
        user2 = User(username='anotheruser', email='test@example.com')
        with self.assertRaises(Exception):
            user2.full_clean()  # This should raise an error because the email is not unique

class CategoryItemModelTests(TestCase):
    def setUp(self):
        """Create a test category item."""
        self.category_item = CategoryItem.objects.create(title='Sample Item', description='A test item.')

    def test_category_item_string_representation(self):
        """Test the string representation of the category item."""
        self.assertEqual(str(self.category_item), 'Sample Item')

    def test_category_item_default_availability(self):
        """Test the default availability of a category item."""
        self.assertTrue(self.category_item.available)  # Default should be True

    def test_category_item_description_blank(self):
        """Test that the description can be blank."""
        category_item_blank_description = CategoryItem.objects.create(title='Item with No Description')
        self.assertEqual(category_item_blank_description.description, '')  # Should be empty
