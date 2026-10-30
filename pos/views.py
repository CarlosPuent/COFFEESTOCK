import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView

from core.mixins import GroupRequiredMixin
from core.models import Producto, Venta
from core.services.ventas import VentaError, registrar_venta


class POSIndexView(GroupRequiredMixin, TemplateView):
    template_name = 'pos/index.html'
    allowed_groups = ['Cajero', 'Administrador']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['productos'] = Producto.objects.filter(activo=True).order_by('categoria', 'nombre')
        return context


class ConfirmarVentaView(GroupRequiredMixin, View):
    allowed_groups = ['Cajero', 'Administrador']

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse(
                {'success': False, 'error': 'Datos de la venta inválidos.'}, status=400
            )

        try:
            venta = registrar_venta(
                usuario=request.user,
                items=payload.get('items') or [],
                metodo_pago=payload.get('metodo_pago') or Venta.MetodoPago.EFECTIVO,
                monto_recibido=payload.get('monto_recibido'),
            )
        except VentaError as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=400)

        return JsonResponse({
            'success': True,
            'venta_id': venta.id,
            'folio': venta.codigo,
            'total': str(venta.total),
            'metodo_pago': venta.get_metodo_pago_display(),
            'monto_recibido': str(venta.monto_recibido) if venta.monto_recibido is not None else None,
            'cambio': str(venta.cambio) if venta.cambio is not None else None,
            'ticket_url': reverse('pos:ticket', args=[venta.pk]),
        })


class TicketView(GroupRequiredMixin, DetailView):
    """Ticket de venta en formato de impresora térmica (80 mm)."""

    model = Venta
    template_name = 'pos/ticket.html'
    context_object_name = 'venta'
    allowed_groups = ['Cajero', 'Administrador']

    def get_queryset(self):
        return Venta.objects.select_related('usuario_cajero').prefetch_related('detalles__producto')


class UltimoTicketView(GroupRequiredMixin, View):
    """Reimprime el ticket de la última venta que registró el usuario."""

    allowed_groups = ['Cajero', 'Administrador']

    def get(self, request):
        venta = Venta.objects.filter(usuario_cajero=request.user).order_by('-fecha').first()
        if venta is None:
            messages.info(request, 'Todavía no has registrado ventas.')
            return redirect('pos:index')
        return redirect('pos:ticket', pk=venta.pk)
