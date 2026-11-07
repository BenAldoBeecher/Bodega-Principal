import random

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

from bodega.models import (
    Categoria, DetalleSolicitud, MovimientoStock, Producto,
    Proveedor, Solicitud, Sucursal,
)

LOTE = 5000  # cuantos registros se guardan juntos en cada consulta


class Command(BaseCommand):
    help = "Genera datos de prueba para la bodega: N productos y N/10 solicitudes y entradas de stock"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cantidad",
            type=int,
            default=100,
            help="Cantidad de productos a crear (100, 1000, 100000, 1000000)",
        )

    def handle(self, *args, **options):
        fake = Faker("es_CL")
        cantidad = options["cantidad"]
        movimientos = max(cantidad // 10, 1)

        # Todo se guarda en una sola transaccion: es mucho mas rapido
        with transaction.atomic():
            self.crear_usuarios()
            self.crear_catalogos(fake)
            self.crear_productos(fake, cantidad)
            self.crear_solicitudes(fake, movimientos)
            self.crear_entradas(fake, movimientos)

        self.stdout.write(self.style.SUCCESS("Datos creados correctamente."))
        self.mostrar_resumen()

    def crear_usuarios(self):
        """Crea los grupos y usuarios base del sistema con contraseñas hasheadas."""
        grupo_admin, _ = Group.objects.get_or_create(name='Administrador')
        grupo_operador, _ = Group.objects.get_or_create(name='Operador')

        usuarios = [
            {
                'username': 'admin@musicpro.cl',
                'email': 'admin@musicpro.cl',
                'first_name': 'Administrador',
                'last_name': 'Music Pro',
                'password': 'admin123',
                'grupo': grupo_admin,
                'is_superuser': True,
                'is_staff': True,
            },
            {
                'username': 'operador@musicpro.cl',
                'email': 'operador@musicpro.cl',
                'first_name': 'Operador',
                'last_name': 'Bodega',
                'password': 'operador123',
                'grupo': grupo_operador,
                'is_superuser': False,
                'is_staff': False,
            },
        ]

        for datos in usuarios:
            password = datos['password']
            grupo = datos['grupo']
            username = datos['username']
            defaults = {
                clave: valor for clave, valor in datos.items()
                if clave not in ('username', 'password', 'grupo')
            }
            usuario, creado = User.objects.get_or_create(username=username, defaults=defaults)
            if creado:
                usuario.set_password(password)
            usuario.email = datos['email']
            usuario.first_name = datos['first_name']
            usuario.last_name = datos['last_name']
            usuario.is_superuser = datos['is_superuser']
            usuario.is_staff = datos['is_staff']
            usuario.is_active = True
            usuario.save()
            usuario.groups.set([grupo])

    def crear_catalogos(self, fake):
        # Tablas pequenas: solo se crean si estan vacias
        if not Categoria.objects.exists():
            nombres = ["Guitarras", "Bajos", "Teclados", "Baterias", "Amplificadores",
                       "Microfonos", "Accesorios", "Audio"]
            for nombre in nombres:
                Categoria.objects.create(nombre=nombre, descripcion=f"Productos de la categoria {nombre}")

        if not Proveedor.objects.exists():
            for i in range(10):
                Proveedor.objects.create(
                    rut=fake.rut(),
                    razon_social=fake.company(),
                    email=fake.company_email(),
                    telefono=fake.phone_number()[:30],
                    activo=True,
                )

        if not Sucursal.objects.exists():
            for i in range(1, 11):
                Sucursal.objects.create(
                    codigo=f"SUC-{i:02d}",
                    nombre=f"Sucursal {fake.city()}",
                    direccion=fake.street_address(),
                    activa=True,
                )

    def crear_productos(self, fake, cantidad):
        tipos = ["Guitarra", "Bajo", "Teclado", "Amplificador", "Microfono", "Bateria"]
        categorias = list(Categoria.objects.values_list("id", flat=True))
        proveedores = list(Proveedor.objects.values_list("id", flat=True))
        inicio = Producto.objects.count()  # evita repetir el SKU entre cargas

        lote = []
        for i in range(cantidad):
            lote.append(
                Producto(
                    sku=f"SKU-{inicio + i + 1:08d}",
                    nombre=f"{random.choice(tipos)} {fake.word().capitalize()}",
                    categoria_id=random.choice(categorias),
                    proveedor_id=random.choice(proveedores),
                    precio=random.randint(5000, 2500000),
                    stock_actual=random.randint(0, 500),
                    stock_minimo=random.randint(5, 50),
                    activo=random.random() < 0.95,
                )
            )
            # Cada 5000 productos se guardan juntos (bulk_create) y se vacia la lista
            if len(lote) == LOTE:
                Producto.objects.bulk_create(lote)
                lote = []
        if lote:
            Producto.objects.bulk_create(lote)

    def crear_solicitudes(self, fake, cantidad):
        productos = list(Producto.objects.values_list("id", flat=True))
        sucursales = list(Sucursal.objects.values_list("id", flat=True))
        estados = ["pendiente", "aprobada", "rechazada", "despachada"]

        detalles = []
        movimientos = []
        for i in range(cantidad):
            estado = random.choice(estados)
            fecha = fake.date_time_between(start_date="-1y", end_date="now", tzinfo=None)
            solicitud = Solicitud.objects.create(
                sucursal_id=random.choice(sucursales),
                fecha=fecha,
                estado=estado,
                observaciones=fake.sentence(),
            )
            # Cada solicitud pide de 1 a 3 productos
            for _ in range(random.randint(1, 3)):
                producto_id = random.choice(productos)
                pedida = random.randint(1, 50)
                aprobada = None
                despachada = None
                if estado == "rechazada":
                    aprobada = 0
                elif estado in ("aprobada", "despachada"):
                    aprobada = random.randint(1, pedida)
                if estado == "despachada":
                    despachada = aprobada
                    movimientos.append(
                        MovimientoStock(
                            producto_id=producto_id,
                            solicitud=solicitud,
                            tipo="salida",
                            cantidad=despachada,
                            fecha=fecha,
                            observacion="Despacho de solicitud",
                        )
                    )
                detalles.append(
                    DetalleSolicitud(
                        solicitud=solicitud,
                        producto_id=producto_id,
                        cantidad_solicitada=pedida,
                        cantidad_aprobada=aprobada,
                        cantidad_despachada=despachada,
                    )
                )
            # Los detalles y movimientos se guardan por lotes
            if len(detalles) >= LOTE:
                DetalleSolicitud.objects.bulk_create(detalles)
                MovimientoStock.objects.bulk_create(movimientos)
                detalles = []
                movimientos = []
        DetalleSolicitud.objects.bulk_create(detalles)
        MovimientoStock.objects.bulk_create(movimientos)

    def crear_entradas(self, fake, cantidad):
        productos = list(Producto.objects.values_list("id", flat=True))

        lote = []
        for i in range(cantidad):
            lote.append(
                MovimientoStock(
                    producto_id=random.choice(productos),
                    tipo="entrada",
                    cantidad=random.randint(10, 200),
                    fecha=fake.date_time_between(start_date="-1y", end_date="now", tzinfo=None),
                    observacion="Ingreso de mercaderia",
                )
            )
            if len(lote) == LOTE:
                MovimientoStock.objects.bulk_create(lote)
                lote = []
        if lote:
            MovimientoStock.objects.bulk_create(lote)

    def mostrar_resumen(self):
        self.stdout.write("Registros en la base de datos:")
        for modelo in (Categoria, Proveedor, Sucursal, Producto,
                       Solicitud, DetalleSolicitud, MovimientoStock):
            self.stdout.write(f"  {modelo._meta.db_table:<20} {modelo.objects.count():>10,}")