import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import (
    Case, Count, DecimalField, Exists, ExpressionWrapper, F, OuterRef, ProtectedError,
    Sum, Value, When,
)
from django.db.models.functions import Coalesce, ExtractHour, TruncDate
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView,
)

from core.mixins import GroupRequiredMixin
from core.services.alertas import estado_configuracion
from core.services.ventas import VentaError, anular_venta
from core.templatetags.formato import cantidad, unidad_corta
from core.models import DetalleVenta, Insumo, Merma, Producto, Venta

from .forms import (
    RECETA_INSUMO_FORMSET_PREFIX,
    AnularVentaForm,
    InsumoFilterForm,
    InsumoForm,
    MermaFilterForm,
    MermaForm,
    ProductoFilterForm,
    ProductoForm,
    RecetaInsumoFormSet,
    VentaFilterForm,
)
from .listados import ListadoMixin, buscar_por_nombre_o_codigo

DINERO = DecimalField(max_digits=28, decimal_places=6)


def inicio_del_dia(fecha):
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time.min))


def fin_del_dia(fecha):
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time.max))


def filtrar_por_fechas(queryset, datos, campo='fecha'):
    if datos.get('fecha_desde'):
        queryset = queryset.filter(**{f'{campo}__gte': inicio_del_dia(datos['fecha_desde'])})
    if datos.get('fecha_hasta'):
        queryset = queryset.filter(**{f'{campo}__lte': fin_del_dia(datos['fecha_hasta'])})
    return queryset


def insumos_info():
    """Unidad y costo de cada insumo activo, para los cálculos en vivo de
    los formularios (receta, compra, merma)."""
    return {
        str(i.pk): {'unidad': i.unidad_medida, 'costo': str(i.costo_unitario), 'stock': str(i.stock_actual)}
        for i in Insumo.objects.filter(activo=True)
    }


def filtrar_por_estado(queryset, estado):
    if estado == 'activos':
        return queryset.filter(activo=True)
    if estado == 'inactivos':
        return queryset.filter(activo=False)
    return queryset


PERIODOS_DASHBOARD = {
    '7': 'Últimos 7 días',
    '30': 'Últimos 30 días',
    'mes': 'Este mes',
}


def _variacion(actual, anterior):
    """Variación porcentual; None si no hay base de comparación."""
    if not anterior:
        return None
    return (actual - anterior) / anterior * 100


class DashboardIndexView(GroupRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'
    allowed_groups = ['Administrador']

    def get_periodo(self):
        clave = self.request.GET.get('periodo', '7')
        if clave not in PERIODOS_DASHBOARD:
            clave = '7'
        hoy = timezone.localdate()
        if clave == 'mes':
            desde = hoy.replace(day=1)
        else:
            desde = hoy - datetime.timedelta(days=int(clave) - 1)
        return clave, desde, hoy

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        ayer = hoy - datetime.timedelta(days=1)
        clave, desde, hasta = self.get_periodo()
        completadas = Venta.objects.completadas()

        def total_y_num(qs):
            fila = qs.aggregate(total=Coalesce(Sum('total'), Value(0, output_field=DINERO)), num=Count('id'))
            return fila['total'], fila['num']

        def del_dia(fecha):
            return completadas.filter(fecha__range=(inicio_del_dia(fecha), fin_del_dia(fecha)))

        # --- Indicadores ---
        total_hoy, num_hoy = total_y_num(del_dia(hoy))
        total_ayer, _ = total_y_num(del_dia(ayer))
        total_mes, num_mes = total_y_num(completadas.filter(fecha__gte=inicio_del_dia(hoy.replace(day=1))))
        insumos = Insumo.objects.all()
        context['kpi'] = {
            'total_hoy': total_hoy,
            'num_hoy': num_hoy,
            'variacion_hoy': _variacion(total_hoy, total_ayer),
            'ticket_hoy': total_hoy / num_hoy if num_hoy else 0,
            'total_mes': total_mes,
            'num_mes': num_mes,
            'en_alerta': insumos.filter(activo=True, stock_actual__lte=F('stock_minimo')).count(),
            'valor_inventario': insumos.aggregate(
                v=Coalesce(Sum(ExpressionWrapper(F('stock_actual') * F('costo_unitario'), output_field=DINERO)),
                           Value(0, output_field=DINERO))
            )['v'],
        }

        context['insumos_alerta'] = Insumo.objects.filter(
            activo=True, stock_actual__lte=F('stock_minimo'),
        ).order_by('nombre')
        context['estado_correo'] = estado_configuracion()
        context['ultimas_ventas'] = Venta.objects.select_related('usuario_cajero').order_by('-fecha')[:6]
        context['periodo'] = clave
        context['periodos'] = PERIODOS_DASHBOARD
        context['periodo_texto'] = PERIODOS_DASHBOARD[clave]

        en_periodo = completadas.filter(fecha__range=(inicio_del_dia(desde), fin_del_dia(hasta)))

        # --- Ventas por día del período (días sin ventas en 0) ---
        por_dia = {
            fila['dia']: fila['monto']
            for fila in en_periodo.annotate(dia=TruncDate('fecha')).values('dia').annotate(monto=Sum('total'))
        }
        dias = [desde + datetime.timedelta(days=i) for i in range((hasta - desde).days + 1)]
        graficas = {
            'ventas': {
                'labels': [d.strftime('%d/%m') for d in dias],
                'data': [float(por_dia.get(d, 0)) for d in dias],
            },
        }

        # --- Top 5 productos por importe ---
        top = list(
            DetalleVenta.objects.filter(venta__in=en_periodo)
            .values('producto__nombre')
            .annotate(importe=Sum('subtotal'), unidades=Sum('cantidad'))
            .order_by('-importe')[:5]
        )
        graficas['productos'] = {
            'labels': [f['producto__nombre'] for f in top],
            'data': [float(f['importe']) for f in top],
            'unidades': [float(f['unidades']) for f in top],
        }

        # --- Horas pico ---
        por_hora = {
            f['hora']: f
            for f in en_periodo.annotate(hora=ExtractHour('fecha')).values('hora')
            .annotate(num=Count('id'), monto=Sum('total'))
        }
        if por_hora:
            horas = list(range(min(por_hora), max(por_hora) + 1))
        else:
            horas = []
        graficas['horas'] = {
            'labels': [f'{h:02d}:00' for h in horas],
            'data': [por_hora[h]['num'] if h in por_hora else 0 for h in horas],
        }

        # --- Mermas del período por causa (en dinero: las cantidades mezclan unidades) ---
        causas = dict(Merma.Causa.choices)
        mermas = list(
            Merma.objects.filter(fecha__range=(inicio_del_dia(desde), fin_del_dia(hasta)))
            .values('causa')
            .annotate(costo=Sum(ExpressionWrapper(F('cantidad') * F('insumo__costo_unitario'), output_field=DINERO)))
            .order_by('-costo')
        )
        graficas['mermas'] = {
            'labels': [causas.get(f['causa'], f['causa']) for f in mermas],
            'data': [round(float(f['costo']), 2) for f in mermas],
        }

        context['graficas'] = graficas
        context['hay_ventas'] = bool(por_dia)
        context['hay_mermas'] = bool(mermas)
        context['total_periodo'] = sum(por_dia.values(), 0)
        return context


class ProtectedDeleteMixin:
    """Maneja con gracia el borrado de objetos protegidos (on_delete=PROTECT)."""

    protected_error_message = (
        'No se puede eliminar "{object}" porque tiene registros relacionados '
        '(recetas, compras, ventas o mermas). Desactívalo en lugar de eliminarlo.'
    )

    def form_valid(self, form):
        object_display = getattr(self.object, 'nombre', str(self.object))
        try:
            respuesta = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                self.protected_error_message.format(object=object_display),
            )
            return redirect(self.success_url)
        messages.success(self.request, f'"{object_display}" eliminado.')
        return respuesta


# ---------------------------------------------------------------------------
# Insumo
# ---------------------------------------------------------------------------

class InsumoListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Insumo
    template_name = 'dashboard/insumo_list.html'
    context_object_name = 'insumos'
    allowed_groups = ['Administrador']
    filtro_form_class = InsumoFilterForm
    titulo_excel = 'Insumos'
    columnas_excel = [
        ('Código', 'texto', 11), ('Insumo', 'texto', 26), ('Unidad', 'texto', 11),
        ('Stock actual', 'cantidad', 13), ('Stock mínimo', 'cantidad', 13),
        ('Costo unitario', 'costo', 14), ('Valor en inventario', 'moneda', 18), ('Estado', 'texto', 13),
    ]

    def fila_excel(self, i):
        estado = 'Inactivo' if not i.activo else ('Bajo mínimo' if i.stock_bajo else 'Normal')
        return [i.codigo, i.nombre, i.get_unidad_medida_display(), i.stock_actual, i.stock_minimo,
                i.costo_unitario, i.valor, estado]
    columnas_orden = {
        'codigo': 'pk',
        'nombre': 'nombre',
        'unidad': 'unidad_medida',
        'stock': 'stock_actual',
        'minimo': 'stock_minimo',
        'costo': 'costo_unitario',
        'valor': 'valor',
        'activo': 'activo',
    }
    orden_defecto = 'nombre'

    def filtrar(self, queryset, datos):
        queryset = buscar_por_nombre_o_codigo(queryset, datos.get('q'), Insumo.PREFIJO)
        if datos.get('unidad'):
            queryset = queryset.filter(unidad_medida=datos['unidad'])
        if datos.get('stock') == 'bajo':
            queryset = queryset.filter(stock_actual__lte=F('stock_minimo'))
        elif datos.get('stock') == 'normal':
            queryset = queryset.filter(stock_actual__gt=F('stock_minimo'))
        return filtrar_por_estado(queryset, datos.get('estado'))

    def get_queryset_filtrado(self):
        self.queryset = Insumo.objects.annotate(
            valor=ExpressionWrapper(F('stock_actual') * F('costo_unitario'), output_field=DINERO),
        )
        return super().get_queryset_filtrado()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtrado = self.get_queryset_filtrado()
        context['valor_total'] = filtrado.aggregate(total=Sum('valor'))['total'] or 0
        context['insumos_en_alerta'] = filtrado.filter(stock_actual__lte=F('stock_minimo')).count()
        return context


class InsumoFormMixin:
    model = Insumo
    form_class = InsumoForm
    template_name = 'dashboard/insumo_form.html'
    success_url = reverse_lazy('dashboard:insumo_list')
    allowed_groups = ['Administrador']

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            self.object.sincronizar_alerta()
        messages.success(self.request, f'Insumo "{self.object.nombre}" guardado.')
        return response


class InsumoCreateView(InsumoFormMixin, GroupRequiredMixin, CreateView):
    pass


class InsumoUpdateView(InsumoFormMixin, GroupRequiredMixin, UpdateView):
    pass


class InsumoDeleteView(GroupRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Insumo
    template_name = 'dashboard/confirmar_eliminar.html'
    success_url = reverse_lazy('dashboard:insumo_list')
    allowed_groups = ['Administrador']


# ---------------------------------------------------------------------------
# Producto (con formset inline de RecetaInsumo)
# ---------------------------------------------------------------------------

class ProductoListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Producto
    template_name = 'dashboard/producto_list.html'
    context_object_name = 'productos'
    allowed_groups = ['Administrador']
    filtro_form_class = ProductoFilterForm
    titulo_excel = 'Productos'
    columnas_excel = [
        ('Código', 'texto', 11), ('Producto', 'texto', 24), ('Categoría', 'texto', 13),
        ('Precio de venta', 'moneda', 15, False), ('Costo', 'moneda', 11, False),
        ('Margen', 'porcentaje', 10), ('Estado', 'texto', 11),
    ]

    def fila_excel(self, p):
        return [p.codigo, p.nombre, p.get_categoria_display(), p.precio_venta, p.costo_total,
                p.margen_pct, 'Activo' if p.activo else 'Inactivo']
    columnas_orden = {
        'codigo': 'pk',
        'nombre': 'nombre',
        'categoria': 'categoria',
        'precio': 'precio_venta',
        'costo': 'costo_total',
        'margen': 'margen_pct',
        'activo': 'activo',
    }
    orden_defecto = 'nombre'

    def get_queryset_filtrado(self):
        costo = Coalesce(
            Sum(
                F('receta_insumos__cantidad_requerida') * F('receta_insumos__insumo__costo_unitario'),
                output_field=DINERO,
            ),
            Value(0, output_field=DINERO),
        )
        self.queryset = Producto.objects.annotate(costo_total=costo).annotate(
            margen_pct=Case(
                When(
                    precio_venta__gt=0,
                    then=ExpressionWrapper(
                        (F('precio_venta') - F('costo_total')) * 100 / F('precio_venta'),
                        output_field=DINERO,
                    ),
                ),
                default=None,
                output_field=DINERO,
            ),
        )
        return super().get_queryset_filtrado()

    def filtrar(self, queryset, datos):
        queryset = buscar_por_nombre_o_codigo(queryset, datos.get('q'), Producto.PREFIJO)
        if datos.get('categoria'):
            queryset = queryset.filter(categoria=datos['categoria'])
        if datos.get('precio_min') is not None:
            queryset = queryset.filter(precio_venta__gte=datos['precio_min'])
        if datos.get('precio_max') is not None:
            queryset = queryset.filter(precio_venta__lte=datos['precio_max'])
        return filtrar_por_estado(queryset, datos.get('estado'))


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
        context['insumos_info'] = insumos_info()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        receta_formset = context['receta_formset']
        if receta_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                receta_formset.instance = self.object
                receta_formset.save()
            messages.success(self.request, f'Producto "{self.object.nombre}" guardado.')
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form))


class ProductoCreateView(ProductoFormsetMixin, GroupRequiredMixin, CreateView):
    pass


class ProductoUpdateView(ProductoFormsetMixin, GroupRequiredMixin, UpdateView):
    pass


class ProductoDeleteView(GroupRequiredMixin, ProtectedDeleteMixin, DeleteView):
    model = Producto
    template_name = 'dashboard/confirmar_eliminar.html'
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
            f'Merma {merma.codigo} registrada: {cantidad(merma.cantidad)} '
            f'{unidad_corta(merma.insumo.unidad_medida)} de {merma.insumo.nombre}.',
        )
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['insumos_info'] = insumos_info()
        return context

    def get_success_url(self):
        if self.request.user.groups.filter(name='Administrador').exists():
            return reverse('dashboard:merma_list')
        return reverse('pos:index')


class MermaListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Merma
    template_name = 'dashboard/merma_list.html'
    context_object_name = 'mermas'
    allowed_groups = ['Administrador']
    filtro_form_class = MermaFilterForm
    titulo_excel = 'Mermas'
    columnas_excel = [
        ('Código', 'texto', 11), ('Fecha', 'fechahora', 17), ('Insumo', 'texto', 24),
        ('Cantidad', 'cantidad', 11), ('Unidad', 'texto', 9), ('Causa', 'texto', 17),
        ('Costo', 'moneda', 12), ('Responsable', 'texto', 16), ('Observación', 'texto', 40),
    ]

    def fila_excel(self, m):
        return [m.codigo, m.fecha, m.insumo.nombre, m.cantidad, m.insumo.get_unidad_medida_display(),
                m.get_causa_display(), m.costo_merma, m.usuario_responsable.get_username(), m.observacion]
    columnas_orden = {
        'codigo': 'pk',
        'fecha': 'fecha',
        'insumo': 'insumo__nombre',
        'cantidad': 'cantidad',
        'causa': 'causa',
        'costo': 'costo_merma',
        'responsable': 'usuario_responsable__username',
    }
    orden_defecto = '-fecha'

    def get_queryset_filtrado(self):
        self.queryset = Merma.objects.select_related('insumo', 'usuario_responsable').annotate(
            costo_merma=ExpressionWrapper(F('cantidad') * F('insumo__costo_unitario'), output_field=DINERO),
        )
        return super().get_queryset_filtrado()

    def filtrar(self, queryset, datos):
        if datos.get('insumo'):
            queryset = queryset.filter(insumo=datos['insumo'])
        if datos.get('causa'):
            queryset = queryset.filter(causa=datos['causa'])
        if datos.get('responsable'):
            queryset = queryset.filter(usuario_responsable=datos['responsable'])
        return filtrar_por_fechas(queryset, datos)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['costo_total'] = self.get_queryset_filtrado().aggregate(total=Sum('costo_merma'))['total'] or 0
        return context


# ---------------------------------------------------------------------------
# Venta (historial)
# ---------------------------------------------------------------------------

class VentaListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = Venta
    template_name = 'dashboard/venta_list.html'
    context_object_name = 'ventas'
    allowed_groups = ['Administrador']
    filtro_form_class = VentaFilterForm
    titulo_excel = 'Ventas'
    columnas_excel = [
        ('Folio', 'texto', 12), ('Fecha', 'fechahora', 17), ('Cajero', 'texto', 16),
        ('Artículos', 'cantidad', 10, True), ('Pago', 'texto', 11), ('Estado', 'texto', 12),
        ('Total', 'moneda', 13),
    ]

    def fila_excel(self, v):
        return [v.codigo, v.fecha, v.usuario_cajero.get_username(), v.num_productos,
                v.get_metodo_pago_display(), v.get_estado_display(), v.total]
    columnas_orden = {
        'folio': 'pk',
        'fecha': 'fecha',
        'cajero': 'usuario_cajero__username',
        'productos': 'num_productos',
        'total': 'total',
        'pago': 'metodo_pago',
        'estado': 'estado',
    }
    orden_defecto = '-fecha'

    def get_queryset_filtrado(self):
        self.queryset = Venta.objects.select_related('usuario_cajero').annotate(
            num_productos=Coalesce(Sum('detalles__cantidad'), Value(0, output_field=DINERO)),
        )
        return super().get_queryset_filtrado()

    def filtrar(self, queryset, datos):
        queryset = buscar_por_nombre_o_codigo(
            queryset, datos.get('q'), Venta.PREFIJO, campo='usuario_cajero__username',
        )
        if datos.get('usuario_cajero'):
            queryset = queryset.filter(usuario_cajero=datos['usuario_cajero'])
        if datos.get('producto'):
            queryset = queryset.filter(
                Exists(DetalleVenta.objects.filter(venta=OuterRef('pk'), producto=datos['producto']))
            )
        if datos.get('total_min') is not None:
            queryset = queryset.filter(total__gte=datos['total_min'])
        if datos.get('total_max') is not None:
            queryset = queryset.filter(total__lte=datos['total_max'])
        if datos.get('metodo_pago'):
            queryset = queryset.filter(metodo_pago=datos['metodo_pago'])
        if datos.get('estado'):
            queryset = queryset.filter(estado=datos['estado'])
        return filtrar_por_fechas(queryset, datos)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtrado = self.get_queryset_filtrado()
        context['monto_total'] = filtrado.completadas().aggregate(total=Sum('total'))['total'] or 0
        context['num_anuladas'] = filtrado.filter(estado=Venta.Estado.ANULADA).count()
        return context


class VentaDetailView(GroupRequiredMixin, DetailView):
    model = Venta
    template_name = 'dashboard/venta_detail.html'
    context_object_name = 'venta'
    allowed_groups = ['Administrador']

    def get_queryset(self):
        return Venta.objects.select_related('usuario_cajero', 'anulada_por').prefetch_related(
            'detalles__producto'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_anular'] = kwargs.get('form_anular') or AnularVentaForm()
        return context


class AnularVentaView(GroupRequiredMixin, View):
    allowed_groups = ['Administrador']

    def post(self, request, pk):
        venta = get_object_or_404(Venta, pk=pk)
        form = AnularVentaForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Indica el motivo de la anulación.')
            return redirect('dashboard:venta_detail', pk=pk)
        try:
            anular_venta(venta, usuario=request.user, motivo=form.cleaned_data['motivo'])
        except VentaError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request, f'Venta {venta.codigo} anulada. Se devolvió al inventario lo que había consumido.'
            )
        return redirect('dashboard:venta_detail', pk=pk)
