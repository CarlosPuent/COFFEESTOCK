"""Envío de alertas de stock bajo por correo.

El proveedor se elige en el .env (ALERTA_EMAIL_PROVEEDOR):
  - consola:  el correo se imprime en la terminal donde corre runserver.
  - sendgrid: se envía por la API de SendGrid.
  - smtp:     se envía por cualquier servidor SMTP (Gmail, Outlook, etc.).

Ninguna función de este módulo deja escapar excepciones: un correo que no
sale nunca debe romper una venta o una merma.
"""
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

ALERTA_STOCK_COOLDOWN = timedelta(hours=24)

PROVEEDORES = ('consola', 'sendgrid', 'smtp')

# Pistas para los errores más comunes de SendGrid.
PISTAS_SENDGRID = {
    400: 'Revisa que SENDGRID_FROM_EMAIL y ALERTA_EMAIL_DESTINATARIOS sean correos válidos.',
    401: 'La SENDGRID_API_KEY es incorrecta, fue borrada o está incompleta.',
    403: (
        'SENDGRID_FROM_EMAIL no es un remitente verificado en tu cuenta de SendGrid '
        '(Settings > Sender Authentication), o la API key no tiene permiso "Mail Send". '
        'Ojo: el remitente NO se cambia por el correo de quien recibe; para eso está '
        'ALERTA_EMAIL_DESTINATARIOS.'
    ),
}


def estado_configuracion():
    """Resume cómo están configuradas las alertas y qué falta, para
    mostrarlo en el dashboard y en el comando probar_correo."""
    proveedor = settings.ALERTA_EMAIL_PROVEEDOR
    destinatarios = list(settings.ALERTA_EMAIL_DESTINATARIOS)
    remitente = settings.DEFAULT_FROM_EMAIL
    problemas = []

    if proveedor not in PROVEEDORES:
        problemas.append(
            f'ALERTA_EMAIL_PROVEEDOR="{proveedor}" no es válido. Usa: {", ".join(PROVEEDORES)}.'
        )
    if not destinatarios:
        problemas.append('Falta ALERTA_EMAIL_DESTINATARIOS (a quién le llegan las alertas).')
    if proveedor == 'sendgrid':
        if not settings.SENDGRID_API_KEY:
            problemas.append('Falta SENDGRID_API_KEY.')
        if not settings.SENDGRID_FROM_EMAIL:
            problemas.append('Falta SENDGRID_FROM_EMAIL (el remitente verificado en SendGrid).')
    if proveedor == 'smtp':
        opciones = settings.MAILERS['default'].get('OPTIONS', {})
        if not opciones.get('username') or not opciones.get('password'):
            problemas.append('Faltan EMAIL_HOST_USER y/o EMAIL_HOST_PASSWORD.')

    return {
        'proveedor': proveedor,
        'remitente': remitente,
        'destinatarios': destinatarios,
        'problemas': problemas,
        'listo': not problemas,
        'sale_a_internet': proveedor in ('sendgrid', 'smtp'),
    }


def _describir_error_sendgrid(exc):
    from urllib.error import URLError

    status = getattr(exc, 'status_code', None)
    if status is None and isinstance(exc, URLError):
        if 'CERTIFICATE_VERIFY_FAILED' in str(exc.reason):
            return (
                'No se pudo verificar el certificado de api.sendgrid.com. Suele ser un '
                'antivirus o una red que inspecciona HTTPS. Corre '
                '"pip install -r requirements.txt" para instalar truststore, que hace '
                'que Python use los certificados de Windows.'
            )
        return (
            f'No se pudo conectar con api.sendgrid.com ({exc.reason}). Revisa la conexión '
            'a internet, un firewall/antivirus o proxy, o en macOS ejecuta '
            '"Install Certificates.command" de tu instalación de Python.'
        )
    detalle = ''
    body = getattr(exc, 'body', None)
    if body:
        try:
            errores = json.loads(body).get('errors', [])
            detalle = '; '.join(e.get('message', '') for e in errores if e.get('message'))
        except (ValueError, AttributeError):
            detalle = body.decode(errors='replace') if isinstance(body, bytes) else str(body)
    partes = [f'SendGrid respondió {status}' if status else str(exc)]
    if detalle:
        partes.append(detalle)
    if status in PISTAS_SENDGRID:
        partes.append(PISTAS_SENDGRID[status])
    return ' | '.join(partes)


def _enviar_por_sendgrid(asunto, cuerpo, destinatarios):
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=settings.SENDGRID_FROM_EMAIL,
        to_emails=destinatarios,
        subject=asunto,
        plain_text_content=cuerpo,
        # Un correo por destinatario: nadie ve las direcciones de los demás.
        is_multiple=True,
    )
    try:
        response = SendGridAPIClient(settings.SENDGRID_API_KEY).send(message)
    except Exception as exc:
        return False, _describir_error_sendgrid(exc)

    if not (200 <= response.status_code < 300):
        return False, f'SendGrid respondió {response.status_code}.'
    return True, f'SendGrid aceptó el correo (status {response.status_code}).'


def enviar_correo(asunto, cuerpo, destinatarios=None):
    """Envía un correo con el proveedor configurado.

    Devuelve (ok, detalle). `detalle` explica en texto qué pasó, sobre todo
    cuando falla, para poder diagnosticar sin leer código.
    """
    estado = estado_configuracion()
    destinatarios = list(destinatarios or estado['destinatarios'])
    problemas = [p for p in estado['problemas'] if 'ALERTA_EMAIL_DESTINATARIOS' not in p]
    if not destinatarios:
        problemas.append('Falta ALERTA_EMAIL_DESTINATARIOS (a quién le llegan las alertas).')
    if problemas:
        return False, 'Configuración de correo incompleta: ' + ' '.join(problemas)

    if estado['proveedor'] == 'sendgrid':
        return _enviar_por_sendgrid(asunto, cuerpo, destinatarios)

    try:
        send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, destinatarios)
    except Exception as exc:
        return False, f'El servidor SMTP rechazó el envío: {exc}'

    if estado['proveedor'] == 'consola':
        return True, 'Correo impreso en la consola (ALERTA_EMAIL_PROVEEDOR=consola, no sale a internet).'
    return True, 'El servidor SMTP aceptó el correo.'


def enviar_alerta_stock(insumo):
    """Envía la alerta de stock bajo de `insumo`.

    No reenvía si ya se notificó este insumo en las últimas 24 horas.
    Devuelve True solo si el correo salió.
    """
    if (
        insumo.ultima_alerta_enviada
        and timezone.now() - insumo.ultima_alerta_enviada < ALERTA_STOCK_COOLDOWN
    ):
        logger.info('Alerta de "%s" omitida: ya se envió una en las últimas 24 h.', insumo.nombre)
        return False

    unidad = insumo.get_unidad_medida_display()
    asunto = f'[CoffeeStock] Stock bajo: {insumo.nombre}'
    cuerpo = (
        f'El insumo "{insumo.nombre}" llegó a su stock mínimo o está por debajo.\n\n'
        f'Stock actual: {insumo.stock_actual} {unidad}\n'
        f'Stock mínimo: {insumo.stock_minimo} {unidad}\n\n'
        'Conviene reabastecerlo pronto. No se volverá a avisar sobre este insumo '
        'en las próximas 24 horas.\n'
    )

    ok, detalle = enviar_correo(asunto, cuerpo)
    if not ok:
        logger.warning('No se pudo enviar la alerta de stock de "%s". %s', insumo.nombre, detalle)
        return False

    ahora = timezone.now()
    type(insumo).objects.filter(pk=insumo.pk).update(ultima_alerta_enviada=ahora)
    insumo.ultima_alerta_enviada = ahora
    logger.info('Alerta de stock de "%s" enviada. %s', insumo.nombre, detalle)
    return True


def programar_alerta_stock(insumo_pk):
    """Envía la alerta cuando la transacción actual se confirme.

    Así el correo no sale si la venta termina revirtiéndose, y la llamada
    HTTP no se hace mientras la fila del insumo está bloqueada.
    """
    def _enviar():
        from core.models import Insumo

        try:
            insumo = Insumo.objects.get(pk=insumo_pk)
        except Insumo.DoesNotExist:
            return
        if insumo.alerta_pendiente:
            enviar_alerta_stock(insumo)

    def _enviar_sin_romper():
        try:
            _enviar()
        except Exception:
            logger.exception('Error inesperado al enviar la alerta de stock (insumo %s).', insumo_pk)

    transaction.on_commit(_enviar_sin_romper)
