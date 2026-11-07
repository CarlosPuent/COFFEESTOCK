from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django.db.models import F
from django.utils import timezone

from core.models import Insumo
from core.services.alertas import (
    ALERTA_STOCK_COOLDOWN, enviar_alerta_stock, enviar_correo, estado_configuracion,
)


class Command(BaseCommand):
    help = (
        'Muestra cómo están configuradas las alertas por correo y envía un '
        'correo de prueba. Si falla, explica el motivo.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--para',
            help='Correo(s) destino separados por coma. Por defecto usa ALERTA_EMAIL_DESTINATARIOS.',
        )
        parser.add_argument(
            '--alerta',
            action='store_true',
            help='En vez del correo de prueba, muestra el estado de las alertas de cada '
                 'insumo bajo el mínimo y envía la alerta real del primero.',
        )

    def handle(self, *args, **options):
        estado = estado_configuracion()
        destinatarios = (
            [c.strip() for c in options['para'].split(',') if c.strip()]
            if options['para'] else estado['destinatarios']
        )

        archivo_env = settings.BASE_DIR / '.env'
        api_key = settings.SENDGRID_API_KEY
        self.stdout.write('Configuración actual de alertas por correo:')
        self.stdout.write(f'  Archivo:       {archivo_env}' + ('' if archivo_env.exists() else '  (NO EXISTE)'))
        self.stdout.write(f'  Proveedor:     {estado["proveedor"]}')
        self.stdout.write(f'  Remitente:     {estado["remitente"] or "(vacío)"}')
        self.stdout.write(f'  Destinatarios: {", ".join(destinatarios) or "(vacío)"}')
        if estado['proveedor'] == 'sendgrid' or api_key:
            self.stdout.write(
                f'  API key:       {api_key[:6] + "..." if api_key else "(vacía)"}'
            )
        self.stdout.write('')

        for sobrante in ('.env.txt', '.env.env'):
            if (settings.BASE_DIR / sobrante).exists():
                self.stdout.write(self.style.WARNING(
                    f'Ojo: existe un archivo "{sobrante}". El sistema solo lee ".env"; '
                    'el Bloc de notas a veces agrega ".txt" al guardar.'
                ))

        if estado['proveedor'] == 'consola':
            self.stdout.write(self.style.WARNING(
                'Estás en modo CONSOLA: el correo solo se imprime aquí abajo, no se envía. '
                'Para enviarlo de verdad, en el .env debe haber una línea '
                '"ALERTA_EMAIL_PROVEEDOR=sendgrid" (o smtp) y guardar con Ctrl + S.'
            ))
            self.stdout.write('')

        if options['alerta']:
            self._probar_alerta()
            return

        ok, detalle = enviar_correo(
            '[CoffeeStock] Correo de prueba',
            'Si estás leyendo esto, las alertas de stock bajo de CoffeeStock '
            'ya pueden llegarte a este correo.\n',
            destinatarios=destinatarios,
        )

        if not ok:
            raise CommandError(detalle)

        self.stdout.write(self.style.SUCCESS(detalle))
        if estado['sale_a_internet']:
            self.stdout.write(
                'Revisa la bandeja de entrada y también Spam / Promociones. '
                'El primer correo puede tardar uno o dos minutos.'
            )

    def _probar_alerta(self):
        bajos = list(Insumo.objects.filter(activo=True, stock_actual__lte=F('stock_minimo')).order_by('nombre'))
        if not bajos:
            raise CommandError(
                'Ningún insumo está en o bajo su mínimo, así que no hay alerta que enviar. '
                'Registra una merma o corre "python manage.py seed_demo_data --reset".'
            )

        ahora = timezone.now()
        self.stdout.write('Insumos en o bajo el mínimo:')
        for insumo in bajos:
            if insumo.ultima_alerta_enviada is None:
                estado = 'nunca se ha avisado'
            elif ahora - insumo.ultima_alerta_enviada < ALERTA_STOCK_COOLDOWN:
                hora = timezone.localtime(insumo.ultima_alerta_enviada).strftime('%d/%m/%Y %H:%M')
                estado = f'ya se avisó el {hora}: no se repite hasta 24 h después'
            else:
                estado = 'se puede avisar de nuevo'
            self.stdout.write(f'  - {insumo.nombre}: {insumo.stock_actual} de {insumo.stock_minimo} mínimo ({estado})')
        self.stdout.write('')

        insumo = bajos[0]
        self.stdout.write(f'Enviando la alerta real de "{insumo.nombre}" (sin esperar las 24 h)...')
        if not enviar_alerta_stock(insumo, forzar=True):
            raise CommandError(
                'La alerta no salió. El motivo aparece arriba en la línea '
                '"No se pudo enviar la alerta de stock".'
            )
        self.stdout.write(self.style.SUCCESS(
            f'Alerta enviada con el asunto "[CoffeeStock] Stock bajo: {insumo.nombre}". '
            'Búscala en la bandeja de entrada y en Spam / Correo no deseado.'
        ))
