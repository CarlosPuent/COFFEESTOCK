from django.contrib import messages
from django.db.models import Count, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView

from core.mixins import GroupRequiredMixin
from core.models import Compra, DetalleCompra, Insumo, Proveedor
from core.services.inventario import registrar_compra

from .forms import (
    DETALLE_COMPRA_PREFIX,
    CompraFilterForm,
    CompraForm,
    DetalleCompraFormSet,
    ProveedorFilterForm,
    ProveedorForm,
)
from .listados import ListadoMixin, buscar_por_nombre_o_codigo
from .views import DINERO, ProtectedDeleteMixin, filtrar_por_estado, filtrar_por_fechas

# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------


class ProveedorListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Proveedor
    template_name = 'dashboard/proveedor_list.html'
    context_object_name = 'proveedores'
    allowed_groups = ['Administrador']
    filtro_form_class = ProveedorFilterForm
    columnas_orden = {
        'codigo': 'pk',
        'nombre': 'nombre',
        'contacto': 'contacto',
        'compras': 'num_compras',
        'total': 'total_comprado',
        'activo': 'activo',
    }
    orden_defecto = 'nombre'

    def get_queryset_filtrado(self):
        self.queryset = Proveedor.objects.annotate(
            num_compras=Count('compras'),
            total_comprado=Coalesce(Sum('compras__total'), Value(0, output_field=DINERO)),
        )
        return super().get_queryset_filtrado()

    def filtrar(self, queryset, datos):
        queryset = buscar_por_nombre_o_codigo(
            queryset, datos.get('q'), Proveedor.PREFIJO, otros_campos=('contacto', 'telefono'),
        )
        return filtrar_por_estado(queryset, datos.get('estado'))


class ProveedorFormMixin:
    model = Proveedor
    form_class = ProveedorForm
    template_name = 'dashboard/proveedor_form.html'
    success_url = reverse_lazy('dashboard:proveedor_list')
    allowed_groups = ['Administrador']

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f'Proveedor "{self.object.nombre}" guardado.')
        return respuesta


class ProveedorCreateView(ProveedorFormMixin, GroupRequiredMixin, CreateView):
    pass


class ProveedorUpdateView(ProveedorFormMixin, GroupRequiredMixin, UpdateView):
    pass


class ProveedorDeleteView(GroupRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Proveedor
    template_name = 'dashboard/confirmar_eliminar.html'
    success_url = reverse_lazy('dashboard:proveedor_list')
    allowed_groups = ['Administrador']
    protected_error_message = (
        'No se puede eliminar "{object}" porque tiene compras registradas. '
        'Desactívalo en lugar de eliminarlo.'
    )


# ---------------------------------------------------------------------------
# Compras
# ---------------------------------------------------------------------------


class CompraListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Compra
    template_name = 'dashboard/compra_list.html'
    context_object_name = 'compras'
    allowed_groups = ['Administrador']
    filtro_form_class = CompraFilterForm
    columnas_orden = {
        'folio': 'pk',
        'fecha': 'fecha',
        'proveedor': 'proveedor__nombre',
        'factura': 'numero_factura',
        'lineas': 'num_lineas',
        'total': 'total',
        'usuario': 'usuario__username',
    }
    orden_defecto = '-fecha'

    def get_queryset_filtrado(self):
        self.queryset = Compra.objects.select_related('proveedor', 'usuario').annotate(
            num_lineas=Count('detalles'),
        )
        return super().get_queryset_filtrado()

    def filtrar(self, queryset, datos):
        queryset = buscar_por_nombre_o_codigo(
            queryset, datos.get('q'), Compra.PREFIJO, campo='numero_factura',
        )
        if datos.get('proveedor'):
            queryset = queryset.filter(proveedor=datos['proveedor'])
        if datos.get('insumo'):
            queryset = queryset.filter(
                pk__in=DetalleCompra.objects.filter(insumo=datos['insumo']).values('compra_id')
            )
        return filtrar_por_fechas(queryset, datos)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['monto_total'] = self.get_queryset_filtrado().aggregate(total=Sum('total'))['total'] or 0
        return context


class CompraCreateView(GroupRequiredMixin, FormView):
    form_class = CompraForm
    template_name = 'dashboard/compra_form.html'
    allowed_groups = ['Administrador']

    def get_formset(self):
        if self.request.method == 'POST':
            return DetalleCompraFormSet(self.request.POST, prefix=DETALLE_COMPRA_PREFIX)
        inicial = []
        insumo_id = self.request.GET.get('insumo')
        if insumo_id and Insumo.objects.filter(pk=insumo_id, activo=True).exists():
            inicial = [{'insumo': insumo_id}]
        return DetalleCompraFormSet(prefix=DETALLE_COMPRA_PREFIX, initial=inicial)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('formset', self.get_formset())
        context['insumos_info'] = {
            str(i.pk): {'unidad': i.unidad_medida, 'costo': str(i.costo_unitario)}
            for i in Insumo.objects.filter(activo=True)
        }
        return context

    def form_valid(self, form):
        formset = self.get_formset()
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))
        lineas = [
            (f.cleaned_data['insumo'], f.cleaned_data['cantidad'], f.cleaned_data['monto'])
            for f in formset.forms if f.cleaned_data
        ]
        compra = registrar_compra(
            usuario=self.request.user,
            lineas=lineas,
            proveedor=form.cleaned_data['proveedor'],
            fecha=form.fecha_y_hora(),
            numero_factura=form.cleaned_data['numero_factura'],
            observacion=form.cleaned_data['observacion'],
        )
        messages.success(
            self.request,
            f'Compra {compra.codigo} registrada: se sumó el stock de {len(lineas)} insumo(s).',
        )
        return redirect('dashboard:compra_detail', pk=compra.pk)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form, formset=self.get_formset()))


class CompraDetailView(GroupRequiredMixin, DetailView):
    model = Compra
    template_name = 'dashboard/compra_detail.html'
    context_object_name = 'compra'
    allowed_groups = ['Administrador']

    def get_queryset(self):
        return Compra.objects.select_related('proveedor', 'usuario').prefetch_related('detalles__insumo')
