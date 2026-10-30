from django.test import TestCase




class UltimoTicketTests(TestCase):
    def test_redirige_a_la_ultima_venta_del_usuario(self):
        from decimal import Decimal

        from django.contrib.auth.models import Group, User
        from django.urls import reverse

        from core.models import Venta

        cajero = User.objects.create_user('caja', password='x')
        cajero.groups.add(Group.objects.create(name='Cajero'))
        self.client.force_login(cajero)
        self.assertRedirects(self.client.get(reverse('pos:ultimo_ticket')), reverse('pos:index'))
        Venta.objects.create(usuario_cajero=cajero, total=Decimal('1'))
        venta = Venta.objects.create(usuario_cajero=cajero, total=Decimal('2'))
        respuesta = self.client.get(reverse('pos:ultimo_ticket'))
        self.assertRedirects(respuesta, reverse('pos:ticket', args=[venta.pk]))
