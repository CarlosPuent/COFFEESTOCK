"""Corte de caja: resumen de lo vendido en un día (o en un rango)."""
import datetime
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, ExtractHour
from django.utils import timezone

from core.models import DetalleVenta, Venta

CERO = Decimal('0')


def _rango_del_dia(fecha_desde, fecha_hasta=None):
    fecha_hasta = fecha_hasta or fecha_desde
    inicio = timezone.make_aware(datetime.datetime.combine(fecha_desde, datetime.time.min))
    fin = timezone.make_aware(datetime.datetime.combine(fecha_hasta, datetime.time.max))
    return inicio, fin


def corte_de_caja(fecha_desde, fecha_hasta=None, cajero=None):
    inicio, fin = _rango_del_dia(fecha_desde, fecha_hasta)
    ventas = Venta.objects.filter(fecha__range=(inicio, fin))
    if cajero is not None:
        ventas = ventas.filter(usuario_cajero=cajero)
    completadas = ventas.completadas()

    def suma(qs, campo='total'):
        return qs.aggregate(t=Coalesce(Sum(campo), CERO))['t']

    efectivo = completadas.filter(metodo_pago=Venta.MetodoPago.EFECTIVO)
    tarjeta = completadas.filter(metodo_pago=Venta.MetodoPago.TARJETA)
    anuladas = ventas.filter(estado=Venta.Estado.ANULADA)

    num_ventas = completadas.count()
    total = suma(completadas)
    total_efectivo = suma(efectivo)
    con_recibido = efectivo.exclude(monto_recibido=None)
    recibido_efectivo = suma(con_recibido, 'monto_recibido')
    cambio_entregado = recibido_efectivo - suma(con_recibido)

    por_cajero = list(
        completadas.values('usuario_cajero__username')
        .annotate(
            num=Count('id'),
            monto=Coalesce(Sum('total'), CERO),
            monto_efectivo=Coalesce(Sum('total', filter=Q(metodo_pago=Venta.MetodoPago.EFECTIVO)), CERO),
            monto_tarjeta=Coalesce(Sum('total', filter=Q(metodo_pago=Venta.MetodoPago.TARJETA)), CERO),
        )
        .order_by('-monto')
    )

    productos = list(
        DetalleVenta.objects.filter(venta__in=completadas)
        .values('producto__nombre')
        .annotate(unidades=Coalesce(Sum('cantidad'), CERO), importe=Coalesce(Sum('subtotal'), CERO))
        .order_by('-importe')
    )

    horas = {
        fila['hora']: fila
        for fila in completadas.annotate(hora=ExtractHour('fecha'))
        .values('hora')
        .annotate(num=Count('id'), monto=Coalesce(Sum('total'), CERO))
    }
    por_hora = [
        {'hora': h, 'num': horas[h]['num'], 'monto': horas[h]['monto']}
        for h in sorted(horas)
    ]

    return {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta or fecha_desde,
        'cajero': cajero,
        'num_ventas': num_ventas,
        'total': total,
        'ticket_promedio': (total / num_ventas) if num_ventas else CERO,
        'efectivo': {
            'num': efectivo.count(),
            'total': total_efectivo,
            'recibido': recibido_efectivo,
            'cambio': cambio_entregado,
        },
        'tarjeta': {'num': tarjeta.count(), 'total': suma(tarjeta)},
        'anuladas': {'num': anuladas.count(), 'total': suma(anuladas)},
        'por_cajero': por_cajero,
        'productos': productos,
        'por_hora': por_hora,
        'ventas': completadas.select_related('usuario_cajero').order_by('fecha'),
    }
