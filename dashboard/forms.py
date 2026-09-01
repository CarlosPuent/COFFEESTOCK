from django import forms
from django.forms import inlineformset_factory

from core.models import Insumo, Merma, Producto, RecetaInsumo


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


class MermaForm(forms.ModelForm):
    class Meta:
        model = Merma
        fields = ['insumo', 'cantidad', 'causa', 'observacion']
        widgets = {
            'observacion': forms.Textarea(attrs={'rows': 3}),
        }


class MermaFilterForm(forms.Form):
    insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.all(), required=False, label='Insumo'
    )
    causa = forms.ChoiceField(
        choices=[('', 'Todas')] + list(Merma.Causa.choices), required=False, label='Causa'
    )
    fecha_desde = forms.DateField(
        required=False, label='Desde', widget=forms.DateInput(attrs={'type': 'date'})
    )
    fecha_hasta = forms.DateField(
        required=False, label='Hasta', widget=forms.DateInput(attrs={'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['insumo'].widget.attrs['class'] = 'form-select form-select-sm'
        self.fields['causa'].widget.attrs['class'] = 'form-select form-select-sm'
        self.fields['fecha_desde'].widget.attrs['class'] = 'form-control form-control-sm'
        self.fields['fecha_hasta'].widget.attrs['class'] = 'form-control form-control-sm'


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
