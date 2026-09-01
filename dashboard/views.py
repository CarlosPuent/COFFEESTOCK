from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from core.mixins import GroupRequiredMixin
from core.models import Insumo, Producto

from .forms import RECETA_INSUMO_FORMSET_PREFIX, InsumoForm, ProductoForm, RecetaInsumoFormSet


class DashboardIndexView(GroupRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'
    allowed_groups = ['Administrador']


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

class InsumoListView(GroupRequiredMixin, ListView):
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

class ProductoListView(GroupRequiredMixin, ListView):
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
