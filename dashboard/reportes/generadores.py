"""Cada reporte: qué datos usa, en qué formato sale y cómo se ve."""
from core.services.caja import corte_de_caja
from core.templatetags.formato import cantidad, moneda, porcentaje, unidad_corta

from . import datos
from .excel import LibroExcel
from .pdf import ReportePDF


DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']


def fecha_con_dia(fecha):
    return f'{DIAS[fecha.weekday()]} {fecha:%d/%m/%Y}'


def texto_periodo(desde, hasta):
    if desde == hasta:
        return f'{desde:%d/%m/%Y}'
    return f'Del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}'


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def pdf_corte_caja(fecha, usuario, cajero=None):
    corte = corte_de_caja(fecha, cajero=cajero)
    subtitulo = f'{fecha:%d/%m/%Y}' + (f'  ·  Cajero {cajero.get_username()}' if cajero else '  ·  Todos los cajeros')
    pdf = ReportePDF('Corte de caja', subtitulo, usuario)

    pdf.kpis([
        ('Ventas', str(corte['num_ventas']), f'Ticket promedio {moneda(corte["ticket_promedio"])}'),
        ('Total vendido', moneda(corte['total']), 'Sin anulaciones'),
        ('Efectivo', moneda(corte['efectivo']['total']), f'{corte["efectivo"]["num"]} ventas'),
        ('Tarjeta', moneda(corte['tarjeta']['total']), f'{corte["tarjeta"]["num"]} ventas'),
    ])

    pdf.seccion('Arqueo de efectivo')
    pdf.tabla(
        ['Concepto', 'Monto'],
        [
            ['Recibido de clientes', moneda(corte['efectivo']['recibido'])],
            ['Cambio entregado', moneda(corte['efectivo']['cambio'])],
            ['Efectivo cobrado (debe haber en caja, además del fondo)', moneda(corte['efectivo']['total'])],
            ['Efectivo contado', '_______________'],
            ['Diferencia', '_______________'],
        ],
        anchos=[3, 1], derecha=(1,), mantener_junta=True,
    )

    if not cajero and corte['por_cajero']:
        pdf.seccion('Por cajero')
        pdf.tabla(
            ['Cajero', 'Ventas', 'Efectivo', 'Tarjeta', 'Total'],
            [[f['usuario_cajero__username'], f['num'], moneda(f['monto_efectivo']),
              moneda(f['monto_tarjeta']), moneda(f['monto'])] for f in corte['por_cajero']],
            anchos=[3, 1, 1.5, 1.5, 1.5], derecha=(1, 2, 3, 4),
        )

    pdf.seccion('Productos vendidos')
    if corte['productos']:
        pdf.tabla(
            ['Producto', 'Unidades', 'Importe'],
            [[f['producto__nombre'], cantidad(f['unidades']), moneda(f['importe'])] for f in corte['productos']],
            anchos=[4, 1, 1.5], derecha=(1, 2),
            total=['Total', cantidad(sum(f['unidades'] for f in corte['productos'])), moneda(corte['total'])],
        )
    else:
        pdf.vacio('No hubo ventas en esta fecha.')

    if corte['anuladas']['num']:
        pdf.espacio(2)
        pdf.parrafo(
            f'Ventas anuladas: {corte["anuladas"]["num"]} por {moneda(corte["anuladas"]["total"])} '
            '(no se incluyen en los totales).', 'suave',
        )

    pdf.espacio(10)
    pdf.firmas(['Entregó (cajero)', 'Recibió (administrador)'])
    return pdf.generar()


def pdf_ventas_periodo(desde, hasta, usuario):
    v = datos.ventas_periodo(desde, hasta)
    pdf = ReportePDF('Ventas del período', texto_periodo(desde, hasta), usuario)

    pdf.kpis([
        ('Total vendido', moneda(v['total']), f'{v["num"]} ventas'),
        ('Ticket promedio', moneda(v['ticket_promedio']), f'{cantidad(v["unidades"])} productos'),
        ('Costo de insumos', moneda(v['costo_estimado']), 'Según recetas'),
        ('Utilidad bruta', moneda(v['utilidad_estimada']),
         f'Margen {porcentaje(v["margen"])}' if v['margen'] is not None else ''),
    ])

    pdf.seccion('Ventas por día')
    pdf.tabla(
        ['Fecha', 'Ventas', 'Total'],
        [[fecha_con_dia(f['dia']), f['num'], moneda(f['monto'])] for f in v['por_dia']],
        anchos=[3, 1, 1.5], derecha=(1, 2),
        total=['Total', v['num'], moneda(v['total'])],
    )

    pdf.seccion('Por método de pago')
    pdf.tabla(
        ['Método', 'Ventas', 'Total', '% del total'],
        [[f['metodo'], f['num'], moneda(f['monto']),
          porcentaje(f['monto'] / v['total'] * 100) if v['total'] else '—'] for f in v['por_metodo']],
        anchos=[3, 1, 1.5, 1.5], derecha=(1, 2, 3), mantener_junta=True,
    )

    pdf.seccion('Por categoría')
    pdf.tabla(
        ['Categoría', 'Unidades', 'Total'],
        [[f['categoria'], cantidad(f['unidades']), moneda(f['monto'])] for f in v['por_categoria']],
        anchos=[3, 1, 1.5], derecha=(1, 2), mantener_junta=True,
    )

    pdf.seccion('Los 10 productos que más vendieron')
    if v['top_productos']:
        pdf.tabla(
            ['#', 'Producto', 'Unidades', 'Total'],
            [[i, f['producto__nombre'], cantidad(f['unidades']), moneda(f['monto'])]
             for i, f in enumerate(v['top_productos'], start=1)],
            anchos=[0.4, 4, 1, 1.5], derecha=(0, 2, 3),
        )
    else:
        pdf.vacio('No hubo ventas en el período.')

    if v['anuladas_num']:
        pdf.espacio(2)
        pdf.parrafo(
            f'Se anularon {v["anuladas_num"]} ventas por {moneda(v["anuladas_monto"])}; no se incluyen en este reporte.',
            'suave',
        )
    pdf.espacio(2)
    pdf.parrafo(
        'El costo de insumos y la utilidad son estimados con la receta y el costo unitario actual de cada insumo.',
        'suave',
    )
    return pdf.generar()


def pdf_lista_compras(usuario):
    filas = datos.lista_de_compras()
    pdf = ReportePDF('Lista de compras sugerida', 'Insumos en o bajo el stock mínimo', usuario)
    if not filas:
        pdf.vacio('Todos los insumos están sobre su stock mínimo. No hace falta comprar nada por ahora.')
        return pdf.generar()

    total = sum(f['costo_estimado'] for f in filas)
    pdf.kpis([
        ('Insumos a reponer', str(len(filas)), 'En o bajo el mínimo'),
        ('Costo estimado', moneda(total), 'Al costo unitario actual'),
    ])
    pdf.seccion('Qué comprar')
    pdf.tabla(
        ['Código', 'Insumo', 'Stock actual', 'Mínimo', 'Comprar', 'Costo est.', 'Último proveedor'],
        [[
            f['insumo'].codigo, f['insumo'].nombre,
            f'{cantidad(f["insumo"].stock_actual)} {unidad_corta(f["insumo"].unidad_medida)}',
            f'{cantidad(f["insumo"].stock_minimo)} {unidad_corta(f["insumo"].unidad_medida)}',
            f'<b>{cantidad(f["sugerido"])} {unidad_corta(f["insumo"].unidad_medida)}</b>',
            moneda(f['costo_estimado']),
            f['proveedor'].nombre if f['proveedor'] else '—',
        ] for f in filas],
        anchos=[1.1, 2.6, 1.3, 1.2, 1.3, 1.2, 2.3], derecha=(2, 3, 4, 5),
        total=['', 'Total estimado', '', '', '', moneda(total), ''],
    )
    pdf.espacio(2)
    pdf.parrafo('La cantidad sugerida lleva cada insumo al doble de su stock mínimo.', 'suave')
    return pdf.generar()


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def excel_ventas_detalle(desde, hasta, usuario):
    libro = LibroExcel('Ventas detalladas', texto_periodo(desde, hasta), usuario)
    libro.hoja(
        'Ventas',
        [('Folio', 'texto', 12), ('Fecha', 'fechahora', 17), ('Cajero', 'texto', 16),
         ('Pago', 'texto', 11), ('Estado', 'texto', 12), ('Código', 'texto', 11),
         ('Producto', 'texto', 24), ('Cantidad', 'cantidad', 10, True), ('Precio unitario', 'moneda', 14, False),
         ('Subtotal', 'moneda', 13)],
        [[d.venta.codigo, d.venta.fecha, d.venta.usuario_cajero.get_username(),
          d.venta.get_metodo_pago_display(), d.venta.get_estado_display(), d.producto.codigo,
          d.producto.nombre, d.cantidad, d.precio_unitario, d.subtotal]
         for d in datos.ventas_detalle(desde, hasta)],
        totales=True,
    )
    v = datos.ventas_periodo(desde, hasta)
    libro.hoja(
        'Por día',
        [('Fecha', 'fecha', 14), ('Ventas', 'entero', 10, True), ('Total', 'moneda', 14)],
        [[f['dia'], f['num'], f['monto']] for f in v['por_dia']],
        totales=True,
    )
    return libro.generar()


def excel_rentabilidad(desde, hasta, usuario):
    libro = LibroExcel('Rentabilidad por producto', texto_periodo(desde, hasta), usuario)
    libro.hoja(
        'Rentabilidad',
        [('Código', 'texto', 11), ('Producto', 'texto', 24), ('Categoría', 'texto', 13),
         ('Precio', 'moneda', 11, False), ('Costo unitario', 'moneda', 14, False), ('Margen', 'porcentaje', 10),
         ('Unidades vendidas', 'cantidad', 16, True), ('Ingresos', 'moneda', 13), ('Costo total', 'moneda', 13),
         ('Utilidad bruta', 'moneda', 14)],
        [[f['producto'].codigo, f['producto'].nombre, f['producto'].get_categoria_display(),
          f['precio'], f['costo'], f['margen'], f['unidades'], f['ingresos'], f['costo_total'], f['utilidad']]
         for f in datos.rentabilidad_productos(desde, hasta)],
        totales=True,
    )
    return libro.generar()


def excel_inventario(usuario):
    libro = LibroExcel('Inventario valorizado', 'Existencias al momento de generar el reporte', usuario)
    libro.hoja(
        'Inventario',
        [('Código', 'texto', 11), ('Insumo', 'texto', 26), ('Unidad', 'texto', 11),
         ('Stock actual', 'cantidad', 13), ('Stock mínimo', 'cantidad', 13), ('Costo unitario', 'costo', 14),
         ('Valor en inventario', 'moneda', 18), ('Estado', 'texto', 14), ('Conteo físico', 'cantidad', 14)],
        [[i.codigo, i.nombre, i.get_unidad_medida_display(), i.stock_actual, i.stock_minimo,
          i.costo_unitario, i.valor,
          'Inactivo' if not i.activo else ('Bajo mínimo' if i.stock_bajo else 'Normal'), None]
         for i in datos.inventario_valorizado()],
        totales=True,
    )
    return libro.generar()


def excel_mermas(desde, hasta, usuario):
    m = datos.mermas_periodo(desde, hasta)
    libro = LibroExcel('Mermas del período', texto_periodo(desde, hasta), usuario)
    libro.hoja(
        'Mermas',
        [('Código', 'texto', 11), ('Fecha', 'fechahora', 17), ('Insumo', 'texto', 24), ('Unidad', 'texto', 10),
         ('Cantidad', 'cantidad', 11), ('Causa', 'texto', 17), ('Costo', 'moneda', 12),
         ('Responsable', 'texto', 16), ('Observación', 'texto', 40)],
        [[x.codigo, x.fecha, x.insumo.nombre, unidad_corta(x.insumo.unidad_medida), x.cantidad,
          x.get_causa_display(), x.costo_merma, x.usuario_responsable.get_username(), x.observacion]
         for x in m['mermas']],
        totales=True,
    )
    libro.hoja(
        'Por causa',
        [('Causa', 'texto', 20), ('Mermas', 'entero', 10, True), ('Costo', 'moneda', 13)],
        [[f['causa'], f['num'], f['costo']] for f in m['por_causa']],
        totales=True,
    )
    return libro.generar()


def excel_compras(desde, hasta, usuario):
    c = datos.compras_periodo(desde, hasta)
    libro = LibroExcel('Compras del período', texto_periodo(desde, hasta), usuario)
    libro.hoja(
        'Compras',
        [('Folio', 'texto', 11), ('Fecha', 'fecha', 12), ('Proveedor', 'texto', 26), ('Factura', 'texto', 13),
         ('Insumo', 'texto', 24), ('Cantidad', 'cantidad', 11), ('Unidad', 'texto', 9),
         ('Costo unitario', 'costo', 14), ('Subtotal', 'moneda', 12), ('Registró', 'texto', 15)],
        [[d.compra.codigo, d.compra.fecha, d.compra.proveedor.nombre if d.compra.proveedor else 'Sin proveedor',
          d.compra.numero_factura, d.insumo.nombre, d.cantidad, unidad_corta(d.insumo.unidad_medida),
          d.costo_unitario, d.subtotal, d.compra.usuario.get_username()]
         for d in c['detalles']],
        totales=True,
    )
    libro.hoja(
        'Por proveedor',
        [('Proveedor', 'texto', 28), ('Compras', 'entero', 10, True), ('Total', 'moneda', 14)],
        [[f['proveedor'], f['num'], f['monto']] for f in c['por_proveedor']],
        totales=True,
    )
    return libro.generar()


# Catálogo que usan la página de Reportes y la vista que los descarga.
CATALOGO = {
    'ventas': {
        'titulo': 'Ventas del período',
        'descripcion': 'Resumen ejecutivo: total, ticket promedio, utilidad estimada, ventas por día, '
                       'por método de pago y por categoría, y los productos que más venden.',
        'icono': 'bi-graph-up-arrow', 'grupo': 'Ventas',
        'pdf': pdf_ventas_periodo, 'xlsx': excel_ventas_detalle, 'periodo': True,
        'nota_xlsx': 'El Excel trae cada producto vendido, línea por línea.',
    },
    'rentabilidad': {
        'titulo': 'Rentabilidad por producto',
        'descripcion': 'Precio, costo según receta, margen, unidades vendidas, ingresos y utilidad bruta '
                       'de cada producto en el período.',
        'icono': 'bi-pie-chart', 'grupo': 'Ventas',
        'xlsx': excel_rentabilidad, 'periodo': True,
    },
    'lista-compras': {
        'titulo': 'Lista de compras sugerida',
        'descripcion': 'Insumos en o bajo el mínimo, cuánto comprar para llegar al doble del mínimo, '
                       'costo estimado y último proveedor. Para enviar o imprimir.',
        'icono': 'bi-cart-check', 'grupo': 'Inventario',
        'pdf': pdf_lista_compras, 'periodo': False,
    },
    'inventario': {
        'titulo': 'Inventario valorizado',
        'descripcion': 'Existencias, costo unitario y valor de cada insumo, con una columna para el '
                       'conteo físico.',
        'icono': 'bi-box-seam', 'grupo': 'Inventario',
        'xlsx': excel_inventario, 'periodo': False,
    },
    'mermas': {
        'titulo': 'Mermas del período',
        'descripcion': 'Cada merma con su costo, responsable y observación, y el resumen por causa.',
        'icono': 'bi-exclamation-triangle', 'grupo': 'Inventario',
        'xlsx': excel_mermas, 'periodo': True,
    },
    'compras': {
        'titulo': 'Compras del período',
        'descripcion': 'Cada insumo comprado con su costo y proveedor, y el total por proveedor.',
        'icono': 'bi-bag', 'grupo': 'Compras',
        'xlsx': excel_compras, 'periodo': True,
    },
}
