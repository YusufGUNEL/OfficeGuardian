from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from .models import CustomUser


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kullanıcı adı',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Şifre',
        })
    )


class RegisterForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'password1', 'password2', 'role']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kullanıcı adı',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Şifre',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Şifre (tekrar)',
        })


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control bg-dark text-light border-secondary',
                'placeholder': 'Ad',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control bg-dark text-light border-secondary',
                'placeholder': 'Soyad',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control bg-dark text-light border-secondary',
                'placeholder': 'E-posta',
            }),
        }
        labels = {
            'first_name': 'Ad',
            'last_name': 'Soyad',
            'email': 'E-posta',
        }


class PasswordChangeCustomForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({
            'class': 'form-control bg-dark text-light border-secondary',
            'placeholder': 'Mevcut sifre',
        })
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control bg-dark text-light border-secondary',
            'placeholder': 'Yeni sifre',
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control bg-dark text-light border-secondary',
            'placeholder': 'Yeni sifre (tekrar)',
        })
