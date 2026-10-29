"""Registro y anulación de ventas, con su efecto en el inventario."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from core.models import DetalleVenta, Insumo, Producto, RecetaInsumo, Venta
from core.templatetags.formato import cantidad as formato_cantidad
from core.templatetags.formato import unidad_corta


class VentaError(Exception):
    """Error de negocio: carrito inválido, pago insuficiente o falta de stock."""


def _a_decimal(valor, mensaje):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        raise VentaError(mensaje)
    if not numero.is_finite():
        raise VentaError(mensaje)
    return numero


def _consumo_por_insumo(lineas):
    """{insumo_id: cantidad total} que consumen las líneas (producto, cantidad)."""
    consumo = defaultdict(Decimal)
    for producto, cantidad in lineas:
        for receta in producto.receta_insumos.all():
            consumo[receta.insumo_id] += receta.cantidad_requerida * cantidad
    return consumo


def _productos_con_receta(ids):
    return Producto.objects.filter(pk__in=ids, activo=True).prefetch_related(
        Prefetch('receta_insumos', queryset=RecetaInsumo.objects.select_related('insumo'))
    )


@transaction.atomic
def registrar_venta(*, usuario, items, metodo_pago=Venta.MetodoPago.EFECTIVO, monto_recibido=None):
    """Crea la venta y descuenta los insumos según la receta de cada producto.

    `items` es una lista de dicts {'producto_id': int, 'cantidad': número}.
    """
    if not items:
        raise VentaError('El carrito está vacío.')
    if metodo_pago not in Venta.MetodoPago.values:
        raise VentaError('Método de pago inválido.')

    ids = [item.get('producto_id') for item in items]
    productos = {p.pk: p for p in _productos_con_receta(ids)}

    lineas = []
    for item in items:
        producto = productos.get(item.get('producto_id'))
        if producto is None:
            raise VentaError('Uno de los productos seleccionados ya no está disponible.')
        cantidad = _a_decimal(item.get('cantidad'), f'Cantidad inválida para "{producto.nombre}".')
        if cantidad <= 0:
            raise VentaError(f'Cantidad inválida para "{producto.nombre}".')
        lineas.append((producto, cantidad))

    total = sum((p.precio_venta * c for p, c in lineas), Decimal('0'))

    if metodo_pago == Venta.MetodoPago.EFECTIVO:
        if monto_recibido in (None, ''):
            monto_recibido = total
        monto_recibido = _a_decimal(monto_recibido, 'El monto recibido no es válido.')
        if monto_recibido < total:
            raise VentaError(f'El monto recibido (${monto_recibido:,.2f}) no cubre el total (${total:,.2f}).')
    else:
        monto_recibido = None

    # Cada insumo se bloquea una sola vez y siempre en orden de ID: dos cajas
    # vendiendo a la vez no pueden quedar esperándose mutuamente.
    consumo = _consumo_por_insumo(lineas)
    insumos = list(Insumo.objects.select_for_update().filter(pk__in=consumo).order_by('pk'))
    faltantes = [
        f'{i.nombre} (hay {formato_cantidad(i.stock_actual)} {unidad_corta(i.unidad_medida)}, '
        f'se necesitan {formato_cantidad(consumo[i.pk])})'
        for i in insumos if i.stock_actual < consumo[i.pk]
    ]
    if faltantes:
        raise VentaError('Stock insuficiente: ' + '; '.join(faltantes) + '.')

    from core.services.alertas import programar_alerta_stock

    for insumo in insumos:
        insumo.stock_actual -= consumo[insumo.pk]
        insumo.alerta_pendiente = insumo.stock_bajo
        insumo.save(update_fields=['stock_actual', 'alerta_pendiente', 'fecha_actualizacion'])
        if insumo.alerta_pendiente:
            programar_alerta_stock(insumo.pk)

    venta = Venta.objects.create(
        usuario_cajero=usuario,
        total=total,
        metodo_pago=metodo_pago,
        monto_recibido=monto_recibido,
    )
    DetalleVenta.objects.bulk_create([
        DetalleVenta(
            venta=venta,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=producto.precio_venta,
            subtotal=producto.precio_venta * cantidad,
        )
        for producto, cantidad in lineas
    ])
    return venta


@transaction.atomic
def anular_venta(venta, *, usuario, motivo):
    """Marca la venta como anulada y devuelve al inventario lo que consumió.

    Se usa la receta vigente de cada producto para calcular lo que se repone.
    """
    motivo = (motivo or '').strip()
    if not motivo:
        raise VentaError('Indica el motivo de la anulación.')

    venta = Venta.objects.select_for_update().get(pk=venta.pk)
    if venta.anulada:
        raise VentaError(f'La venta {venta.codigo} ya estaba anulada.')

    detalles = venta.detalles.select_related('producto').prefetch_related(
        Prefetch('producto__receta_insumos', queryset=RecetaInsumo.objects.select_related('insumo'))
    )
    consumo = _consumo_por_insumo([(d.producto, d.cantidad) for d in detalles])
    for insumo in Insumo.objects.filter(pk__in=consumo).order_by('pk'):
        insumo.reponer_stock(consumo[insumo.pk])

    venta.estado = Venta.Estado.ANULADA
    venta.anulada_por = usuario
    venta.fecha_anulacion = timezone.now()
    venta.motivo_anulacion = motivo
    venta.save(update_fields=['estado', 'anulada_por', 'fecha_anulacion', 'motivo_anulacion'])
    return venta
