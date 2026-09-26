import datetime
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import DetalleVenta, Insumo, Merma, Producto, RecetaInsumo, Venta

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Llena la base de datos con datos de ejemplo realistas de una cafetería: '
        'insumos, productos con receta, ventas de los últimos 7 días y mermas.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina insumos, productos, recetas, ventas y mermas existentes antes de sembrar.',
        )

    def handle(self, *args, **options):
        reset = options['reset']

        hay_datos = Insumo.objects.exists() or Producto.objects.exists() or Venta.objects.exists()

        if reset:
            self.stdout.write('Eliminando datos existentes (insumos, productos, ventas, mermas)...')
            DetalleVenta.objects.all().delete()
            Venta.objects.all().delete()
            Merma.objects.all().delete()
            RecetaInsumo.objects.all().delete()
            Producto.objects.all().delete()
            Insumo.objects.all().delete()
        elif hay_datos:
            respuesta = input(
                'Ya existen insumos, productos o ventas en la base de datos.\n'
                'Continuar puede duplicar información. ¿Deseas continuar de todas formas? [y/N]: '
            )
            if respuesta.strip().lower() not in ('y', 'yes', 's', 'si', 'sí'):
                self.stdout.write(self.style.WARNING(
                    'Operación cancelada. Vuelve a ejecutar con --reset para limpiar antes de sembrar.'
                ))
                return

        with transaction.atomic():
            insumos = self._crear_insumos()
            productos = self._crear_productos()
            self._crear_recetas(productos, insumos)
            usuarios = self._obtener_usuarios()
            self._crear_ventas(productos, usuarios)
            self._crear_mermas(insumos, usuarios)

        self.stdout.write(self.style.SUCCESS(
            f'Datos de ejemplo creados: {len(insumos)} insumos, {len(productos)} productos, '
            f'{Venta.objects.count()} ventas, {Merma.objects.count()} mermas.'
        ))

    # ------------------------------------------------------------------
    # Insumos
    # ------------------------------------------------------------------

    def _crear_insumos(self):
        # (nombre, unidad, stock_actual, stock_minimo, costo_unitario)
        # Dos insumos quedan deliberadamente por debajo de su mínimo para
        # que el dashboard muestre alertas de stock de inmediato.
        datos = [
            ('Leche entera', Insumo.UnidadMedida.MILILITROS, Decimal('8000'), Decimal('2000'), Decimal('0.02')),
            ('Leche de almendra', Insumo.UnidadMedida.MILILITROS, Decimal('3000'), Decimal('1500'), Decimal('0.04')),
            ('Café en grano arábica', Insumo.UnidadMedida.GRAMOS, Decimal('4000'), Decimal('1000'), Decimal('0.08')),
            ('Café en grano robusta', Insumo.UnidadMedida.GRAMOS, Decimal('350'), Decimal('500'), Decimal('0.06')),
            ('Sirope de vainilla', Insumo.UnidadMedida.MILILITROS, Decimal('1500'), Decimal('500'), Decimal('0.05')),
            ('Sirope de caramelo', Insumo.UnidadMedida.MILILITROS, Decimal('120'), Decimal('500'), Decimal('0.05')),
            ('Harina de trigo', Insumo.UnidadMedida.GRAMOS, Decimal('6000'), Decimal('2000'), Decimal('0.01')),
            ('Azúcar', Insumo.UnidadMedida.GRAMOS, Decimal('5000'), Decimal('1500'), Decimal('0.008')),
            ('Chocolate en polvo', Insumo.UnidadMedida.GRAMOS, Decimal('2500'), Decimal('800'), Decimal('0.03')),
            ('Mantequilla', Insumo.UnidadMedida.GRAMOS, Decimal('3000'), Decimal('1000'), Decimal('0.015')),
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
            ('Espresso', Producto.Categoria.BEBIDA, Decimal('28')),
            ('Americano', Producto.Categoria.BEBIDA, Decimal('30')),
            ('Cappuccino', Producto.Categoria.BEBIDA, Decimal('38')),
            ('Latte Vainilla', Producto.Categoria.BEBIDA, Decimal('42')),
            ('Mocha', Producto.Categoria.BEBIDA, Decimal('45')),
            ('Croissant', Producto.Categoria.REPOSTERIA, Decimal('32')),
            ('Muffin de chocolate', Producto.Categoria.REPOSTERIA, Decimal('35')),
            ('Brownie', Producto.Categoria.REPOSTERIA, Decimal('38')),
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
        recetas = {
            'Espresso': [('Café en grano arábica', 18)],
            'Americano': [('Café en grano arábica', 18)],
            'Cappuccino': [('Café en grano arábica', 18), ('Leche entera', 120)],
            'Latte Vainilla': [
                ('Café en grano arábica', 18), ('Leche entera', 200), ('Sirope de vainilla', 20),
            ],
            'Mocha': [
                ('Café en grano arábica', 18), ('Leche entera', 150), ('Chocolate en polvo', 25),
            ],
            'Croissant': [('Harina de trigo', 80), ('Mantequilla', 40)],
            'Muffin de chocolate': [
                ('Harina de trigo', 60), ('Azúcar', 30), ('Chocolate en polvo', 20),
            ],
            'Brownie': [
                ('Harina de trigo', 50), ('Chocolate en polvo', 40),
                ('Mantequilla', 30), ('Azúcar', 35),
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
    # Ventas (últimos 7 días)
    # ------------------------------------------------------------------

    def _crear_ventas(self, productos, usuarios):
        catalogo = list(productos.values())
        ahora = timezone.now()
        num_ventas = random.randint(15, 20)

        for _ in range(num_ventas):
            momento = ahora - datetime.timedelta(
                days=random.randint(0, 6),
                hours=random.randint(0, 10),
                minutes=random.randint(0, 59),
            )
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
                    venta=venta, producto=producto, cantidad=cantidad, subtotal=subtotal
                )

            Venta.objects.filter(pk=venta.pk).update(total=total, fecha=momento)

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

        for nombre_insumo, cantidad, causa, observacion in datos:
            insumo = insumos.get(nombre_insumo)
            if insumo is None:
                continue

            responsable = random.choice(usuarios)
            momento = ahora - datetime.timedelta(
                days=random.randint(0, 6), hours=random.randint(0, 10)
            )

            merma = Merma.objects.create(
                insumo=insumo,
                cantidad=cantidad,
                causa=causa,
                usuario_responsable=responsable,
                observacion=observacion,
            )
            Merma.objects.filter(pk=merma.pk).update(fecha=momento)
            Insumo.objects.filter(pk=insumo.pk).update(stock_actual=F('stock_actual') - cantidad)
