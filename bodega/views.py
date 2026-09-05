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
    return redirect('index')


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


# ========== USUARIOS (Admin) ==========

@admin_required
def usuarios_list(request):
    usuarios = data.get_usuarios()
    return render(request, 'admin/usuarios.html', {
        'usuarios': usuarios,
        'rol': request.session.get('rol'),
    })


@admin_required
def usuario_detail(request, pk):
    usuario = data.get_usuario_by_id(pk)
    if not usuario:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('usuarios_list')
    return render(request, 'admin/usuario_detail.html', {
        'usuario': usuario,
        'rol': request.session.get('rol'),
    })


@admin_required
def usuario_crear(request):
    if request.method == 'POST':
        # Simulación: en U1 solo mostramos el flujo. En U2 se guardará en BD.
        nombre = request.POST.get('nombre', '').strip()
        email = request.POST.get('email', '').strip()
        rol = request.POST.get('rol', 'Operador')
        if nombre and email:
            messages.success(request, f'Usuario "{nombre}" creado correctamente (simulación). En la Evaluación 2 se guardará en base de datos.')
            return redirect('usuarios_list')
        messages.error(request, 'Completa todos los campos obligatorios.')
    return render(request, 'admin/usuario_form.html', {
        'titulo': 'Crear nuevo usuario',
        'accion': 'crear',
        'rol': request.session.get('rol'),
    })


@admin_required
def usuario_editar(request, pk):
    usuario = data.get_usuario_by_id(pk)
    if not usuario:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('usuarios_list')

    if request.method == 'POST':
        nuevo_rol = request.POST.get('rol', usuario['rol'])
        nuevo_estado = request.POST.get('estado', usuario['estado'])
        messages.success(request, f'Usuario "{usuario["nombre"]}" actualizado: Rol={nuevo_rol}, Estado={nuevo_estado} (simulación).')
        return redirect('usuarios_list')

    return render(request, 'admin/usuario_form.html', {
        'titulo': 'Editar rol o estado',
        'accion': 'editar',
        'usuario': usuario,
        'rol': request.session.get('rol'),
    })


@admin_required
def usuario_eliminar(request, pk):
    usuario = data.get_usuario_by_id(pk)
    if not usuario:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('usuarios_list')

    if request.method == 'POST':
        messages.success(request, f'Usuario "{usuario["nombre"]}" eliminado (simulación). En la Evaluación 2 se eliminará de la base de datos.')
        return redirect('usuarios_list')

    return render(request, 'admin/usuario_eliminar.html', {
        'usuario': usuario,
        'rol': request.session.get('rol'),
    })


# ========== INGRESOS Y SALIDAS ==========

@login_required
def ingresos_list(request):
    ingresos = data.get_ingresos()
    return render(request, 'admin/ingresos.html', {
        'ingresos': ingresos,
        'rol': request.session.get('rol'),
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
        'rol': request.session.get('rol'),
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
