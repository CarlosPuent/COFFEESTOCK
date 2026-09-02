from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View


def _redirect_url_por_grupo(user):
    """Devuelve la URL a la que debe ir un usuario autenticado según su grupo,
    o None si no pertenece a ningún grupo autorizado."""
    if user.groups.filter(name='Cajero').exists():
        return 'pos:index'
    if user.groups.filter(name='Administrador').exists():
        return 'dashboard:index'
    return None


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        auth_login(self.request, form.get_user())
        user = self.request.user

        url_name = _redirect_url_por_grupo(user)
        if url_name:
            return redirect(url_name)

        messages.error(
            self.request,
            'Tu usuario no pertenece a ningún grupo autorizado. Contacta a un administrador.',
        )
        auth_logout(self.request)
        return redirect('core:login')


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('core:login')


class RootRedirectView(LoginRequiredMixin, View):
    """Vista raíz ('/'): redirige al usuario autenticado según su grupo.

    Es el destino seguro para LOGIN_REDIRECT_URL: nunca apunta de vuelta a
    la propia página de login, evitando el loop de redirección que Django
    detecta cuando LOGIN_REDIRECT_URL coincide con la URL de login.
    """

    def get(self, request, *args, **kwargs):
        url_name = _redirect_url_por_grupo(request.user)
        if url_name:
            return redirect(url_name)

        messages.error(
            request,
            'Tu usuario no pertenece a ningún grupo autorizado. Contacta a un administrador.',
        )
        auth_logout(request)
        return redirect('core:login')
