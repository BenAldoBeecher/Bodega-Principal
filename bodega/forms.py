from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import (
    Categoria, DetalleSolicitud, MovimientoStock, Producto, Proveedor,
    Solicitud, Sucursal,
)

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


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ('nombre', 'descripcion')
        labels = {'nombre': 'Nombre', 'descripcion': 'Descripción'}
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Guitarras'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise ValidationError('El nombre es obligatorio.')
        categorias = Categoria.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            categorias = categorias.exclude(pk=self.instance.pk)
        if categorias.exists():
            raise ValidationError('Ya existe una categoría con ese nombre.')
        return nombre


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ('rut', 'razon_social', 'email', 'telefono', 'activo')
        labels = {
            'rut': 'RUT',
            'razon_social': 'Razón social',
            'email': 'Correo electrónico',
            'telefono': 'Teléfono',
            'activo': 'Proveedor activo',
        }
        widgets = {
            'rut': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12.345.678-9'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Empresa S.A.'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contacto@empresa.cl'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 1234 5678'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_rut(self):
        rut = (self.cleaned_data.get('rut') or '').strip()
        if rut:
            proveedores = Proveedor.objects.filter(rut__iexact=rut)
            if self.instance.pk:
                proveedores = proveedores.exclude(pk=self.instance.pk)
            if proveedores.exists():
                raise ValidationError('Ya existe un proveedor con ese RUT.')
        return rut

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if email:
            from django.core.validators import validate_email
            validate_email(email)
        return email


class SucursalForm(forms.ModelForm):
    class Meta:
        model = Sucursal
        fields = ('codigo', 'nombre', 'direccion', 'activa')
        labels = {
            'codigo': 'Código',
            'nombre': 'Nombre',
            'direccion': 'Dirección',
            'activa': 'Sucursal activa',
        }
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SUC-01'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sucursal Centro'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Av. Principal 123'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_codigo(self):
        codigo = (self.cleaned_data.get('codigo') or '').strip().upper()
        if not codigo:
            raise ValidationError('El código es obligatorio.')
        sucursales = Sucursal.objects.filter(codigo__iexact=codigo)
        if self.instance.pk:
            sucursales = sucursales.exclude(pk=self.instance.pk)
        if sucursales.exists():
            raise ValidationError('Ya existe una sucursal con ese código.')
        return codigo


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = (
            'sku', 'nombre', 'categoria', 'proveedor', 'precio',
            'stock_actual', 'stock_minimo', 'activo',
        )
        labels = {
            'sku': 'SKU',
            'nombre': 'Nombre',
            'categoria': 'Categoría',
            'proveedor': 'Proveedor',
            'precio': 'Precio',
            'stock_actual': 'Stock actual',
            'stock_minimo': 'Stock mínimo',
            'activo': 'Producto activo',
        }
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SKU-00000001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Guitarra eléctrica'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'stock_actual': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_sku(self):
        sku = (self.cleaned_data.get('sku') or '').strip().upper()
        if not sku:
            raise ValidationError('El SKU es obligatorio.')
        productos = Producto.objects.filter(sku__iexact=sku)
        if self.instance.pk:
            productos = productos.exclude(pk=self.instance.pk)
        if productos.exists():
            raise ValidationError('Ya existe un producto con ese SKU.')
        return sku

    def clean_precio(self):
        precio = self.cleaned_data.get('precio')
        if precio is not None and precio <= 0:
            raise ValidationError('El precio debe ser mayor que cero.')
        return precio

    def clean_stock_actual(self):
        stock = self.cleaned_data.get('stock_actual')
        if stock is not None and stock < 0:
            raise ValidationError('El stock actual no puede ser negativo.')
        return stock

    def clean_stock_minimo(self):
        stock = self.cleaned_data.get('stock_minimo')
        if stock is not None and stock < 0:
            raise ValidationError('El stock mínimo no puede ser negativo.')
        return stock


class SolicitudForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ('sucursal', 'fecha', 'observaciones')
        labels = {
            'sucursal': 'Sucursal',
            'fecha': 'Fecha',
            'observaciones': 'Observaciones',
        }
        widgets = {
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sucursal'].queryset = Sucursal.objects.order_by('nombre')
        self.fields['fecha'].input_formats = [
            '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
        ]


class DetalleSolicitudForm(forms.ModelForm):
    class Meta:
        model = DetalleSolicitud
        fields = ('producto', 'cantidad_solicitada')
        labels = {
            'producto': 'Producto',
            'cantidad_solicitada': 'Cantidad solicitada',
        }
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        productos = Producto.objects.filter(activo=True).order_by('nombre')
        if self.instance.pk and self.instance.producto_id:
            productos = Producto.objects.filter(
                Q(activo=True) | Q(pk=self.instance.producto_id)
            ).order_by('nombre')
        self.fields['producto'].queryset = productos

    def clean_cantidad_solicitada(self):
        cantidad = self.cleaned_data.get('cantidad_solicitada')
        if cantidad is None or cantidad <= 0:
            raise ValidationError('La cantidad solicitada debe ser mayor que cero.')
        return cantidad


class MovimientoStockForm(forms.ModelForm):
    class Meta:
        model = MovimientoStock
        fields = ('tipo', 'producto', 'cantidad', 'fecha', 'observacion')
        labels = {
            'tipo': 'Tipo de movimiento',
            'producto': 'Producto',
            'cantidad': 'Cantidad',
            'fecha': 'Fecha',
            'observacion': 'Observación',
        }
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'fecha': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = Producto.objects.filter(activo=True).order_by('nombre')
        self.fields['fecha'].input_formats = [
            '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
        ]

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is None or cantidad <= 0:
            raise ValidationError('La cantidad debe ser mayor que cero.')
        return cantidad


class MovimientoStockEditarForm(forms.ModelForm):
    class Meta:
        model = MovimientoStock
        fields = ('fecha', 'observacion')
        labels = {
            'fecha': 'Fecha',
            'observacion': 'Observación',
        }
        widgets = {
            'fecha': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].input_formats = [
            '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
        ]
