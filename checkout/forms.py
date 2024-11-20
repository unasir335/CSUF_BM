from django import forms
from .models import Order
from django.core.validators import RegexValidator

# Added 10/23
from datetime import datetime
import re
import random
import time


#Updated 10/23
class OrderForm(forms.ModelForm):
    # Phone validation
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    # Phone field with validation and styling
    phone = forms.CharField(
        validators=[phone_regex],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone Number (e.g., +1234567890)'
        })
    )
    
    # Add checkbox for same billing address
    use_shipping_address_for_billing = forms.BooleanField(
        initial=True,
        required=False,
        label='Use shipping address for billing',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'same_billing_address'
        })
    )

    class Meta:
        model = Order
        fields = [
            # Shipping Information
            'first_name', 'last_name', 'phone', 'email',
            'address_line_1', 'address_line_2', 'country', 'state', 'city', 'zipcode',
            # Billing Information
            'billing_first_name', 'billing_last_name',
            'billing_address_line_1', 'billing_address_line_2',
            'billing_country', 'billing_state', 'billing_city', 'billing_zipcode'
        ]
        widgets = {
            # Shipping fields
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email Address'
            }),
            'address_line_1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Street Address'
            }),
            'address_line_2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apartment, suite, etc. (optional)'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State/Province'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'zipcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ZIP / Postal Code'
            }),
            # Billing fields
            'billing_first_name': forms.TextInput(attrs={
                'class': 'form-control billing-field',
                'placeholder': 'Billing First Name'
            }),
            'billing_last_name': forms.TextInput(attrs={
                'class': 'form-control billing-field',
                'placeholder': 'Billing Last Name'
            }),
            'billing_address_line_1': forms.TextInput(attrs={
                'class': 'form-control billing-field',
                'placeholder': 'Billing Street Address'
            }),
            'billing_address_line_2': forms.TextInput(attrs={
                'class': 'form-control billing-field',
                'placeholder': 'Billing Apartment, suite, etc. (optional)'
            }),
            'billing_country': forms.TextInput(attrs={
                'class': 'form-control billing-field',
                'placeholder': 'Billing Country'
            }),
            'billing_state': forms.TextInput(attrs={
                'class': 'form-control billing-field',
                'placeholder': 'Billing State/Province'
            }),
            'billing_city': forms.TextInput(attrs={
                'class': 'form-control billing-field',
                'placeholder': 'Billing City'
            }),
            'billing_zipcode': forms.TextInput(attrs={
                'class': 'form-control billing-field',
                'placeholder': 'Billing ZIP / Postal Code'
            }),
        }

class GuestOrderForm(OrderForm):
    order_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Any additional information about your order',
            'rows': 3
        })
    )

    class Meta(OrderForm.Meta):
        model = Order
        fields = OrderForm.Meta.fields + ['order_note']
        

# Added 10/23
class CreditCardForm(forms.Form):
    CARD_TYPES = [
        ('visa', 'Visa'),
        ('mastercard', 'MasterCard'),
        ('amex', 'American Express'),
        ('discover', 'Discover')
    ]
    
    card_type = forms.ChoiceField(
        choices=CARD_TYPES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'card_type'
        })
    )
    
    card_number = forms.CharField(
        max_length=19,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Card Number',
            'id': 'card_number'
        })
    )
    
    expiry_month = forms.ChoiceField(
        choices=[(str(i).zfill(2), str(i).zfill(2)) for i in range(1, 13)],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'expiry_month'
        })
    )
    
    expiry_year = forms.ChoiceField(
        choices=[(str(i), str(i)) for i in range(datetime.now().year, datetime.now().year + 11)],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'expiry_year'
        })
    )
    
    cvv = forms.CharField(
        max_length=4,
        min_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'CVV',
            'id': 'cvv'
        })
    )

    # Validate card number using Luhn algorithm and card-specific patterns
    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number').replace(' ', '')
        card_type = self.cleaned_data.get('card_type')
        
        # Card pattern validation
        patterns = {
            'visa': r'^4[0-9]{12}(?:[0-9]{3})?$',
            'mastercard': r'^5[1-5][0-9]{14}$',
            'amex': r'^3[47][0-9]{13}$',
            'discover': r'^6(?:011|5[0-9]{2})[0-9]{12}$'
        }
        
        if not re.match(patterns.get(card_type, ''), card_number):
            raise forms.ValidationError('Invalid card number for selected card type.')
            
        # Luhn algorithm validation
        if not self.luhn_check(card_number):
            raise forms.ValidationError('Invalid card number.')
            
        return card_number

    # Validate CVV based on card type
    def clean_cvv(self):
        cvv = self.cleaned_data.get('cvv')
        card_type = self.cleaned_data.get('card_type')
        
        if card_type == 'amex' and len(cvv) != 4:
            raise forms.ValidationError('American Express cards require a 4-digit CVV.')
        elif card_type != 'amex' and len(cvv) != 3:
            raise forms.ValidationError('Card verification value must be 3 digits.')
            
        return cvv
    
    # Validate expiry date and simulate random payment failures
    def clean(self):
       
        cleaned_data = super().clean()
        
        # Expiry date validation
        if 'expiry_month' in cleaned_data and 'expiry_year' in cleaned_data:
            expiry = datetime(
                int(cleaned_data['expiry_year']),
                int(cleaned_data['expiry_month']),
                1
            )
            if expiry < datetime.now():
                raise forms.ValidationError('Card has expired.')

        # Simulate random payment failures (30% chance)
        if random.random() < 0.3:
            error_messages = [
                'Card declined by issuer.',
                'Insufficient funds.',
                'Transaction flagged as suspicious.',
                'Network error, please try again.',
                'Card reported as stolen.'
            ]
            raise forms.ValidationError(random.choice(error_messages))

        return cleaned_data

    # Luhn algorithm for card number validation
    @staticmethod
    def luhn_check(card_number):
        digits = [int(d) for d in str(card_number)]
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(divmod(d * 2, 10))
        return checksum % 10 == 0

# Simulation payment processing
class FakePaymentGateway:
    @staticmethod
    def process_payment(order, card_data):
       
        # Generate a fake transaction ID
        transaction_id = f"TRANS_{random.randint(100000, 999999)}"
        
        # Simulate processing time
        time.sleep(1)
        
        # Return transaction details
        return {
            'success': True,
            'transaction_id': transaction_id,
            'amount': order.order_total + order.tax,
            'currency': 'USD',
            'timestamp': datetime.now().isoformat()
        }