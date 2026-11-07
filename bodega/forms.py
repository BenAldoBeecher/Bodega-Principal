from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

ROLES = [
    ('Operador', 'Operador'),
    ('Administrador', 'Administrador'),
]


class BaseUsuarioForm(forms.ModelForm):
    rol = forms.ChoiceField(
        choices=ROLES,
        label='Rol',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo electrónico',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'usuario@musicpro.cl'}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            raise ValidationError('El correo electrónico es obligatorio.')

        usuarios = User.objects.filter(email__iexact=email)
        usuarios_username = User.objects.filter(username__iexact=email)
        if self.instance.pk:
            usuarios = usuarios.exclude(pk=self.instance.pk)
            usuarios_username = usuarios_username.exclude(pk=self.instance.pk)
        if usuarios.exists() or usuarios_username.exists():
            raise ValidationError('Ya existe un usuario con ese correo electrónico.')
        return email

    def asignar_rol(self, user):
        grupo, _ = Group.objects.get_or_create(name=self.cleaned_data['rol'])
        user.groups.set([grupo])


class UsuarioCrearForm(BaseUsuarioForm):
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='Mínimo 8 caracteres, no totalmente numérica y no demasiado común.',
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            try:
                validate_password(password, self.instance)
            except ValidationError as error:
                raise forms.ValidationError(error.messages)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.is_staff = self.cleaned_data['rol'] == 'Administrador'
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            self.asignar_rol(user)
        return user


class UsuarioEditarForm(BaseUsuarioForm):
    is_active = forms.BooleanField(
        label='Usuario activo',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta(BaseUsuarioForm.Meta):
        fields = ('first_name', 'last_name', 'email', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            es_admin = self.instance.is_superuser or self.instance.groups.filter(name='Administrador').exists()
            self.fields['rol'].initial = 'Administrador' if es_admin else 'Operador'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        es_admin_rol = self.cleaned_data['rol'] == 'Administrador'
        user.is_staff = es_admin_rol
        if not es_admin_rol:
            user.is_superuser = False
        if commit:
            user.save()
            self.asignar_rol(user)
        return user
