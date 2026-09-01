from django.views.generic import TemplateView

from core.mixins import GroupRequiredMixin


class DashboardIndexView(GroupRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'
    allowed_groups = ['Administrador']
