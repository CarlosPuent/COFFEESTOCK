import datetime
import json

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import ProtectedError, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from core.mixins import GroupRequiredMixin
from core.models import DetalleVenta, Insumo, Merma, Producto, Venta

from .forms import (
    RECETA_INSUMO_FORMSET_PREFIX,
    InsumoForm,
    MermaFilterForm,
    MermaForm,
    ProductoForm,
    RecetaInsumoFormSet,
)


class DashboardIndexView(GroupRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'
    allowed_groups = ['Administrador']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['insumos_alerta'] = Insumo.objects.filter(alerta_pendiente=True).order_by('nombre')

        hoy = timezone.localdate()

        # 1. Ventas de los últimos 7 días, agrupadas por día (con días sin venta en 0).
        inicio_7d = hoy - datetime.timedelta(days=6)
        inicio_7d_dt = timezone.make_aware(datetime.datetime.combine(inicio_7d, datetime.time.min))

        ventas_por_dia = {
            row['dia']: row['total_dia']
            for row in (
                Venta.objects.filter(fecha__gte=inicio_7d_dt)
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
            DetalleVenta.objects.filter(venta__fecha__gte=inicio_30d_dt)
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


class PreserveQuerystringMixin:
    """Agrega al contexto la querystring actual (sin 'page') para armar
    los enlaces de paginación conservando filtros/búsqueda."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['querystring'] = params.urlencode()
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

class InsumoListView(PreserveQuerystringMixin, GroupRequiredMixin, ListView):
    model = Insumo
    template_name = 'dashboard/insumo_list.html'
    context_object_name = 'insumos'
    paginate_by = 20
    allowed_groups = ['Administrador']

    def get_queryset(self):
        queryset = Insumo.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(nombre__icontains=q)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        return context


class InsumoCreateView(GroupRequiredMixin, CreateView):
    model = Insumo
    form_class = InsumoForm
    template_name = 'dashboard/insumo_form.html'
    success_url = reverse_lazy('dashboard:insumo_list')
    allowed_groups = ['Administrador']


class InsumoUpdateView(GroupRequiredMixin, UpdateView):
    model = Insumo
    form_class = InsumoForm
    template_name = 'dashboard/insumo_form.html'
    success_url = reverse_lazy('dashboard:insumo_list')
    allowed_groups = ['Administrador']


class InsumoDeleteView(GroupRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Insumo
    template_name = 'dashboard/insumo_confirm_delete.html'
    success_url = reverse_lazy('dashboard:insumo_list')
    allowed_groups = ['Administrador']


# ---------------------------------------------------------------------------
# Producto (con formset inline de RecetaInsumo)
# ---------------------------------------------------------------------------

class ProductoListView(PreserveQuerystringMixin, GroupRequiredMixin, ListView):
    model = Producto
    template_name = 'dashboard/producto_list.html'
    context_object_name = 'productos'
    paginate_by = 20
    allowed_groups = ['Administrador']

    def get_queryset(self):
        queryset = Producto.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(nombre__icontains=q)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        return context


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


class MermaListView(PreserveQuerystringMixin, GroupRequiredMixin, ListView):
    model = Merma
    template_name = 'dashboard/merma_list.html'
    context_object_name = 'mermas'
    paginate_by = 20
    allowed_groups = ['Administrador']

    def get_queryset(self):
        queryset = Merma.objects.select_related('insumo', 'usuario_responsable').all()
        form = MermaFilterForm(self.request.GET or None)
        if form.is_valid():
            data = form.cleaned_data
            if data.get('insumo'):
                queryset = queryset.filter(insumo=data['insumo'])
            if data.get('causa'):
                queryset = queryset.filter(causa=data['causa'])
            if data.get('fecha_desde'):
                inicio = timezone.make_aware(
                    datetime.datetime.combine(data['fecha_desde'], datetime.time.min)
                )
                queryset = queryset.filter(fecha__gte=inicio)
            if data.get('fecha_hasta'):
                fin = timezone.make_aware(
                    datetime.datetime.combine(data['fecha_hasta'], datetime.time.max)
                )
                queryset = queryset.filter(fecha__lte=fin)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = MermaFilterForm(self.request.GET or None)
        return context
