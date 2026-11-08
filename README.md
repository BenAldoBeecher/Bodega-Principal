# Music Pro - Bodega Central

Sistema web de gestión de bodega desarrollado con **Django** y **MySQL** para la Evaluación 3 de Programación Backend.

La aplicación permite administrar el inventario, mantener usuarios con roles, gestionar solicitudes de pedido de las sucursales, registrar movimientos de stock y consultar reportes construidos exclusivamente con el **ORM de Django**.

---

## Funcionalidades

- Autenticación con `authenticate`, `login` y `logout`; contraseñas almacenadas con hash.
- Protección de vistas con `@login_required` y `@admin_required`.
- Roles **Administrador** y **Operador** mediante grupos de Django.
- CRUD de usuarios, categorías, proveedores, sucursales y productos.
- Solicitudes de pedido con detalles por producto.
- Aprobación o rechazo de solicitudes con cantidades aprobadas.
- Despacho de solicitudes con descuento automático de stock y generación de movimientos.
- Registro de entradas y salidas directas de stock.
- Edición de movimientos directos (fecha y observación).
- Validación de stock insuficiente y reversión de stock al eliminar movimientos directos.
- Alertas de productos bajo el stock mínimo.
- Página de reportes con las **20 consultas ORM** de la guía.
- Persistencia real en MySQL mediante el ORM, sin SQL directo para las consultas de la aplicación.
- Formularios HTML procesados directamente en `views.py` con `request.POST`, sin `ModelForm`.

---

## Tecnologías

- Python 3.12
- Django 6.1
- MySQL 8 / MariaDB
- `mysqlclient` 2.3.0
- Bootstrap 5 en las plantillas
- Faker para generar datos de prueba

---

## Requisitos previos

- Python 3.12 o superior.
- MySQL ejecutándose en `localhost:3306`.
- Base de datos `bodega` creada.

---

## Instalación

1. Crear y activar un entorno virtual:

   ```bash
   python -m venv venv
   ```

   En Windows:

   ```bash
   venv\Scripts\activate
   ```

   En Linux/macOS:

   ```bash
   source venv/bin/activate
   ```

2. Instalar las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

3. Crear la base de datos en MySQL:

   ```sql
   CREATE DATABASE bodega CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

4. Configurar las credenciales de MySQL en `musicpro_bodega/settings.py`. La configuración por defecto es:

   ```python
   'NAME': 'bodega',
   'USER': 'root',
   'PASSWORD': 'root',
   'HOST': 'localhost',
   'PORT': '3306',
   ```

   Si tu usuario o contraseña de MySQL son distintos, ajusta esos valores.

5. Aplicar las migraciones:

   ```bash
   python manage.py migrate
   ```

6. Cargar los datos de prueba (catálogos, productos, solicitudes, movimientos y usuarios):

   ```bash
   python manage.py seed_bodega --cantidad 100
   ```

   El parámetro `--cantidad` indica cuántos productos se generan. El comando crea además 10 categorías, 10 proveedores, 10 sucursales, solicitudes, movimientos y los usuarios de prueba. Si se ejecuta nuevamente, agrega más productos y solicitudes sobre los datos existentes.

7. Ejecutar el servidor:

   ```bash
   python manage.py runserver
   ```

8. Abrir en el navegador:

   ```text
   http://127.0.0.1:8000/
   ```

---

## Usuarios de prueba

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin@musicpro.cl` | `admin123` |
| Operador | `operador@musicpro.cl` | `operador123` |

El campo `username` corresponde al correo electrónico. Las contraseñas se almacenan hasheadas en la base de datos.

---

## Formularios y validación

Los formularios están construidos directamente en HTML y se procesan en `views.py` mediante `request.POST`. La validación de campos, la verificación de duplicados y los mensajes de error se realizan en el servidor, sin utilizar `ModelForm` ni clases `ProductoForm`. Todos los formularios incorporan `{% csrf_token %}` y las operaciones que modifican datos se ejecutan exclusivamente por POST.

---

## Roles y permisos

### Administrador

- Ver el dashboard administrativo.
- Crear, consultar, editar y eliminar usuarios.
- Gestionar categorías, proveedores, sucursales y productos.
- Autorizar o rechazar solicitudes de pedido.
- Despachar solicitudes aprobadas, descontando stock.
- Registrar entradas y salidas directas de stock.
- Editar movimientos directos (fecha y observación).
- Eliminar movimientos directos, revirtiendo el stock.
- Consultar inventario, alertas, movimientos y reportes.

### Operador

- Ver el dashboard operacional.
- Consultar inventario, stock, alertas y movimientos.
- Crear solicitudes de pedido y agregar detalles.
- Editar o eliminar solicitudes pendientes.
- Registrar entradas de stock.
- Consultar reportes.

Las vistas de administración están protegidas con `admin_required`. Si un operador intenta acceder, el sistema lo redirige al dashboard con un mensaje de error. Las salidas directas de stock también están reservadas al Administrador; el Operador debe usar una solicitud de pedido.

---

## Flujo de una solicitud

1. El usuario crea una solicitud indicando la sucursal y la fecha.
2. Agrega uno o más productos con la cantidad solicitada.
3. El Administrador revisa la solicitud y puede:
   - Aprobarla, ajustando la cantidad aprobada de cada producto.
   - Rechazarla, sin afectar el stock.
4. Si la solicitud es aprobada, el Administrador puede despacharla.
5. Al despachar:
   - Se valida que exista stock suficiente.
   - Se descuenta el stock de cada producto.
   - Se registra un movimiento de salida asociado a la solicitud.
   - La solicitud queda en estado `despachada`.

Los movimientos generados por una solicitud no se pueden eliminar manualmente, para mantener la trazabilidad del historial.

---

## Rutas principales

| Ruta | Descripción |
|---|---|
| `/login/` | Inicio de sesión |
| `/logout/` | Cierre de sesión |
| `/dashboard/` | Panel principal según el rol |
| `/productos/` | Listado y búsqueda de productos |
| `/productos/crear/` | Crear producto |
| `/productos/<id>/` | Detalle del producto |
| `/categorias/` | Catálogo de categorías |
| `/proveedores/` | Catálogo de proveedores |
| `/sucursales/` | Catálogo de sucursales |
| `/usuarios/` | Mantenedor de usuarios (solo Administrador) |
| `/solicitudes/` | Listado de solicitudes |
| `/solicitudes/crear/` | Crear solicitud |
| `/solicitudes/<id>/` | Detalle, autorización y despacho |
| `/movimientos/` | Historial de movimientos de stock |
| `/movimientos/crear/` | Registrar entrada o salida directa |
| `/movimientos/<id>/editar/` | Editar fecha y observación de un movimiento directo |
| `/reportes/` | Página con las 20 consultas ORM |
| `/alertas/` | Productos bajo el stock mínimo |
| `/stock/` | Consulta de stock |

---

## Reportes ORM

La página `/reportes/` incluye las 20 preguntas de la guía, agrupadas en:

- **Básicas:** productos, productos por categoría, stock bajo mínimo, top 10 por precio y conteo por categoría.
- **Intermedias:** productos por proveedor, solicitudes por sucursal, detalle de una solicitud, solicitudes por estado, solicitudes por rango de fechas, top 5 sucursales y productos más solicitados.
- **Avanzadas:** proveedor con más productos diferentes, valor total del inventario, productos nunca solicitados, salidas del último mes y sucursales con solicitudes pendientes.
- **Análisis:** categoría con mayor valor de inventario, promedio de productos solicitados y top 5 productos por período.

Cada reporte permite:

- Seleccionar la consulta desde el menú lateral.
- Aplicar filtros por categoría, proveedor, sucursal, solicitud o rango de fechas.
- Ver los resultados en una tabla.
- Desplegar la consulta ORM utilizada como evidencia.

Todas las consultas usan el ORM de Django: `filter`, `annotate`, `aggregate`, `values`, `Sum`, `Count`, `Avg`, `F`, `Q`, `select_related`, entre otros.

---

## Estructura del proyecto

```text
musicpro_bodega/              Configuración del proyecto Django
  settings.py                 MySQL, autenticación, zona horaria, estáticos
  urls.py                     Rutas generales del proyecto
bodega/
  models.py                   Modelos alineados al esquema de la bodega
  views.py                    Autenticación, CRUD con request.POST, solicitudes y movimientos
  reportes.py                 Catálogo y ejecución de las 20 consultas ORM
  permisos.py                 Helpers y decorador de roles
  context_processors.py       Expone el rol a las plantillas
  urls.py                     Rutas de la aplicación
  admin.py                    Registro legado de Django Admin (ruta deshabilitada)
  management/commands/
    seed_bodega.py            Generador de datos de prueba
  templates/admin/            Plantillas de la interfaz web
static/                       Estilos y recursos estáticos
```

---

## Comandos útiles

```bash
# Verificar el proyecto
python manage.py check

# Comprobar que no faltan migraciones
python manage.py makemigrations --check --dry-run

# Aplicar migraciones
python manage.py migrate

# Generar datos de prueba
python manage.py seed_bodega --cantidad 100

# Ejecutar el servidor
python manage.py runserver
```

---

## Nota sobre Django Admin

La ruta `/admin/` está deshabilitada en esta entrega. Toda la gestión se realiza desde la interfaz web propia: login, dashboard, mantenedores, solicitudes, movimientos y reportes. El archivo `bodega/admin.py` se conserva como registro legado de la Evaluación 2, pero no está expuesto en las rutas del proyecto.

---

## Consideraciones

- La base de datos utilizada es MySQL; `db.sqlite3` no forma parte del flujo de la aplicación y está excluida en `.gitignore`.
- La zona horaria configurada es `America/Santiago` y `USE_TZ = False`, por lo que las fechas se almacenan en hora local.
- Las migraciones crean las tablas `categoria`, `proveedor`, `sucursal`, `producto`, `solicitud`, `detalle_solicitud` y `movimiento_stock`, respetando el esquema entregado para la evaluación.
