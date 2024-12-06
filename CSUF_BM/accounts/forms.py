from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.contrib.auth.forms import PasswordChangeForm
from .models.student import Student
from .models.faculty import Faculty
from .models.profile import UserProfile
from .models.account import Account
from .models.address import Address
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.cache import cache

Account = get_user_model()
# updated 10/24 to include secret phrases
class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)
    security_question = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your security question'
        })
    )
    security_answer = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your answer'
        })
    )

    class Meta:
        model = Account
        fields = ('username', 'email', 'first_name', 'last_name', 'security_question', 'security_answer')

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        if Account.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        
        # Store the email domain for later use
        self.email_domain = email.split('@')[1]
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.security_question = self.cleaned_data["security_question"]
        user.security_answer = self.cleaned_data["security_answer"]
        
        # Set user type based on email domain
        if hasattr(self, 'email_domain'):
            if self.email_domain == 'csu.fullerton.edu':
                user.is_student = True
            elif self.email_domain == 'fullerton.edu':
                user.is_faculty = True
                
        if commit:
            user.save()
        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'
                  
class StudentRegistrationForm(forms.Form):
    student_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your CSUF Student ID'
        })
    )
    
    major = forms.ChoiceField(
        choices=[
            ('Computer Science', 'Computer Science'),
            ('Business Administration', 'Business Administration'),
            ('Engineering', 'Engineering'),
            ('Mathematics', 'Mathematics'),
            ('Physics', 'Physics'),
            ('Chemistry', 'Chemistry'),
            ('Biology', 'Biology'),
            ('Psychology', 'Psychology'),
            ('Communications', 'Communications'),
            ('Other', 'Other')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    year = forms.ChoiceField(
        choices=[(i, str(i)) for i in range(2024, 2031)],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Expected Graduation Year'
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Check for stored profile data
        if self.user:
            cache_key = f"stored_profiles_{self.user.email}"
            stored_profiles = cache.get(cache_key, {})
            stored_student_data = stored_profiles.get('student', {})
            
            if stored_student_data:
                # Pre-fill the form with stored data
                self.initial = {
                    'student_id': stored_student_data.get('student_id'),
                    'major': stored_student_data.get('major'),
                    'year': stored_student_data.get('year')
                }
                
                # Make student_id readonly if it's restored
                self.fields['student_id'].widget.attrs.update({
                    'readonly': 'readonly',
                    'class': 'form-control bg-light'
                })
                self.fields['student_id'].help_text = "ID restored from previous registration"

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        
        # Check if this is a restored student ID
        if self.user:
            cache_key = f"stored_profiles_{self.user.email}"
            stored_profiles = cache.get(cache_key, {})
            stored_student_data = stored_profiles.get('student', {})
            
            if stored_student_data and stored_student_data.get('student_id') == student_id:
                return student_id  # Skip validation for restored IDs
        
        # Check for existing student ID
        existing = Student.objects.filter(student_id=student_id)
        if self.user:
            # Exclude the current user's ID if updating
            existing = existing.exclude(user=self.user)
        if existing.exists():
            raise forms.ValidationError("This Student ID is already registered.")
        return student_id

    def save(self, commit=True):
        """
        Save the form data to create or update a Student instance
        """
        if not self.user:
            raise ValueError("User must be set before saving")
            
        student_data = {
            'student_id': self.cleaned_data['student_id'],
            'major': self.cleaned_data['major'],
            'year': self.cleaned_data['year']
        }
        
        student, created = Student.objects.update_or_create(
            user=self.user,
            defaults=student_data
        )
        
        return student
    
    
class FacultyRegistrationForm(forms.ModelForm):
    faculty_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Faculty ID'
        })
    )
    
    department = forms.ChoiceField(
        choices=[
            ('Computer Science', 'Computer Science'),
            ('Business Administration', 'Business Administration'),
            ('Engineering', 'Engineering'),
            ('Mathematics', 'Mathematics'),
            ('Physics', 'Physics'),
            ('Chemistry', 'Chemistry'),
            ('Biology', 'Biology'),
            ('Psychology', 'Psychology'),
            ('Communications', 'Communications'),
            ('Other', 'Other')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    position = forms.ChoiceField(
        choices=[
            ('Professor', 'Professor'),
            ('Associate Professor', 'Associate Professor'),
            ('Assistant Professor', 'Assistant Professor'),
            ('Lecturer', 'Lecturer'),
            ('Adjunct Faculty', 'Adjunct Faculty'),
            ('Other', 'Other')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    research_areas = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': '3',
            'placeholder': 'Enter your research interests'
        })
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Check for stored profile data
        if self.user:
            cache_key = f"stored_profiles_{self.user.email}"
            stored_profiles = cache.get(cache_key, {})
            stored_faculty_data = stored_profiles.get('faculty', {})
            
            if stored_faculty_data:
                # Pre-fill the form with stored data
                self.fields['faculty_id'].initial = stored_faculty_data.get('faculty_id')
                self.fields['department'].initial = stored_faculty_data.get('department')
                self.fields['position'].initial = stored_faculty_data.get('position')
                self.fields['research_areas'].initial = stored_faculty_data.get('research_areas')
                
                # Make faculty_id readonly if it's restored
                self.fields['faculty_id'].widget.attrs.update({
                    'readonly': 'readonly',
                    'class': 'form-control bg-light'
                })
                self.fields['faculty_id'].help_text = "ID restored from previous registration"

    def clean_faculty_id(self):
        faculty_id = self.cleaned_data.get('faculty_id')
        
        # Check if this is a restored faculty ID
        if self.user:
            cache_key = f"stored_profiles_{self.user.email}"
            stored_profiles = cache.get(cache_key, {})
            stored_faculty_data = stored_profiles.get('faculty', {})
            
            if stored_faculty_data and stored_faculty_data.get('faculty_id') == faculty_id:
                return faculty_id  # Skip validation for restored IDs
        
        # Check for existing faculty ID
        existing = Faculty.objects.filter(faculty_id=faculty_id)
        if self.instance.pk:  # If we're updating
            existing = existing.exclude(user=self.instance.user)
        if existing.exists():
            raise forms.ValidationError("This Faculty ID is already registered.")
        return faculty_id

    class Meta:
        model = Faculty
        fields = ['faculty_id', 'department', 'position', 'research_areas']

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

class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    
    # Phone field with regex validation
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', 
                               message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone_number = forms.CharField(validators=[phone_regex], 
                                 max_length=17, 
                                 required=False,
                                 widget=forms.TextInput(attrs={'placeholder': 'Enter phone number'}))
    
    # Address fields
    address_line1 = forms.CharField(max_length=100, required=False,
                                  widget=forms.TextInput(attrs={'placeholder': 'Enter Address Line 1'}))
    address_line2 = forms.CharField(max_length=100, required=False,
                                  widget=forms.TextInput(attrs={'placeholder': 'Enter Address Line 2 (Optional)'}))
    city = forms.CharField(max_length=50, required=False,
                         widget=forms.TextInput(attrs={'placeholder': 'Enter City'}))
    state = forms.CharField(max_length=50, required=False,
                          widget=forms.TextInput(attrs={'placeholder': 'Enter State'}))
    country = forms.CharField(max_length=50, required=False,
                            widget=forms.TextInput(attrs={'placeholder': 'Enter Country'}))
    zipcode = forms.CharField(max_length=10, required=False,
                            widget=forms.TextInput(attrs={'placeholder': 'Enter Zipcode'}))

    class Meta:
        model = UserProfile
        fields = ['profile_picture']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Apply Bootstrap classes
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
            })

    def save(self, commit=True):
        profile = super().save(commit=False)
        
        if commit:
            with transaction.atomic():
                # Save profile
                profile.save()
                
                # Update user information
                if self.user:
                    self.user.first_name = self.cleaned_data['first_name']
                    self.user.last_name = self.cleaned_data['last_name']
                    self.user.phone_number = self.cleaned_data.get('phone_number', '')
                    self.user.save()
                    
                    # Update or create address
                    address, _ = Address.objects.get_or_create(user=self.user)
                    address.address_line1 = self.cleaned_data.get('address_line1', '')
                    address.address_line2 = self.cleaned_data.get('address_line2', '')
                    address.city = self.cleaned_data.get('city', '')
                    address.state = self.cleaned_data.get('state', '')
                    address.country = self.cleaned_data.get('country', '')
                    address.zipcode = self.cleaned_data.get('zipcode', '')
                    address.save()
        
        return profile
    
# Student-specific form
class StudentProfileForm(UserProfileForm):
    student_id = forms.CharField(
        max_length=20,
        required=False,  # Make it not required since it's read-only
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-light',
            'placeholder': 'Enter Student ID',
            'readonly': 'readonly',
            'aria-describedby': 'studentIdHelp'
        })
    )
    
    major = forms.ChoiceField(
        choices=[
            ('Computer Science', 'Computer Science'),
            ('Business Administration', 'Business Administration'),
            ('Engineering', 'Engineering'),
            ('Mathematics', 'Mathematics'),
            ('Physics', 'Physics'),
            ('Chemistry', 'Chemistry'),
            ('Biology', 'Biology'),
            ('Psychology', 'Psychology'),
            ('Communications', 'Communications'),
            ('Other', 'Other')
        ],
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
            'aria-label': 'Select Major'
        })
    )
    
    year = forms.ChoiceField(
        choices=[(str(i), str(i)) for i in range(2024, 2031)],
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
            'aria-label': 'Select Graduation Year'
        })
    )

    class Meta:
        model = UserProfile
        fields = UserProfileForm.Meta.fields  # Keep the base fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.user and hasattr(self.user, 'student'):
            # Set initial values
            self.fields['student_id'].initial = self.user.student.student_id
            self.fields['major'].initial = self.user.student.major
            self.fields['year'].initial = str(self.user.student.year)
            
            # Make student_id read-only
            self.fields['student_id'].widget.attrs['readonly'] = True

    def save(self, commit=True):
        profile = super().save(commit=False)
        
        if commit:
            with transaction.atomic():
                profile.save()
                
                if self.user and hasattr(self.user, 'student'):
                    student = self.user.student
                    student.major = self.cleaned_data['major']
                    student.year = int(self.cleaned_data['year'])
                    student.save()
        
        return profile

# Faculty-specific form
class FacultyProfileForm(UserProfileForm):
    faculty_id = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control bg-light',
            'placeholder': 'Enter Faculty ID',
            'readonly': 'readonly',
            'aria-describedby': 'facultyIdHelp'
        })
    )
    
    department = forms.ChoiceField(
        choices=[
            ('Computer Science', 'Computer Science'),
            ('Business Administration', 'Business Administration'),
            ('Engineering', 'Engineering'),
            ('Mathematics', 'Mathematics'),
            ('Physics', 'Physics'),
            ('Chemistry', 'Chemistry'),
            ('Biology', 'Biology'),
            ('Psychology', 'Psychology'),
            ('Communications', 'Communications'),
            ('Other', 'Other')
        ],
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
            'aria-label': 'Select Department'
        })
    )
    
    position = forms.ChoiceField(
        choices=[
            ('Professor', 'Professor'),
            ('Associate Professor', 'Associate Professor'),
            ('Assistant Professor', 'Assistant Professor'),
            ('Lecturer', 'Lecturer'),
            ('Adjunct Faculty', 'Adjunct Faculty'),
            ('Other', 'Other')
        ],
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
            'aria-label': 'Select Position'
        })
    )

    research_areas = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': '3',
            'placeholder': 'Enter your research interests and areas of expertise'
        })
    )

    class Meta:
        model = UserProfile
        fields = UserProfileForm.Meta.fields  # Keep the base fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.user and hasattr(self.user, 'faculty'):
            # Set initial values
            self.fields['faculty_id'].initial = self.user.faculty.faculty_id
            self.fields['department'].initial = self.user.faculty.department
            self.fields['position'].initial = self.user.faculty.position
            self.fields['research_areas'].initial = self.user.faculty.research_areas
            
            # Make faculty_id read-only
            self.fields['faculty_id'].widget.attrs['readonly'] = True

    def save(self, commit=True):
        profile = super().save(commit=False)
        
        if commit:
            with transaction.atomic():
                profile.save()
                
                if self.user and hasattr(self.user, 'faculty'):
                    faculty = self.user.faculty
                    faculty.department = self.cleaned_data.get('department')
                    faculty.position = self.cleaned_data.get('position')
                    faculty.research_areas = self.cleaned_data.get('research_areas')
                    faculty.save()

        return profile
    
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
    
