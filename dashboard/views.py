import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from core.mixins import GroupRequiredMixin
from core.models import Insumo, Merma, Producto

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
