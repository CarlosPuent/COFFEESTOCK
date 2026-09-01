from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Crea usuarios de prueba: "cajero1" (grupo Cajero) y '
        '"admin_coffeestock" (grupo Administrador).'
    )

    def handle(self, *args, **options):
        cajero_group, _ = Group.objects.get_or_create(name='Cajero')
        admin_group, _ = Group.objects.get_or_create(name='Administrador')

        cajero, _ = User.objects.get_or_create(
            username='cajero1', defaults={'is_staff': True}
        )
        cajero.set_password('Cajero123!')
        cajero.is_staff = True
        cajero.save()
        cajero.groups.add(cajero_group)

        admin_user, _ = User.objects.get_or_create(
            username='admin_coffeestock', defaults={'is_staff': True}
        )
        admin_user.set_password('Admin123!')
        admin_user.is_staff = True
        admin_user.save()
        admin_user.groups.add(admin_group)

        self.stdout.write(
            self.style.SUCCESS(
                'Usuarios de prueba "cajero1" y "admin_coffeestock" creados/actualizados.'
            )
        )
