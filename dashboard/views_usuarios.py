from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from core.mixins import GroupRequiredMixin
from core.services.caja import corte_de_caja

from .forms_usuarios import CambiarContrasenaForm, CorteCajaForm, UsuarioFilterForm, UsuarioForm
from .listados import ListadoMixin

User = get_user_model()


def es_administrador(usuario):
    return usuario.is_superuser or usuario.groups.filter(name='Administrador').exists()


class UsuarioListView(ListadoMixin, GroupRequiredMixin, ListView):
    model = User
    template_name = 'dashboard/usuario_list.html'
    context_object_name = 'usuarios'
    allowed_groups = ['Administrador']
    filtro_form_class = UsuarioFilterForm
    columnas_orden = {
        'usuario': 'username',
        'nombre': ['first_name', 'last_name'],
        'correo': 'email',
        'acceso': 'last_login',
        'ventas': 'num_ventas',
        'activo': 'is_active',
    }
    orden_defecto = 'usuario'

    def get_queryset_filtrado(self):
        self.queryset = User.objects.prefetch_related('groups').annotate(
            num_ventas=Count('ventas', filter=Q(ventas__estado='completada')),
        )
        return super().get_queryset_filtrado()

    def filtrar(self, queryset, datos):
        texto = (datos.get('q') or '').strip()
        if texto:
            queryset = queryset.filter(
                Q(username__icontains=texto) | Q(first_name__icontains=texto)
                | Q(last_name__icontains=texto) | Q(email__icontains=texto)
            )
        if datos.get('rol'):
            queryset = queryset.filter(groups__name=datos['rol'])
        if datos.get('estado') == 'activos':
            queryset = queryset.filter(is_active=True)
        elif datos.get('estado') == 'inactivos':
            queryset = queryset.filter(is_active=False)
        return queryset


class UsuarioFormMixin:
    model = User
    form_class = UsuarioForm
    template_name = 'dashboard/usuario_form.html'
    success_url = reverse_lazy('dashboard:usuario_list')
    allowed_groups = ['Administrador']

    def get_queryset(self):
        # Los superusuarios solo se administran desde /admin/.
        return User.objects.filter(is_superuser=False)

    def form_valid(self, form):
        if self.object and self.object.pk == self.request.user.pk:
            if not form.cleaned_data['is_active'] or form.cleaned_data['rol'] != 'Administrador':
                form.add_error(None, 'No puedes desactivarte ni quitarte el rol de Administrador a ti mismo.')
                return self.form_invalid(form)
        respuesta = super().form_valid(form)
        messages.success(self.request, f'Usuario "{self.object.username}" guardado.')
        return respuesta


class UsuarioCreateView(UsuarioFormMixin, GroupRequiredMixin, CreateView):
    def get_initial(self):
        return {'is_active': True, 'rol': 'Cajero'}


class UsuarioUpdateView(UsuarioFormMixin, GroupRequiredMixin, UpdateView):
    context_object_name = 'usuario'


class CambiarContrasenaView(GroupRequiredMixin, FormView):
    form_class = CambiarContrasenaForm
    template_name = 'dashboard/usuario_contrasena.html'
    allowed_groups = ['Administrador']

    def dispatch(self, request, *args, **kwargs):
        self.usuario = get_object_or_404(User, pk=kwargs['pk'], is_superuser=False)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.usuario
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usuario'] = self.usuario
        return context

    def form_valid(self, form):
        form.save()
        if self.usuario.pk == self.request.user.pk:
            update_session_auth_hash(self.request, self.usuario)
        messages.success(self.request, f'Contraseña de "{self.usuario.username}" actualizada.')
        return redirect('dashboard:usuario_list')


class CambiarEstadoUsuarioView(GroupRequiredMixin, View):
    allowed_groups = ['Administrador']

    def post(self, request, pk):
        usuario = get_object_or_404(User, pk=pk, is_superuser=False)
        if usuario.pk == request.user.pk:
            messages.error(request, 'No puedes desactivar tu propio usuario.')
        else:
            usuario.is_active = not usuario.is_active
            usuario.save(update_fields=['is_active'])
            estado = 'activado' if usuario.is_active else 'desactivado (ya no puede iniciar sesión)'
            messages.success(request, f'Usuario "{usuario.username}" {estado}.')
        return redirect('dashboard:usuario_list')


class CorteCajaView(GroupRequiredMixin, TemplateView):
    """Resumen de caja del día. Un cajero solo ve sus propias ventas."""

    template_name = 'dashboard/corte_caja.html'
    allowed_groups = ['Administrador', 'Cajero']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        admin = es_administrador(self.request.user)
        datos = self.request.GET.copy()
        datos.setdefault('fecha', timezone.localdate().isoformat())
        form = CorteCajaForm(datos)
        if not admin:
            del form.fields['cajero']

        fecha, cajero = timezone.localdate(), None
        if form.is_valid():
            fecha = form.cleaned_data['fecha']
            cajero = form.cleaned_data.get('cajero')
        if not admin:
            cajero = self.request.user

        context['filtro_form'] = form
        context['hay_filtros'] = bool(self.request.GET)
        context['corte'] = corte_de_caja(fecha, cajero=cajero)
        context['es_admin'] = admin
        return context
