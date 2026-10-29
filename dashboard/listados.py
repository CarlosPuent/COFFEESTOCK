"""Comportamiento común de las tablas del panel: filtros, orden por columna,
paginación con tamaño de página y contador de resultados.

Uso:
    class InsumoListView(ListadoMixin, GroupRequiredMixin, ListView):
        filtro_form_class = InsumoFilterForm
        columnas_orden = {'nombre': 'nombre', 'stock': 'stock_actual'}
        orden_defecto = 'nombre'

        def filtrar(self, queryset, datos):
            ...
"""
import re

from django import forms
from django.db.models import Q

OPCIONES_POR_PAGINA = (10, 20, 50, 100)
PARAMETROS_DE_LISTADO = {'page', 'orden', 'por_pagina'}


class FiltroForm(forms.Form):
    """Formulario de filtros: aplica el estilo compacto a todos sus campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')


def buscar_por_nombre_o_codigo(queryset, texto, prefijo, campo='nombre', otros_campos=()):
    """Busca por nombre (u otros campos de texto) o por código (INS-0007, ins7, 7)."""
    texto = (texto or '').strip()
    if not texto:
        return queryset
    condicion = Q(**{f'{campo}__icontains': texto})
    for otro in otros_campos:
        condicion |= Q(**{f'{otro}__icontains': texto})
    coincide = re.fullmatch(rf'(?:{prefijo}-?)?0*(\d+)', texto, flags=re.IGNORECASE)
    if coincide:
        condicion |= Q(pk=int(coincide.group(1)))
    return queryset.filter(condicion)


class ListadoMixin:
    # Exportar a Excel: columnas (titulo, formato, ancho[, sumar]) y una
    # función que convierte cada objeto en su fila.
    columnas_excel = None
    titulo_excel = None
    filtro_form_class = None
    # clave que viaja en la URL -> campo (o lista de campos) para order_by
    columnas_orden = {}
    # clave de columnas_orden; con '-' delante para orden descendente
    orden_defecto = None
    paginate_by = 20

    def fila_excel(self, objeto):
        raise NotImplementedError

    def get(self, request, *args, **kwargs):
        if request.GET.get('exportar') == 'xlsx' and self.columnas_excel:
            return self.exportar_excel()
        return super().get(request, *args, **kwargs)

    def descripcion_filtros(self):
        form = self.get_filtro_form()
        if form is None or not form.is_valid():
            return 'Sin filtros'
        partes = []
        for nombre, valor in form.cleaned_data.items():
            if valor in (None, '', []):
                continue
            campo = form.fields[nombre]
            if hasattr(campo, 'choices') and not hasattr(valor, 'pk'):
                valor = dict(campo.choices).get(valor, valor)
            elif hasattr(valor, 'strftime'):
                valor = valor.strftime('%d/%m/%Y')
            partes.append(f'{campo.label}: {valor}')
        return 'Filtros: ' + '; '.join(partes) if partes else 'Sin filtros'

    def exportar_excel(self):
        from django.http import HttpResponse
        from django.utils import timezone

        from .reportes.excel import LibroExcel

        titulo = self.titulo_excel or self.model._meta.verbose_name_plural.capitalize()
        libro = LibroExcel(titulo, self.descripcion_filtros(), self.request.user)
        libro.hoja(titulo, self.columnas_excel,
                   [self.fila_excel(obj) for obj in self.get_queryset_filtrado()], totales=True)
        respuesta = HttpResponse(
            libro.generar(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        nombre = f'coffeestock-{self.model._meta.model_name}-{timezone.localdate():%Y%m%d}.xlsx'
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
        return respuesta

    # --- filtros ---

    def get_filtro_form(self):
        if not hasattr(self, '_filtro_form'):
            self._filtro_form = (
                self.filtro_form_class(self.request.GET or None)
                if self.filtro_form_class else None
            )
        return self._filtro_form

    def filtrar(self, queryset, datos):
        return queryset

    def get_queryset_filtrado(self):
        """Queryset con filtros y orden, sin paginar (también lo usa exportar)."""
        queryset = super().get_queryset()
        form = self.get_filtro_form()
        if form is not None and form.is_valid():
            queryset = self.filtrar(queryset, form.cleaned_data)
        return self.ordenar(queryset)

    def get_queryset(self):
        return self.get_queryset_filtrado()

    # --- orden ---

    def get_orden(self):
        orden = self.request.GET.get('orden') or self.orden_defecto or ''
        if orden.lstrip('-') not in self.columnas_orden:
            orden = self.orden_defecto or ''
        return orden

    def ordenar(self, queryset):
        orden = self.get_orden()
        if not orden:
            return queryset
        descendente = orden.startswith('-')
        campos = self.columnas_orden[orden.lstrip('-')]
        if isinstance(campos, str):
            campos = [campos]
        signo = '-' if descendente else ''
        # pk al final para que el orden sea estable entre páginas
        return queryset.order_by(*[signo + c for c in campos], signo + 'pk')

    # --- paginación ---

    def get_paginate_by(self, queryset):
        try:
            por_pagina = int(self.request.GET.get('por_pagina', self.paginate_by))
        except (TypeError, ValueError):
            por_pagina = self.paginate_by
        return por_pagina if por_pagina in OPCIONES_POR_PAGINA else self.paginate_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['querystring'] = params.urlencode()
        sin_orden = params.copy()
        sin_orden.pop('orden', None)
        context['querystring_sin_orden'] = sin_orden.urlencode()
        sin_tamano = params.copy()
        sin_tamano.pop('por_pagina', None)
        context['querystring_sin_tamano'] = sin_tamano.urlencode()

        context['filtro_form'] = self.get_filtro_form() or None
        context['orden_actual'] = self.get_orden()
        context['por_pagina'] = self.get_paginate_by(None)
        context['opciones_por_pagina'] = OPCIONES_POR_PAGINA
        context['hay_filtros'] = any(
            valor for clave, valor in self.request.GET.items()
            if clave not in PARAMETROS_DE_LISTADO
        )

        paginator = context.get('paginator')
        page_obj = context.get('page_obj')
        if paginator is not None and page_obj is not None:
            context['total_resultados'] = paginator.count
            context['paginas'] = list(
                paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
            )
            context['elipsis'] = paginator.ELLIPSIS
        else:
            context['total_resultados'] = len(context.get('object_list') or [])
        return context
