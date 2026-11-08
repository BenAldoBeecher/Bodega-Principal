from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    Categoria, DetalleSolicitud, MovimientoStock, Producto, Proveedor,
    Solicitud, Sucursal,
)
from .permisos import admin_required, es_admin
from .reportes import REPORTES, obtener_reporte

ROLES = [
    ('Operador', 'Operador'),
    ('Administrador', 'Administrador'),
]


def _texto(request, key):
    return request.POST.get(key, '').strip()


def _entero(request, key, etiqueta, errores, minimo=None):
    raw = request.POST.get(key, '').strip()
    if raw == '':
        errores[key] = f'{etiqueta} es obligatorio.'
        return None
    try:
        valor = int(raw)
    except (TypeError, ValueError):
        errores[key] = f'{etiqueta} debe ser un número entero.'
        return None
    if minimo is not None and valor < minimo:
        errores[key] = f'{etiqueta} debe ser mayor o igual a {minimo}.'
        return None
    return valor


def _decimal(request, key, etiqueta, errores, minimo=None):
    raw = request.POST.get(key, '').strip()
    if raw == '':
        errores[key] = f'{etiqueta} es obligatorio.'
        return None
    try:
        valor = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        errores[key] = f'{etiqueta} debe ser un número válido.'
        return None
    if minimo is not None and valor < minimo:
        errores[key] = f'{etiqueta} debe ser mayor o igual a {minimo}.'
        return None
    return valor


def _fecha_hora(request, key, etiqueta, errores):
    raw = request.POST.get(key, '').strip()
    if not raw:
        errores[key] = f'{etiqueta} es obligatoria.'
        return None
    valor = parse_datetime(raw)
    if valor is None:
        errores[key] = f'{etiqueta} no tiene un formato válido.'
    return valor


def _email(request, key, etiqueta, errores, requerido=False):
    raw = request.POST.get(key, '').strip()
    if not raw:
        if requerido:
            errores[key] = f'{etiqueta} es obligatorio.'
        return ''
    try:
        validate_email(raw)
    except ValidationError:
        errores[key] = f'{etiqueta} no es válido.'
    return raw


def _objeto(request, key, etiqueta, modelo, errores, queryset=None):
    raw = request.POST.get(key, '').strip()
    if not raw:
        errores[key] = f'Debes seleccionar {etiqueta.lower()}.'
        return None
    qs = queryset if queryset is not None else modelo.objects.all()
    try:
        return qs.get(pk=raw)
    except (modelo.DoesNotExist, ValueError, TypeError):
        errores[key] = f'{etiqueta} no es válido.'
        return None


def _opcion(request, key, etiqueta, opciones, errores):
    raw = request.POST.get(key, '').strip()
    if raw not in dict(opciones):
        errores[key] = f'{etiqueta} no es válida.'
        return None
    return raw


def _datos_post(request, campos):
    return {campo: request.POST.get(campo, '') for campo in campos}


def _datos_producto(producto=None):
    if producto is None:
        return {
            'sku': '', 'nombre': '', 'categoria': '', 'proveedor': '',
            'precio': '', 'stock_actual': '0', 'stock_minimo': '0',
            'activo': 'on',
        }
    return {
        'sku': producto.sku,
        'nombre': producto.nombre,
        'categoria': str(producto.categoria_id),
        'proveedor': str(producto.proveedor_id),
        'precio': str(producto.precio),
        'stock_actual': str(producto.stock_actual),
        'stock_minimo': str(producto.stock_minimo),
        'activo': 'on' if producto.activo else '',
    }


def _datos_categoria(categoria=None):
    if categoria is None:
        return {'nombre': '', 'descripcion': ''}
    return {'nombre': categoria.nombre, 'descripcion': categoria.descripcion or ''}


def _datos_proveedor(proveedor=None):
    if proveedor is None:
        return {
            'rut': '', 'razon_social': '', 'email': '', 'telefono': '',
            'activo': 'on',
        }
    return {
        'rut': proveedor.rut or '',
        'razon_social': proveedor.razon_social,
        'email': proveedor.email or '',
        'telefono': proveedor.telefono or '',
        'activo': 'on' if proveedor.activo else '',
    }


def _datos_sucursal(sucursal=None):
    if sucursal is None:
        return {'codigo': '', 'nombre': '', 'direccion': '', 'activa': 'on'}
    return {
        'codigo': sucursal.codigo,
        'nombre': sucursal.nombre,
        'direccion': sucursal.direccion or '',
        'activa': 'on' if sucursal.activa else '',
    }


def _datos_solicitud(solicitud=None):
    if solicitud is None:
        return {
            'sucursal': '',
            'fecha': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'observaciones': '',
        }
    return {
        'sucursal': str(solicitud.sucursal_id),
        'fecha': solicitud.fecha.strftime('%Y-%m-%dT%H:%M'),
        'observaciones': solicitud.observaciones or '',
    }


def _datos_detalle(detalle=None):
    if detalle is None:
        return {'producto': '', 'cantidad_solicitada': ''}
    return {
        'producto': str(detalle.producto_id),
        'cantidad_solicitada': str(detalle.cantidad_solicitada),
    }


def _datos_movimiento(movimiento=None, tipo='entrada'):
    if movimiento is None:
        return {
            'tipo': tipo,
            'producto': '',
            'cantidad': '',
            'fecha': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'observacion': '',
        }
    return {
        'tipo': movimiento.tipo,
        'producto': str(movimiento.producto_id),
        'cantidad': str(movimiento.cantidad),
        'fecha': movimiento.fecha.strftime('%Y-%m-%dT%H:%M'),
        'observacion': movimiento.observacion or '',
    }


def _datos_usuario(usuario=None):
    if usuario is None:
        return {
            'first_name': '', 'last_name': '', 'email': '',
            'rol': 'Operador', 'password1': '', 'password2': '',
            'is_active': 'on',
        }
    return {
        'first_name': usuario.first_name,
        'last_name': usuario.last_name,
        'email': usuario.email or usuario.username,
        'rol': 'Administrador' if es_admin(usuario) else 'Operador',
        'is_active': 'on' if usuario.is_active else '',
    }


def index(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'public/index.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        usuario = authenticate(request, username=email, password=password)

        if usuario is not None:
            login(request, usuario)
            messages.success(request, f'Bienvenido, {usuario.get_full_name() or usuario.username}')
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('dashboard')

        messages.error(request, 'Credenciales incorrectas o usuario inactivo.')

    return render(request, 'public/login.html', {
        'next': request.POST.get('next') or request.GET.get('next', ''),
    })


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('index')


@login_required
def dashboard(request):
    stats = {
        'total_productos': Producto.objects.count(),
        'stock_bajo': Producto.objects.filter(stock_actual__lt=F('stock_minimo')).count(),
        'total_ingresos': MovimientoStock.objects.filter(tipo='entrada').count(),
        'total_salidas': MovimientoStock.objects.filter(tipo='salida').count(),
        'total_usuarios': User.objects.count(),
    }
    alertas = (
        Producto.objects.filter(stock_actual__lt=F('stock_minimo'))
        .select_related('categoria', 'proveedor')[:5]
    )
    return render(request, 'admin/dashboard.html', {'stats': stats, 'alertas': alertas})


@login_required
def productos_list(request):
    q = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('categoria', '').strip()
    productos = Producto.objects.select_related('categoria', 'proveedor').order_by('nombre')
    if q:
        productos = productos.filter(Q(sku__icontains=q) | Q(nombre__icontains=q))

    categoria_seleccionada = None
    if categoria_id.isdigit():
        categoria_seleccionada = int(categoria_id)
        productos = productos.filter(categoria_id=categoria_seleccionada)

    return render(request, 'admin/productos.html', {
        'productos': productos,
        'categorias': Categoria.objects.order_by('nombre'),
        'q': q,
        'categoria_seleccionada': categoria_seleccionada,
    })


@login_required
def producto_detail(request, pk):
    producto = get_object_or_404(
        Producto.objects.select_related('categoria', 'proveedor'), pk=pk,
    )
    return render(request, 'admin/producto_detail.html', {
        'producto': producto,
        'detalles': producto.detallesolicitud_set.select_related('solicitud__sucursal').order_by('-solicitud__fecha')[:10],
        'movimientos': producto.movimientostock_set.order_by('-fecha')[:10],
    })


@admin_required
def producto_crear(request):
    categorias = Categoria.objects.order_by('nombre')
    proveedores = Proveedor.objects.order_by('razon_social')
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, (
            'sku', 'nombre', 'categoria', 'proveedor', 'precio',
            'stock_actual', 'stock_minimo', 'activo',
        ))
        sku = _texto(request, 'sku').upper()
        nombre = _texto(request, 'nombre')
        datos['sku'] = sku
        datos['nombre'] = nombre
        if not sku:
            errores['sku'] = 'El SKU es obligatorio.'
        elif Producto.objects.filter(sku__iexact=sku).exists():
            errores['sku'] = 'Ya existe un producto con ese SKU.'
        if not nombre:
            errores['nombre'] = 'El nombre es obligatorio.'
        categoria = _objeto(request, 'categoria', 'Categoría', Categoria, errores)
        proveedor = _objeto(request, 'proveedor', 'Proveedor', Proveedor, errores)
        precio = _decimal(request, 'precio', 'Precio', errores, minimo=Decimal('0.01'))
        stock_actual = _entero(request, 'stock_actual', 'Stock actual', errores, minimo=0)
        stock_minimo = _entero(request, 'stock_minimo', 'Stock mínimo', errores, minimo=0)
        activo = request.POST.get('activo') == 'on'
        if not errores:
            producto = Producto.objects.create(
                sku=sku,
                nombre=nombre,
                categoria=categoria,
                proveedor=proveedor,
                precio=precio,
                stock_actual=stock_actual,
                stock_minimo=stock_minimo,
                activo=activo,
            )
            messages.success(request, f'Producto "{producto.nombre}" creado correctamente.')
            return redirect('productos_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_producto()

    return render(request, 'admin/producto_form.html', {
        'datos': datos,
        'errores': errores,
        'categorias': categorias,
        'proveedores': proveedores,
        'titulo': 'Nuevo producto',
        'cancelar_url_name': 'productos_list',
    })


@admin_required
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    categorias = Categoria.objects.order_by('nombre')
    proveedores = Proveedor.objects.order_by('razon_social')
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, (
            'sku', 'nombre', 'categoria', 'proveedor', 'precio',
            'stock_actual', 'stock_minimo', 'activo',
        ))
        sku = _texto(request, 'sku').upper()
        nombre = _texto(request, 'nombre')
        datos['sku'] = sku
        datos['nombre'] = nombre
        if not sku:
            errores['sku'] = 'El SKU es obligatorio.'
        elif Producto.objects.filter(sku__iexact=sku).exclude(pk=producto.pk).exists():
            errores['sku'] = 'Ya existe un producto con ese SKU.'
        if not nombre:
            errores['nombre'] = 'El nombre es obligatorio.'
        categoria = _objeto(request, 'categoria', 'Categoría', Categoria, errores)
        proveedor = _objeto(request, 'proveedor', 'Proveedor', Proveedor, errores)
        precio = _decimal(request, 'precio', 'Precio', errores, minimo=Decimal('0.01'))
        stock_actual = _entero(request, 'stock_actual', 'Stock actual', errores, minimo=0)
        stock_minimo = _entero(request, 'stock_minimo', 'Stock mínimo', errores, minimo=0)
        activo = request.POST.get('activo') == 'on'
        if not errores:
            producto.sku = sku
            producto.nombre = nombre
            producto.categoria = categoria
            producto.proveedor = proveedor
            producto.precio = precio
            producto.stock_actual = stock_actual
            producto.stock_minimo = stock_minimo
            producto.activo = activo
            producto.save()
            messages.success(request, f'Producto "{producto.nombre}" actualizado correctamente.')
            return redirect('producto_detail', pk=producto.pk)
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_producto(producto)

    return render(request, 'admin/producto_form.html', {
        'datos': datos,
        'errores': errores,
        'categorias': categorias,
        'proveedores': proveedores,
        'titulo': 'Editar producto',
        'producto': producto,
        'cancelar_url_name': 'producto_detail',
        'cancelar_pk': producto.pk,
    })


@admin_required
def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        nombre = producto.nombre
        try:
            producto.delete()
            messages.success(request, f'Producto "{nombre}" eliminado correctamente.')
        except ProtectedError:
            messages.error(request, 'No se puede eliminar el producto porque tiene solicitudes o movimientos asociados.')
        return redirect('productos_list')

    return render(request, 'admin/confirmar_eliminar.html', {
        'titulo': 'Eliminar producto',
        'objeto': f'{producto.sku} - {producto.nombre}',
        'detalle': 'Si el producto tiene detalles de solicitud o movimientos de stock, no se podrá eliminar.',
        'cancelar_url_name': 'productos_list',
    })


@login_required
def categorias_list(request):
    categorias = Categoria.objects.annotate(total_productos=Count('producto')).order_by('nombre')
    return render(request, 'admin/categorias.html', {'categorias': categorias})


@admin_required
def categoria_crear(request):
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, ('nombre', 'descripcion'))
        nombre = _texto(request, 'nombre')
        descripcion = request.POST.get('descripcion', '').strip()
        datos['nombre'] = nombre
        if not nombre:
            errores['nombre'] = 'El nombre es obligatorio.'
        elif Categoria.objects.filter(nombre__iexact=nombre).exists():
            errores['nombre'] = 'Ya existe una categoría con ese nombre.'
        if not errores:
            categoria = Categoria.objects.create(
                nombre=nombre,
                descripcion=descripcion or None,
            )
            messages.success(request, f'Categoría "{categoria.nombre}" creada correctamente.')
            return redirect('categorias_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_categoria()

    return render(request, 'admin/categoria_form.html', {
        'datos': datos,
        'errores': errores,
        'titulo': 'Nueva categoría',
        'cancelar_url_name': 'categorias_list',
    })


@admin_required
def categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, ('nombre', 'descripcion'))
        nombre = _texto(request, 'nombre')
        descripcion = request.POST.get('descripcion', '').strip()
        datos['nombre'] = nombre
        if not nombre:
            errores['nombre'] = 'El nombre es obligatorio.'
        elif Categoria.objects.filter(nombre__iexact=nombre).exclude(pk=categoria.pk).exists():
            errores['nombre'] = 'Ya existe una categoría con ese nombre.'
        if not errores:
            categoria.nombre = nombre
            categoria.descripcion = descripcion or None
            categoria.save()
            messages.success(request, f'Categoría "{categoria.nombre}" actualizada correctamente.')
            return redirect('categorias_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_categoria(categoria)

    return render(request, 'admin/categoria_form.html', {
        'datos': datos,
        'errores': errores,
        'titulo': 'Editar categoría',
        'categoria': categoria,
        'cancelar_url_name': 'categorias_list',
    })


@admin_required
def categoria_eliminar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        nombre = categoria.nombre
        try:
            categoria.delete()
            messages.success(request, f'Categoría "{nombre}" eliminada correctamente.')
        except ProtectedError:
            messages.error(request, 'No se puede eliminar la categoría porque tiene productos asociados.')
        return redirect('categorias_list')

    return render(request, 'admin/confirmar_eliminar.html', {
        'titulo': 'Eliminar categoría',
        'objeto': categoria.nombre,
        'detalle': 'Si la categoría tiene productos asociados, no se podrá eliminar.',
        'cancelar_url_name': 'categorias_list',
    })


@login_required
def proveedores_list(request):
    q = request.GET.get('q', '').strip()
    proveedores = Proveedor.objects.annotate(total_productos=Count('producto')).order_by('razon_social')
    if q:
        proveedores = proveedores.filter(
            Q(razon_social__icontains=q) | Q(rut__icontains=q) | Q(email__icontains=q)
        )
    return render(request, 'admin/proveedores.html', {'proveedores': proveedores, 'q': q})


@admin_required
def proveedor_crear(request):
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, (
            'rut', 'razon_social', 'email', 'telefono', 'activo',
        ))
        rut = _texto(request, 'rut')
        razon_social = _texto(request, 'razon_social')
        email = _email(request, 'email', 'Correo electrónico', errores)
        telefono = _texto(request, 'telefono')
        activo = request.POST.get('activo') == 'on'
        datos['rut'] = rut
        datos['razon_social'] = razon_social
        datos['email'] = email
        datos['telefono'] = telefono
        if not razon_social:
            errores['razon_social'] = 'La razón social es obligatoria.'
        if rut and Proveedor.objects.filter(rut__iexact=rut).exists():
            errores['rut'] = 'Ya existe un proveedor con ese RUT.'
        if not errores:
            proveedor = Proveedor.objects.create(
                rut=rut or None,
                razon_social=razon_social,
                email=email or None,
                telefono=telefono or None,
                activo=activo,
            )
            messages.success(request, f'Proveedor "{proveedor.razon_social}" creado correctamente.')
            return redirect('proveedores_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_proveedor()

    return render(request, 'admin/proveedor_form.html', {
        'datos': datos,
        'errores': errores,
        'titulo': 'Nuevo proveedor',
        'cancelar_url_name': 'proveedores_list',
    })


@admin_required
def proveedor_editar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, (
            'rut', 'razon_social', 'email', 'telefono', 'activo',
        ))
        rut = _texto(request, 'rut')
        razon_social = _texto(request, 'razon_social')
        email = _email(request, 'email', 'Correo electrónico', errores)
        telefono = _texto(request, 'telefono')
        activo = request.POST.get('activo') == 'on'
        datos['rut'] = rut
        datos['razon_social'] = razon_social
        datos['email'] = email
        datos['telefono'] = telefono
        if not razon_social:
            errores['razon_social'] = 'La razón social es obligatoria.'
        if rut and Proveedor.objects.filter(rut__iexact=rut).exclude(pk=proveedor.pk).exists():
            errores['rut'] = 'Ya existe un proveedor con ese RUT.'
        if not errores:
            proveedor.rut = rut or None
            proveedor.razon_social = razon_social
            proveedor.email = email or None
            proveedor.telefono = telefono or None
            proveedor.activo = activo
            proveedor.save()
            messages.success(request, f'Proveedor "{proveedor.razon_social}" actualizado correctamente.')
            return redirect('proveedores_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_proveedor(proveedor)

    return render(request, 'admin/proveedor_form.html', {
        'datos': datos,
        'errores': errores,
        'titulo': 'Editar proveedor',
        'proveedor': proveedor,
        'cancelar_url_name': 'proveedores_list',
    })


@admin_required
def proveedor_eliminar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        nombre = proveedor.razon_social
        try:
            proveedor.delete()
            messages.success(request, f'Proveedor "{nombre}" eliminado correctamente.')
        except ProtectedError:
            messages.error(request, 'No se puede eliminar el proveedor porque tiene productos asociados.')
        return redirect('proveedores_list')

    return render(request, 'admin/confirmar_eliminar.html', {
        'titulo': 'Eliminar proveedor',
        'objeto': proveedor.razon_social,
        'detalle': 'Si el proveedor tiene productos asociados, no se podrá eliminar.',
        'cancelar_url_name': 'proveedores_list',
    })


@login_required
def sucursales_list(request):
    q = request.GET.get('q', '').strip()
    sucursales = Sucursal.objects.annotate(total_solicitudes=Count('solicitud')).order_by('codigo')
    if q:
        sucursales = sucursales.filter(Q(codigo__icontains=q) | Q(nombre__icontains=q))
    return render(request, 'admin/sucursales.html', {'sucursales': sucursales, 'q': q})


@admin_required
def sucursal_crear(request):
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, ('codigo', 'nombre', 'direccion', 'activa'))
        codigo = _texto(request, 'codigo').upper()
        nombre = _texto(request, 'nombre')
        direccion = _texto(request, 'direccion')
        activa = request.POST.get('activa') == 'on'
        datos['codigo'] = codigo
        datos['nombre'] = nombre
        if not codigo:
            errores['codigo'] = 'El código es obligatorio.'
        elif Sucursal.objects.filter(codigo__iexact=codigo).exists():
            errores['codigo'] = 'Ya existe una sucursal con ese código.'
        if not nombre:
            errores['nombre'] = 'El nombre es obligatorio.'
        if not errores:
            sucursal = Sucursal.objects.create(
                codigo=codigo,
                nombre=nombre,
                direccion=direccion or None,
                activa=activa,
            )
            messages.success(request, f'Sucursal "{sucursal.nombre}" creada correctamente.')
            return redirect('sucursales_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_sucursal()

    return render(request, 'admin/sucursal_form.html', {
        'datos': datos,
        'errores': errores,
        'titulo': 'Nueva sucursal',
        'cancelar_url_name': 'sucursales_list',
    })


@admin_required
def sucursal_editar(request, pk):
    sucursal = get_object_or_404(Sucursal, pk=pk)
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, ('codigo', 'nombre', 'direccion', 'activa'))
        codigo = _texto(request, 'codigo').upper()
        nombre = _texto(request, 'nombre')
        direccion = _texto(request, 'direccion')
        activa = request.POST.get('activa') == 'on'
        datos['codigo'] = codigo
        datos['nombre'] = nombre
        if not codigo:
            errores['codigo'] = 'El código es obligatorio.'
        elif Sucursal.objects.filter(codigo__iexact=codigo).exclude(pk=sucursal.pk).exists():
            errores['codigo'] = 'Ya existe una sucursal con ese código.'
        if not nombre:
            errores['nombre'] = 'El nombre es obligatorio.'
        if not errores:
            sucursal.codigo = codigo
            sucursal.nombre = nombre
            sucursal.direccion = direccion or None
            sucursal.activa = activa
            sucursal.save()
            messages.success(request, f'Sucursal "{sucursal.nombre}" actualizada correctamente.')
            return redirect('sucursales_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_sucursal(sucursal)

    return render(request, 'admin/sucursal_form.html', {
        'datos': datos,
        'errores': errores,
        'titulo': 'Editar sucursal',
        'sucursal': sucursal,
        'cancelar_url_name': 'sucursales_list',
    })


@admin_required
def sucursal_eliminar(request, pk):
    sucursal = get_object_or_404(Sucursal, pk=pk)
    if request.method == 'POST':
        nombre = sucursal.nombre
        try:
            sucursal.delete()
            messages.success(request, f'Sucursal "{nombre}" eliminada correctamente.')
        except ProtectedError:
            messages.error(request, 'No se puede eliminar la sucursal porque tiene solicitudes asociadas.')
        return redirect('sucursales_list')

    return render(request, 'admin/confirmar_eliminar.html', {
        'titulo': 'Eliminar sucursal',
        'objeto': f'{sucursal.codigo} - {sucursal.nombre}',
        'detalle': 'Si la sucursal tiene solicitudes asociadas, no se podrá eliminar.',
        'cancelar_url_name': 'sucursales_list',
    })


# ========== USUARIOS (Admin) ==========

@admin_required
def usuarios_list(request):
    usuarios = list(User.objects.prefetch_related('groups').order_by('first_name', 'last_name', 'username'))
    for usuario in usuarios:
        usuario.rol_nombre = 'Administrador' if es_admin(usuario) else 'Operador'
    return render(request, 'admin/usuarios.html', {'usuarios': usuarios})


@admin_required
def usuario_detail(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    return render(request, 'admin/usuario_detail.html', {
        'usuario': usuario,
        'rol_usuario': 'Administrador' if es_admin(usuario) else 'Operador',
    })


@admin_required
def usuario_crear(request):
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, (
            'first_name', 'last_name', 'email', 'rol', 'password1', 'password2',
        ))
        first_name = _texto(request, 'first_name')
        last_name = _texto(request, 'last_name')
        email = _email(
            request, 'email', 'Correo electrónico', errores, requerido=True,
        ).lower()
        rol = _opcion(request, 'rol', 'Rol', ROLES, errores)
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        datos['first_name'] = first_name
        datos['last_name'] = last_name
        datos['email'] = email
        if email and 'email' not in errores:
            if User.objects.filter(
                Q(email__iexact=email) | Q(username__iexact=email)
            ).exists():
                errores['email'] = 'Ya existe un usuario con ese correo electrónico.'
        if not password1:
            errores['password1'] = 'La contraseña es obligatoria.'
        else:
            usuario_temporal = User(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            try:
                validate_password(password1, usuario_temporal)
            except ValidationError as error:
                errores['password1'] = ' '.join(error.messages)
        if not password2:
            errores['password2'] = 'Debes confirmar la contraseña.'
        elif password1 and password1 != password2:
            errores['password2'] = 'Las contraseñas no coinciden.'
        if not errores:
            usuario = User.objects.create_user(
                username=email,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                is_staff=(rol == 'Administrador'),
            )
            grupo, _ = Group.objects.get_or_create(name=rol)
            usuario.groups.set([grupo])
            messages.success(
                request,
                f'Usuario "{usuario.get_full_name() or usuario.username}" creado correctamente.',
            )
            return redirect('usuarios_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_usuario()

    return render(request, 'admin/usuario_form.html', {
        'datos': datos,
        'errores': errores,
        'roles': ROLES,
        'titulo': 'Crear nuevo usuario',
        'accion': 'crear',
    })


@admin_required
def usuario_editar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, (
            'first_name', 'last_name', 'email', 'rol', 'is_active',
        ))
        first_name = _texto(request, 'first_name')
        last_name = _texto(request, 'last_name')
        email = _email(
            request, 'email', 'Correo electrónico', errores, requerido=True,
        ).lower()
        rol = _opcion(request, 'rol', 'Rol', ROLES, errores)
        is_active = request.POST.get('is_active') == 'on'
        datos['first_name'] = first_name
        datos['last_name'] = last_name
        datos['email'] = email
        if email and 'email' not in errores:
            if User.objects.filter(
                Q(email__iexact=email) | Q(username__iexact=email)
            ).exclude(pk=usuario.pk).exists():
                errores['email'] = 'Ya existe un usuario con ese correo electrónico.'
        if usuario == request.user and rol and rol != 'Administrador':
            errores['rol'] = 'No puedes quitarte a ti mismo el rol de Administrador.'
        if usuario == request.user and not is_active:
            errores['is_active'] = 'No puedes desactivar tu propio usuario.'
        if es_admin(usuario) and rol and (rol != 'Administrador' or not is_active):
            otros_admins = User.objects.filter(
                Q(is_superuser=True) | Q(groups__name='Administrador'),
                is_active=True,
            ).exclude(pk=usuario.pk).distinct().count()
            if otros_admins == 0:
                errores['rol' if rol != 'Administrador' else 'is_active'] = (
                    'No puedes dejar el sistema sin administradores activos.'
                )
        if not errores:
            usuario.first_name = first_name
            usuario.last_name = last_name
            usuario.username = email
            usuario.email = email
            usuario.is_staff = (rol == 'Administrador')
            if rol != 'Administrador':
                usuario.is_superuser = False
            usuario.is_active = is_active
            usuario.save()
            grupo, _ = Group.objects.get_or_create(name=rol)
            usuario.groups.set([grupo])
            messages.success(
                request,
                f'Usuario "{usuario.get_full_name() or usuario.username}" actualizado correctamente.',
            )
            return redirect('usuarios_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_usuario(usuario)

    return render(request, 'admin/usuario_form.html', {
        'datos': datos,
        'errores': errores,
        'roles': ROLES,
        'titulo': 'Editar usuario',
        'accion': 'editar',
        'usuario': usuario,
    })


@admin_required
def usuario_eliminar(request, pk):
    usuario = get_object_or_404(User, pk=pk)

    if usuario == request.user:
        messages.error(request, 'No puedes eliminar tu propio usuario.')
        return redirect('usuarios_list')

    if es_admin(usuario):
        administradores = User.objects.filter(
            Q(is_superuser=True) | Q(groups__name='Administrador'),
            is_active=True,
        ).distinct().count()
        if administradores <= 1:
            messages.error(request, 'No puedes eliminar al último administrador activo.')
            return redirect('usuarios_list')

    if request.method == 'POST':
        nombre = usuario.get_full_name() or usuario.username
        usuario.delete()
        messages.success(request, f'Usuario "{nombre}" eliminado correctamente.')
        return redirect('usuarios_list')

    return render(request, 'admin/usuario_eliminar.html', {'usuario': usuario})


# ========== SOLICITUDES, DETALLES Y MOVIMIENTOS DE STOCK ==========

def _contexto_solicitud_detail(
    solicitud, detalle_datos=None, detalle_errores=None, productos=None,
):
    detalles = list(
        solicitud.detallesolicitud_set.select_related('producto__categoria')
        .order_by('producto__nombre')
    )
    movimientos = (
        solicitud.movimientostock_set.select_related('producto')
        .order_by('-fecha')
    )
    totales = {
        'solicitado': sum(d.cantidad_solicitada or 0 for d in detalles),
        'aprobado': sum(d.cantidad_aprobada or 0 for d in detalles),
        'despachado': sum(d.cantidad_despachada or 0 for d in detalles),
    }
    if productos is None:
        productos = Producto.objects.filter(activo=True).order_by('nombre')
    if detalle_datos is None:
        detalle_datos = _datos_detalle()
    if detalle_errores is None:
        detalle_errores = {}
    return {
        'solicitud': solicitud,
        'detalles': detalles,
        'movimientos': movimientos,
        'totales': totales,
        'detalle_datos': detalle_datos,
        'detalle_errores': detalle_errores,
        'productos': productos,
    }


@login_required
def solicitudes_list(request):
    estado = request.GET.get('estado', '').strip()
    sucursal_id = request.GET.get('sucursal', '').strip()

    solicitudes = (
        Solicitud.objects.select_related('sucursal')
        .annotate(
            total_items=Count('detallesolicitud'),
            total_solicitado=Sum('detallesolicitud__cantidad_solicitada'),
        )
        .order_by('-fecha')
    )
    if estado in dict(Solicitud.ESTADO_CHOICES):
        solicitudes = solicitudes.filter(estado=estado)

    sucursal_seleccionada = None
    if sucursal_id.isdigit():
        sucursal_seleccionada = int(sucursal_id)
        solicitudes = solicitudes.filter(sucursal_id=sucursal_seleccionada)

    return render(request, 'admin/solicitudes.html', {
        'solicitudes': solicitudes,
        'estados': Solicitud.ESTADO_CHOICES,
        'estado_seleccionado': estado,
        'sucursales': Sucursal.objects.order_by('nombre'),
        'sucursal_seleccionada': sucursal_seleccionada,
    })


@login_required
def solicitud_crear(request):
    sucursales = Sucursal.objects.order_by('nombre')
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, ('sucursal', 'fecha', 'observaciones'))
        sucursal = _objeto(
            request, 'sucursal', 'Sucursal', Sucursal, errores, queryset=sucursales,
        )
        fecha = _fecha_hora(request, 'fecha', 'Fecha', errores)
        observaciones = request.POST.get('observaciones', '').strip()
        if not errores:
            solicitud = Solicitud.objects.create(
                sucursal=sucursal,
                fecha=fecha,
                estado='pendiente',
                observaciones=observaciones or None,
            )
            messages.success(
                request,
                f'Solicitud #{solicitud.pk} creada. Agrega los productos solicitados.',
            )
            return redirect('solicitud_detail', pk=solicitud.pk)
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_solicitud()

    return render(request, 'admin/solicitud_form.html', {
        'datos': datos,
        'errores': errores,
        'sucursales': sucursales,
        'titulo': 'Nueva solicitud',
        'cancelar_url_name': 'solicitudes_list',
    })


@login_required
def solicitud_detail(request, pk):
    solicitud = get_object_or_404(Solicitud.objects.select_related('sucursal'), pk=pk)
    return render(request, 'admin/solicitud_detail.html', _contexto_solicitud_detail(solicitud))


@login_required
def solicitud_editar(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)
    if solicitud.estado != 'pendiente':
        messages.error(request, 'Solo se pueden editar solicitudes pendientes.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    sucursales = Sucursal.objects.order_by('nombre')
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, ('sucursal', 'fecha', 'observaciones'))
        sucursal = _objeto(
            request, 'sucursal', 'Sucursal', Sucursal, errores, queryset=sucursales,
        )
        fecha = _fecha_hora(request, 'fecha', 'Fecha', errores)
        observaciones = request.POST.get('observaciones', '').strip()
        if not errores:
            solicitud.sucursal = sucursal
            solicitud.fecha = fecha
            solicitud.observaciones = observaciones or None
            solicitud.save()
            messages.success(request, f'Solicitud #{solicitud.pk} actualizada correctamente.')
            return redirect('solicitud_detail', pk=solicitud.pk)
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        datos = _datos_solicitud(solicitud)

    return render(request, 'admin/solicitud_form.html', {
        'datos': datos,
        'errores': errores,
        'sucursales': sucursales,
        'titulo': f'Editar solicitud #{solicitud.pk}',
        'solicitud': solicitud,
        'cancelar_url_name': 'solicitud_detail',
        'cancelar_pk': solicitud.pk,
    })


@login_required
def solicitud_eliminar(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)
    if solicitud.estado != 'pendiente':
        messages.error(request, 'Solo se pueden eliminar solicitudes pendientes.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    if request.method == 'POST':
        numero = solicitud.pk
        solicitud.delete()
        messages.success(request, f'Solicitud #{numero} eliminada correctamente.')
        return redirect('solicitudes_list')

    return render(request, 'admin/confirmar_eliminar.html', {
        'titulo': f'Eliminar solicitud #{solicitud.pk}',
        'objeto': f'Solicitud #{solicitud.pk} - {solicitud.sucursal.nombre}',
        'detalle': 'Se eliminarán también todos sus detalles.',
        'cancelar_url_name': 'solicitud_detail',
        'cancelar_pk': solicitud.pk,
    })


@login_required
@require_POST
def detalle_crear(request, solicitud_pk):
    solicitud = get_object_or_404(Solicitud.objects.select_related('sucursal'), pk=solicitud_pk)
    if solicitud.estado != 'pendiente':
        messages.error(request, 'Solo se pueden agregar productos a solicitudes pendientes.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    productos = Producto.objects.filter(activo=True).order_by('nombre')
    errores = {}
    datos = _datos_post(request, ('producto', 'cantidad_solicitada'))
    producto = _objeto(
        request, 'producto', 'Producto', Producto, errores, queryset=productos,
    )
    cantidad = _entero(
        request, 'cantidad_solicitada', 'Cantidad solicitada', errores, minimo=1,
    )
    if not errores and solicitud.detallesolicitud_set.filter(producto=producto).exists():
        errores['producto'] = (
            'Ese producto ya está en la solicitud. '
            'Edita la cantidad del detalle existente.'
        )
    if errores:
        messages.error(request, 'Revisa los datos del producto y la cantidad.')
        return render(
            request,
            'admin/solicitud_detail.html',
            _contexto_solicitud_detail(
                solicitud,
                detalle_datos=datos,
                detalle_errores=errores,
                productos=productos,
            ),
        )

    DetalleSolicitud.objects.create(
        solicitud=solicitud,
        producto=producto,
        cantidad_solicitada=cantidad,
    )
    messages.success(request, f'Producto "{producto.nombre}" agregado a la solicitud.')
    return redirect('solicitud_detail', pk=solicitud.pk)


@login_required
def detalle_editar(request, pk):
    detalle = get_object_or_404(
        DetalleSolicitud.objects.select_related('solicitud', 'producto'), pk=pk,
    )
    solicitud = detalle.solicitud
    if solicitud.estado != 'pendiente':
        messages.error(request, 'Solo se pueden editar detalles de solicitudes pendientes.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    productos = Producto.objects.filter(
        Q(activo=True) | Q(pk=detalle.producto_id),
    ).order_by('nombre')
    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, ('producto', 'cantidad_solicitada'))
        producto = _objeto(
            request, 'producto', 'Producto', Producto, errores, queryset=productos,
        )
        cantidad = _entero(
            request, 'cantidad_solicitada', 'Cantidad solicitada', errores, minimo=1,
        )
        if not errores:
            duplicado = (
                solicitud.detallesolicitud_set
                .filter(producto=producto)
                .exclude(pk=detalle.pk)
                .exists()
            )
            if duplicado:
                errores['producto'] = 'Ese producto ya está en la solicitud.'
            else:
                detalle.producto = producto
                detalle.cantidad_solicitada = cantidad
                detalle.save()
                messages.success(request, 'Detalle actualizado correctamente.')
                return redirect('solicitud_detail', pk=solicitud.pk)
        messages.error(request, 'Revisa los datos del detalle.')
    else:
        datos = _datos_detalle(detalle)

    return render(request, 'admin/detalle_form.html', {
        'datos': datos,
        'errores': errores,
        'productos': productos,
        'titulo': f'Editar detalle de solicitud #{solicitud.pk}',
        'detalle': detalle,
        'cancelar_url_name': 'solicitud_detail',
        'cancelar_pk': solicitud.pk,
    })


@login_required
def detalle_eliminar(request, pk):
    detalle = get_object_or_404(
        DetalleSolicitud.objects.select_related('solicitud', 'producto'), pk=pk,
    )
    solicitud = detalle.solicitud
    if solicitud.estado != 'pendiente':
        messages.error(request, 'Solo se pueden eliminar detalles de solicitudes pendientes.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    if request.method == 'POST':
        detalle.delete()
        messages.success(request, 'Detalle eliminado correctamente.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    return render(request, 'admin/confirmar_eliminar.html', {
        'titulo': 'Eliminar detalle de solicitud',
        'objeto': f'{detalle.producto.nombre} ({detalle.cantidad_solicitada} unidades)',
        'detalle': 'El producto se quitará de esta solicitud.',
        'cancelar_url_name': 'solicitud_detail',
        'cancelar_pk': solicitud.pk,
    })


@admin_required
def solicitud_autorizar(request, pk):
    solicitud = get_object_or_404(Solicitud.objects.select_related('sucursal'), pk=pk)
    if solicitud.estado != 'pendiente':
        messages.error(request, 'Solo se pueden autorizar solicitudes pendientes.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    detalles = list(
        solicitud.detallesolicitud_set.select_related('producto')
        .order_by('producto__nombre')
    )
    if not detalles:
        messages.error(request, 'Agrega al menos un producto antes de autorizar la solicitud.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    for detalle in detalles:
        if request.method == 'POST':
            detalle.valor_aprobacion = request.POST.get(
                f'cantidad_{detalle.pk}', detalle.cantidad_solicitada,
            )
        else:
            detalle.valor_aprobacion = (
                detalle.cantidad_aprobada
                if detalle.cantidad_aprobada is not None
                else detalle.cantidad_solicitada
            )

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'rechazar':
            with transaction.atomic():
                for detalle in detalles:
                    detalle.cantidad_aprobada = 0
                    detalle.save(update_fields=['cantidad_aprobada'])
                solicitud.estado = 'rechazada'
                solicitud.save(update_fields=['estado'])
            messages.warning(request, f'Solicitud #{solicitud.pk} rechazada.')
            return redirect('solicitud_detail', pk=solicitud.pk)

        if accion == 'aprobar':
            errores = []
            cantidades = {}
            for detalle in detalles:
                raw = str(detalle.valor_aprobacion).strip()
                try:
                    cantidad = int(raw)
                except (TypeError, ValueError):
                    errores.append(f'Cantidad inválida para {detalle.producto.nombre}.')
                    continue
                if cantidad < 0 or cantidad > detalle.cantidad_solicitada:
                    errores.append(
                        f'La cantidad aprobada de {detalle.producto.nombre} debe estar '
                        f'entre 0 y {detalle.cantidad_solicitada}.'
                    )
                    continue
                cantidades[detalle.pk] = cantidad

            if not errores and not any(cantidades.values()):
                errores.append('Debes aprobar al menos una unidad o rechazar la solicitud.')

            if errores:
                for error in errores:
                    messages.error(request, error)
            else:
                with transaction.atomic():
                    for detalle in detalles:
                        detalle.cantidad_aprobada = cantidades[detalle.pk]
                        detalle.save(update_fields=['cantidad_aprobada'])
                    solicitud.estado = 'aprobada'
                    solicitud.save(update_fields=['estado'])
                messages.success(
                    request,
                    f'Solicitud #{solicitud.pk} aprobada. Ya puede despacharse.',
                )
                return redirect('solicitud_detail', pk=solicitud.pk)
        else:
            messages.error(request, 'Acción no válida.')

    return render(request, 'admin/solicitud_autorizar.html', {
        'solicitud': solicitud,
        'detalles': detalles,
    })


@admin_required
@require_POST
def solicitud_despachar(request, pk):
    solicitud = get_object_or_404(Solicitud.objects.select_related('sucursal'), pk=pk)

    if solicitud.estado != 'aprobada':
        messages.error(request, 'Solo se pueden despachar solicitudes aprobadas.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    detalles = list(
        solicitud.detallesolicitud_set.select_related('producto')
        .order_by('producto__nombre')
    )
    if not detalles:
        messages.error(request, 'La solicitud no tiene detalles para despachar.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    try:
        with transaction.atomic():
            solicitud = Solicitud.objects.select_for_update().get(pk=solicitud.pk)
            if solicitud.estado != 'aprobada':
                raise ValueError('La solicitud ya fue procesada por otro usuario.')

            detalles = list(
                solicitud.detallesolicitud_set.select_related('producto')
                .order_by('producto__nombre')
            )
            if not detalles:
                raise ValueError('La solicitud no tiene detalles para despachar.')

            movimientos = []
            for detalle in detalles:
                cantidad = detalle.cantidad_aprobada or 0
                if cantidad <= 0:
                    continue

                producto = Producto.objects.select_for_update().get(pk=detalle.producto_id)
                if producto.stock_actual < cantidad:
                    raise ValueError(
                        f'Stock insuficiente para {producto.nombre}: '
                        f'disponible {producto.stock_actual}, requerido {cantidad}.'
                    )

                producto.stock_actual -= cantidad
                producto.save(update_fields=['stock_actual'])

                detalle.cantidad_despachada = cantidad
                detalle.save(update_fields=['cantidad_despachada'])

                movimientos.append(MovimientoStock(
                    producto=producto,
                    solicitud=solicitud,
                    tipo='salida',
                    cantidad=cantidad,
                    fecha=timezone.now(),
                    observacion=f'Despacho de solicitud #{solicitud.pk}',
                ))

            if not movimientos:
                raise ValueError(
                    'No hay cantidades aprobadas mayores que cero para despachar.'
                )

            MovimientoStock.objects.bulk_create(movimientos)
            solicitud.estado = 'despachada'
            solicitud.save(update_fields=['estado'])
    except ValueError as error:
        messages.error(request, str(error))
        return redirect('solicitud_detail', pk=solicitud.pk)

    messages.success(
        request,
        f'Solicitud #{solicitud.pk} despachada y stock actualizado correctamente.',
    )
    return redirect('solicitud_detail', pk=solicitud.pk)


@login_required
def movimientos_list(request):
    tipo = request.GET.get('tipo', '').strip()
    producto_id = request.GET.get('producto', '').strip()
    desde = request.GET.get('desde', '').strip()
    hasta = request.GET.get('hasta', '').strip()

    movimientos = (
        MovimientoStock.objects.select_related('producto', 'solicitud__sucursal')
        .order_by('-fecha')
    )
    if tipo in dict(MovimientoStock.TIPO_CHOICES):
        movimientos = movimientos.filter(tipo=tipo)

    producto_seleccionado = None
    if producto_id.isdigit():
        producto_seleccionado = int(producto_id)
        movimientos = movimientos.filter(producto_id=producto_seleccionado)

    fecha_desde = parse_date(desde) if desde else None
    fecha_hasta = parse_date(hasta) if hasta else None
    if fecha_desde:
        movimientos = movimientos.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        movimientos = movimientos.filter(fecha__date__lte=fecha_hasta)

    return render(request, 'admin/movimientos.html', {
        'movimientos': movimientos,
        'tipos': MovimientoStock.TIPO_CHOICES,
        'tipo_seleccionado': tipo,
        'productos': Producto.objects.order_by('nombre'),
        'producto_seleccionado': producto_seleccionado,
        'desde': desde,
        'hasta': hasta,
    })


@login_required
def movimiento_crear(request):
    usuario_admin = es_admin(request.user)
    tipo_inicial = request.GET.get('tipo', 'entrada')
    if not usuario_admin:
        tipo_inicial = 'entrada'
    if tipo_inicial not in dict(MovimientoStock.TIPO_CHOICES):
        tipo_inicial = 'entrada'

    productos = Producto.objects.filter(activo=True).order_by('nombre')
    tipos = MovimientoStock.TIPO_CHOICES if usuario_admin else [('entrada', 'Entrada')]
    errores = {}
    if request.method == 'POST':
        tipo_solicitado = request.POST.get('tipo')
        if not usuario_admin and tipo_solicitado != 'entrada':
            messages.error(
                request,
                'Solo el administrador puede registrar salidas directas. '
                'Para enviar productos a una sucursal crea una solicitud de pedido.',
            )
            datos = _datos_movimiento(tipo='entrada')
        else:
            datos = _datos_post(request, (
                'tipo', 'producto', 'cantidad', 'fecha', 'observacion',
            ))
            tipo = _opcion(request, 'tipo', 'Tipo de movimiento', tipos, errores)
            producto = _objeto(
                request, 'producto', 'Producto', Producto, errores,
                queryset=productos,
            )
            cantidad = _entero(request, 'cantidad', 'Cantidad', errores, minimo=1)
            fecha = _fecha_hora(request, 'fecha', 'Fecha', errores)
            observacion = request.POST.get('observacion', '').strip()
            if not errores:
                with transaction.atomic():
                    producto = Producto.objects.select_for_update().get(pk=producto.pk)
                    if tipo == 'salida' and producto.stock_actual < cantidad:
                        errores['cantidad'] = (
                            f'Stock insuficiente para {producto.nombre}: '
                            f'disponible {producto.stock_actual}, solicitado {cantidad}.'
                        )
                    else:
                        movimiento = MovimientoStock.objects.create(
                            producto=producto,
                            tipo=tipo,
                            cantidad=cantidad,
                            fecha=fecha,
                            observacion=observacion or None,
                        )
                        if tipo == 'entrada':
                            producto.stock_actual += cantidad
                        else:
                            producto.stock_actual -= cantidad
                        producto.save(update_fields=['stock_actual'])
                if not errores:
                    messages.success(
                        request,
                        f'Movimiento de {movimiento.get_tipo_display().lower()} registrado correctamente.',
                    )
                    return redirect('movimientos_list')
            if errores:
                messages.error(request, 'Revisa los datos del movimiento.')
    else:
        datos = _datos_movimiento(tipo=tipo_inicial)

    return render(request, 'admin/movimiento_form.html', {
        'datos': datos,
        'errores': errores,
        'productos': productos,
        'tipos': tipos,
        'titulo': 'Registrar movimiento de stock',
        'cancelar_url_name': 'movimientos_list',
    })


@admin_required
def movimiento_editar(request, pk):
    movimiento = get_object_or_404(
        MovimientoStock.objects.select_related('producto', 'solicitud'), pk=pk,
    )
    if movimiento.solicitud_id:
        messages.error(
            request,
            'No se puede editar un movimiento generado por una solicitud.',
        )
        return redirect('movimientos_list')

    errores = {}
    if request.method == 'POST':
        datos = _datos_post(request, ('fecha', 'observacion'))
        fecha = _fecha_hora(request, 'fecha', 'Fecha', errores)
        observacion = request.POST.get('observacion', '').strip()
        if not errores:
            movimiento.fecha = fecha
            movimiento.observacion = observacion or None
            movimiento.save(update_fields=['fecha', 'observacion'])
            messages.success(request, 'Movimiento actualizado correctamente.')
            return redirect('movimientos_list')
        messages.error(request, 'Revisa los datos del movimiento.')
    else:
        datos = {
            'fecha': movimiento.fecha.strftime('%Y-%m-%dT%H:%M'),
            'observacion': movimiento.observacion or '',
        }

    return render(request, 'admin/movimiento_editar.html', {
        'datos': datos,
        'errores': errores,
        'titulo': f'Editar movimiento #{movimiento.pk}',
        'movimiento': movimiento,
        'cancelar_url_name': 'movimientos_list',
    })


@admin_required
def movimiento_eliminar(request, pk):
    movimiento = get_object_or_404(
        MovimientoStock.objects.select_related('producto', 'solicitud'), pk=pk,
    )

    if movimiento.solicitud_id:
        messages.error(
            request,
            'No se puede eliminar un movimiento generado por una solicitud.',
        )
        return redirect('movimientos_list')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                producto = Producto.objects.select_for_update().get(pk=movimiento.producto_id)
                if movimiento.tipo == 'entrada':
                    if producto.stock_actual < movimiento.cantidad:
                        raise ValueError(
                            f'No se puede eliminar la entrada: el stock actual de '
                            f'{producto.nombre} ({producto.stock_actual}) es menor que '
                            f'la cantidad ingresada ({movimiento.cantidad}).'
                        )
                    producto.stock_actual -= movimiento.cantidad
                else:
                    producto.stock_actual += movimiento.cantidad
                producto.save(update_fields=['stock_actual'])
                movimiento.delete()
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(
                request,
                'Movimiento eliminado y stock ajustado correctamente.',
            )
        return redirect('movimientos_list')

    return render(request, 'admin/confirmar_eliminar.html', {
        'titulo': 'Eliminar movimiento de stock',
        'objeto': (
            f'{movimiento.get_tipo_display()} de {movimiento.cantidad} '
            f'x {movimiento.producto.nombre}'
        ),
        'detalle': 'El stock del producto se ajustará para revertir este movimiento.',
        'cancelar_url_name': 'movimientos_list',
    })


# Redirecciones de compatibilidad con las rutas antiguas de ingresos/salidas.

@login_required
def ingresos_list(request):
    return redirect('movimientos_list')


@login_required
def ingreso_registrar(request):
    return redirect('movimiento_crear')


@login_required
def salidas_list(request):
    return redirect('solicitudes_list')


@login_required
def salida_registrar(request):
    return redirect('solicitud_crear')


@admin_required
def salida_autorizar(request, pk):
    return redirect('solicitud_autorizar', pk=pk)


@login_required
def alertas(request):
    alertas = (
        Producto.objects.filter(stock_actual__lt=F('stock_minimo'))
        .select_related('categoria', 'proveedor')
        .order_by('nombre')
    )
    return render(request, 'admin/alertas.html', {'alertas': alertas})


@login_required
def stock(request):
    productos = Producto.objects.select_related('categoria', 'proveedor').order_by('nombre')
    return render(request, 'admin/stock.html', {'productos': productos})


@login_required
def reportes(request):
    try:
        reporte_id = int(request.GET.get('reporte', '1'))
    except (TypeError, ValueError):
        reporte_id = 1

    contexto = obtener_reporte(reporte_id, request.GET)
    contexto['reportes'] = REPORTES
    return render(request, 'admin/reportes.html', contexto)
