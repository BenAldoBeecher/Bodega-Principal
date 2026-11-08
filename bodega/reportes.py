from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import (
    Categoria, DetalleSolicitud, MovimientoStock, Producto, Proveedor,
    Solicitud, Sucursal,
)

REPORTES = [
    {
        'id': 1,
        'nivel': 'Básico',
        'titulo': 'Todos los productos',
        'pregunta': '¿Cuáles son todos los productos registrados en la bodega?',
    },
    {
        'id': 2,
        'nivel': 'Básico',
        'titulo': 'Productos por categoría',
        'pregunta': '¿Qué productos pertenecen a una categoría seleccionada?',
    },
    {
        'id': 3,
        'nivel': 'Básico',
        'titulo': 'Stock bajo el mínimo',
        'pregunta': '¿Cuáles son los productos cuyo stock está por debajo del mínimo establecido?',
    },
    {
        'id': 4,
        'nivel': 'Básico',
        'titulo': 'Top 10 productos más caros',
        'pregunta': '¿Cuáles son los 10 productos con mayor precio?',
    },
    {
        'id': 5,
        'nivel': 'Básico',
        'titulo': 'Productos por categoría (conteo)',
        'pregunta': '¿Cuántos productos existen registrados por categoría?',
    },
    {
        'id': 6,
        'nivel': 'Intermedio',
        'titulo': 'Productos por proveedor',
        'pregunta': '¿Qué productos suministra un proveedor seleccionado?',
    },
    {
        'id': 7,
        'nivel': 'Intermedio',
        'titulo': 'Solicitudes por sucursal',
        'pregunta': '¿Cuáles son las solicitudes realizadas por una sucursal específica?',
    },
    {
        'id': 8,
        'nivel': 'Intermedio',
        'titulo': 'Detalle de una solicitud',
        'pregunta': '¿Qué productos y cantidades contiene una solicitud seleccionada?',
    },
    {
        'id': 9,
        'nivel': 'Intermedio',
        'titulo': 'Solicitudes por estado',
        'pregunta': '¿Cuántas solicitudes se encuentran pendientes, aprobadas, rechazadas o despachadas?',
    },
    {
        'id': 10,
        'nivel': 'Intermedio',
        'titulo': 'Solicitudes por rango de fechas',
        'pregunta': '¿Cuáles son las solicitudes realizadas durante un rango de fechas?',
    },
    {
        'id': 11,
        'nivel': 'Intermedio',
        'titulo': 'Top 5 sucursales por unidades solicitadas',
        'pregunta': '¿Cuáles son las cinco sucursales que han solicitado la mayor cantidad de productos?',
    },
    {
        'id': 12,
        'nivel': 'Intermedio',
        'titulo': 'Productos más solicitados',
        'pregunta': '¿Cuáles son los productos más solicitados por las sucursales?',
    },
    {
        'id': 13,
        'nivel': 'Avanzado',
        'titulo': 'Proveedor con más productos diferentes',
        'pregunta': '¿Qué proveedor suministra la mayor cantidad de productos diferentes?',
    },
    {
        'id': 14,
        'nivel': 'Avanzado',
        'titulo': 'Valor total del inventario',
        'pregunta': '¿Cuál es el valor total del inventario, calculado según precio y stock de cada producto?',
    },
    {
        'id': 15,
        'nivel': 'Avanzado',
        'titulo': 'Productos nunca solicitados',
        'pregunta': '¿Qué productos no han sido solicitados por ninguna sucursal?',
    },
    {
        'id': 16,
        'nivel': 'Avanzado',
        'titulo': 'Salidas del último mes',
        'pregunta': '¿Cuántas unidades de cada producto han salido de la bodega durante el último mes?',
    },
    {
        'id': 17,
        'nivel': 'Avanzado',
        'titulo': 'Sucursales con solicitudes pendientes',
        'pregunta': '¿Qué sucursales tienen solicitudes pendientes de atención?',
    },
    {
        'id': 18,
        'nivel': 'Análisis',
        'titulo': 'Categoría con mayor valor de inventario',
        'pregunta': '¿Qué categoría concentra el mayor valor económico del inventario?',
    },
    {
        'id': 19,
        'nivel': 'Análisis',
        'titulo': 'Promedio de productos solicitados',
        'pregunta': '¿Cuál es el promedio de productos solicitados por solicitud, considerando las cantidades de cada detalle?',
    },
    {
        'id': 20,
        'nivel': 'Análisis',
        'titulo': 'Top 5 productos por período',
        'pregunta': '¿Cuáles son los cinco productos con mayor cantidad de unidades solicitadas durante un período seleccionado?',
    },
]

PERIODOS = {
    '7': 'Últimos 7 días',
    '30': 'Últimos 30 días',
    '90': 'Últimos 90 días',
}


def _moneda(valor):
    if valor is None:
        return '$0'
    return '$' + f'{valor:,.0f}'.replace(',', '.')


def _numero(valor):
    if valor is None:
        return '0'
    return f'{valor:,.0f}'.replace(',', '.')


def _fecha(valor):
    return valor.strftime('%d-%m-%Y %H:%M') if valor else '-'


def _dato(valor):
    return '-' if valor is None or valor == '' else valor


def _rango_fechas(params):
    hoy = timezone.now().date()
    desde = parse_date(params.get('desde', '')) or (hoy - timedelta(days=30))
    hasta = parse_date(params.get('hasta', '')) or hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def _seleccionar_id(params, clave, opciones):
    valor = params.get(clave, '')
    if valor.isdigit():
        return int(valor)
    if opciones:
        return opciones[0].id
    return None


def obtener_reporte(reporte_id, params):
    reporte = next((r for r in REPORTES if r['id'] == reporte_id), REPORTES[0])
    categorias = list(Categoria.objects.order_by('nombre'))
    proveedores = list(Proveedor.objects.order_by('razon_social'))
    sucursales = list(Sucursal.objects.order_by('nombre'))
    solicitudes = list(Solicitud.objects.select_related('sucursal').order_by('-fecha'))

    desde, hasta = _rango_fechas(params)
    seleccion = {
        'categoria': None,
        'proveedor': None,
        'sucursal': None,
        'solicitud': None,
        'desde': desde.isoformat(),
        'hasta': hasta.isoformat(),
    }

    filtros = None
    columnas = []
    filas = []
    resumen = []
    nota = ''
    consulta = ''

    if reporte['id'] == 1:
        productos = Producto.objects.select_related('categoria', 'proveedor').order_by('nombre')
        columnas = ['SKU', 'Producto', 'Categoría', 'Proveedor', 'Precio', 'Stock actual', 'Stock mínimo', 'Estado']
        filas = [
            [
                p.sku, p.nombre, p.categoria.nombre, p.proveedor.razon_social,
                _moneda(p.precio), p.stock_actual, p.stock_minimo,
                'Activo' if p.activo else 'Inactivo',
            ]
            for p in productos
        ]
        consulta = "Producto.objects.select_related('categoria', 'proveedor').order_by('nombre')"

    elif reporte['id'] == 2:
        filtros = 'categoria'
        seleccion['categoria'] = _seleccionar_id(params, 'categoria', categorias)
        if seleccion['categoria']:
            productos = (
                Producto.objects.filter(categoria_id=seleccion['categoria'])
                .select_related('categoria', 'proveedor')
                .order_by('nombre')
            )
            columnas = ['SKU', 'Producto', 'Proveedor', 'Precio', 'Stock actual', 'Stock mínimo', 'Estado']
            filas = [
                [
                    p.sku, p.nombre, p.proveedor.razon_social, _moneda(p.precio),
                    p.stock_actual, p.stock_minimo, 'Activo' if p.activo else 'Inactivo',
                ]
                for p in productos
            ]
            categoria = next((c for c in categorias if c.id == seleccion['categoria']), None)
            nota = f'Categoría: {categoria.nombre}' if categoria else ''
        else:
            nota = 'No hay categorías registradas.'
        consulta = (
            "Producto.objects.filter(categoria_id=categoria_id)"
            ".select_related('categoria', 'proveedor').order_by('nombre')"
        )

    elif reporte['id'] == 3:
        productos = (
            Producto.objects.filter(stock_actual__lt=F('stock_minimo'))
            .select_related('categoria', 'proveedor')
            .order_by('stock_actual')
        )
        columnas = ['SKU', 'Producto', 'Categoría', 'Stock actual', 'Stock mínimo', 'Faltante', 'Proveedor']
        filas = [
            [
                p.sku, p.nombre, p.categoria.nombre, p.stock_actual,
                p.stock_minimo, p.stock_minimo - p.stock_actual, p.proveedor.razon_social,
            ]
            for p in productos
        ]
        consulta = (
            "Producto.objects.filter(stock_actual__lt=F('stock_minimo'))"
            ".select_related('categoria', 'proveedor').order_by('stock_actual')"
        )

    elif reporte['id'] == 4:
        productos = Producto.objects.select_related('categoria').order_by('-precio')[:10]
        columnas = ['SKU', 'Producto', 'Precio', 'Categoría', 'Stock actual']
        filas = [[p.sku, p.nombre, _moneda(p.precio), p.categoria.nombre, p.stock_actual] for p in productos]
        consulta = "Producto.objects.select_related('categoria').order_by('-precio')[:10]"

    elif reporte['id'] == 5:
        categorias_qs = (
            Categoria.objects.annotate(total_productos=Count('producto'))
            .order_by('-total_productos', 'nombre')
        )
        columnas = ['Categoría', 'Total de productos']
        filas = [[c.nombre, c.total_productos] for c in categorias_qs]
        consulta = (
            "Categoria.objects.annotate(total_productos=Count('producto'))"
            ".order_by('-total_productos', 'nombre')"
        )

    elif reporte['id'] == 6:
        filtros = 'proveedor'
        seleccion['proveedor'] = _seleccionar_id(params, 'proveedor', proveedores)
        if seleccion['proveedor']:
            productos = (
                Producto.objects.filter(proveedor_id=seleccion['proveedor'])
                .select_related('categoria')
                .order_by('nombre')
            )
            columnas = ['SKU', 'Producto', 'Categoría', 'Precio', 'Stock actual']
            filas = [
                [p.sku, p.nombre, p.categoria.nombre, _moneda(p.precio), p.stock_actual]
                for p in productos
            ]
            proveedor = next((p for p in proveedores if p.id == seleccion['proveedor']), None)
            nota = f'Proveedor: {proveedor.razon_social}' if proveedor else ''
        else:
            nota = 'No hay proveedores registrados.'
        consulta = (
            "Producto.objects.filter(proveedor_id=proveedor_id)"
            ".select_related('categoria').order_by('nombre')"
        )

    elif reporte['id'] == 7:
        filtros = 'sucursal'
        seleccion['sucursal'] = _seleccionar_id(params, 'sucursal', sucursales)
        if seleccion['sucursal']:
            solicitudes_qs = (
                Solicitud.objects.filter(sucursal_id=seleccion['sucursal'])
                .select_related('sucursal')
                .annotate(
                    total_items=Count('detallesolicitud'),
                    total_unidades=Sum('detallesolicitud__cantidad_solicitada'),
                )
                .order_by('-fecha')
            )
            columnas = ['N°', 'Fecha', 'Sucursal', 'Estado', 'Productos', 'Unidades']
            filas = [
                [
                    s.id, _fecha(s.fecha), s.sucursal.nombre, s.get_estado_display(),
                    s.total_items, s.total_unidades or 0,
                ]
                for s in solicitudes_qs
            ]
            sucursal = next((s for s in sucursales if s.id == seleccion['sucursal']), None)
            nota = f'Sucursal: {sucursal.nombre}' if sucursal else ''
        else:
            nota = 'No hay sucursales registradas.'
        consulta = (
            "Solicitud.objects.filter(sucursal_id=sucursal_id).select_related('sucursal')"
            ".annotate(total_items=Count('detallesolicitud'), "
            "total_unidades=Sum('detallesolicitud__cantidad_solicitada')).order_by('-fecha')"
        )

    elif reporte['id'] == 8:
        filtros = 'solicitud'
        seleccion['solicitud'] = _seleccionar_id(params, 'solicitud', solicitudes)
        if seleccion['solicitud']:
            detalles = (
                DetalleSolicitud.objects.filter(solicitud_id=seleccion['solicitud'])
                .select_related('producto__categoria', 'solicitud__sucursal')
                .order_by('producto__nombre')
            )
            columnas = [
                'Solicitud', 'Sucursal', 'SKU', 'Producto', 'Categoría',
                'Cantidad solicitada', 'Cantidad aprobada', 'Cantidad despachada',
            ]
            filas = [
                [
                    f'#{d.solicitud.id}', d.solicitud.sucursal.nombre, d.producto.sku,
                    d.producto.nombre, d.producto.categoria.nombre,
                    d.cantidad_solicitada, _dato(d.cantidad_aprobada),
                    _dato(d.cantidad_despachada),
                ]
                for d in detalles
            ]
            solicitud = next((s for s in solicitudes if s.id == seleccion['solicitud']), None)
            nota = f'Solicitud #{solicitud.id} - {solicitud.sucursal.nombre}' if solicitud else ''
        else:
            nota = 'No hay solicitudes registradas.'
        consulta = (
            "DetalleSolicitud.objects.filter(solicitud_id=solicitud_id)"
            ".select_related('producto__categoria', 'solicitud__sucursal')"
            ".order_by('producto__nombre')"
        )

    elif reporte['id'] == 9:
        conteos = {
            row['estado']: row['total']
            for row in Solicitud.objects.values('estado').annotate(total=Count('id'))
        }
        columnas = ['Estado', 'Cantidad de solicitudes']
        filas = [[etiqueta, conteos.get(valor, 0)] for valor, etiqueta in Solicitud.ESTADO_CHOICES]
        consulta = "Solicitud.objects.values('estado').annotate(total=Count('id'))"

    elif reporte['id'] == 10:
        filtros = 'fechas'
        solicitudes_qs = (
            Solicitud.objects.filter(fecha__date__gte=desde, fecha__date__lte=hasta)
            .select_related('sucursal')
            .annotate(
                total_items=Count('detallesolicitud'),
                total_unidades=Sum('detallesolicitud__cantidad_solicitada'),
            )
            .order_by('-fecha')
        )
        columnas = ['N°', 'Fecha', 'Sucursal', 'Estado', 'Productos', 'Unidades']
        filas = [
            [
                s.id, _fecha(s.fecha), s.sucursal.nombre, s.get_estado_display(),
                s.total_items, s.total_unidades or 0,
            ]
            for s in solicitudes_qs
        ]
        nota = f'Rango consultado: {desde.strftime("%d-%m-%Y")} al {hasta.strftime("%d-%m-%Y")}'
        consulta = (
            "Solicitud.objects.filter(fecha__date__gte=desde, fecha__date__lte=hasta)"
            ".select_related('sucursal').annotate(total_items=Count('detallesolicitud'), "
            "total_unidades=Sum('detallesolicitud__cantidad_solicitada')).order_by('-fecha')"
        )

    elif reporte['id'] == 11:
        sucursales_qs = (
            Sucursal.objects.annotate(
                total_unidades=Sum('solicitud__detallesolicitud__cantidad_solicitada'),
                total_solicitudes=Count('solicitud', distinct=True),
            )
            .filter(total_unidades__gt=0)
            .order_by('-total_unidades')[:5]
        )
        columnas = ['Sucursal', 'Solicitudes', 'Unidades solicitadas']
        filas = [[s.nombre, s.total_solicitudes, s.total_unidades] for s in sucursales_qs]
        consulta = (
            "Sucursal.objects.annotate("
            "total_unidades=Sum('solicitud__detallesolicitud__cantidad_solicitada'), "
            "total_solicitudes=Count('solicitud', distinct=True))"
            ".filter(total_unidades__gt=0).order_by('-total_unidades')[:5]"
        )

    elif reporte['id'] == 12:
        productos_qs = (
            Producto.objects.annotate(total_solicitado=Sum('detallesolicitud__cantidad_solicitada'))
            .filter(total_solicitado__gt=0)
            .select_related('categoria')
            .order_by('-total_solicitado')[:10]
        )
        columnas = ['SKU', 'Producto', 'Categoría', 'Unidades solicitadas']
        filas = [[p.sku, p.nombre, p.categoria.nombre, p.total_solicitado] for p in productos_qs]
        consulta = (
            "Producto.objects.annotate(total_solicitado=Sum('detallesolicitud__cantidad_solicitada'))"
            ".filter(total_solicitado__gt=0).order_by('-total_solicitado')[:10]"
        )

    elif reporte['id'] == 13:
        proveedores_qs = list(
            Proveedor.objects.annotate(total_productos=Count('producto', distinct=True))
            .order_by('-total_productos', 'razon_social')
        )
        columnas = ['Proveedor', 'RUT', 'Productos diferentes']
        filas = [[p.razon_social, _dato(p.rut), p.total_productos] for p in proveedores_qs]
        if proveedores_qs:
            resumen = [
                {'etiqueta': 'Proveedor con más productos', 'valor': proveedores_qs[0].razon_social},
                {'etiqueta': 'Cantidad de productos diferentes', 'valor': proveedores_qs[0].total_productos},
            ]
        consulta = (
            "Proveedor.objects.annotate(total_productos=Count('producto', distinct=True))"
            ".order_by('-total_productos', 'razon_social')"
        )

    elif reporte['id'] == 14:
        valor_expr = ExpressionWrapper(
            F('precio') * F('stock_actual'),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        total = Producto.objects.aggregate(total=Sum(valor_expr))['total'] or Decimal('0')
        productos_valor = (
            Producto.objects.annotate(valor=valor_expr)
            .select_related('categoria')
            .order_by('-valor')[:10]
        )
        columnas = ['SKU', 'Producto', 'Categoría', 'Precio', 'Stock', 'Valor']
        filas = [
            [
                p.sku, p.nombre, p.categoria.nombre, _moneda(p.precio),
                p.stock_actual, _moneda(p.valor),
            ]
            for p in productos_valor
        ]
        resumen = [{'etiqueta': 'Valor total del inventario', 'valor': _moneda(total)}]
        consulta = "Producto.objects.aggregate(total=Sum(F('precio') * F('stock_actual')))"

    elif reporte['id'] == 15:
        productos = (
            Producto.objects.filter(detallesolicitud__isnull=True)
            .select_related('categoria', 'proveedor')
            .order_by('nombre')
        )
        columnas = ['SKU', 'Producto', 'Categoría', 'Proveedor', 'Stock actual', 'Precio']
        filas = [
            [
                p.sku, p.nombre, p.categoria.nombre, p.proveedor.razon_social,
                p.stock_actual, _moneda(p.precio),
            ]
            for p in productos
        ]
        consulta = (
            "Producto.objects.filter(detallesolicitud__isnull=True)"
            ".select_related('categoria', 'proveedor').order_by('nombre')"
        )

    elif reporte['id'] == 16:
        desde_mes = timezone.now() - timedelta(days=30)
        salidas = (
            MovimientoStock.objects.filter(tipo='salida', fecha__gte=desde_mes)
            .values('producto__sku', 'producto__nombre')
            .annotate(total=Sum('cantidad'))
            .order_by('-total')
        )
        columnas = ['SKU', 'Producto', 'Unidades salidas']
        filas = [[row['producto__sku'], row['producto__nombre'], row['total']] for row in salidas]
        nota = f'Últimos 30 días: desde {desde_mes.strftime("%d-%m-%Y %H:%M")}'
        consulta = (
            "MovimientoStock.objects.filter(tipo='salida', fecha__gte=timezone.now() - timedelta(days=30))"
            ".values('producto__sku', 'producto__nombre').annotate(total=Sum('cantidad')).order_by('-total')"
        )

    elif reporte['id'] == 17:
        sucursales_qs = (
            Sucursal.objects.annotate(
                total_pendientes=Count('solicitud', filter=Q(solicitud__estado='pendiente')),
            )
            .filter(total_pendientes__gt=0)
            .order_by('-total_pendientes', 'nombre')
        )
        columnas = ['Sucursal', 'Código', 'Solicitudes pendientes']
        filas = [[s.nombre, s.codigo, s.total_pendientes] for s in sucursales_qs]
        consulta = (
            "Sucursal.objects.annotate(total_pendientes=Count('solicitud', "
            "filter=Q(solicitud__estado='pendiente'))).filter(total_pendientes__gt=0)"
            ".order_by('-total_pendientes', 'nombre')"
        )

    elif reporte['id'] == 18:
        valor_expr = ExpressionWrapper(
            F('producto__precio') * F('producto__stock_actual'),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
        categorias_qs = list(
            Categoria.objects.annotate(valor=Sum(valor_expr)).order_by('-valor')
        )
        columnas = ['Categoría', 'Valor económico del inventario']
        filas = [[c.nombre, _moneda(c.valor or 0)] for c in categorias_qs]
        if categorias_qs:
            resumen = [
                {'etiqueta': 'Categoría con mayor valor', 'valor': categorias_qs[0].nombre},
                {'etiqueta': 'Valor económico', 'valor': _moneda(categorias_qs[0].valor or 0)},
            ]
        consulta = (
            "Categoria.objects.annotate(valor=Sum(F('producto__precio') * "
            "F('producto__stock_actual'))).order_by('-valor')"
        )

    elif reporte['id'] == 19:
        solicitudes_qs = (
            Solicitud.objects.annotate(total_unidades=Sum('detallesolicitud__cantidad_solicitada'))
            .select_related('sucursal')
            .order_by('-fecha')
        )
        totales = [s.total_unidades or 0 for s in solicitudes_qs]
        promedio = sum(totales) / len(totales) if totales else 0
        columnas = ['N°', 'Fecha', 'Sucursal', 'Unidades solicitadas']
        filas = [[s.id, _fecha(s.fecha), s.sucursal.nombre, s.total_unidades or 0] for s in solicitudes_qs]
        resumen = [
            {'etiqueta': 'Promedio de unidades por solicitud', 'valor': f'{promedio:.2f}'},
            {'etiqueta': 'Solicitudes consideradas', 'valor': len(totales)},
        ]
        consulta = (
            "Solicitud.objects.annotate(total_unidades=Sum('detallesolicitud__cantidad_solicitada'))"
            ".select_related('sucursal').order_by('-fecha')"
        )

    elif reporte['id'] == 20:
        filtros = 'fechas'
        detalles = (
            DetalleSolicitud.objects.filter(
                solicitud__fecha__date__gte=desde,
                solicitud__fecha__date__lte=hasta,
            )
            .values('producto__sku', 'producto__nombre')
            .annotate(total=Sum('cantidad_solicitada'))
            .order_by('-total')[:5]
        )
        columnas = ['SKU', 'Producto', 'Unidades solicitadas']
        filas = [[row['producto__sku'], row['producto__nombre'], row['total']] for row in detalles]
        nota = f'Período consultado: {desde.strftime("%d-%m-%Y")} al {hasta.strftime("%d-%m-%Y")}'
        consulta = (
            "DetalleSolicitud.objects.filter(solicitud__fecha__date__gte=desde, "
            "solicitud__fecha__date__lte=hasta).values('producto__sku', 'producto__nombre')"
            ".annotate(total=Sum('cantidad_solicitada')).order_by('-total')[:5]"
        )

    return {
        'reporte': reporte,
        'columnas': columnas,
        'filas': filas,
        'resumen': resumen,
        'nota': nota,
        'consulta': consulta,
        'filtros': filtros,
        'seleccion': seleccion,
        'opciones': {
            'categorias': categorias,
            'proveedores': proveedores,
            'sucursales': sucursales,
            'solicitudes': solicitudes,
        },
    }


def obtener_resumen(params):
    """Datos del panel visual de reportes, calculados con el ORM."""
    periodo = params.get('periodo', '30')
    if periodo not in PERIODOS:
        periodo = '30'

    dias = int(periodo)
    fin = timezone.now()
    inicio = fin - timedelta(days=dias - 1)

    valor_expr = ExpressionWrapper(
        F('precio') * F('stock_actual'),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
    total_productos = Producto.objects.count()
    stock_critico = Producto.objects.filter(stock_actual__lt=F('stock_minimo')).count()
    solicitudes_pendientes = Solicitud.objects.filter(estado='pendiente').count()
    valor_inventario = (
        Producto.objects.aggregate(total=Sum(valor_expr))['total'] or Decimal('0')
    )

    categorias = list(
        Categoria.objects.annotate(total=Count('producto'))
        .filter(total__gt=0)
        .order_by('-total', 'nombre')
    )
    if len(categorias) > 5:
        principales = categorias[:4]
        otros_total = sum(categoria.total for categoria in categorias[4:])
        inventario_categoria = [
            {'label': categoria.nombre, 'total': categoria.total}
            for categoria in principales
        ]
        inventario_categoria.append({'label': 'Otros', 'total': otros_total})
    else:
        inventario_categoria = [
            {'label': categoria.nombre, 'total': categoria.total}
            for categoria in categorias
        ]

    conteos_estado = {
        fila['estado']: fila['total']
        for fila in Solicitud.objects.values('estado').annotate(total=Count('id'))
    }
    solicitudes_estado = [
        {
            'estado': clave,
            'label': etiqueta,
            'total': conteos_estado.get(clave, 0),
        }
        for clave, etiqueta in Solicitud.ESTADO_CHOICES
    ]

    movimientos_qs = (
        MovimientoStock.objects.filter(fecha__gte=inicio, fecha__lte=fin)
        .annotate(dia=TruncDate('fecha'))
        .values('dia', 'tipo')
        .annotate(total=Sum('cantidad'))
        .order_by('dia')
    )
    dias_rango = [
        inicio.date() + timedelta(days=indice)
        for indice in range((fin.date() - inicio.date()).days + 1)
    ]
    entradas = {dia: 0 for dia in dias_rango}
    salidas = {dia: 0 for dia in dias_rango}
    for fila in movimientos_qs:
        dia = fila['dia']
        if isinstance(dia, str):
            dia = parse_date(dia)
        if dia not in entradas:
            continue
        if fila['tipo'] == 'entrada':
            entradas[dia] += fila['total'] or 0
        elif fila['tipo'] == 'salida':
            salidas[dia] += fila['total'] or 0

    movimientos_periodo = {
        'labels': [dia.strftime('%d-%m') for dia in dias_rango],
        'entradas': [entradas[dia] for dia in dias_rango],
        'salidas': [salidas[dia] for dia in dias_rango],
    }

    productos_stock_bajo = (
        Producto.objects.filter(stock_actual__lt=F('stock_minimo'))
        .select_related('categoria')
        .order_by('stock_actual', 'nombre')[:5]
    )
    ultimas_solicitudes = (
        Solicitud.objects.select_related('sucursal')
        .annotate(items=Count('detallesolicitud'))
        .order_by('-fecha')[:5]
    )

    return {
        'vista': 'resumen',
        'periodo': periodo,
        'periodo_label': PERIODOS[periodo],
        'periodos': PERIODOS,
        'total_productos': total_productos,
        'total_productos_texto': _numero(total_productos),
        'stock_critico': stock_critico,
        'stock_critico_texto': _numero(stock_critico),
        'solicitudes_pendientes': solicitudes_pendientes,
        'solicitudes_pendientes_texto': _numero(solicitudes_pendientes),
        'valor_inventario': valor_inventario,
        'valor_inventario_texto': _moneda(valor_inventario),
        'inventario_categoria': inventario_categoria,
        'solicitudes_estado': solicitudes_estado,
        'movimientos_periodo': movimientos_periodo,
        'productos_stock_bajo': productos_stock_bajo,
        'ultimas_solicitudes': ultimas_solicitudes,
    }
