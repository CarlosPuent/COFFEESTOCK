from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.RootRedirectView.as_view(), name='root'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
]
