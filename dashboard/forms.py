from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from core.models import Insumo, Merma, Producto, RecetaInsumo

User = get_user_model()


def anteponer_opcion_vacia(campo, texto):
    """Reemplaza la opción vacía por defecto de Django ('---------') por una
    etiqueta en español, conservando el resto de las opciones."""
    opciones = [(valor, etiqueta) for valor, etiqueta in campo.choices if valor != '']
    campo.choices = [('', texto)] + opciones


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = [
            'nombre', 'unidad_medida', 'stock_actual', 'stock_minimo',
            'costo_unitario', 'activo',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        anteponer_opcion_vacia(self.fields['unidad_medida'], 'Selecciona una unidad')


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'categoria', 'precio_venta', 'activo', 'imagen']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        anteponer_opcion_vacia(self.fields['categoria'], 'Selecciona una categoría')


class MermaForm(forms.ModelForm):
    class Meta:
        model = Merma
        fields = ['insumo', 'cantidad', 'causa', 'observacion']
        widgets = {
            'observacion': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['insumo'].empty_label = 'Selecciona un insumo'
        anteponer_opcion_vacia(self.fields['causa'], 'Selecciona una causa')


class MermaFilterForm(forms.Form):
    insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.all(),
        required=False,
        label='Insumo',
        empty_label='Todos los insumos',
    )
    causa = forms.ChoiceField(
        choices=[('', 'Todas las causas')] + list(Merma.Causa.choices),
        required=False,
        label='Causa',
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


class VentaFilterForm(forms.Form):
    usuario_cajero = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Cajero').order_by('username'),
        required=False,
        label='Cajero',
        empty_label='Todos los cajeros',
    )
    fecha_desde = forms.DateField(
        required=False, label='Desde', widget=forms.DateInput(attrs={'type': 'date'})
    )
    fecha_hasta = forms.DateField(
        required=False, label='Hasta', widget=forms.DateInput(attrs={'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['usuario_cajero'].widget.attrs['class'] = 'form-select form-select-sm'
        self.fields['fecha_desde'].widget.attrs['class'] = 'form-control form-control-sm'
        self.fields['fecha_hasta'].widget.attrs['class'] = 'form-control form-control-sm'


RECETA_INSUMO_FORMSET_PREFIX = 'receta_insumos'


class RecetaInsumoForm(forms.ModelForm):
    class Meta:
        model = RecetaInsumo
        fields = ['insumo', 'cantidad_requerida']
        widgets = {
            'insumo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'cantidad_requerida': forms.NumberInput(
                attrs={'class': 'form-control form-control-sm', 'step': '0.01'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['insumo'].empty_label = 'Selecciona un insumo'


RecetaInsumoFormSet = inlineformset_factory(
    Producto,
    RecetaInsumo,
    form=RecetaInsumoForm,
    fields=['insumo', 'cantidad_requerida'],
    extra=1,
    can_delete=True,
)
