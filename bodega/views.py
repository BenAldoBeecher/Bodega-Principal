from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import (
    CategoriaForm, DetalleSolicitudForm, MovimientoStockEditarForm,
    MovimientoStockForm, ProductoForm, ProveedorForm, SolicitudForm,
    SucursalForm, UsuarioCrearForm, UsuarioEditarForm,
)
from .models import (
    Categoria, DetalleSolicitud, MovimientoStock, Producto, Proveedor,
    Solicitud, Sucursal,
)
from .permisos import admin_required, es_admin
from .reportes import REPORTES, obtener_reporte


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


# ========== SOLICITUDES, DETALLES Y MOVIMIENTOS DE STOCK ==========

def _contexto_solicitud_detail(solicitud, detalle_form=None):
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
    if detalle_form is None and solicitud.estado == 'pendiente':
        detalle_form = DetalleSolicitudForm()
    return {
        'solicitud': solicitud,
        'detalles': detalles,
        'movimientos': movimientos,
        'totales': totales,
        'detalle_form': detalle_form,
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
    if request.method == 'POST':
        form = SolicitudForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.estado = 'pendiente'
            solicitud.save()
            messages.success(
                request,
                f'Solicitud #{solicitud.pk} creada. Agrega los productos solicitados.',
            )
            return redirect('solicitud_detail', pk=solicitud.pk)
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = SolicitudForm(initial={'fecha': timezone.now()})

    return render(request, 'admin/solicitud_form.html', {
        'form': form,
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

    if request.method == 'POST':
        form = SolicitudForm(request.POST, instance=solicitud)
        if form.is_valid():
            form.save()
            messages.success(request, f'Solicitud #{solicitud.pk} actualizada correctamente.')
            return redirect('solicitud_detail', pk=solicitud.pk)
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = SolicitudForm(instance=solicitud)

    return render(request, 'admin/solicitud_form.html', {
        'form': form,
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
def detalle_crear(request, solicitud_pk):
    solicitud = get_object_or_404(Solicitud.objects.select_related('sucursal'), pk=solicitud_pk)
    if solicitud.estado != 'pendiente':
        messages.error(request, 'Solo se pueden agregar productos a solicitudes pendientes.')
        return redirect('solicitud_detail', pk=solicitud.pk)

    if request.method != 'POST':
        return redirect('solicitud_detail', pk=solicitud.pk)

    form = DetalleSolicitudForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Revisa los datos del producto y la cantidad.')
        return render(
            request,
            'admin/solicitud_detail.html',
            _contexto_solicitud_detail(solicitud, form),
        )

    producto = form.cleaned_data['producto']
    if solicitud.detallesolicitud_set.filter(producto=producto).exists():
        messages.error(
            request,
            'Ese producto ya está en la solicitud. Edita la cantidad del detalle existente.',
        )
        return render(
            request,
            'admin/solicitud_detail.html',
            _contexto_solicitud_detail(solicitud, form),
        )

    detalle = form.save(commit=False)
    detalle.solicitud = solicitud
    detalle.save()
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

    if request.method == 'POST':
        form = DetalleSolicitudForm(request.POST, instance=detalle)
        if form.is_valid():
            producto = form.cleaned_data['producto']
            duplicado = (
                solicitud.detallesolicitud_set
                .filter(producto=producto)
                .exclude(pk=detalle.pk)
                .exists()
            )
            if duplicado:
                messages.error(request, 'Ese producto ya está en la solicitud.')
            else:
                form.save()
                messages.success(request, 'Detalle actualizado correctamente.')
                return redirect('solicitud_detail', pk=solicitud.pk)
        else:
            messages.error(request, 'Revisa los datos del detalle.')
    else:
        form = DetalleSolicitudForm(instance=detalle)

    return render(request, 'admin/detalle_form.html', {
        'form': form,
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
def solicitud_despachar(request, pk):
    solicitud = get_object_or_404(Solicitud.objects.select_related('sucursal'), pk=pk)
    if request.method != 'POST':
        return redirect('solicitud_detail', pk=solicitud.pk)

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

    if request.method == 'POST':
        tipo_solicitado = request.POST.get('tipo')
        if not usuario_admin and tipo_solicitado != 'entrada':
            messages.error(
                request,
                'Solo el administrador puede registrar salidas directas. '
                'Para enviar productos a una sucursal crea una solicitud de pedido.',
            )
            form = MovimientoStockForm(
                initial={'fecha': timezone.now(), 'tipo': 'entrada'},
            )
        else:
            form = MovimientoStockForm(request.POST)
            if form.is_valid():
                tipo = form.cleaned_data['tipo']
                cantidad = form.cleaned_data['cantidad']
                try:
                    with transaction.atomic():
                        producto = Producto.objects.select_for_update().get(
                            pk=form.cleaned_data['producto'].pk,
                        )
                        if tipo == 'salida' and producto.stock_actual < cantidad:
                            raise ValueError(
                                f'Stock insuficiente para {producto.nombre}: '
                                f'disponible {producto.stock_actual}, solicitado {cantidad}.'
                            )

                        movimiento = form.save(commit=False)
                        movimiento.producto = producto
                        movimiento.save()

                        if tipo == 'entrada':
                            producto.stock_actual += cantidad
                        else:
                            producto.stock_actual -= cantidad
                        producto.save(update_fields=['stock_actual'])
                except ValueError as error:
                    messages.error(request, str(error))
                else:
                    messages.success(
                        request,
                        f'Movimiento de {movimiento.get_tipo_display().lower()} registrado correctamente.',
                    )
                    return redirect('movimientos_list')
            else:
                messages.error(request, 'Revisa los datos del movimiento.')
    else:
        form = MovimientoStockForm(initial={'fecha': timezone.now(), 'tipo': tipo_inicial})

    if not usuario_admin:
        form.fields['tipo'].choices = [('entrada', 'Entrada')]
        form.fields['tipo'].initial = 'entrada'

    return render(request, 'admin/movimiento_form.html', {
        'form': form,
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

    if request.method == 'POST':
        form = MovimientoStockEditarForm(request.POST, instance=movimiento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Movimiento actualizado correctamente.')
            return redirect('movimientos_list')
        messages.error(request, 'Revisa los datos del movimiento.')
    else:
        form = MovimientoStockEditarForm(instance=movimiento)

    return render(request, 'admin/movimiento_editar.html', {
        'form': form,
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
