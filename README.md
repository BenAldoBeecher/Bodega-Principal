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
python manage.py makemigrations
python manage.py migrate
```

3. Ejecutar el servidor:
```
python manage.py runserver
```

4. Abrir en el navegador:
```
http://127.0.0.1:8000/
```

---

## Credenciales de acceso

**Administrador**
- Email: benjamin@musicpro.cl
- Contraseña: admin123

**Operadores**
- adam@musicpro.cl / operador123
- michael@musicpro.cl / operador123
- gianluigi@musicpro.cl / operador123
- paolo@musicpro.cl / operador123

---

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

## Notas

- En la Unidad 1 los datos se cargan desde `data.json` (sin base de datos real).
- Las acciones de crear/editar/eliminar/autorizar son simulaciones funcionales listas para conectarse a base de datos en la Evaluación 2.
- Los comandos `makemigrations` y `migrate` quedan preparados para la Evaluación 2.
- El logout redirige a la pantalla principal (landing).
- No existe registro público: los usuarios los crea únicamente el Administrador.
