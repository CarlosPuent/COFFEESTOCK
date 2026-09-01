from django.contrib import admin

from .models import DetalleVenta, Insumo, Merma, Producto, RecetaInsumo, Venta


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'unidad_medida', 'stock_actual', 'stock_minimo',
        'costo_unitario', 'activo', 'alerta_pendiente', 'fecha_actualizacion',
    )
    list_filter = ('unidad_medida', 'activo', 'alerta_pendiente')
    search_fields = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio_venta', 'activo')
    list_filter = ('categoria', 'activo')
    search_fields = ('nombre',)


@admin.register(RecetaInsumo)
class RecetaInsumoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'insumo', 'cantidad_requerida')
    list_filter = ('producto', 'insumo')
    search_fields = ('producto__nombre', 'insumo__nombre')


@admin.register(Merma)
class MermaAdmin(admin.ModelAdmin):
    list_display = ('insumo', 'cantidad', 'causa', 'usuario_responsable', 'fecha')
    list_filter = ('causa', 'fecha')
    search_fields = ('insumo__nombre', 'usuario_responsable__username', 'observacion')


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario_cajero', 'fecha', 'total')
    list_filter = ('fecha', 'usuario_cajero')
    search_fields = ('usuario_cajero__username',)
    inlines = [DetalleVentaInline]


@admin.register(DetalleVenta)
class DetalleVentaAdmin(admin.ModelAdmin):
    list_display = ('venta', 'producto', 'cantidad', 'subtotal')
    list_filter = ('producto',)
    search_fields = ('producto__nombre', 'venta__id')
