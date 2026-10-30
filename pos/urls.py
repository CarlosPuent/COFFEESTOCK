from django.urls import path

from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.POSIndexView.as_view(), name='index'),
    path('confirmar-venta/', views.ConfirmarVentaView.as_view(), name='confirmar_venta'),
    path('ticket/<int:pk>/', views.TicketView.as_view(), name='ticket'),
    path('ultimo-ticket/', views.UltimoTicketView.as_view(), name='ultimo_ticket'),
]
