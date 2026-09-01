from django.urls import path

from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.POSIndexView.as_view(), name='index'),
]
