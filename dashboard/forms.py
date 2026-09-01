from django import forms
from django.forms import inlineformset_factory

from core.models import Insumo, Producto, RecetaInsumo


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = [
            'nombre', 'unidad_medida', 'stock_actual', 'stock_minimo',
            'costo_unitario', 'activo',
        ]


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'categoria', 'precio_venta', 'activo', 'imagen']


RECETA_INSUMO_FORMSET_PREFIX = 'receta_insumos'

RecetaInsumoFormSet = inlineformset_factory(
    Producto,
    RecetaInsumo,
    fields=['insumo', 'cantidad_requerida'],
    extra=1,
    can_delete=True,
    widgets={
        'insumo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'cantidad_requerida': forms.NumberInput(
            attrs={'class': 'form-control form-control-sm', 'step': '0.01'}
        ),
    },
)
