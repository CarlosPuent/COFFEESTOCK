from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction


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
    costo_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
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

    def __str__(self):
        return f'{self.nombre} ({self.get_unidad_medida_display()})'

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

    def __str__(self):
        return self.nombre


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

    def __str__(self):
        return f'Merma de {self.cantidad} {self.insumo.unidad_medida} - {self.insumo}'


class Venta(models.Model):
    usuario_cajero = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ventas'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['fecha'], name='idx_venta_fecha'),
        ]

    def __str__(self):
        return f'Venta #{self.pk} - {self.fecha:%Y-%m-%d %H:%M}'


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
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ['venta', 'id']

    def __str__(self):
        return f'{self.producto} x{self.cantidad} (Venta #{self.venta_id})'
