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
    path('productos/<int:pk>/', views.producto_detail, name='producto_detail'),

    # Categorías
    path('categorias/', views.categorias_list, name='categorias_list'),

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
