from django.shortcuts import render, redirect
from django.contrib import messages
from functools import wraps
from . import data_loader as data


def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('usuario_id'):
            messages.warning(request, 'Debes iniciar sesión para continuar.')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('usuario_id'):
            messages.warning(request, 'Debes iniciar sesión para continuar.')
            return redirect('login')
        if request.session.get('rol') != 'Administrador':
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def index(request):
    if request.session.get('usuario_id'):
        return redirect('dashboard')
    return render(request, 'public/index.html')


def login_view(request):
    if request.session.get('usuario_id'):
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        usuario = data.get_usuario_by_email(email)

        if usuario and usuario['password'] == password and usuario['estado'] == 'activo':
            request.session['usuario_id'] = usuario['id']
            request.session['nombre'] = usuario['nombre']
            request.session['email'] = usuario['email']
            request.session['rol'] = usuario['rol']
            messages.success(request, f'Bienvenido, {usuario["nombre"]}')
            return redirect('dashboard')
        else:
            messages.error(request, 'Credenciales incorrectas o usuario inactivo.')

    return render(request, 'public/login.html')


def logout_view(request):
    request.session.flush()
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('login')


@login_required
def dashboard(request):
    stats = data.get_stats()
    alertas = data.get_productos_alerta()
    context = {
        'stats': stats,
        'alertas': alertas[:5],
        'rol': request.session.get('rol'),
        'nombre': request.session.get('nombre'),
    }
    return render(request, 'admin/dashboard.html', context)


@login_required
def productos_list(request):
    productos = data.get_productos()
    return render(request, 'admin/productos.html', {
        'productos': productos,
        'rol': request.session.get('rol'),
    })


@login_required
def producto_detail(request, pk):
    producto = data.get_producto_by_id(pk)
    if not producto:
        messages.error(request, 'Producto no encontrado.')
        return redirect('productos_list')
    return render(request, 'admin/producto_detail.html', {
        'producto': producto,
        'rol': request.session.get('rol'),
    })


@login_required
def categorias_list(request):
    categorias = data.get_categorias()
    return render(request, 'admin/categorias.html', {
        'categorias': categorias,
        'rol': request.session.get('rol'),
    })


@admin_required
def usuarios_list(request):
    usuarios = data.get_usuarios()
    return render(request, 'admin/usuarios.html', {
        'usuarios': usuarios,
        'rol': request.session.get('rol'),
    })


@login_required
def ingresos_list(request):
    ingresos = data.get_ingresos()
    return render(request, 'admin/ingresos.html', {
        'ingresos': ingresos,
        'rol': request.session.get('rol'),
    })


@login_required
def salidas_list(request):
    salidas = data.get_salidas()
    return render(request, 'admin/salidas.html', {
        'salidas': salidas,
        'rol': request.session.get('rol'),
    })


@login_required
def alertas(request):
    alertas = data.get_productos_alerta()
    return render(request, 'admin/alertas.html', {
        'alertas': alertas,
        'rol': request.session.get('rol'),
    })


@login_required
def stock(request):
    productos = data.get_productos()
    return render(request, 'admin/stock.html', {
        'productos': productos,
        'rol': request.session.get('rol'),
    })
