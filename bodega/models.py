from django.db import models


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'categoria'

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    rut = models.CharField(max_length=20, null=True, blank=True)
    razon_social = models.CharField(max_length=150)
    email = models.CharField(max_length=150, null=True, blank=True)
    telefono = models.CharField(max_length=30, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'proveedor'

    def __str__(self):
        return self.razon_social


class Sucursal(models.Model):
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=120)
    direccion = models.CharField(max_length=200, null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = 'sucursal'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class Producto(models.Model):
    sku = models.CharField(max_length=50)
    nombre = models.CharField(max_length=150)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, db_column='categoria_id')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, db_column='proveedor_id')
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    stock_actual = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'producto'

    def __str__(self):
        return f'{self.sku} - {self.nombre}'


class Solicitud(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
        ('despachada', 'Despachada'),
    ]

    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, db_column='sucursal_id')
    fecha = models.DateTimeField()
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='pendiente')
    observaciones = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'solicitud'

    def __str__(self):
        return f'Solicitud #{self.pk} - {self.sucursal}'


class DetalleSolicitud(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, db_column='solicitud_id')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, db_column='producto_id')
    cantidad_solicitada = models.IntegerField()
    cantidad_aprobada = models.IntegerField(null=True, blank=True)
    cantidad_despachada = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'detalle_solicitud'

    def __str__(self):
        return f'{self.cantidad_solicitada} x {self.producto}'


class MovimientoStock(models.Model):
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, db_column='producto_id')
    solicitud = models.ForeignKey(
        Solicitud, on_delete=models.PROTECT, null=True, blank=True, db_column='solicitud_id',
    )
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES)
    cantidad = models.IntegerField()
    fecha = models.DateTimeField()
    observacion = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'movimiento_stock'

    def __str__(self):
        return f'{self.tipo} {self.cantidad} x {self.producto}'