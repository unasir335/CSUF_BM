from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.contrib.auth.forms import PasswordChangeForm
from .models import Student, Faculty, UserProfile, Account
from django.core.exceptions import ValidationError

Account = get_user_model()

# SRP: RegistrationForm is responsible only for common user registration fields
# OCP: Can be extended for different user types without modification
class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

    class Meta:
        model = Account
        fields = ('username', 'email', 'first_name', 'last_name')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'
                
                      
# SRP: StudentRegistrationForm is responsible only for student-specific fields
# ISP: Provides only the fields needed for student registration
class StudentRegistrationForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['student_id', 'major', 'year']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_id'].widget.attrs['placeholder'] = 'Enter Student ID'
        self.fields['major'].widget.attrs['placeholder'] = 'Enter Major'
        self.fields['year'].widget.attrs['placeholder'] = 'Enter Year'
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


# SRP: FacultyRegistrationForm is responsible only for faculty-specific fields
# ISP: Provides only the fields needed for faculty registration
class FacultyRegistrationForm(forms.ModelForm):
    class Meta:
        model = Faculty
        fields = ['faculty_id', 'department', 'position']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['faculty_id'].widget.attrs['placeholder'] = 'Enter Faculty ID'
        self.fields['department'].widget.attrs['placeholder'] = 'Enter Department'
        self.fields['position'].widget.attrs['placeholder'] = 'Enter Position'
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'

# SRP: LoginForm is responsible only for login fields
class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'placeholder': 'Enter Email',
        'class': 'form-control',
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Enter Password',
        'class': 'form-control',
    }))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'
     
            
# SRP: UserProfileForm is responsible only for user profile fields         
class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)

    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name', 'phone_number', 'profile_picture', 
                  'address_line1', 'address_line2', 'city', 'state', 'country', 'zipcode']
        widgets = {
            'profile_picture': forms.FileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'first_name': 'Enter First Name',
            'last_name': 'Enter Last Name',
            'phone_number': 'Enter Phone Number',
            'address_line1': 'Enter Address Line 1',
            'address_line2': 'Enter Address Line 2',
            'city': 'Enter City',
            'state': 'Enter State',
            'country': 'Enter Country',
            'zipcode': 'Enter Zipcode',
        }
        for field in self.fields:
            if field != 'profile_picture':
                self.fields[field].widget.attrs.update({
                    'class': 'form-control',
                    'placeholder': placeholders.get(field, '')
                })
        
        # If an instance is provided, populate fields with existing data
        if self.instance and self.instance.pk:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            for field in self.fields:
                if field not in ['first_name', 'last_name', 'profile_picture']:
                    self.fields[field].initial = getattr(self.instance, field)

    def save(self, commit=True):
        user_profile = super().save(commit=False)
        user = user_profile.user
        
        # Update User model fields
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            user_profile.save()
        return user_profile
    
    
    
class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter your current password'}),
    )
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter new password'}),
        help_text="Your password must contain at least 8 characters.",
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError("The two password fields didn't match.")
            
            if len(new_password1) < 8:
                raise forms.ValidationError("Password must be at least 8 characters long.")

        return cleaned_data