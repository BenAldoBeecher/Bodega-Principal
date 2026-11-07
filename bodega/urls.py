from django.urls import path

from . import views

urlpatterns = [
    # Públicas
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Productos
    path('productos/', views.productos_list, name='productos_list'),
    path('productos/crear/', views.producto_crear, name='producto_crear'),
    path('productos/<int:pk>/', views.producto_detail, name='producto_detail'),
    path('productos/<int:pk>/editar/', views.producto_editar, name='producto_editar'),
    path('productos/<int:pk>/eliminar/', views.producto_eliminar, name='producto_eliminar'),

    # Categorías
    path('categorias/', views.categorias_list, name='categorias_list'),
    path('categorias/crear/', views.categoria_crear, name='categoria_crear'),
    path('categorias/<int:pk>/editar/', views.categoria_editar, name='categoria_editar'),
    path('categorias/<int:pk>/eliminar/', views.categoria_eliminar, name='categoria_eliminar'),

    # Proveedores
    path('proveedores/', views.proveedores_list, name='proveedores_list'),
    path('proveedores/crear/', views.proveedor_crear, name='proveedor_crear'),
    path('proveedores/<int:pk>/editar/', views.proveedor_editar, name='proveedor_editar'),
    path('proveedores/<int:pk>/eliminar/', views.proveedor_eliminar, name='proveedor_eliminar'),

    # Sucursales
    path('sucursales/', views.sucursales_list, name='sucursales_list'),
    path('sucursales/crear/', views.sucursal_crear, name='sucursal_crear'),
    path('sucursales/<int:pk>/editar/', views.sucursal_editar, name='sucursal_editar'),
    path('sucursales/<int:pk>/eliminar/', views.sucursal_eliminar, name='sucursal_eliminar'),

    # Usuarios (solo admin)
    path('usuarios/', views.usuarios_list, name='usuarios_list'),
    path('usuarios/crear/', views.usuario_crear, name='usuario_crear'),
    path('usuarios/<int:pk>/', views.usuario_detail, name='usuario_detail'),
    path('usuarios/<int:pk>/editar/', views.usuario_editar, name='usuario_editar'),
    path('usuarios/<int:pk>/eliminar/', views.usuario_eliminar, name='usuario_eliminar'),

    # Ingresos
    path('ingresos/', views.ingresos_list, name='ingresos_list'),
    path('ingresos/registrar/', views.ingreso_registrar, name='ingreso_registrar'),

    # Salidas / Solicitudes de pedidos
    path('salidas/', views.salidas_list, name='salidas_list'),
    path('salidas/registrar/', views.salida_registrar, name='salida_registrar'),
    path('salidas/<int:pk>/autorizar/', views.salida_autorizar, name='salida_autorizar'),

    # Alertas y Stock
    path('alertas/', views.alertas, name='alertas'),
    path('stock/', views.stock, name='stock'),
]
