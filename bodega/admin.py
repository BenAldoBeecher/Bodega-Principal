from django.contrib import admin

from .models import (
    Categoria, DetalleSolicitud, MovimientoStock, Producto,
    Proveedor, Solicitud, Sucursal,
)

admin.site.site_header = 'Music Pro - Bodega Central'
admin.site.site_title = 'Music Pro Bodega'
admin.site.index_title = 'Administracion de la bodega'


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'descripcion')
    search_fields = ('nombre',)
    ordering = ('nombre',)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('id', 'rut', 'razon_social', 'email', 'telefono', 'activo')
    list_filter = ('activo',)
    search_fields = ('razon_social', 'rut', 'email')
    ordering = ('razon_social',)


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ('id', 'codigo', 'nombre', 'direccion', 'activa')
    list_filter = ('activa',)
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        'sku', 'nombre', 'categoria', 'proveedor',
        'precio', 'stock_actual', 'stock_minimo', 'activo', 'stock_bajo',
    )
    list_filter = ('categoria', 'proveedor', 'activo')
    search_fields = ('sku', 'nombre')
    list_select_related = ('categoria', 'proveedor')
    ordering = ('sku',)
    list_per_page = 50
    show_full_result_count = False  # evita un COUNT(*) pesado con muchos registros

    @admin.display(boolean=True, description='Stock bajo')
    def stock_bajo(self, obj):
        return obj.stock_actual <= obj.stock_minimo


class DetalleSolicitudInline(admin.TabularInline):
    model = DetalleSolicitud
    extra = 1
    autocomplete_fields = ('producto',)


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ('id', 'sucursal', 'fecha', 'estado')
    list_filter = ('estado', 'sucursal', 'fecha')
    search_fields = ('sucursal__nombre', 'sucursal__codigo', 'observaciones')
    list_select_related = ('sucursal',)
    date_hierarchy = 'fecha'
    inlines = [DetalleSolicitudInline]
    list_per_page = 50
    show_full_result_count = False


@admin.register(DetalleSolicitud)
class DetalleSolicitudAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'solicitud', 'producto',
        'cantidad_solicitada', 'cantidad_aprobada', 'cantidad_despachada',
    )
    search_fields = ('producto__sku', 'producto__nombre')
    list_select_related = ('solicitud', 'producto')
    autocomplete_fields = ('solicitud', 'producto')
    show_full_result_count = False


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('id', 'producto', 'tipo', 'cantidad', 'fecha', 'solicitud')
    list_filter = ('tipo', 'fecha')
    search_fields = ('producto__sku', 'producto__nombre', 'observacion')
    list_select_related = ('producto', 'solicitud')
    date_hierarchy = 'fecha'
    autocomplete_fields = ('producto', 'solicitud')
    show_full_result_count = False