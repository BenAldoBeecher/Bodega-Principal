from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from . import data_loader as data
from .forms import UsuarioCrearForm, UsuarioEditarForm
from .permisos import admin_required, es_admin


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


def logout_view(request):
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('index')


@login_required
def dashboard(request):
    stats = data.get_stats()
    alertas = data.get_productos_alerta()
    context = {
        'stats': stats,
        'alertas': alertas[:5],
    }
    return render(request, 'admin/dashboard.html', context)


@login_required
def productos_list(request):
    productos = data.get_productos()
    return render(request, 'admin/productos.html', {
        'productos': productos,
    })


@login_required
def producto_detail(request, pk):
    producto = data.get_producto_by_id(pk)
    if not producto:
        messages.error(request, 'Producto no encontrado.')
        return redirect('productos_list')
    return render(request, 'admin/producto_detail.html', {
        'producto': producto,
    })


@login_required
def categorias_list(request):
    categorias = data.get_categorias()
    return render(request, 'admin/categorias.html', {
        'categorias': categorias,
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
    if request.method == 'POST':
        form = UsuarioCrearForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            messages.success(request, f'Usuario "{usuario.get_full_name() or usuario.username}" creado correctamente.')
            return redirect('usuarios_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = UsuarioCrearForm()

    return render(request, 'admin/usuario_form.html', {
        'titulo': 'Crear nuevo usuario',
        'accion': 'crear',
        'form': form,
    })


@admin_required
def usuario_editar(request, pk):
    usuario = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UsuarioEditarForm(request.POST, instance=usuario)
        if form.is_valid():
            if usuario == request.user and form.cleaned_data['rol'] != 'Administrador':
                messages.error(request, 'No puedes quitarte a ti mismo el rol de Administrador.')
            elif usuario == request.user and not form.cleaned_data['is_active']:
                messages.error(request, 'No puedes desactivar tu propio usuario.')
            else:
                form.save()
                messages.success(request, f'Usuario "{usuario.get_full_name() or usuario.username}" actualizado correctamente.')
                return redirect('usuarios_list')
        else:
            messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = UsuarioEditarForm(instance=usuario)

    return render(request, 'admin/usuario_form.html', {
        'titulo': 'Editar usuario',
        'accion': 'editar',
        'usuario': usuario,
        'form': form,
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


# ========== INGRESOS Y SALIDAS ==========

@login_required
def ingresos_list(request):
    ingresos = data.get_ingresos()
    return render(request, 'admin/ingresos.html', {
        'ingresos': ingresos,
    })


@login_required
def ingreso_registrar(request):
    productos = data.get_productos()
    proveedores = data.get_proveedores()

    if request.method == 'POST':
        proveedor = request.POST.get('proveedor')
        observacion = request.POST.get('observacion', '')
        messages.success(request, 'Ingreso de productos registrado correctamente (simulación). En la Evaluación 2 se guardará y actualizará el stock automáticamente.')
        return redirect('ingresos_list')

    return render(request, 'admin/ingreso_form.html', {
        'productos': productos,
        'proveedores': proveedores,
    })


@login_required
def salidas_list(request):
    salidas = data.get_salidas()
    return render(request, 'admin/salidas.html', {
        'salidas': salidas,
    })


@login_required
def salida_registrar(request):
    """Solo operadores registran salidas. Quedan en estado pendiente para autorización del admin."""
    productos = data.get_productos()

    if request.method == 'POST':
        destino = request.POST.get('destino', '')
        observacion = request.POST.get('observacion', '')
        messages.success(request, 'Solicitud de salida/envío registrada. Queda pendiente de autorización por el Administrador (simulación).')
        return redirect('salidas_list')

    return render(request, 'admin/salida_form.html', {
        'productos': productos,
    })


@admin_required
def salida_autorizar(request, pk):
    """Administrador revisa y autoriza (o rechaza) una solicitud de pedido."""
    salidas = data.get_salidas()
    salida = next((s for s in salidas if s['id'] == pk), None)
    if not salida:
        messages.error(request, 'Solicitud no encontrada.')
        return redirect('salidas_list')

    if request.method == 'POST':
        accion = request.POST.get('accion', 'autorizar')
        if accion == 'autorizar':
            messages.success(request, f'Solicitud #{pk} autorizada. El despacho puede proceder (simulación).')
        else:
            messages.warning(request, f'Solicitud #{pk} rechazada (simulación).')
        return redirect('salidas_list')

    return render(request, 'admin/salida_autorizar.html', {
        'salida': salida,
    })


@login_required
def alertas(request):
    alertas = data.get_productos_alerta()
    return render(request, 'admin/alertas.html', {
        'alertas': alertas,
    })


@login_required
def stock(request):
    productos = data.get_productos()
    return render(request, 'admin/stock.html', {
        'productos': productos,
    })
