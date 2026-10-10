from django.db import models


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'categorias'

    def __str__(self):
        return self.nombre


class Ubicacion(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20)

    class Meta:
        db_table = 'ubicaciones'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    email = models.EmailField(max_length=150)
    telefono = models.CharField(max_length=20)

    class Meta:
        db_table = 'proveedores'

    def __str__(self):
        return self.nombre


class Usuario(models.Model):
    ROL_CHOICES = [
        ('Administrador', 'Administrador'),
        ('Operador', 'Operador'),
    ]
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    ]

    nombre = models.CharField(max_length=100)
    email = models.EmailField(max_length=150, unique=True)
    password = models.CharField(max_length=130)  # guardar siempre el hash (make_password)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='Operador')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')

    class Meta:
        db_table = 'usuarios'

    def __str__(self):
        return f'{self.nombre} ({self.rol})'


class Producto(models.Model):
    sku = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    stock = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, db_column='categoria_id')
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, db_column='ubicacion_id')

    class Meta:
        db_table = 'productos'

    def __str__(self):
        return f'{self.sku} - {self.nombre}'


class Ingreso(models.Model):
    fecha = models.DateField()
    observacion = models.TextField(blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, db_column='proveedor_id')
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, db_column='usuario_id')

    class Meta:
        db_table = 'ingresos'

    def __str__(self):
        return f'Ingreso #{self.pk} - {self.fecha}'


class DetalleIngreso(models.Model):
    ingreso = models.ForeignKey(Ingreso, on_delete=models.CASCADE, db_column='ingreso_id')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, db_column='producto_id')
    cantidad = models.PositiveIntegerField()

    class Meta:
        db_table = 'detalles_ingreso'

    def __str__(self):
        return f'{self.cantidad} x {self.producto}'


class Salida(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('autorizada', 'Autorizada'),
    ]

    fecha = models.DateField()
    destino = models.CharField(max_length=150)
    observacion = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, db_column='usuario_id')

    class Meta:
        db_table = 'salidas'

    def __str__(self):
        return f'Salida #{self.pk} -> {self.destino}'


class DetalleSalida(models.Model):
    salida = models.ForeignKey(Salida, on_delete=models.CASCADE, db_column='salida_id')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, db_column='producto_id')
    cantidad = models.PositiveIntegerField()

    class Meta:
        db_table = 'detalles_salida'

    def __str__(self):
        return f'{self.cantidad} x {self.producto}'
