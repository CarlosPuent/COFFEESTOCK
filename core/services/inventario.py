"""Movimientos de inventario que involucran varios insumos a la vez."""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from core.models import Compra, DetalleCompra

CENTAVO = Decimal('0.01')


@transaction.atomic
def registrar_compra(*, usuario, lineas, proveedor=None, fecha=None, numero_factura='', observacion=''):
    """Registra una compra y suma el stock de cada insumo.

    `lineas` es una lista de (insumo, cantidad, monto_pagado). El costo
    unitario de cada línea se calcula como monto_pagado / cantidad, y el
    costo del insumo pasa a ser el promedio ponderado.
    """
    if not lineas:
        raise ValueError('La compra debe tener al menos un insumo.')

    compra = Compra(
        usuario=usuario,
        proveedor=proveedor,
        numero_factura=numero_factura,
        observacion=observacion,
    )
    if fecha is not None:
        compra.fecha = fecha
    compra.save()

    total = Decimal('0')
    # Mismo orden de bloqueo en todas las transacciones: evita bloqueos cruzados.
    for insumo, cantidad, monto in sorted(lineas, key=lambda linea: linea[0].pk):
        monto = Decimal(monto).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        costo_unitario = (monto / cantidad).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        DetalleCompra.objects.create(
            compra=compra,
            insumo=insumo,
            cantidad=cantidad,
            costo_unitario=costo_unitario,
            subtotal=monto,
        )
        insumo.registrar_entrada(cantidad, costo_unitario)
        total += monto

    compra.total = total
    compra.save(update_fields=['total'])
    return compra
