from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User

class loginForm(AuthenticationForm):

    username = forms.CharField(
        label = 'Usuario',
        widget = forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Escriba su usuario'
        })
    )

    password = forms.CharField(
        label = 'Contraseña',
        widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Escriba su contraseña'
        })
    )

    class Meta:

        model = User
        fields = ['username', 'password']
