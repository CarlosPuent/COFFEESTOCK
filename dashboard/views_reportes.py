import datetime

from django import forms
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from core.mixins import GroupRequiredMixin

from .forms_usuarios import CorteCajaForm
from .listados import FiltroForm
from .reportes.generadores import CATALOGO, pdf_corte_caja
from .views_usuarios import es_administrador

TIPOS = {
    'pdf': ('application/pdf', 'inline'),
    'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'attachment'),
}


def respuesta_archivo(contenido, formato, nombre):
    tipo, disposicion = TIPOS[formato]
    respuesta = HttpResponse(contenido, content_type=tipo)
    respuesta['Content-Disposition'] = f'{disposicion}; filename="{nombre}.{formato}"'
    return respuesta


class PeriodoForm(FiltroForm):
    desde = forms.DateField(
        label='Desde', input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'data-fecha': '', 'autocomplete': 'off'}),
    )
    hasta = forms.DateField(
        label='Hasta', input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'data-fecha': '', 'autocomplete': 'off'}),
    )

    def clean(self):
        datos = super().clean()
        if datos.get('desde') and datos.get('hasta') and datos['desde'] > datos['hasta']:
            raise forms.ValidationError('La fecha "desde" no puede ser posterior a "hasta".')
        return datos


def periodos_rapidos():
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    fin_mes_anterior = inicio_mes - datetime.timedelta(days=1)
    return [
        ('Hoy', hoy, hoy),
        ('Últimos 7 días', hoy - datetime.timedelta(days=6), hoy),
        ('Este mes', inicio_mes, hoy),
        ('Mes anterior', fin_mes_anterior.replace(day=1), fin_mes_anterior),
    ]


def leer_periodo(request):
    hoy = timezone.localdate()
    datos = request.GET.copy()
    datos.setdefault('desde', hoy.replace(day=1).isoformat())
    datos.setdefault('hasta', hoy.isoformat())
    form = PeriodoForm(datos)
    if form.is_valid():
        return form, form.cleaned_data['desde'], form.cleaned_data['hasta']
    return form, hoy.replace(day=1), hoy


class ReportesView(GroupRequiredMixin, TemplateView):
    template_name = 'dashboard/reportes.html'
    allowed_groups = ['Administrador']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form, desde, hasta = leer_periodo(self.request)
        grupos = {}
        for clave, reporte in CATALOGO.items():
            # La plantilla recibe datos, no las funciones generadoras: Django
            # intentaría ejecutarlas al evaluarlas.
            grupos.setdefault(reporte['grupo'], []).append({
                'clave': clave,
                'titulo': reporte['titulo'],
                'descripcion': reporte['descripcion'],
                'icono': reporte['icono'],
                'nota_xlsx': reporte.get('nota_xlsx', ''),
                'periodo': reporte['periodo'],
                'pdf': 'pdf' in reporte,
                'xlsx': 'xlsx' in reporte,
            })
        context.update({
            'filtro_form': form,
            'desde': desde,
            'hasta': hasta,
            'grupos': grupos,
            'periodos_rapidos': periodos_rapidos(),
            'hay_filtros': False,
        })
        return context


class DescargarReporteView(GroupRequiredMixin, View):
    allowed_groups = ['Administrador']

    def get(self, request, clave, formato):
        reporte = CATALOGO.get(clave)
        if reporte is None or formato not in TIPOS or formato not in reporte:
            raise Http404('Reporte no disponible en ese formato.')
        generador = reporte[formato]
        if reporte['periodo']:
            _, desde, hasta = leer_periodo(request)
            contenido = generador(desde, hasta, request.user)
            nombre = f'coffeestock-{clave}-{desde:%Y%m%d}-{hasta:%Y%m%d}'
        else:
            contenido = generador(request.user)
            nombre = f'coffeestock-{clave}-{timezone.localdate():%Y%m%d}'
        return respuesta_archivo(contenido, formato, nombre)


class CorteCajaPDFView(GroupRequiredMixin, View):
    """El PDF del corte respeta las mismas reglas que la pantalla: un
    cajero solo obtiene su propio corte."""

    allowed_groups = ['Administrador', 'Cajero']

    def get(self, request):
        datos = request.GET.copy()
        datos.setdefault('fecha', timezone.localdate().isoformat())
        form = CorteCajaForm(datos)
        fecha, cajero = timezone.localdate(), None
        if form.is_valid():
            fecha, cajero = form.cleaned_data['fecha'], form.cleaned_data.get('cajero')
        if not es_administrador(request.user):
            cajero = request.user
        contenido = pdf_corte_caja(fecha, request.user, cajero=cajero)
        sufijo = f'-{cajero.get_username()}' if cajero else ''
        return respuesta_archivo(contenido, 'pdf', f'coffeestock-corte-{fecha:%Y%m%d}{sufijo}')
