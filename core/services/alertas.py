import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)

ALERTA_STOCK_COOLDOWN = timedelta(hours=24)


def enviar_alerta_stock(insumo):
    """Envía un correo de stock bajo para `insumo` vía SendGrid.

    No reenvía si ya se notificó este insumo en las últimas 24 horas.
    Nunca deja escapar excepciones: cualquier fallo se registra como
    WARNING y la función retorna False.
    """
    if (
        insumo.ultima_alerta_enviada
        and timezone.now() - insumo.ultima_alerta_enviada < ALERTA_STOCK_COOLDOWN
    ):
        return False

    asunto = f'Alerta de stock bajo: {insumo.nombre}'
    cuerpo = (
        f'El insumo "{insumo.nombre}" está por debajo de su stock mínimo.\n\n'
        f'Stock actual: {insumo.stock_actual} {insumo.get_unidad_medida_display()}\n'
        f'Stock mínimo: {insumo.stock_minimo} {insumo.get_unidad_medida_display()}\n'
        f'Unidad de medida: {insumo.get_unidad_medida_display()}\n'
    )

    message = Mail(
        from_email=settings.SENDGRID_FROM_EMAIL,
        to_emails=settings.SENDGRID_ADMIN_EMAIL,
        subject=asunto,
        plain_text_content=cuerpo,
    )

    try:
        client = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = client.send(message)
    except Exception as exc:
        logger.warning(
            'No se pudo enviar la alerta de stock bajo para "%s": %s', insumo.nombre, exc
        )
        return False

    if not (200 <= response.status_code < 300):
        logger.warning(
            'SendGrid respondió con status %s al enviar la alerta de stock para "%s".',
            response.status_code, insumo.nombre,
        )
        return False

    insumo.ultima_alerta_enviada = timezone.now()
    insumo.save(update_fields=['ultima_alerta_enviada'])
    return True
