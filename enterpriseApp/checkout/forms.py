from django import forms
from .models import Order

#just a basic form. Update however you want.

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'phone', 'email', 'address_line_1', 'address_line_2', 'country', 'state', 'city', 'zipcode']

class GuestOrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'phone', 'email', 'address_line_1', 'address_line_2', 'country', 'state', 'city', 'zipcode', 'order_note']
    
    order_note = forms.CharField(required=False, widget=forms.Textarea(attrs={'placeholder': 'Any additional information about your order'}))