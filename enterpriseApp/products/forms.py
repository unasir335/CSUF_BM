from django import forms

class ProductSortForm(forms.Form):
    SORT_CHOICES = [
        ('name', 'Name (A-Z)'),
        ('-name', 'Name (Z-A)'),
        ('price', 'Price (Low to High)'),
        ('-price', 'Price (High to Low)'),
        ('-created_date', 'Newest First'),
    ]
    sort_by = forms.ChoiceField(choices=SORT_CHOICES, required=False, label='Sort by')