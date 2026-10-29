import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from python_http_client.exceptions import ForbiddenError

from core.models import Compra, Insumo, Producto, RecetaInsumo
from core.services.alertas import enviar_alerta_stock, enviar_correo

User = get_user_model()

CONSOLA = dict(
    ALERTA_EMAIL_PROVEEDOR='consola',
    ALERTA_EMAIL_DESTINATARIOS=['dueno@ejemplo.com'],
    DEFAULT_FROM_EMAIL='alertas@coffeestock.local',
)
SENDGRID = dict(
    ALERTA_EMAIL_PROVEEDOR='sendgrid',
    ALERTA_EMAIL_DESTINATARIOS=['dueno@ejemplo.com'],
    SENDGRID_API_KEY='SG.prueba',
    SENDGRID_FROM_EMAIL='verificado@ejemplo.com',
    DEFAULT_FROM_EMAIL='verificado@ejemplo.com',
)


def crear_insumo(**kwargs):
    datos = dict(
        nombre='Leche', unidad_medida='ml', stock_actual=Decimal('1000'),
        stock_minimo=Decimal('500'), costo_unitario=Decimal('0.02'),
    )
    datos.update(kwargs)
    return Insumo.objects.create(**datos)


@override_settings(**CONSOLA)
class AlertaPorVentaTests(TestCase):
    def setUp(self):
        self.cajero = User.objects.create_user('cajero', password='x')
        self.cajero.groups.add(Group.objects.create(name='Cajero'))
        self.client.force_login(self.cajero)

        self.leche = crear_insumo()
        self.cafe = crear_insumo(nombre='Café', unidad_medida='g', stock_actual=Decimal('100'),
                                 stock_minimo=Decimal('0'))
        self.latte = Producto.objects.create(nombre='Latte', categoria='bebida', precio_venta=40)
        RecetaInsumo.objects.create(producto=self.latte, insumo=self.leche, cantidad_requerida=300)
        RecetaInsumo.objects.create(producto=self.latte, insumo=self.cafe, cantidad_requerida=5)

    def vender(self, cantidad):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse('pos:confirmar_venta'),
                data=json.dumps({'items': [{'producto_id': self.latte.pk, 'cantidad': cantidad}]}),
                content_type='application/json',
            )

    def test_venta_que_deja_stock_bajo_envia_un_correo(self):
        self.assertEqual(self.vender(2).status_code, 200)

        self.leche.refresh_from_db()
        self.assertTrue(self.leche.alerta_pendiente)
        self.assertIsNotNone(self.leche.ultima_alerta_enviada)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['dueno@ejemplo.com'])
        self.assertIn('Leche', mail.outbox[0].subject)

    def test_segunda_venta_no_reenvia_por_el_cooldown(self):
        self.vender(2)
        self.vender(1)
        self.assertEqual(len(mail.outbox), 1)

    def test_venta_revertida_no_envia_correo(self):
        # 3 lattes necesitan 15 g de café y solo hay 10: la venta falla
        # después de haber descontado la leche, y todo se revierte.
        Insumo.objects.filter(pk=self.cafe.pk).update(stock_actual=10)
        respuesta = self.vender(3)

        self.assertEqual(respuesta.status_code, 400)
        self.leche.refresh_from_db()
        self.assertEqual(self.leche.stock_actual, Decimal('1000'))
        self.assertEqual(len(mail.outbox), 0)


@override_settings(**CONSOLA)
class AlertaPorEdicionManualTests(TestCase):
    def setUp(self):
        admin = User.objects.create_user('admin', password='x')
        admin.groups.add(Group.objects.create(name='Administrador'))
        self.client.force_login(admin)

    def editar(self, insumo, stock):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('dashboard:insumo_update', args=[insumo.pk]), {
                'nombre': insumo.nombre, 'unidad_medida': insumo.unidad_medida,
                'stock_actual': stock, 'stock_minimo': insumo.stock_minimo,
                'costo_unitario': insumo.costo_unitario, 'activo': 'on',
            })
        insumo.refresh_from_db()

    def test_bajar_stock_a_mano_dispara_alerta(self):
        insumo = crear_insumo()
        self.editar(insumo, '100')
        self.assertTrue(insumo.alerta_pendiente)
        self.assertEqual(len(mail.outbox), 1)

    def test_reabastecer_limpia_la_alerta_y_el_cooldown(self):
        insumo = crear_insumo(stock_actual=Decimal('100'), alerta_pendiente=True,
                              ultima_alerta_enviada=timezone.now())
        self.editar(insumo, '2000')
        self.assertFalse(insumo.alerta_pendiente)
        self.assertIsNone(insumo.ultima_alerta_enviada)


class ProveedoresDeCorreoTests(TestCase):
    @override_settings(**SENDGRID)
    def test_remitente_no_verificado_explica_el_error(self):
        error = ForbiddenError(403, 'Forbidden', json.dumps({'errors': [{
            'message': 'The from address does not match a verified Sender Identity.',
        }]}).encode(), {})
        insumo = crear_insumo(stock_actual=Decimal('100'))

        with mock.patch('sendgrid.SendGridAPIClient.send', side_effect=error), \
                self.assertLogs('core.services.alertas', 'WARNING') as logs:
            self.assertFalse(enviar_alerta_stock(insumo))

        self.assertIn('verified Sender Identity', logs.output[0])
        self.assertIn('ALERTA_EMAIL_DESTINATARIOS', logs.output[0])
        insumo.refresh_from_db()
        self.assertIsNone(insumo.ultima_alerta_enviada)

    @override_settings(**SENDGRID)
    def test_sendgrid_envia_a_cada_destinatario_por_separado(self):
        respuesta = mock.Mock(status_code=202)
        with mock.patch('sendgrid.SendGridAPIClient.send', return_value=respuesta) as send:
            ok, _ = enviar_correo('Asunto', 'Cuerpo', ['a@ejemplo.com', 'b@ejemplo.com'])

        self.assertTrue(ok)
        mensaje = send.call_args.args[0].get()
        self.assertEqual(mensaje['from']['email'], 'verificado@ejemplo.com')
        self.assertCountEqual(
            [p['to'][0]['email'] for p in mensaje['personalizations']],
            ['a@ejemplo.com', 'b@ejemplo.com'],
        )

    @override_settings(**dict(SENDGRID, SENDGRID_API_KEY=''))
    def test_falta_api_key(self):
        ok, detalle = enviar_correo('Asunto', 'Cuerpo')
        self.assertFalse(ok)
        self.assertIn('SENDGRID_API_KEY', detalle)

    @override_settings(**dict(CONSOLA, ALERTA_EMAIL_DESTINATARIOS=[]))
    def test_sin_destinatarios_no_envia(self):
        with self.assertLogs('core.services.alertas', 'WARNING'):
            self.assertFalse(enviar_alerta_stock(crear_insumo(stock_actual=Decimal('1'))))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(**CONSOLA)
    def test_cooldown_de_24_horas(self):
        insumo = crear_insumo(stock_actual=Decimal('1'),
                              ultima_alerta_enviada=timezone.now() - timedelta(hours=23))
        self.assertFalse(enviar_alerta_stock(insumo))
        insumo.ultima_alerta_enviada = timezone.now() - timedelta(hours=25)
        self.assertTrue(enviar_alerta_stock(insumo))


class ProbarCorreoCommandTests(TestCase):
    @override_settings(**CONSOLA)
    def test_envia_al_correo_indicado(self):
        call_command('probar_correo', '--para', 'otra@ejemplo.com', stdout=mock.Mock())
        self.assertEqual(mail.outbox[0].to, ['otra@ejemplo.com'])

    @override_settings(**dict(SENDGRID, SENDGRID_API_KEY=''))
    def test_falla_con_mensaje_claro(self):
        with self.assertRaisesMessage(CommandError, 'SENDGRID_API_KEY'):
            call_command('probar_correo', stdout=mock.Mock())


class LeerEnvTests(TestCase):
    def test_tolera_espacios_sangria_y_bom(self):
        import os
        import tempfile
        from pathlib import Path

        from coffeestock.settings import _leer_env

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / '.env'
            ruta.write_text(
                '﻿PRUEBA_ENV_A = uno\n   PRUEBA_ENV_B=dos\n# PRUEBA_ENV_C=tres\n',
                encoding='utf-8',
            )
            try:
                _leer_env(ruta)
                self.assertEqual(os.environ.get('PRUEBA_ENV_A'), 'uno')
                self.assertEqual(os.environ.get('PRUEBA_ENV_B'), 'dos')
                self.assertIsNone(os.environ.get('PRUEBA_ENV_C'))
            finally:
                for clave in ('PRUEBA_ENV_A', 'PRUEBA_ENV_B'):
                    os.environ.pop(clave, None)


class FormatoTests(TestCase):
    def test_filtros_de_numeros(self):
        from core.templatetags.formato import cantidad, moneda, unidad_corta

        self.assertEqual(moneda('1234.5'), '$1,234.50')
        self.assertEqual(moneda(None), '—')
        self.assertEqual(cantidad('8000.00'), '8,000')
        self.assertEqual(cantidad('12.50'), '12.5')
        self.assertEqual(unidad_corta('unidad'), 'u')


@override_settings(**CONSOLA)
class CompraTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x')
        self.admin.groups.add(Group.objects.create(name='Administrador'))
        self.client.force_login(self.admin)
        self.cafe = crear_insumo(
            nombre='Café', unidad_medida='g', stock_actual=Decimal('1000'),
            stock_minimo=Decimal('2000'), costo_unitario=Decimal('0.0180'),
            alerta_pendiente=True, ultima_alerta_enviada=timezone.now(),
        )

    def test_costo_promedio_ponderado_y_alerta_limpia(self):
        from core.services.inventario import registrar_compra

        compra = registrar_compra(usuario=self.admin, lineas=[(self.cafe, Decimal('3000'), Decimal('66'))])
        self.cafe.refresh_from_db()
        # (1000 x 0.018 + 3000 x 0.022) / 4000 = 0.021
        self.assertEqual(self.cafe.stock_actual, Decimal('4000'))
        self.assertEqual(self.cafe.costo_unitario, Decimal('0.0210'))
        self.assertFalse(self.cafe.alerta_pendiente)
        self.assertIsNone(self.cafe.ultima_alerta_enviada)
        self.assertEqual(compra.total, Decimal('66.00'))
        self.assertEqual(compra.detalles.get().costo_unitario, Decimal('0.0220'))

    def test_formulario_de_compra(self):
        respuesta = self.client.post(reverse('dashboard:compra_create'), {
            'fecha': timezone.localdate().isoformat(),
            'numero_factura': 'F-123',
            'lineas-TOTAL_FORMS': '1', 'lineas-INITIAL_FORMS': '0',
            'lineas-MIN_NUM_FORMS': '1', 'lineas-MAX_NUM_FORMS': '1000',
            'lineas-0-insumo': self.cafe.pk, 'lineas-0-cantidad': '500', 'lineas-0-monto': '10',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.cafe.refresh_from_db()
        self.assertEqual(self.cafe.stock_actual, Decimal('1500'))

    def test_compra_sin_lineas_no_se_guarda(self):
        respuesta = self.client.post(reverse('dashboard:compra_create'), {
            'fecha': timezone.localdate().isoformat(),
            'lineas-TOTAL_FORMS': '0', 'lineas-INITIAL_FORMS': '0',
            'lineas-MIN_NUM_FORMS': '1', 'lineas-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Compra.objects.exists())
