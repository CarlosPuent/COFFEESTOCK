"""Consultas de los reportes. Cada función devuelve datos listos para
llevar a PDF o a Excel; ninguna sabe de formatos."""
import datetime
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from core.models import Compra, DetalleCompra, DetalleVenta, Insumo, Merma, Producto, Venta

CERO = Decimal('0')
DINERO = DecimalField(max_digits=28, decimal_places=6)


def rango(desde, hasta):
    inicio = timezone.make_aware(datetime.datetime.combine(desde, datetime.time.min))
    fin = timezone.make_aware(datetime.datetime.combine(hasta, datetime.time.max))
    return inicio, fin


def _suma(qs, campo):
    return qs.aggregate(t=Coalesce(Sum(campo), CERO))['t']


def _costos_de_receta():
    """{producto_id: costo de una unidad según la receta y el costo actual}."""
    costos = defaultdict(Decimal)
    for producto_id, cantidad, costo in Producto.objects.values_list(
        'pk', 'receta_insumos__cantidad_requerida', 'receta_insumos__insumo__costo_unitario',
    ):
        if cantidad is not None:
            costos[producto_id] += cantidad * costo
    return costos


# ---------------------------------------------------------------------------
# Ventas
# ---------------------------------------------------------------------------

def ventas_periodo(desde, hasta):
    inicio, fin = rango(desde, hasta)
    ventas = Venta.objects.filter(fecha__range=(inicio, fin))
    completadas = ventas.completadas()
    detalles = DetalleVenta.objects.filter(venta__in=completadas)

    num = completadas.count()
    total = _suma(completadas, 'total')
    costos = _costos_de_receta()
    costo_total = sum(
        (costos[pid] * cant for pid, cant in detalles.values_list('producto_id', 'cantidad')), CERO,
    )

    por_dia_db = {
        fila['dia']: fila
        for fila in completadas.annotate(dia=TruncDate('fecha'))
        .values('dia').annotate(num=Count('id'), monto=Coalesce(Sum('total'), CERO))
    }
    por_dia = []
    dia = desde
    while dia <= hasta:
        fila = por_dia_db.get(dia, {})
        por_dia.append({'dia': dia, 'num': fila.get('num', 0), 'monto': fila.get('monto', CERO)})
        dia += datetime.timedelta(days=1)

    por_metodo = [
        {
            'metodo': etiqueta,
            'num': completadas.filter(metodo_pago=valor).count(),
            'monto': _suma(completadas.filter(metodo_pago=valor), 'total'),
        }
        for valor, etiqueta in Venta.MetodoPago.choices
    ]

    categorias = dict(Producto.Categoria.choices)
    por_categoria = [
        {
            'categoria': categorias.get(fila['producto__categoria'], fila['producto__categoria']),
            'unidades': fila['unidades'],
            'monto': fila['monto'],
        }
        for fila in detalles.values('producto__categoria')
        .annotate(unidades=Coalesce(Sum('cantidad'), CERO), monto=Coalesce(Sum('subtotal'), CERO))
        .order_by('-monto')
    ]

    top_productos = list(
        detalles.values('producto__nombre')
        .annotate(unidades=Coalesce(Sum('cantidad'), CERO), monto=Coalesce(Sum('subtotal'), CERO))
        .order_by('-monto')[:10]
    )

    anuladas = ventas.filter(estado=Venta.Estado.ANULADA)
    return {
        'num': num,
        'total': total,
        'ticket_promedio': total / num if num else CERO,
        'unidades': _suma(detalles, 'cantidad'),
        'costo_estimado': costo_total,
        'utilidad_estimada': total - costo_total,
        'margen': (total - costo_total) / total * 100 if total else None,
        'por_dia': por_dia,
        'por_metodo': por_metodo,
        'por_categoria': por_categoria,
        'top_productos': top_productos,
        'anuladas_num': anuladas.count(),
        'anuladas_monto': _suma(anuladas, 'total'),
    }


def ventas_detalle(desde, hasta):
    """Una fila por producto vendido, incluidas las ventas anuladas."""
    inicio, fin = rango(desde, hasta)
    return (
        DetalleVenta.objects.filter(venta__fecha__range=(inicio, fin))
        .select_related('venta__usuario_cajero', 'producto')
        .order_by('venta__fecha', 'venta_id', 'id')
    )


def rentabilidad_productos(desde, hasta):
    inicio, fin = rango(desde, hasta)
    costos = _costos_de_receta()
    vendidos = {
        fila['producto_id']: fila
        for fila in DetalleVenta.objects.filter(
            venta__fecha__range=(inicio, fin), venta__estado=Venta.Estado.COMPLETADA,
        ).values('producto_id').annotate(
            unidades=Coalesce(Sum('cantidad'), CERO), ingresos=Coalesce(Sum('subtotal'), CERO),
        )
    }
    filas = []
    for producto in Producto.objects.order_by('categoria', 'nombre'):
        costo = costos[producto.pk]
        venta = vendidos.get(producto.pk, {})
        unidades = venta.get('unidades', CERO)
        ingresos = venta.get('ingresos', CERO)
        costo_total = costo * unidades
        filas.append({
            'producto': producto,
            'precio': producto.precio_venta,
            'costo': costo,
            'margen': (producto.precio_venta - costo) / producto.precio_venta * 100 if producto.precio_venta else None,
            'unidades': unidades,
            'ingresos': ingresos,
            'costo_total': costo_total,
            'utilidad': ingresos - costo_total,
        })
    filas.sort(key=lambda f: f['utilidad'], reverse=True)
    return filas


# ---------------------------------------------------------------------------
# Inventario
# ---------------------------------------------------------------------------

def inventario_valorizado():
    return Insumo.objects.annotate(
        valor=ExpressionWrapper(F('stock_actual') * F('costo_unitario'), output_field=DINERO),
    ).order_by('nombre')


def lista_de_compras():
    """Insumos en o bajo el mínimo, con la cantidad sugerida para llegar
    al doble del mínimo y el último proveedor que los vendió."""
    filas = []
    for insumo in Insumo.objects.filter(activo=True, stock_actual__lte=F('stock_minimo')).order_by('nombre'):
        sugerido = max(insumo.stock_minimo * 2 - insumo.stock_actual, CERO)
        ultima = (
            DetalleCompra.objects.filter(insumo=insumo, compra__proveedor__isnull=False)
            .select_related('compra__proveedor').order_by('-compra__fecha').first()
        )
        filas.append({
            'insumo': insumo,
            'sugerido': sugerido,
            'costo_estimado': sugerido * insumo.costo_unitario,
            'proveedor': ultima.compra.proveedor if ultima else None,
        })
    return filas


def mermas_periodo(desde, hasta):
    inicio, fin = rango(desde, hasta)
    mermas = (
        Merma.objects.filter(fecha__range=(inicio, fin))
        .select_related('insumo', 'usuario_responsable')
        .annotate(costo_merma=ExpressionWrapper(F('cantidad') * F('insumo__costo_unitario'), output_field=DINERO))
        .order_by('fecha')
    )
    causas = dict(Merma.Causa.choices)
    por_causa = [
        {'causa': causas.get(f['causa'], f['causa']), 'num': f['num'], 'costo': f['costo']}
        for f in mermas.values('causa').annotate(num=Count('id'), costo=Coalesce(Sum('costo_merma'), CERO))
        .order_by('-costo')
    ]
    return {'mermas': mermas, 'por_causa': por_causa, 'total': _suma(mermas, 'costo_merma')}


def compras_periodo(desde, hasta):
    inicio, fin = rango(desde, hasta)
    detalles = (
        DetalleCompra.objects.filter(compra__fecha__range=(inicio, fin))
        .select_related('compra__proveedor', 'compra__usuario', 'insumo')
        .order_by('compra__fecha', 'compra_id', 'id')
    )
    compras = Compra.objects.filter(fecha__range=(inicio, fin))
    por_proveedor = [
        {'proveedor': f['proveedor__nombre'] or 'Sin proveedor', 'num': f['num'], 'monto': f['monto']}
        for f in compras.values('proveedor__nombre')
        .annotate(num=Count('id'), monto=Coalesce(Sum('total'), CERO)).order_by('-monto')
    ]
    return {'detalles': detalles, 'por_proveedor': por_proveedor, 'total': _suma(compras, 'total')}
