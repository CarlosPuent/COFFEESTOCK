import datetime
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from core.models import (
    Compra, DetalleCompra, DetalleVenta, Insumo, Merma, Producto, Proveedor, RecetaInsumo, Venta,
)

User = get_user_model()

# En orden: primero lo que depende de otros modelos.
MODELOS_A_REINICIAR = [
    DetalleVenta, Venta, Merma, DetalleCompra, Compra, Proveedor, RecetaInsumo, Producto, Insumo,
]


class Command(BaseCommand):
    help = (
        'Llena la base de datos con datos de ejemplo realistas de una cafetería: '
        'insumos, productos con receta, proveedores, compras, ventas de los '
        'últimos 7 días y mermas.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina los datos del negocio (no los usuarios) antes de sembrar.',
        )

    def handle(self, *args, **options):
        reset = options['reset']

        hay_datos = Insumo.objects.exists() or Producto.objects.exists() or Venta.objects.exists()

        if not reset and hay_datos:
            respuesta = input(
                'Ya existen insumos, productos o ventas en la base de datos.\n'
                'Continuar puede duplicar información. ¿Deseas continuar de todas formas? [y/N]: '
            )
            if respuesta.strip().lower() not in ('y', 'yes', 's', 'si', 'sí'):
                self.stdout.write(self.style.WARNING(
                    'Operación cancelada. Vuelve a ejecutar con --reset para limpiar antes de sembrar.'
                ))
                return

        # Borrado y carga en una sola transacción: si algo falla, no se pierde nada.
        with transaction.atomic():
            if reset:
                self.stdout.write('Eliminando datos existentes...')
                for modelo in MODELOS_A_REINICIAR:
                    modelo.objects.all().delete()
                self._reiniciar_numeracion(MODELOS_A_REINICIAR)

            insumos = self._crear_insumos()
            productos = self._crear_productos()
            self._crear_recetas(productos, insumos)
            usuarios = self._obtener_usuarios()
            proveedores = self._crear_proveedores()
            self._crear_compras(insumos, proveedores, usuarios)
            self._crear_ventas(productos, usuarios)
            self._crear_mermas(insumos, usuarios)

        self.stdout.write(self.style.SUCCESS(
            f'Datos de ejemplo creados: {len(insumos)} insumos, {len(productos)} productos, '
            f'{len(proveedores)} proveedores, {Compra.objects.count()} compras, '
            f'{Venta.objects.count()} ventas, {Merma.objects.count()} mermas.'
        ))

    def _reiniciar_numeracion(self, modelos):
        """Hace que los IDs vuelvan a empezar en 1 después de --reset."""
        if connection.vendor != 'microsoft':
            return
        with connection.cursor() as cursor:
            for modelo in modelos:
                tabla = modelo._meta.db_table
                # Si la tabla nunca tuvo filas, RESEED 0 haría que el primer
                # ID fuera 0, así que solo se reinicia si ya se usó.
                cursor.execute(
                    'SELECT CAST(last_value AS bigint) FROM sys.identity_columns WHERE object_id = OBJECT_ID(%s)',
                    [tabla],
                )
                fila = cursor.fetchone()
                if fila and fila[0] is not None:
                    cursor.execute(f"DBCC CHECKIDENT ('{tabla}', RESEED, 0) WITH NO_INFOMSGS")

    # ------------------------------------------------------------------
    # Insumos
    # ------------------------------------------------------------------

    def _crear_insumos(self):
        # (nombre, unidad, stock_actual, stock_minimo, costo_unitario)
        # Dos insumos quedan deliberadamente por debajo de su mínimo para
        # que el dashboard muestre alertas de stock de inmediato.
        datos = [
            ('Leche entera', Insumo.UnidadMedida.MILILITROS, Decimal('8000'), Decimal('2000'), Decimal('0.0012')),
            ('Leche de almendra', Insumo.UnidadMedida.MILILITROS, Decimal('3000'), Decimal('1500'), Decimal('0.0035')),
            ('Café en grano arábica', Insumo.UnidadMedida.GRAMOS, Decimal('4000'), Decimal('1000'), Decimal('0.0220')),
            ('Café en grano robusta', Insumo.UnidadMedida.GRAMOS, Decimal('350'), Decimal('500'), Decimal('0.0150')),
            ('Sirope de vainilla', Insumo.UnidadMedida.MILILITROS, Decimal('1500'), Decimal('500'), Decimal('0.0120')),
            ('Sirope de caramelo', Insumo.UnidadMedida.MILILITROS, Decimal('120'), Decimal('500'), Decimal('0.0120')),
            ('Harina de trigo', Insumo.UnidadMedida.GRAMOS, Decimal('6000'), Decimal('2000'), Decimal('0.0012')),
            ('Azúcar', Insumo.UnidadMedida.GRAMOS, Decimal('5000'), Decimal('1500'), Decimal('0.0011')),
            ('Chocolate en polvo', Insumo.UnidadMedida.GRAMOS, Decimal('2500'), Decimal('800'), Decimal('0.0090')),
            ('Mantequilla', Insumo.UnidadMedida.GRAMOS, Decimal('3000'), Decimal('1000'), Decimal('0.0080')),
            ('Huevo', Insumo.UnidadMedida.UNIDAD, Decimal('60'), Decimal('24'), Decimal('0.1500')),
            ('Vaso para llevar 12 oz', Insumo.UnidadMedida.UNIDAD, Decimal('300'), Decimal('100'), Decimal('0.1200')),
        ]

        insumos = {}
        for nombre, unidad, stock_actual, stock_minimo, costo in datos:
            insumo, _ = Insumo.objects.update_or_create(
                nombre=nombre,
                defaults=dict(
                    unidad_medida=unidad,
                    stock_actual=stock_actual,
                    stock_minimo=stock_minimo,
                    costo_unitario=costo,
                    activo=True,
                    alerta_pendiente=stock_actual <= stock_minimo,
                ),
            )
            insumos[nombre] = insumo
        return insumos

    # ------------------------------------------------------------------
    # Productos
    # ------------------------------------------------------------------

    def _crear_productos(self):
        datos = [
            ('Espresso', Producto.Categoria.BEBIDA, Decimal('1.75')),
            ('Americano', Producto.Categoria.BEBIDA, Decimal('2.00')),
            ('Cappuccino', Producto.Categoria.BEBIDA, Decimal('2.75')),
            ('Latte Vainilla', Producto.Categoria.BEBIDA, Decimal('3.25')),
            ('Mocha', Producto.Categoria.BEBIDA, Decimal('3.50')),
            ('Croissant', Producto.Categoria.REPOSTERIA, Decimal('2.25')),
            ('Muffin de chocolate', Producto.Categoria.REPOSTERIA, Decimal('2.50')),
            ('Brownie', Producto.Categoria.REPOSTERIA, Decimal('2.75')),
        ]

        productos = {}
        for nombre, categoria, precio in datos:
            producto, _ = Producto.objects.update_or_create(
                nombre=nombre,
                defaults=dict(categoria=categoria, precio_venta=precio, activo=True),
            )
            productos[nombre] = producto
        return productos

    # ------------------------------------------------------------------
    # Recetas
    # ------------------------------------------------------------------

    def _crear_recetas(self, productos, insumos):
        vaso = ('Vaso para llevar 12 oz', 1)
        recetas = {
            'Espresso': [('Café en grano arábica', 18), vaso],
            'Americano': [('Café en grano arábica', 18), vaso],
            'Cappuccino': [('Café en grano arábica', 18), ('Leche entera', 120), vaso],
            'Latte Vainilla': [
                ('Café en grano arábica', 18), ('Leche entera', 200), ('Sirope de vainilla', 20), vaso,
            ],
            'Mocha': [
                ('Café en grano arábica', 18), ('Leche entera', 150), ('Chocolate en polvo', 25), vaso,
            ],
            'Croissant': [('Harina de trigo', 80), ('Mantequilla', 40)],
            'Muffin de chocolate': [
                ('Harina de trigo', 60), ('Azúcar', 30), ('Chocolate en polvo', 20), ('Huevo', 1),
            ],
            'Brownie': [
                ('Harina de trigo', 50), ('Chocolate en polvo', 40),
                ('Mantequilla', 30), ('Azúcar', 35), ('Huevo', 1),
            ],
        }

        for nombre_producto, items in recetas.items():
            producto = productos[nombre_producto]
            for nombre_insumo, cantidad in items:
                RecetaInsumo.objects.update_or_create(
                    producto=producto,
                    insumo=insumos[nombre_insumo],
                    defaults={'cantidad_requerida': Decimal(cantidad)},
                )

    # ------------------------------------------------------------------
    # Usuarios responsables
    # ------------------------------------------------------------------

    def _obtener_usuarios(self):
        usuarios = list(
            User.objects.filter(username__in=['cajero1', 'admin_coffeestock'])
        )
        if not usuarios:
            self.stdout.write(self.style.WARNING(
                'No se encontraron los usuarios "cajero1" / "admin_coffeestock". '
                'Ejecuta primero "python manage.py create_test_users". '
                'Se intentará usar otro usuario disponible.'
            ))
            usuarios = list(User.objects.all()[:1])

        if not usuarios:
            raise CommandError(
                'No hay ningún usuario en la base de datos para asignar como '
                'cajero/responsable. Crea uno primero (create_test_users o createsuperuser).'
            )
        return usuarios

    # ------------------------------------------------------------------
    # Proveedores y compras
    # ------------------------------------------------------------------

    def _crear_proveedores(self):
        datos = [
            ('Beneficio Las Nubes', 'Marta Rivas', '2250-1100', 'ventas@lasnubes.example'),
            ('Lácteos del Valle', 'José Hernández', '2260-2200', 'pedidos@lacteosdelvalle.example'),
            ('Distribuidora La Despensa', 'Ana Martínez', '2270-3300', ''),
            ('Empaques Centroamérica', 'Luis Pineda', '2280-4400', 'info@empaquesca.example'),
        ]
        proveedores = {}
        for nombre, contacto, telefono, correo in datos:
            proveedor, _ = Proveedor.objects.update_or_create(
                nombre=nombre,
                defaults=dict(contacto=contacto, telefono=telefono, correo=correo, activo=True),
            )
            proveedores[nombre] = proveedor
        return proveedores

    def _crear_compras(self, insumos, proveedores, usuarios):
        """Historial de compras de las últimas dos semanas.

        Es solo historial: el stock inicial de los insumos ya las incluye, así
        que no se vuelve a sumar. Se usa el costo actual de cada insumo para
        que el costo promedio no cambie.
        """
        responsable = next((u for u in usuarios if u.username == 'admin_coffeestock'), usuarios[0])
        ahora = timezone.now()
        compras = [
            (13, 'Beneficio Las Nubes', 'F-1045', [
                ('Café en grano arábica', 5000), ('Café en grano robusta', 2000)]),
            (12, 'Lácteos del Valle', 'LV-2210', [
                ('Leche entera', 12000), ('Leche de almendra', 4000), ('Mantequilla', 2000)]),
            (10, 'Distribuidora La Despensa', 'D-778', [
                ('Harina de trigo', 5000), ('Azúcar', 5000), ('Chocolate en polvo', 2000),
                ('Sirope de vainilla', 1000), ('Huevo', 60)]),
            (9, 'Empaques Centroamérica', 'EC-5521', [('Vaso para llevar 12 oz', 500)]),
            (5, 'Lácteos del Valle', 'LV-2287', [('Leche entera', 6000)]),
            (2, 'Distribuidora La Despensa', '', [('Azúcar', 2000), ('Huevo', 30)]),
        ]
        for dias, nombre_proveedor, factura, lineas in compras:
            fecha = (ahora - datetime.timedelta(days=dias)).replace(hour=14, minute=30)
            compra = Compra.objects.create(
                proveedor=proveedores[nombre_proveedor],
                usuario=responsable,
                fecha=fecha,
                numero_factura=factura,
            )
            total = Decimal('0')
            for nombre_insumo, cantidad in lineas:
                insumo = insumos[nombre_insumo]
                subtotal = (insumo.costo_unitario * cantidad).quantize(Decimal('0.01'))
                DetalleCompra.objects.create(
                    compra=compra, insumo=insumo, cantidad=Decimal(cantidad),
                    costo_unitario=insumo.costo_unitario, subtotal=subtotal,
                )
                total += subtotal
            Compra.objects.filter(pk=compra.pk).update(total=total, fecha_registro=fecha)

    # ------------------------------------------------------------------
    # Ventas (últimos 7 días)
    # ------------------------------------------------------------------

    def _crear_ventas(self, productos, usuarios):
        catalogo = list(productos.values())
        ahora = timezone.now()
        num_ventas = random.randint(15, 20)

        # Se generan las fechas primero y se ordenan, para que los números de
        # venta vayan en el mismo orden que las fechas.
        momentos = sorted(
            ahora - datetime.timedelta(
                days=random.randint(0, 6),
                hours=random.randint(0, 10),
                minutes=random.randint(0, 59),
            )
            for _ in range(num_ventas)
        )

        for momento in momentos:
            cajero = random.choice(usuarios)
            num_lineas = random.randint(1, 3)
            productos_venta = random.sample(catalogo, k=min(num_lineas, len(catalogo)))

            venta = Venta.objects.create(usuario_cajero=cajero, total=Decimal('0'))

            total = Decimal('0')
            for producto in productos_venta:
                cantidad = Decimal(random.randint(1, 3))
                subtotal = producto.precio_venta * cantidad
                total += subtotal
                DetalleVenta.objects.create(
                    venta=venta, producto=producto, cantidad=cantidad,
                    precio_unitario=producto.precio_venta, subtotal=subtotal,
                )

            # 7 de cada 10 ventas en efectivo, con el billete más cercano.
            if random.random() < 0.7:
                metodo = Venta.MetodoPago.EFECTIVO
                billete = random.choice([1, 5, 10, 20])
                recibido = (total / billete).to_integral_value(rounding='ROUND_CEILING') * billete
            else:
                metodo, recibido = Venta.MetodoPago.TARJETA, None

            Venta.objects.filter(pk=venta.pk).update(
                total=total, fecha=momento, metodo_pago=metodo, monto_recibido=recibido,
            )

        # Una venta anulada, para mostrar cómo se ve en el listado y el corte.
        anulada = Venta.objects.order_by('fecha').first()
        if anulada is not None:
            administrador = next(
                (u for u in usuarios if u.username == 'admin_coffeestock'), usuarios[0]
            )
            Venta.objects.filter(pk=anulada.pk).update(
                estado=Venta.Estado.ANULADA,
                anulada_por=administrador,
                fecha_anulacion=anulada.fecha + datetime.timedelta(minutes=5),
                motivo_anulacion='El cliente cambió su pedido.',
            )

    # ------------------------------------------------------------------
    # Mermas
    # ------------------------------------------------------------------

    def _crear_mermas(self, insumos, usuarios):
        ahora = timezone.now()
        datos = [
            ('Leche entera', Decimal('300'), Merma.Causa.CADUCIDAD,
             'Leche vencida encontrada en refrigerador.'),
            ('Café en grano robusta', Decimal('50'), Merma.Causa.MALA_PREPARACION,
             'Molienda incorrecta, lote desechado.'),
            ('Harina de trigo', Decimal('150'), Merma.Causa.OTRO,
             'Bolsa dañada durante el almacenamiento.'),
            ('Sirope de caramelo', Decimal('30'), Merma.Causa.CADUCIDAD,
             'Botella abierta fuera de fecha de consumo.'),
        ]

        # Fechas ordenadas, para que los números de merma sigan la cronología.
        momentos = sorted(
            ahora - datetime.timedelta(
                days=random.randint(0, 6), hours=random.randint(0, 10), minutes=random.randint(0, 59)
            )
            for _ in datos
        )

        for (nombre_insumo, cantidad, causa, observacion), momento in zip(datos, momentos):
            insumo = insumos.get(nombre_insumo)
            if insumo is None:
                continue

            responsable = random.choice(usuarios)

            merma = Merma.objects.create(
                insumo=insumo,
                cantidad=cantidad,
                causa=causa,
                usuario_responsable=responsable,
                observacion=observacion,
            )
            Merma.objects.filter(pk=merma.pk).update(fecha=momento)
            Insumo.objects.filter(pk=insumo.pk).update(stock_actual=F('stock_actual') - cantidad)
