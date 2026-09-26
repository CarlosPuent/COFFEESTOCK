from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.services.alertas import enviar_correo, estado_configuracion


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
