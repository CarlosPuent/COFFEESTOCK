from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class GroupRequiredMixin(LoginRequiredMixin):
    """Restringe una class-based view a usuarios que pertenezcan a alguno
    de los grupos indicados en ``allowed_groups``.

    Uso:
        class MiVista(GroupRequiredMixin, TemplateView):
            allowed_groups = ['Administrador']
    """

    allowed_groups = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_superuser and not request.user.groups.filter(
            name__in=self.allowed_groups
        ).exists():
            raise PermissionDenied('No tienes permiso para acceder a esta sección.')
        return super().dispatch(request, *args, **kwargs)
