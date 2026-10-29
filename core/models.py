from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


def codigo(prefijo, pk, digitos=4):
    """Código legible para mostrar en pantallas y reportes: INS-0007."""
    return f'{prefijo}-{pk:0{digitos}d}' if pk else f'{prefijo}-nuevo'


class Insumo(models.Model):
    class UnidadMedida(models.TextChoices):
        GRAMOS = 'g', 'Gramos'
        MILILITROS = 'ml', 'Mililitros'
        UNIDAD = 'unidad', 'Unidad'

    nombre = models.CharField(max_length=150)
    unidad_medida = models.CharField(max_length=10, choices=UnidadMedida.choices)
    stock_actual = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    stock_minimo = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    # 4 decimales: el costo por gramo o mililitro suele ser de milésimas.
    costo_unitario = models.DecimalField(
        max_digits=14, decimal_places=4, validators=[MinValueValidator(0)]
    )
    activo = models.BooleanField(default=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    alerta_pendiente = models.BooleanField(default=False)
    ultima_alerta_enviada = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre'], name='idx_insumo_nombre'),
            models.Index(fields=['alerta_pendiente'], name='idx_insumo_alerta_pendiente'),
        ]

    PREFIJO = 'INS'

    def __str__(self):
        return f'{self.nombre} ({self.get_unidad_medida_display()})'

    @property
    def codigo(self):
        return codigo(self.PREFIJO, self.pk)

    @property
    def valor_inventario(self):
        return (self.stock_actual or 0) * (self.costo_unitario or 0)

    @transaction.atomic
    def descontar_stock(self, cantidad):
        """Descuenta stock de forma atómica, bloqueando la fila para evitar carreras."""
        insumo = Insumo.objects.select_for_update().get(pk=self.pk)
        if insumo.stock_actual < cantidad:
            raise ValueError(
                f'Stock insuficiente de {insumo.nombre}: disponible {insumo.stock_actual}, requerido {cantidad}'
            )
        insumo.stock_actual -= cantidad
        insumo.alerta_pendiente = insumo.stock_bajo
        insumo.save(update_fields=['stock_actual', 'alerta_pendiente', 'fecha_actualizacion'])

        if insumo.alerta_pendiente:
            from core.services.alertas import programar_alerta_stock
            programar_alerta_stock(insumo.pk)

        self.refresh_from_db()

    @transaction.atomic
    def registrar_entrada(self, cantidad, costo_unitario):
        """Suma stock por una compra y recalcula el costo promedio ponderado.

        Ejemplo: 1,000 g a $0.018 + compra de 1,000 g a $0.022 = 2,000 g a $0.020.
        """
        insumo = Insumo.objects.select_for_update().get(pk=self.pk)
        stock_previo = max(insumo.stock_actual, Decimal('0'))
        nuevo_stock = stock_previo + cantidad
        if nuevo_stock > 0:
            insumo.costo_unitario = (
                (stock_previo * insumo.costo_unitario + cantidad * costo_unitario) / nuevo_stock
            ).quantize(Decimal('0.0001'))
        insumo.stock_actual = insumo.stock_actual + cantidad
        insumo.save(update_fields=['stock_actual', 'costo_unitario', 'fecha_actualizacion'])
        insumo.sincronizar_alerta()
        self.refresh_from_db()

    @transaction.atomic
    def reponer_stock(self, cantidad):
        """Devuelve stock sin tocar el costo (por ejemplo, al anular una venta)."""
        insumo = Insumo.objects.select_for_update().get(pk=self.pk)
        insumo.stock_actual = insumo.stock_actual + cantidad
        insumo.save(update_fields=['stock_actual', 'fecha_actualizacion'])
        insumo.sincronizar_alerta()
        self.refresh_from_db()

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo

    def sincronizar_alerta(self):
        """Recalcula `alerta_pendiente` después de editar el stock a mano.

        Si el insumo quedó bajo el mínimo, programa el correo. Si se
        reabasteció, reinicia el cooldown para que la próxima caída avise
        de inmediato.
        """
        self.alerta_pendiente = self.stock_bajo
        if not self.alerta_pendiente:
            self.ultima_alerta_enviada = None
        self.save(update_fields=['alerta_pendiente', 'ultima_alerta_enviada'])

        if self.alerta_pendiente:
            from core.services.alertas import programar_alerta_stock
            programar_alerta_stock(self.pk)


class Producto(models.Model):
    class Categoria(models.TextChoices):
        BEBIDA = 'bebida', 'Bebida'
        REPOSTERIA = 'repostería', 'Repostería'
        OTRO = 'otro', 'Otro'

    nombre = models.CharField(max_length=150)
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    precio_venta = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    activo = models.BooleanField(default=True)
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)

    class Meta:
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre'], name='idx_producto_nombre'),
        ]

    PREFIJO = 'PRD'

    def __str__(self):
        return self.nombre

    @property
    def codigo(self):
        return codigo(self.PREFIJO, self.pk)

    @property
    def costo_receta(self):
        """Costo de los insumos que lleva una unidad del producto."""
        return sum(
            (r.cantidad_requerida * r.insumo.costo_unitario for r in self.receta_insumos.all()),
            Decimal('0'),
        )

    @property
    def margen(self):
        """Margen de ganancia sobre el precio de venta, en porcentaje."""
        if not self.precio_venta:
            return None
        return (self.precio_venta - self.costo_receta) / self.precio_venta * 100


class RecetaInsumo(models.Model):
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, related_name='receta_insumos'
    )
    insumo = models.ForeignKey(
        Insumo, on_delete=models.PROTECT, related_name='usos_en_recetas'
    )
    cantidad_requerida = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)]
    )

    class Meta:
        ordering = ['producto', 'insumo']
        constraints = [
            models.UniqueConstraint(
                fields=['producto', 'insumo'], name='unique_insumo_por_producto'
            )
        ]

    def __str__(self):
        return f'{self.producto} - {self.insumo} ({self.cantidad_requerida})'


class Merma(models.Model):
    class Causa(models.TextChoices):
        CADUCIDAD = 'caducidad', 'Caducidad'
        MALA_PREPARACION = 'mala_preparacion', 'Mala preparación'
        OTRO = 'otro', 'Otro'

    insumo = models.ForeignKey(
        Insumo, on_delete=models.PROTECT, related_name='mermas'
    )
    cantidad = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    causa = models.CharField(max_length=20, choices=Causa.choices)
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='mermas'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['fecha'], name='idx_merma_fecha'),
            models.Index(fields=['fecha', 'causa'], name='idx_merma_fecha_causa'),
        ]

    PREFIJO = 'MER'

    def __str__(self):
        return f'Merma de {self.cantidad} {self.insumo.unidad_medida} - {self.insumo}'

    @property
    def codigo(self):
        return codigo(self.PREFIJO, self.pk)

    @property
    def costo(self):
        """Valor perdido, al costo unitario actual del insumo."""
        return self.cantidad * self.insumo.costo_unitario


class VentaQuerySet(models.QuerySet):
    def completadas(self):
        return self.filter(estado=Venta.Estado.COMPLETADA)


class Venta(models.Model):
    class MetodoPago(models.TextChoices):
        EFECTIVO = 'efectivo', 'Efectivo'
        TARJETA = 'tarjeta', 'Tarjeta'

    class Estado(models.TextChoices):
        COMPLETADA = 'completada', 'Completada'
        ANULADA = 'anulada', 'Anulada'

    usuario_cajero = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ventas'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    metodo_pago = models.CharField(
        'método de pago', max_length=10, choices=MetodoPago.choices, default=MetodoPago.EFECTIVO
    )
    monto_recibido = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.COMPLETADA
    )
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ventas_anuladas',
        null=True, blank=True,
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True)

    objects = VentaQuerySet.as_manager()

    class Meta:
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['fecha'], name='idx_venta_fecha'),
            models.Index(fields=['estado', 'fecha'], name='idx_venta_estado_fecha'),
        ]

    PREFIJO = 'V'

    def __str__(self):
        return f'Venta {self.codigo} - {self.fecha:%Y-%m-%d %H:%M}'

    @property
    def codigo(self):
        return codigo(self.PREFIJO, self.pk, digitos=6)

    @property
    def anulada(self):
        return self.estado == self.Estado.ANULADA

    @property
    def cambio(self):
        if self.monto_recibido is None:
            return None
        return self.monto_recibido - self.total


class DetalleVenta(models.Model):
    venta = models.ForeignKey(
        Venta, on_delete=models.CASCADE, related_name='detalles'
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name='detalles_venta'
    )
    cantidad = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    # Precio al momento de la venta: si el producto cambia de precio, el
    # historial conserva el que se cobró.
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ['venta', 'id']

    def __str__(self):
        return f'{self.producto} x{self.cantidad} (Venta #{self.venta_id})'


class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    contacto = models.CharField('persona de contacto', max_length=150, blank=True)
    telefono = models.CharField('teléfono', max_length=30, blank=True)
    correo = models.EmailField(blank=True)
    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    PREFIJO = 'PRV'

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'proveedores'
        indexes = [models.Index(fields=['nombre'], name='idx_proveedor_nombre')]

    def __str__(self):
        return self.nombre

    @property
    def codigo(self):
        return codigo(self.PREFIJO, self.pk, digitos=3)


class Compra(models.Model):
    """Entrada de inventario: mercadería recibida de un proveedor."""

    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT, related_name='compras', null=True, blank=True
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='compras'
    )
    fecha = models.DateTimeField(default=timezone.now)
    numero_factura = models.CharField('número de factura', max_length=50, blank=True)
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    observacion = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    PREFIJO = 'C'

    class Meta:
        ordering = ['-fecha']
        indexes = [models.Index(fields=['fecha'], name='idx_compra_fecha')]

    def __str__(self):
        return f'Compra {self.codigo}'

    @property
    def codigo(self):
        return codigo(self.PREFIJO, self.pk, digitos=6)


class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='detalles')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='detalles_compra')
    cantidad = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))]
    )
    costo_unitario = models.DecimalField(
        max_digits=14, decimal_places=4, validators=[MinValueValidator(0)]
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ['compra', 'id']

    def __str__(self):
        return f'{self.insumo} x{self.cantidad} (Compra #{self.compra_id})'
