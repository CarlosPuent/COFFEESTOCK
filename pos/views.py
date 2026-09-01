import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from core.mixins import GroupRequiredMixin
from core.models import DetalleVenta, Producto, RecetaInsumo, Venta


class VentaError(Exception):
    """Error de negocio al confirmar una venta (carrito inválido o stock insuficiente)."""


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

        items = payload.get('items') or []
        if not items:
            return JsonResponse(
                {'success': False, 'error': 'El carrito está vacío.'}, status=400
            )

        try:
            venta = self._procesar_venta(request.user, items)
        except VentaError as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=400)

        return JsonResponse({'success': True, 'venta_id': venta.id, 'total': str(venta.total)})

    @transaction.atomic
    def _procesar_venta(self, usuario, items):
        producto_ids = [item.get('producto_id') for item in items]
        productos_by_id = {
            p.id: p for p in Producto.objects.filter(id__in=producto_ids, activo=True)
        }

        lineas = []
        total = Decimal('0')
        for item in items:
            producto = productos_by_id.get(item.get('producto_id'))
            if producto is None:
                raise VentaError('Uno de los productos seleccionados ya no está disponible.')

            try:
                cantidad = Decimal(str(item.get('cantidad')))
            except (InvalidOperation, TypeError, ValueError):
                raise VentaError(f'Cantidad inválida para "{producto.nombre}".')

            if cantidad <= 0:
                raise VentaError(f'Cantidad inválida para "{producto.nombre}".')

            subtotal = producto.precio_venta * cantidad
            total += subtotal
            lineas.append((producto, cantidad, subtotal))

        venta = Venta.objects.create(usuario_cajero=usuario, total=total)

        for producto, cantidad, subtotal in lineas:
            DetalleVenta.objects.create(
                venta=venta, producto=producto, cantidad=cantidad, subtotal=subtotal
            )
            recetas = RecetaInsumo.objects.filter(producto=producto).select_related('insumo')
            for receta in recetas:
                cantidad_a_descontar = receta.cantidad_requerida * cantidad
                try:
                    receta.insumo.descontar_stock(cantidad_a_descontar)
                except ValueError as exc:
                    raise VentaError(str(exc))

        return venta
