import random

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from bodega.models import (
    Categoria, DetalleIngreso, DetalleSalida, Ingreso, Producto,
    Proveedor, Salida, Ubicacion, Usuario,
)


class Command(BaseCommand):
    help = "Genera datos de prueba para la bodega: N productos y N/10 ingresos y salidas"

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

        with transaction.atomic():
            self.crear_catalogos(fake)
            self.crear_productos(fake, cantidad)
            self.crear_ingresos(fake, max(cantidad // 10, 1))
            self.crear_salidas(fake, max(cantidad // 10, 1))

        self.stdout.write(self.style.SUCCESS("Datos creados correctamente."))
        self.mostrar_resumen()

    def crear_catalogos(self, fake):
        if not Categoria.objects.exists():
            for nombre in ["Guitarras", "Bajos", "Teclados", "Baterias", "Audio"]:
                Categoria.objects.create(nombre=nombre)

        if not Ubicacion.objects.exists():
            for i in range(1, 11):
                Ubicacion.objects.create(nombre=f"Pasillo {i}", codigo=f"P-{i:02d}")

        if not Proveedor.objects.exists():
            for i in range(10):
                Proveedor.objects.create(
                    nombre=fake.company(),
                    email=fake.company_email(),
                    telefono=fake.phone_number()[:20],
                )

        if not Usuario.objects.exists():
            clave = make_password("musicpro123")  # se encripta una sola vez
            for i in range(1, 6):
                Usuario.objects.create(
                    nombre=fake.name(),
                    email=f"usuario{i}@musicpro.cl",
                    password=clave,
                    rol="Administrador" if i == 1 else "Operador",
                    estado="activo",
                )

    def crear_productos(self, fake, cantidad):
        tipos = ["Guitarra", "Bajo", "Teclado", "Amplificador", "Microfono", "Bateria"]
        categorias = list(Categoria.objects.values_list("id", flat=True))
        ubicaciones = list(Ubicacion.objects.values_list("id", flat=True))
        inicio = Producto.objects.count()

        lote = []
        for i in range(cantidad):
            lote.append(
                Producto(
                    sku=f"SKU-{inicio + i + 1:08d}",
                    nombre=f"{random.choice(tipos)} {fake.word().capitalize()}",
                    stock=random.randint(0, 500),
                    stock_minimo=random.randint(5, 50),
                    precio=random.randint(5000, 2500000),
                    categoria_id=random.choice(categorias),
                    ubicacion_id=random.choice(ubicaciones),
                )
            )
            if len(lote) == 5000:
                Producto.objects.bulk_create(lote)
                lote = []
        if lote:
            Producto.objects.bulk_create(lote)

    def crear_ingresos(self, fake, cantidad):
        productos = list(Producto.objects.values_list("id", flat=True))
        proveedores = list(Proveedor.objects.values_list("id", flat=True))
        usuarios = list(Usuario.objects.values_list("id", flat=True))

        for i in range(cantidad):
            ingreso = Ingreso.objects.create(
                fecha=fake.date_between(start_date="-1y", end_date="today"),
                observacion=fake.sentence(),
                proveedor_id=random.choice(proveedores),
                usuario_id=random.choice(usuarios),
            )
            for _ in range(random.randint(1, 3)):
                DetalleIngreso.objects.create(
                    ingreso=ingreso,
                    producto_id=random.choice(productos),
                    cantidad=random.randint(1, 100),
                )

    def crear_salidas(self, fake, cantidad):
        productos = list(Producto.objects.values_list("id", flat=True))
        usuarios = list(Usuario.objects.values_list("id", flat=True))
        admin = Usuario.objects.filter(rol="Administrador").first()

        for i in range(cantidad):
            autorizada = random.random() < 0.6
            salida = Salida.objects.create(
                fecha=fake.date_between(start_date="-1y", end_date="today"),
                destino=fake.city(),
                observacion=fake.sentence(),
                estado="autorizada" if autorizada else "pendiente",
                usuario_id=random.choice(usuarios),
                autorizado_por=admin if autorizada else None,
                fecha_autorizacion=timezone.now() if autorizada else None,
            )
            for _ in range(random.randint(1, 3)):
                DetalleSalida.objects.create(
                    salida=salida,
                    producto_id=random.choice(productos),
                    cantidad=random.randint(1, 50),
                )

    def mostrar_resumen(self):
        self.stdout.write("Registros en la base de datos:")
        for modelo in (Categoria, Ubicacion, Proveedor, Usuario, Producto,
                       Ingreso, DetalleIngreso, Salida, DetalleSalida):
            self.stdout.write(f"  {modelo._meta.db_table:<18} {modelo.objects.count():>10,}")