from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        auth_login(self.request, form.get_user())
        user = self.request.user

        if user.groups.filter(name='Cajero').exists():
            return redirect('pos:index')

        if user.groups.filter(name='Administrador').exists():
            return redirect('dashboard:index')

        messages.error(
            self.request,
            'Tu usuario no pertenece a ningún grupo autorizado. Contacta a un administrador.',
        )
        auth_logout(self.request)
        return redirect('core:login')


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('core:login')
