from django import forms
from .models import Category, Product, DigitalProduct, ProductReview


class ProductSortForm(forms.Form):
    SORT_CHOICES = [
        ('', 'Sort by...'),
        ('-created_date', 'Newest'),
        ('price', 'Price: Low to High'),
        ('-price', 'Price: High to Low'),
        ('name', 'Name: A to Z'),
        ('-name', 'Name: Z to A'),
        ('recommendations', 'Most Recommended'),
    ]
    
    sort_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )   

# Added 10/22
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

# Updated 10/24
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'category', 'description', 'price', 'image',
            'stock', 'brand', 'discount', 'featured', 'is_available'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def clean_discount(self):
        discount = self.cleaned_data.get('discount')
        if discount < 0 or discount > 100:
            raise forms.ValidationError("Discount must be between 0 and 100")
        return discount

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only set initial value for is_available if this is a new product
        if not kwargs.get('instance'):
            self.initial['is_available'] = True

class DigitalProductForm(ProductForm):
    class Meta(ProductForm.Meta):
        model = DigitalProduct
        fields = ProductForm.Meta.fields + [
            'version',
            'download_link',
            'file_size',
            'system_requirements',
            'release_notes'
        ]
        widgets = {
            **ProductForm.Meta.widgets,
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'download_link': forms.URLInput(attrs={'class': 'form-control'}),
            'file_size': forms.TextInput(attrs={'class': 'form-control'}),
            'system_requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'release_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['stock'].widget = forms.HiddenInput()  # Hide stock field for digital products
        self.fields['stock'].initial = -1  # Set default stock to -1 (unlimited)
        
    def clean_stock(self):
        return -1  # Ensure stock is always -1 for digital products
    
class ProductReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(i, f'{i} stars') for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'star-rating'}),
    )
    
    class Meta:
        model = ProductReview
        fields = ['rating', 'review']
        widgets = {
            'review': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Write your review here...'
            })
        } 
    
    
    