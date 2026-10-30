from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from core.models import DetalleVenta, Insumo, Merma, Producto, RecetaInsumo, Venta

from .views import InsumoListView, MermaListView, ProductoListView, VentaListView

User = get_user_model()


class ListadosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('admin', password='x')
        cls.admin.groups.add(Group.objects.create(name='Administrador'))
        cls.cafe = Insumo.objects.create(
            nombre='Café', unidad_medida='g', stock_actual=Decimal('100'),
            stock_minimo=Decimal('500'), costo_unitario=Decimal('0.0180'),
        )
        cls.leche = Insumo.objects.create(
            nombre='Leche', unidad_medida='ml', stock_actual=Decimal('9000'),
            stock_minimo=Decimal('1000'), costo_unitario=Decimal('0.0012'), activo=False,
        )
        cls.latte = Producto.objects.create(nombre='Latte', categoria='bebida', precio_venta=Decimal('3.00'))
        cls.galleta = Producto.objects.create(nombre='Galleta', categoria='repostería', precio_venta=Decimal('1.00'))
        RecetaInsumo.objects.create(producto=cls.latte, insumo=cls.cafe, cantidad_requerida=Decimal('18'))
        RecetaInsumo.objects.create(producto=cls.latte, insumo=cls.leche, cantidad_requerida=Decimal('200'))
        cls.venta = Venta.objects.create(usuario_cajero=cls.admin, total=Decimal('6.00'))
        DetalleVenta.objects.create(venta=cls.venta, producto=cls.latte, cantidad=2, subtotal=Decimal('6.00'))
        Venta.objects.create(usuario_cajero=cls.admin, total=Decimal('1.00'))
        Merma.objects.create(insumo=cls.cafe, cantidad=Decimal('10'), causa='otro', usuario_responsable=cls.admin)

    def setUp(self):
        self.client.force_login(self.admin)

    def objetos(self, nombre_url, **params):
        respuesta = self.client.get(reverse(nombre_url), params)
        self.assertEqual(respuesta.status_code, 200)
        return list(respuesta.context['object_list'])

    def test_todas_las_columnas_ordenan_en_ambos_sentidos(self):
        for nombre_url, vista in [
            ('dashboard:insumo_list', InsumoListView),
            ('dashboard:producto_list', ProductoListView),
            ('dashboard:merma_list', MermaListView),
            ('dashboard:venta_list', VentaListView),
        ]:
            for clave in vista.columnas_orden:
                for orden in (clave, f'-{clave}'):
                    with self.subTest(url=nombre_url, orden=orden):
                        self.objetos(nombre_url, orden=orden)

    def test_insumos_filtros(self):
        self.assertEqual(self.objetos('dashboard:insumo_list', stock='bajo'), [self.cafe])
        self.assertEqual(self.objetos('dashboard:insumo_list', estado='inactivos'), [self.leche])
        self.assertEqual(self.objetos('dashboard:insumo_list', q=self.leche.codigo), [self.leche])
        self.assertEqual(self.objetos('dashboard:insumo_list', unidad='g'), [self.cafe])

    def test_productos_costo_margen_y_filtros(self):
        latte = self.objetos('dashboard:producto_list', q='latte')[0]
        # 18 g x 0.018 + 200 ml x 0.0012 = 0.564
        self.assertEqual(round(latte.costo_total, 3), Decimal('0.564'))
        self.assertEqual(round(latte.margen_pct, 1), Decimal('81.2'))
        self.assertEqual(self.objetos('dashboard:producto_list', orden='-margen')[-1], self.latte)
        self.assertEqual(self.objetos('dashboard:producto_list', precio_min='2'), [self.latte])
        self.assertEqual(self.objetos('dashboard:producto_list', categoria='repostería'), [self.galleta])

    def test_ventas_filtros(self):
        self.assertEqual(self.objetos('dashboard:venta_list', producto=self.latte.pk), [self.venta])
        self.assertEqual(self.objetos('dashboard:venta_list', total_min='5'), [self.venta])
        self.assertEqual(self.objetos('dashboard:venta_list', q=self.venta.codigo), [self.venta])
        self.assertEqual(
            self.objetos('dashboard:venta_list', fecha_desde='2000-01-01', fecha_hasta='01/01/2001'), []
        )

    def test_paginacion_y_tamano_de_pagina(self):
        respuesta = self.client.get(reverse('dashboard:venta_list'), {'por_pagina': 10})
        self.assertEqual(respuesta.context['por_pagina'], 10)
        self.assertEqual(respuesta.context['total_resultados'], 2)
        # un tamaño no permitido vuelve al de por defecto
        respuesta = self.client.get(reverse('dashboard:venta_list'), {'por_pagina': 7})
        self.assertEqual(respuesta.context['por_pagina'], 20)

    def test_resumen_de_mermas(self):
        respuesta = self.client.get(reverse('dashboard:merma_list'))
        self.assertEqual(round(respuesta.context['costo_total'], 2), Decimal('0.18'))


class UsuariosYCorteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo_admin = Group.objects.create(name='Administrador')
        cls.grupo_cajero = Group.objects.create(name='Cajero')
        cls.admin = User.objects.create_user('jefa', password='x')
        cls.admin.groups.add(cls.grupo_admin)
        cls.cajero = User.objects.create_user('caja1', password='x')
        cls.cajero.groups.add(cls.grupo_cajero)
        cls.otro = User.objects.create_user('caja2', password='x')
        cls.otro.groups.add(cls.grupo_cajero)
        Venta.objects.create(usuario_cajero=cls.cajero, total=Decimal('7.75'),
                             metodo_pago='efectivo', monto_recibido=Decimal('10'))
        Venta.objects.create(usuario_cajero=cls.otro, total=Decimal('3.00'), metodo_pago='tarjeta')
        Venta.objects.create(usuario_cajero=cls.cajero, total=Decimal('5.00'), estado='anulada')

    def test_crear_usuario_con_rol(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse('dashboard:usuario_create'), {
            'username': 'nuevo', 'first_name': 'Ana', 'last_name': 'Pérez', 'email': 'ana@ejemplo.com',
            'rol': 'Cajero', 'password1': 'CafeSeguro#2026', 'password2': 'CafeSeguro#2026', 'is_active': 'on',
        })
        self.assertEqual(respuesta.status_code, 302)
        nuevo = User.objects.get(username='nuevo')
        self.assertTrue(nuevo.check_password('CafeSeguro#2026'))
        self.assertEqual(list(nuevo.groups.values_list('name', flat=True)), ['Cajero'])

    def test_cambiar_rol_quita_el_anterior(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('dashboard:usuario_update', args=[self.cajero.pk]), {
            'username': 'caja1', 'rol': 'Administrador', 'is_active': 'on',
        })
        self.assertEqual(list(self.cajero.groups.values_list('name', flat=True)), ['Administrador'])

    def test_no_puede_desactivarse_a_si_mismo(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('dashboard:usuario_estado', args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.client.post(reverse('dashboard:usuario_estado', args=[self.otro.pk]))
        self.otro.refresh_from_db()
        self.assertFalse(self.otro.is_active)

    def test_cajero_no_entra_a_usuarios(self):
        self.client.force_login(self.cajero)
        self.assertEqual(self.client.get(reverse('dashboard:usuario_list')).status_code, 403)

    def test_corte_de_caja_admin(self):
        self.client.force_login(self.admin)
        corte = self.client.get(reverse('dashboard:corte_caja')).context['corte']
        self.assertEqual(corte['num_ventas'], 2)
        self.assertEqual(corte['total'], Decimal('10.75'))
        self.assertEqual(corte['efectivo']['cambio'], Decimal('2.25'))
        self.assertEqual(corte['tarjeta']['total'], Decimal('3.00'))
        self.assertEqual(corte['anuladas']['num'], 1)

    def test_cajero_solo_ve_su_corte(self):
        self.client.force_login(self.cajero)
        corte = self.client.get(reverse('dashboard:corte_caja'), {'cajero': self.otro.pk}).context['corte']
        self.assertEqual(corte['cajero'], self.cajero)
        self.assertEqual(corte['total'], Decimal('7.75'))


class ReportesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('admin', password='x')
        cls.admin.groups.add(Group.objects.create(name='Administrador'))
        cls.cajero = User.objects.create_user('caja', password='x')
        cls.cajero.groups.add(Group.objects.create(name='Cajero'))
        cafe = Insumo.objects.create(nombre='Café', unidad_medida='g', stock_actual=Decimal('100'),
                                     stock_minimo=Decimal('500'), costo_unitario=Decimal('0.02'))
        latte = Producto.objects.create(nombre='Latte', categoria='bebida', precio_venta=Decimal('3'))
        RecetaInsumo.objects.create(producto=latte, insumo=cafe, cantidad_requerida=18)
        venta = Venta.objects.create(usuario_cajero=cls.cajero, total=Decimal('6'),
                                     metodo_pago='efectivo', monto_recibido=Decimal('10'))
        DetalleVenta.objects.create(venta=venta, producto=latte, cantidad=2,
                                    precio_unitario=Decimal('3'), subtotal=Decimal('6'))
        Merma.objects.create(insumo=cafe, cantidad=Decimal('5'), causa='otro', usuario_responsable=cls.admin)

    def test_todos_los_reportes_se_generan(self):
        from .reportes.generadores import CATALOGO

        self.client.force_login(self.admin)
        for clave, reporte in CATALOGO.items():
            for formato in ('pdf', 'xlsx'):
                if formato not in reporte:
                    continue
                with self.subTest(reporte=clave, formato=formato):
                    respuesta = self.client.get(reverse('dashboard:reporte', args=[clave, formato]))
                    self.assertEqual(respuesta.status_code, 200)
                    contenido = respuesta.content
                    self.assertTrue(contenido.startswith(b'%PDF' if formato == 'pdf' else b'PK'))

    def test_formato_no_disponible_da_404(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('dashboard:reporte', args=['inventario', 'pdf'])).status_code, 404)

    def test_reporte_de_ventas_en_excel_tiene_las_lineas(self):
        from io import BytesIO

        from openpyxl import load_workbook

        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('dashboard:reporte', args=['ventas', 'xlsx']))
        hoja = load_workbook(BytesIO(respuesta.content)).worksheets[0]
        self.assertEqual(hoja['G6'].value, 'Latte')
        self.assertEqual(hoja['J6'].value, 6)

    def test_exportar_listados(self):
        self.client.force_login(self.admin)
        for nombre in ['insumo_list', 'producto_list', 'merma_list', 'venta_list', 'compra_list', 'proveedor_list']:
            with self.subTest(listado=nombre):
                respuesta = self.client.get(reverse(f'dashboard:{nombre}'), {'exportar': 'xlsx'})
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(respuesta.content.startswith(b'PK'))

    def test_cajero_no_ve_reportes_pero_si_su_corte_en_pdf(self):
        self.client.force_login(self.cajero)
        self.assertEqual(self.client.get(reverse('dashboard:reportes')).status_code, 403)
        respuesta = self.client.get(reverse('dashboard:corte_caja_pdf'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('caja', respuesta['Content-Disposition'])

    def test_pagina_de_reportes_muestra_los_botones(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('dashboard:reportes'))
        self.assertContains(respuesta, reverse('dashboard:reporte', args=['ventas', 'pdf']))
        self.assertContains(respuesta, reverse('dashboard:reporte', args=['inventario', 'xlsx']))


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('admin', password='x')
        cls.admin.groups.add(Group.objects.create(name='Administrador'))
        Venta.objects.create(usuario_cajero=cls.admin, total=Decimal('10'))
        Venta.objects.create(usuario_cajero=cls.admin, total=Decimal('4'), estado='anulada')

    def test_periodos_e_indicadores(self):
        self.client.force_login(self.admin)
        for periodo in ('7', '30', 'mes', 'cualquier-cosa'):
            with self.subTest(periodo=periodo):
                respuesta = self.client.get(reverse('dashboard:index'), {'periodo': periodo})
                self.assertEqual(respuesta.status_code, 200)
                # la venta anulada no cuenta
                self.assertEqual(respuesta.context['kpi']['total_hoy'], Decimal('10'))
                self.assertEqual(respuesta.context['kpi']['num_hoy'], 1)
        self.assertEqual(respuesta.context['periodo'], '7')
