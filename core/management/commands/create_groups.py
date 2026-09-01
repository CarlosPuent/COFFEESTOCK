from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import DetalleVenta, Insumo, Merma, Producto, RecetaInsumo, Venta


class Command(BaseCommand):
    help = 'Crea los grupos "Administrador" y "Cajero" con sus permisos correspondientes.'

    def handle(self, *args, **options):
        admin_group, _ = Group.objects.get_or_create(name='Administrador')
        cajero_group, _ = Group.objects.get_or_create(name='Cajero')

        # Administrador: permisos completos (add/change/delete/view) sobre
        # Insumo, Producto, RecetaInsumo y Merma. El acceso al dashboard se
        # controla vía GroupRequiredMixin en dashboard.views.DashboardIndexView.
        admin_models = [Insumo, Producto, RecetaInsumo, Merma]
        admin_content_types = [ContentType.objects.get_for_model(m) for m in admin_models]
        admin_actions = ['add', 'change', 'delete', 'view']
        admin_perms = Permission.objects.filter(
            content_type__in=admin_content_types
        ).filter(
            Q(*(Q(codename__startswith=f'{action}_') for action in admin_actions), _connector=Q.OR)
        )
        admin_group.permissions.set(admin_perms)

        # Cajero: permisos limitados a add/view sobre Venta, DetalleVenta y Merma.
        cajero_models = [Venta, DetalleVenta, Merma]
        cajero_content_types = [ContentType.objects.get_for_model(m) for m in cajero_models]
        cajero_actions = ['add', 'view']
        cajero_perms = Permission.objects.filter(
            content_type__in=cajero_content_types
        ).filter(
            Q(*(Q(codename__startswith=f'{action}_') for action in cajero_actions), _connector=Q.OR)
        )
        cajero_group.permissions.set(cajero_perms)

        self.stdout.write(
            self.style.SUCCESS(
                'Grupos "Administrador" y "Cajero" creados/actualizados con sus permisos.'
            )
        )
