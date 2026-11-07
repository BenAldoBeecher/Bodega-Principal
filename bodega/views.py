from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, F, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from . import data_loader as data
from .forms import (
    CategoriaForm, ProductoForm, ProveedorForm, SucursalForm,
    UsuarioCrearForm, UsuarioEditarForm,
)
from .models import Categoria, MovimientoStock, Producto, Proveedor, Solicitud, Sucursal
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
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save()
            messages.success(request, f'Producto "{producto.nombre}" creado correctamente.')
            return redirect('productos_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = ProductoForm()

    return render(request, 'admin/producto_form.html', {
        'form': form,
        'titulo': 'Nuevo producto',
        'cancelar_url_name': 'productos_list',
    })


@admin_required
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, f'Producto "{producto.nombre}" actualizado correctamente.')
            return redirect('producto_detail', pk=producto.pk)
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'admin/producto_form.html', {
        'form': form,
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
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f'Categoría "{categoria.nombre}" creada correctamente.')
            return redirect('categorias_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = CategoriaForm()

    return render(request, 'admin/categoria_form.html', {
        'form': form,
        'titulo': 'Nueva categoría',
        'cancelar_url_name': 'categorias_list',
    })


@admin_required
def categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, f'Categoría "{categoria.nombre}" actualizada correctamente.')
            return redirect('categorias_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = CategoriaForm(instance=categoria)

    return render(request, 'admin/categoria_form.html', {
        'form': form,
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
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, f'Proveedor "{proveedor.razon_social}" creado correctamente.')
            return redirect('proveedores_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = ProveedorForm()

    return render(request, 'admin/proveedor_form.html', {
        'form': form,
        'titulo': 'Nuevo proveedor',
        'cancelar_url_name': 'proveedores_list',
    })


@admin_required
def proveedor_editar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Proveedor "{proveedor.razon_social}" actualizado correctamente.')
            return redirect('proveedores_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = ProveedorForm(instance=proveedor)

    return render(request, 'admin/proveedor_form.html', {
        'form': form,
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
    if request.method == 'POST':
        form = SucursalForm(request.POST)
        if form.is_valid():
            sucursal = form.save()
            messages.success(request, f'Sucursal "{sucursal.nombre}" creada correctamente.')
            return redirect('sucursales_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = SucursalForm()

    return render(request, 'admin/sucursal_form.html', {
        'form': form,
        'titulo': 'Nueva sucursal',
        'cancelar_url_name': 'sucursales_list',
    })


@admin_required
def sucursal_editar(request, pk):
    sucursal = get_object_or_404(Sucursal, pk=pk)
    if request.method == 'POST':
        form = SucursalForm(request.POST, instance=sucursal)
        if form.is_valid():
            form.save()
            messages.success(request, f'Sucursal "{sucursal.nombre}" actualizada correctamente.')
            return redirect('sucursales_list')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = SucursalForm(instance=sucursal)

    return render(request, 'admin/sucursal_form.html', {
        'form': form,
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
