import datetime
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.forms import formset_factory, inlineformset_factory
from django.utils import timezone

from core.models import Compra, Insumo, Merma, Producto, Proveedor, RecetaInsumo

from .listados import FiltroForm

User = get_user_model()


def campo_fecha(label):
    """Campo de fecha para filtros: se muestra como dd/mm/aaaa con el
    selector de calendario y se envía como AAAA-MM-DD."""
    return forms.DateField(
        required=False,
        label=label,
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={
                'class': 'form-control form-control-sm',
                'data-fecha': '',
                'placeholder': 'dd/mm/aaaa',
                'autocomplete': 'off',
            },
        ),
    )


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


ESTADO_CHOICES = [('', 'Todos'), ('activos', 'Activos'), ('inactivos', 'Inactivos')]


def campo_monto(label, placeholder):
    return forms.DecimalField(
        required=False,
        label=label,
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'placeholder': placeholder, 'step': '0.01'}),
    )


class InsumoFilterForm(FiltroForm):
    q = forms.CharField(
        required=False, label='Buscar',
        widget=forms.TextInput(attrs={'placeholder': 'Nombre o código (INS-0001)'}),
    )
    unidad = forms.ChoiceField(
        required=False, label='Unidad',
        choices=[('', 'Todas')] + list(Insumo.UnidadMedida.choices),
    )
    stock = forms.ChoiceField(
        required=False, label='Stock',
        choices=[('', 'Todos'), ('bajo', 'En alerta (bajo el mínimo)'), ('normal', 'Normal')],
    )
    estado = forms.ChoiceField(required=False, label='Estado', choices=ESTADO_CHOICES)


class ProductoFilterForm(FiltroForm):
    q = forms.CharField(
        required=False, label='Buscar',
        widget=forms.TextInput(attrs={'placeholder': 'Nombre o código (PRD-0001)'}),
    )
    categoria = forms.ChoiceField(
        required=False, label='Categoría',
        choices=[('', 'Todas')] + list(Producto.Categoria.choices),
    )
    estado = forms.ChoiceField(required=False, label='Estado', choices=ESTADO_CHOICES)
    precio_min = campo_monto('Precio desde', '$ mín.')
    precio_max = campo_monto('Precio hasta', '$ máx.')


class MermaFilterForm(FiltroForm):
    insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.all(), required=False, label='Insumo',
        empty_label='Todos los insumos',
    )
    causa = forms.ChoiceField(
        choices=[('', 'Todas las causas')] + list(Merma.Causa.choices),
        required=False, label='Causa',
    )
    responsable = forms.ModelChoiceField(
        queryset=User.objects.filter(mermas__isnull=False).distinct().order_by('username'),
        required=False, label='Responsable', empty_label='Todos',
    )
    fecha_desde = campo_fecha('Desde')
    fecha_hasta = campo_fecha('Hasta')


class VentaFilterForm(FiltroForm):
    q = forms.CharField(
        required=False, label='Folio',
        widget=forms.TextInput(attrs={'placeholder': 'V-000123'}),
    )
    usuario_cajero = forms.ModelChoiceField(
        queryset=User.objects.filter(ventas__isnull=False).distinct().order_by('username'),
        required=False, label='Cajero', empty_label='Todos los cajeros',
    )
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.all(), required=False, label='Producto',
        empty_label='Todos',
    )
    fecha_desde = campo_fecha('Desde')
    fecha_hasta = campo_fecha('Hasta')
    total_min = campo_monto('Total desde', '$ mín.')
    total_max = campo_monto('Total hasta', '$ máx.')


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


# ---------------------------------------------------------------------------
# Proveedores y compras
# ---------------------------------------------------------------------------

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto', 'telefono', 'correo', 'notas', 'activo']
        widgets = {'notas': forms.Textarea(attrs={'rows': 3})}
        labels = {'correo': 'Correo electrónico'}


class ProveedorFilterForm(FiltroForm):
    q = forms.CharField(
        required=False, label='Buscar',
        widget=forms.TextInput(attrs={'placeholder': 'Nombre, contacto o código'}),
    )
    estado = forms.ChoiceField(required=False, label='Estado', choices=ESTADO_CHOICES)


class CompraForm(forms.Form):
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.filter(activo=True), required=False,
        label='Proveedor', empty_label='Sin proveedor',
    )
    fecha = forms.DateField(
        label='Fecha de la compra',
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'data-fecha': '', 'autocomplete': 'off'}),
    )
    numero_factura = forms.CharField(label='N.º de factura', max_length=50, required=False)
    observacion = forms.CharField(
        label='Observación', required=False, widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].initial = timezone.localdate()

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha > timezone.localdate():
            raise forms.ValidationError('La fecha no puede ser futura.')
        return fecha

    def fecha_y_hora(self):
        """Hoy: la hora actual. Otro día: el mediodía de esa fecha."""
        fecha = self.cleaned_data['fecha']
        if fecha == timezone.localdate():
            return timezone.now()
        return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time(12, 0)))


class DetalleCompraForm(forms.Form):
    insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.filter(activo=True), label='Insumo',
        empty_label='Selecciona un insumo',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    cantidad = forms.DecimalField(
        label='Cantidad', min_value=Decimal('0.01'), max_digits=12, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
    )
    monto = forms.DecimalField(
        label='Monto pagado', min_value=Decimal('0'), max_digits=12, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
    )


DetalleCompraFormSet = formset_factory(
    DetalleCompraForm, extra=0, min_num=1, validate_min=True,
)
DETALLE_COMPRA_PREFIX = 'lineas'


class CompraFilterForm(FiltroForm):
    q = forms.CharField(
        required=False, label='Buscar',
        widget=forms.TextInput(attrs={'placeholder': 'Folio o n.º de factura'}),
    )
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.all(), required=False, label='Proveedor', empty_label='Todos',
    )
    insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.all(), required=False, label='Insumo', empty_label='Todos',
    )
    fecha_desde = campo_fecha('Desde')
    fecha_hasta = campo_fecha('Hasta')
