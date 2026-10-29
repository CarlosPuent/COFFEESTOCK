import datetime
import json

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import (
    Case, Count, DecimalField, Exists, ExpressionWrapper, F, OuterRef, ProtectedError,
    Sum, Value, When,
)
from django.db.models.functions import Coalesce, TruncDate
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView,
)

from core.mixins import GroupRequiredMixin
from core.services.alertas import estado_configuracion
from core.services.ventas import VentaError, anular_venta
from core.models import DetalleVenta, Insumo, Merma, Producto, RecetaInsumo, Venta

from .forms import (
    RECETA_INSUMO_FORMSET_PREFIX,
    AnularVentaForm,
    InsumoFilterForm,
    InsumoForm,
    MermaFilterForm,
    MermaForm,
    ProductoFilterForm,
    ProductoForm,
    RecetaInsumoFormSet,
    VentaFilterForm,
)
from .listados import ListadoMixin, buscar_por_nombre_o_codigo

DINERO = DecimalField(max_digits=28, decimal_places=6)


def inicio_del_dia(fecha):
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time.min))


def fin_del_dia(fecha):
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time.max))


def filtrar_por_fechas(queryset, datos, campo='fecha'):
    if datos.get('fecha_desde'):
        queryset = queryset.filter(**{f'{campo}__gte': inicio_del_dia(datos['fecha_desde'])})
    if datos.get('fecha_hasta'):
        queryset = queryset.filter(**{f'{campo}__lte': fin_del_dia(datos['fecha_hasta'])})
    return queryset


def filtrar_por_estado(queryset, estado):
    if estado == 'activos':
        return queryset.filter(activo=True)
    if estado == 'inactivos':
        return queryset.filter(activo=False)
    return queryset


class DashboardIndexView(GroupRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'
    allowed_groups = ['Administrador']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['insumos_alerta'] = Insumo.objects.filter(alerta_pendiente=True).order_by('nombre')
        context['estado_correo'] = estado_configuracion()

        hoy = timezone.localdate()

        # 1. Ventas de los últimos 7 días, agrupadas por día (con días sin venta en 0).
        inicio_7d = hoy - datetime.timedelta(days=6)
        inicio_7d_dt = timezone.make_aware(datetime.datetime.combine(inicio_7d, datetime.time.min))

        ventas_por_dia = {
            row['dia']: row['total_dia']
            for row in (
                Venta.objects.completadas().filter(fecha__gte=inicio_7d_dt)
                .annotate(dia=TruncDate('fecha'))
                .values('dia')
                .annotate(total_dia=Sum('total'))
            )
        }
        rango_7d = [inicio_7d + datetime.timedelta(days=i) for i in range(7)]
        ventas_chart = {
            'labels': [dia.strftime('%d/%m') for dia in rango_7d],
            'data': [float(ventas_por_dia.get(dia, 0)) for dia in rango_7d],
        }
        context['ventas_has_data'] = bool(ventas_por_dia)
        context['ventas_chart_json'] = json.dumps(ventas_chart, cls=DjangoJSONEncoder)

        # 2. Top 5 productos más vendidos en los últimos 30 días.
        inicio_30d = hoy - datetime.timedelta(days=29)
        inicio_30d_dt = timezone.make_aware(datetime.datetime.combine(inicio_30d, datetime.time.min))

        top_productos = list(
            DetalleVenta.objects.filter(
                venta__fecha__gte=inicio_30d_dt, venta__estado=Venta.Estado.COMPLETADA,
            )
            .values('producto__nombre')
            .annotate(cantidad_total=Sum('cantidad'))
            .order_by('-cantidad_total')[:5]
        )
        productos_chart = {
            'labels': [row['producto__nombre'] for row in top_productos],
            'data': [float(row['cantidad_total']) for row in top_productos],
        }
        context['productos_has_data'] = bool(top_productos)
        context['productos_chart_json'] = json.dumps(productos_chart, cls=DjangoJSONEncoder)

        # 3. Mermas del mes actual agrupadas por causa.
        inicio_mes = hoy.replace(day=1)
        inicio_mes_dt = timezone.make_aware(datetime.datetime.combine(inicio_mes, datetime.time.min))

        causa_display = dict(Merma.Causa.choices)
        mermas_por_causa = list(
            Merma.objects.filter(fecha__gte=inicio_mes_dt)
            .values('causa')
            .annotate(cantidad_total=Sum('cantidad'))
            .order_by('causa')
        )
        mermas_chart = {
            'labels': [causa_display.get(row['causa'], row['causa']) for row in mermas_por_causa],
            'data': [float(row['cantidad_total']) for row in mermas_por_causa],
        }
        context['mermas_has_data'] = bool(mermas_por_causa)
        context['mermas_chart_json'] = json.dumps(mermas_chart, cls=DjangoJSONEncoder)

        return context


class ProtectedDeleteMixin:
    """Maneja con gracia el borrado de objetos protegidos (on_delete=PROTECT)."""

    protected_error_message = (
        'No se puede eliminar "{object}" porque tiene registros relacionados '
        '(recetas o mermas). Desactívalo en lugar de eliminarlo.'
    )

    def form_valid(self, form):
        object_display = str(self.object)
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                self.protected_error_message.format(object=object_display),
            )
            return redirect(self.success_url)


# ---------------------------------------------------------------------------
# Insumo
# ---------------------------------------------------------------------------

class InsumoListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Insumo
    template_name = 'dashboard/insumo_list.html'
    context_object_name = 'insumos'
    allowed_groups = ['Administrador']
    filtro_form_class = InsumoFilterForm
    columnas_orden = {
        'codigo': 'pk',
        'nombre': 'nombre',
        'unidad': 'unidad_medida',
        'stock': 'stock_actual',
        'minimo': 'stock_minimo',
        'costo': 'costo_unitario',
        'valor': 'valor',
        'activo': 'activo',
    }
    orden_defecto = 'nombre'

    def filtrar(self, queryset, datos):
        queryset = buscar_por_nombre_o_codigo(queryset, datos.get('q'), Insumo.PREFIJO)
        if datos.get('unidad'):
            queryset = queryset.filter(unidad_medida=datos['unidad'])
        if datos.get('stock') == 'bajo':
            queryset = queryset.filter(stock_actual__lte=F('stock_minimo'))
        elif datos.get('stock') == 'normal':
            queryset = queryset.filter(stock_actual__gt=F('stock_minimo'))
        return filtrar_por_estado(queryset, datos.get('estado'))

    def get_queryset_filtrado(self):
        self.queryset = Insumo.objects.annotate(
            valor=ExpressionWrapper(F('stock_actual') * F('costo_unitario'), output_field=DINERO),
        )
        return super().get_queryset_filtrado()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtrado = self.get_queryset_filtrado()
        context['valor_total'] = filtrado.aggregate(total=Sum('valor'))['total'] or 0
        context['insumos_en_alerta'] = filtrado.filter(stock_actual__lte=F('stock_minimo')).count()
        return context


class InsumoFormMixin:
    model = Insumo
    form_class = InsumoForm
    template_name = 'dashboard/insumo_form.html'
    success_url = reverse_lazy('dashboard:insumo_list')
    allowed_groups = ['Administrador']

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            self.object.sincronizar_alerta()
        return response


class InsumoCreateView(InsumoFormMixin, GroupRequiredMixin, CreateView):
    pass


class InsumoUpdateView(InsumoFormMixin, GroupRequiredMixin, UpdateView):
    pass


class InsumoDeleteView(GroupRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Insumo
    template_name = 'dashboard/insumo_confirm_delete.html'
    success_url = reverse_lazy('dashboard:insumo_list')
    allowed_groups = ['Administrador']


# ---------------------------------------------------------------------------
# Producto (con formset inline de RecetaInsumo)
# ---------------------------------------------------------------------------

class ProductoListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Producto
    template_name = 'dashboard/producto_list.html'
    context_object_name = 'productos'
    allowed_groups = ['Administrador']
    filtro_form_class = ProductoFilterForm
    columnas_orden = {
        'codigo': 'pk',
        'nombre': 'nombre',
        'categoria': 'categoria',
        'precio': 'precio_venta',
        'costo': 'costo_total',
        'margen': 'margen_pct',
        'activo': 'activo',
    }
    orden_defecto = 'nombre'

    def get_queryset_filtrado(self):
        costo = Coalesce(
            Sum(
                F('receta_insumos__cantidad_requerida') * F('receta_insumos__insumo__costo_unitario'),
                output_field=DINERO,
            ),
            Value(0, output_field=DINERO),
        )
        self.queryset = Producto.objects.annotate(costo_total=costo).annotate(
            margen_pct=Case(
                When(
                    precio_venta__gt=0,
                    then=ExpressionWrapper(
                        (F('precio_venta') - F('costo_total')) * 100 / F('precio_venta'),
                        output_field=DINERO,
                    ),
                ),
                default=None,
                output_field=DINERO,
            ),
        )
        return super().get_queryset_filtrado()

    def filtrar(self, queryset, datos):
        queryset = buscar_por_nombre_o_codigo(queryset, datos.get('q'), Producto.PREFIJO)
        if datos.get('categoria'):
            queryset = queryset.filter(categoria=datos['categoria'])
        if datos.get('precio_min') is not None:
            queryset = queryset.filter(precio_venta__gte=datos['precio_min'])
        if datos.get('precio_max') is not None:
            queryset = queryset.filter(precio_venta__lte=datos['precio_max'])
        return filtrar_por_estado(queryset, datos.get('estado'))


class ProductoFormsetMixin:
    """Combina ProductoForm con RecetaInsumoFormSet en la misma vista."""

    model = Producto
    form_class = ProductoForm
    template_name = 'dashboard/producto_form.html'
    success_url = reverse_lazy('dashboard:producto_list')
    allowed_groups = ['Administrador']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['receta_formset'] = RecetaInsumoFormSet(
                self.request.POST, instance=self.object, prefix=RECETA_INSUMO_FORMSET_PREFIX
            )
        else:
            context['receta_formset'] = RecetaInsumoFormSet(
                instance=self.object, prefix=RECETA_INSUMO_FORMSET_PREFIX
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        receta_formset = context['receta_formset']
        if receta_formset.is_valid():
            self.object = form.save()
            receta_formset.instance = self.object
            receta_formset.save()
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form))


class ProductoCreateView(ProductoFormsetMixin, GroupRequiredMixin, CreateView):
    pass


class ProductoUpdateView(ProductoFormsetMixin, GroupRequiredMixin, UpdateView):
    pass


class ProductoDeleteView(GroupRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Producto
    template_name = 'dashboard/producto_confirm_delete.html'
    success_url = reverse_lazy('dashboard:producto_list')
    allowed_groups = ['Administrador']


# ---------------------------------------------------------------------------
# Merma
# ---------------------------------------------------------------------------

class MermaCreateView(GroupRequiredMixin, CreateView):
    model = Merma
    form_class = MermaForm
    template_name = 'dashboard/merma_form.html'
    allowed_groups = ['Cajero', 'Administrador']

    def form_valid(self, form):
        merma = form.save(commit=False)
        merma.usuario_responsable = self.request.user

        try:
            with transaction.atomic():
                merma.insumo.descontar_stock(merma.cantidad)
                merma.save()
        except ValueError as exc:
            form.add_error('cantidad', str(exc))
            return self.form_invalid(form)

        messages.success(
            self.request,
            f'Merma registrada correctamente: {merma.cantidad} de "{merma.insumo}".',
        )
        return redirect(self.get_success_url())

    def get_success_url(self):
        if self.request.user.groups.filter(name='Administrador').exists():
            return reverse('dashboard:merma_list')
        return reverse('pos:index')


class MermaListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Merma
    template_name = 'dashboard/merma_list.html'
    context_object_name = 'mermas'
    allowed_groups = ['Administrador']
    filtro_form_class = MermaFilterForm
    columnas_orden = {
        'codigo': 'pk',
        'fecha': 'fecha',
        'insumo': 'insumo__nombre',
        'cantidad': 'cantidad',
        'causa': 'causa',
        'costo': 'costo_merma',
        'responsable': 'usuario_responsable__username',
    }
    orden_defecto = '-fecha'

    def get_queryset_filtrado(self):
        self.queryset = Merma.objects.select_related('insumo', 'usuario_responsable').annotate(
            costo_merma=ExpressionWrapper(F('cantidad') * F('insumo__costo_unitario'), output_field=DINERO),
        )
        return super().get_queryset_filtrado()

    def filtrar(self, queryset, datos):
        if datos.get('insumo'):
            queryset = queryset.filter(insumo=datos['insumo'])
        if datos.get('causa'):
            queryset = queryset.filter(causa=datos['causa'])
        if datos.get('responsable'):
            queryset = queryset.filter(usuario_responsable=datos['responsable'])
        return filtrar_por_fechas(queryset, datos)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['costo_total'] = self.get_queryset_filtrado().aggregate(total=Sum('costo_merma'))['total'] or 0
        return context


# ---------------------------------------------------------------------------
# Venta (historial)
# ---------------------------------------------------------------------------

class VentaListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Venta
    template_name = 'dashboard/venta_list.html'
    context_object_name = 'ventas'
    allowed_groups = ['Administrador']
    filtro_form_class = VentaFilterForm
    columnas_orden = {
        'folio': 'pk',
        'fecha': 'fecha',
        'cajero': 'usuario_cajero__username',
        'productos': 'num_productos',
        'total': 'total',
        'pago': 'metodo_pago',
        'estado': 'estado',
    }
    orden_defecto = '-fecha'

    def get_queryset_filtrado(self):
        self.queryset = Venta.objects.select_related('usuario_cajero').annotate(
            num_productos=Coalesce(Sum('detalles__cantidad'), Value(0, output_field=DINERO)),
        )
        return super().get_queryset_filtrado()

    def filtrar(self, queryset, datos):
        queryset = buscar_por_nombre_o_codigo(
            queryset, datos.get('q'), Venta.PREFIJO, campo='usuario_cajero__username',
        )
        if datos.get('usuario_cajero'):
            queryset = queryset.filter(usuario_cajero=datos['usuario_cajero'])
        if datos.get('producto'):
            queryset = queryset.filter(
                Exists(DetalleVenta.objects.filter(venta=OuterRef('pk'), producto=datos['producto']))
            )
        if datos.get('total_min') is not None:
            queryset = queryset.filter(total__gte=datos['total_min'])
        if datos.get('total_max') is not None:
            queryset = queryset.filter(total__lte=datos['total_max'])
        if datos.get('metodo_pago'):
            queryset = queryset.filter(metodo_pago=datos['metodo_pago'])
        if datos.get('estado'):
            queryset = queryset.filter(estado=datos['estado'])
        return filtrar_por_fechas(queryset, datos)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtrado = self.get_queryset_filtrado()
        context['monto_total'] = filtrado.completadas().aggregate(total=Sum('total'))['total'] or 0
        context['num_anuladas'] = filtrado.filter(estado=Venta.Estado.ANULADA).count()
        return context


class VentaDetailView(GroupRequiredMixin, DetailView):
    model = Venta
    template_name = 'dashboard/venta_detail.html'
    context_object_name = 'venta'
    allowed_groups = ['Administrador']

    def get_queryset(self):
        return Venta.objects.select_related('usuario_cajero', 'anulada_por').prefetch_related(
            'detalles__producto'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_anular'] = kwargs.get('form_anular') or AnularVentaForm()
        return context


class AnularVentaView(GroupRequiredMixin, View):
    allowed_groups = ['Administrador']

    def post(self, request, pk):
        venta = get_object_or_404(Venta, pk=pk)
        form = AnularVentaForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Indica el motivo de la anulación.')
            return redirect('dashboard:venta_detail', pk=pk)
        try:
            anular_venta(venta, usuario=request.user, motivo=form.cleaned_data['motivo'])
        except VentaError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request, f'Venta {venta.codigo} anulada. Se devolvió al inventario lo que había consumido.'
            )
        return redirect('dashboard:venta_detail', pk=pk)
