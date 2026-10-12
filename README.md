# Music Pro - Bodega Principal

Sistema de gestión de bodega principal

---

## Comandos usados para crear el proyecto

```
django-admin startproject musicpro_bodega .
python manage.py startapp bodega
```

---

## Instalación y ejecución (rápida)

1. Instalar dependencias:
```
pip install -r requirements.txt
```

2. Aplicar migraciones:
```
python manage.py migrate
```

3. Crear el superusuario para entrar al Django Admin:
```
python manage.py createsuperuser
```

4. Ejecutar el servidor:
```
python manage.py runserver
```

5. Abrir en el navegador:
```
http://127.0.0.1:8000/        (aplicación)
http://127.0.0.1:8000/admin/  (Django Admin)
```

## Datos de prueba (Faker)

python manage.py seed_bodega --cantidad [##numero]

## Roles y flujo del sistema

**Administrador**
- Dashboard de administración
- Gestionar inventario y stock (productos, categorías, alertas)
- Mantenedor de usuarios (crear, ver, editar rol/estado, eliminar)
- Revisar y autorizar solicitudes de pedidos (salidas)
- Ver historial de ingresos y salidas

**Operador**
- Dashboard operacional
- Registrar ingreso de productos
- Registrar salida / envío (queda pendiente de autorización)
- Consultar inventario y stock
- Ver alertas de stock

---

