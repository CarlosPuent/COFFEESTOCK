"""
URL configuration for coffeestock project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.templatetags.static import static as url_estatica
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve


class FaviconView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        # Se resuelve en cada petición: con DEBUG=False el nombre lleva un hash.
        return url_estatica('img/favicon.svg')


urlpatterns = [
    path('favicon.ico', FaviconView.as_view()),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('pos/', include('pos.urls')),
    path('dashboard/', include('dashboard.urls')),
    # Imágenes de productos. La app corre en la computadora del negocio, así
    # que Django las sirve también con DEBUG=False.
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
