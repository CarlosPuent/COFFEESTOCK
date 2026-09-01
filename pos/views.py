from django.views.generic import TemplateView

from core.mixins import GroupRequiredMixin


class POSIndexView(GroupRequiredMixin, TemplateView):
    template_name = 'pos/index.html'
    allowed_groups = ['Cajero', 'Administrador']
