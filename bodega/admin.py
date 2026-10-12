from django.contrib import admin
from django.contrib.auth.hashers import identify_hasher, make_password

from .models import (
    Categoria, DetalleIngreso, DetalleSalida, Ingreso, Producto,
    Proveedor, Salida, Ubicacion, Usuario,
)

admin.site.site_header = 'Music Pro - Bodega Principal'
admin.site.site_title = 'Music Pro Bodega'
admin.site.index_title = 'Administracion de la bodega'


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)
    ordering = ('nombre',)


@admin.register(Ubicacion)
class UbicacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'codigo', 'nombre')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'email', 'telefono')
    search_fields = ('nombre', 'email', 'telefono')
    ordering = ('nombre',)


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'email', 'rol', 'estado')
    list_filter = ('rol', 'estado')
    search_fields = ('nombre', 'email')
    ordering = ('nombre',)

    def save_model(self, request, obj, form, change):
        try:
            identify_hasher(obj.password)
        except ValueError:
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        'sku', 'nombre', 'categoria', 'ubicacion',
        'stock', 'stock_minimo', 'precio', 'stock_bajo',
    )
    list_filter = ('categoria', 'ubicacion')
    search_fields = ('sku', 'nombre')
    list_select_related = ('categoria', 'ubicacion')
    ordering = ('sku',)
    list_per_page = 50
    show_full_result_count = False

    @admin.display(boolean=True, description='Stock bajo')
    def stock_bajo(self, obj):
        return obj.stock <= obj.stock_minimo


class DetalleIngresoInline(admin.TabularInline):
    model = DetalleIngreso
    extra = 1
    autocomplete_fields = ('producto',)


@admin.register(Ingreso)
class IngresoAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'proveedor', 'usuario')
    list_filter = ('fecha', 'proveedor')
    search_fields = ('proveedor__nombre', 'usuario__nombre', 'observacion')
    list_select_related = ('proveedor', 'usuario')
    date_hierarchy = 'fecha'
    autocomplete_fields = ('proveedor', 'usuario')
    inlines = [DetalleIngresoInline]
    list_per_page = 50
    show_full_result_count = False


class DetalleSalidaInline(admin.TabularInline):
    model = DetalleSalida
    extra = 1
    autocomplete_fields = ('producto',)


@admin.register(Salida)
class SalidaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'destino', 'estado', 'usuario', 'autorizado_por')
    list_filter = ('estado', 'fecha')
    search_fields = ('destino', 'usuario__nombre', 'autorizado_por__nombre', 'observacion')
    list_select_related = ('usuario', 'autorizado_por')
    date_hierarchy = 'fecha'
    autocomplete_fields = ('usuario', 'autorizado_por')
    inlines = [DetalleSalidaInline]
    list_per_page = 50
    show_full_result_count = False


@admin.register(DetalleIngreso)
class DetalleIngresoAdmin(admin.ModelAdmin):
    list_display = ('id', 'ingreso', 'producto', 'cantidad')
    search_fields = ('producto__sku', 'producto__nombre')
    list_select_related = ('ingreso', 'producto')
    autocomplete_fields = ('ingreso', 'producto')
    show_full_result_count = False


@admin.register(DetalleSalida)
class DetalleSalidaAdmin(admin.ModelAdmin):
    list_display = ('id', 'salida', 'producto', 'cantidad')
    search_fields = ('producto__sku', 'producto__nombre')
    list_select_related = ('salida', 'producto')
    autocomplete_fields = ('salida', 'producto')
    show_full_result_count = False