from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, SetPasswordForm
from .models import DocumentRequest


class AdminRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    ROLE_CHOICES = [
        ('standard', 'Standard Admin'),
        ('super', 'Super Admin'),
    ]

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        required=True
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'password'
        ]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")

        if password != confirm:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        role = self.cleaned_data["role"]

        if role == "super":
            user.is_superuser = True
            user.is_staff = True
        else:
            user.is_staff = True
            user.is_superuser = False

        if commit:
            user.save()

        return user


class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )


class CustomSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        })
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )


class UserRegisterForm(UserCreationForm):
    username = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your username',
            'autocomplete': 'username',
            'inputmode': 'text'
        })
    )
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your first name',
            'autocomplete': 'given-name',
            'inputmode': 'text'
        })
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your last name',
            'autocomplete': 'family-name',
            'inputmode': 'text'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email',
            'autocomplete': 'email',
            'inputmode': 'email'
        })
    )
    student_id = forms.CharField(
        max_length=20, 
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter Student ID/NA',
            'autocomplete': 'off',
            'inputmode': 'text'
        })
    )
    phone_number = forms.CharField(
        max_length=15, 
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter Phone Number',
            'autocomplete': 'tel',
            'inputmode': 'tel'
        })
    )
    face_image = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 'student_id', 'phone_number'
        ]

    def __init__(self, *args, **kwargs):
        super(UserRegisterForm, self).__init__(*args, **kwargs)
        
        self.fields['password1'].widget = forms.PasswordInput(attrs={
            'placeholder': 'Enter password (min. 8 chars)',
            'autocomplete': 'new-password',
            'class': 'form-control'
        })
        self.fields['password1'].help_text = None
        
        self.fields['password2'].widget = forms.PasswordInput(attrs={
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password',
            'class': 'form-control'
        })
        self.fields['password2'].help_text = None
        
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                existing_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{existing_class} form-control".strip()

    def save(self, commit=True):
        user = super(UserRegisterForm, self).save(commit=False)
        user.email = self.cleaned_data.get('email')
        user.first_name = self.cleaned_data.get('first_name')
        user.last_name = self.cleaned_data.get('last_name')
        
        if commit:
            user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class DocumentRequestForm(forms.ModelForm):
    tor_type = forms.ChoiceField(
        choices=DocumentRequest.TOR_TYPE,
        required=False,
        widget=forms.Select(attrs={'id': 'id_tor_type', 'class': 'form-select'})
    )

    course = forms.ChoiceField(
        choices=DocumentRequest.COURSES,
        required=False,
        widget=forms.Select(attrs={'id': 'id_course', 'class': 'form-select'})
    )

    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'id': 'id_quantity', 'class': 'form-control'})
    )

    purpose = forms.CharField(
        widget=forms.Textarea(attrs={'id': 'id_purpose', 'class': 'form-control', 'rows': 3})
    )

    payment_receipt = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'id': 'id_payment_receipt', 'class': 'form-control'})
    )

    class Meta:
        model = DocumentRequest
        fields = ['document_type', 'tor_type', 'course', 'quantity', 'purpose', 'payment_receipt']
        widgets = {
            'document_type': forms.Select(attrs={'id': 'id_document_type', 'class': 'form-select'}),
        }