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

    # Ingresos y Salidas
    path('ingresos/', views.ingresos_list, name='ingresos_list'),
    path('salidas/', views.salidas_list, name='salidas_list'),

    # Alertas y Stock
    path('alertas/', views.alertas, name='alertas'),
    path('stock/', views.stock, name='stock'),
]
