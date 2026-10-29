from django.urls import path

from . import views, views_compras, views_usuarios

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardIndexView.as_view(), name='index'),

    path('insumos/', views.InsumoListView.as_view(), name='insumo_list'),
    path('insumos/nuevo/', views.InsumoCreateView.as_view(), name='insumo_create'),
    path('insumos/<int:pk>/editar/', views.InsumoUpdateView.as_view(), name='insumo_update'),
    path('insumos/<int:pk>/eliminar/', views.InsumoDeleteView.as_view(), name='insumo_delete'),

    path('productos/', views.ProductoListView.as_view(), name='producto_list'),
    path('productos/nuevo/', views.ProductoCreateView.as_view(), name='producto_create'),
    path('productos/<int:pk>/editar/', views.ProductoUpdateView.as_view(), name='producto_update'),
    path('productos/<int:pk>/eliminar/', views.ProductoDeleteView.as_view(), name='producto_delete'),

    path('mermas/nueva/', views.MermaCreateView.as_view(), name='merma_create'),
    path('mermas/', views.MermaListView.as_view(), name='merma_list'),

    path('proveedores/', views_compras.ProveedorListView.as_view(), name='proveedor_list'),
    path('proveedores/nuevo/', views_compras.ProveedorCreateView.as_view(), name='proveedor_create'),
    path('proveedores/<int:pk>/editar/', views_compras.ProveedorUpdateView.as_view(), name='proveedor_update'),
    path('proveedores/<int:pk>/eliminar/', views_compras.ProveedorDeleteView.as_view(), name='proveedor_delete'),

    path('compras/', views_compras.CompraListView.as_view(), name='compra_list'),
    path('compras/nueva/', views_compras.CompraCreateView.as_view(), name='compra_create'),
    path('compras/<int:pk>/', views_compras.CompraDetailView.as_view(), name='compra_detail'),

    path('usuarios/', views_usuarios.UsuarioListView.as_view(), name='usuario_list'),
    path('usuarios/nuevo/', views_usuarios.UsuarioCreateView.as_view(), name='usuario_create'),
    path('usuarios/<int:pk>/editar/', views_usuarios.UsuarioUpdateView.as_view(), name='usuario_update'),
    path('usuarios/<int:pk>/contrasena/', views_usuarios.CambiarContrasenaView.as_view(), name='usuario_contrasena'),
    path('usuarios/<int:pk>/estado/', views_usuarios.CambiarEstadoUsuarioView.as_view(), name='usuario_estado'),

    path('corte-de-caja/', views_usuarios.CorteCajaView.as_view(), name='corte_caja'),

    path('ventas/', views.VentaListView.as_view(), name='venta_list'),
    path('ventas/<int:pk>/', views.VentaDetailView.as_view(), name='venta_detail'),
    path('ventas/<int:pk>/anular/', views.AnularVentaView.as_view(), name='venta_anular'),
]
