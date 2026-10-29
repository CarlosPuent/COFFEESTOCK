from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag(takes_context=True)
def th_orden(context, etiqueta, clave, clase=''):
    """Encabezado de columna que ordena la tabla al hacer clic.

    {% th_orden 'Stock actual' 'stock' 'text-end' %}
    """
    actual = context.get('orden_actual', '')
    if actual == clave:
        siguiente, icono, aria = f'-{clave}', 'bi-arrow-up', 'ascending'
    elif actual == f'-{clave}':
        siguiente, icono, aria = clave, 'bi-arrow-down', 'descending'
    else:
        siguiente, icono, aria = clave, 'bi-arrow-down-up', 'none'

    base = context.get('querystring_sin_orden', '')
    href = f'?{base}&orden={siguiente}' if base else f'?orden={siguiente}'
    activo = ' th-orden-activo' if aria != 'none' else ''
    return format_html(
        '<th class="{}" aria-sort="{}"><a class="th-orden{}" href="{}">{}'
        '<i class="bi {} th-orden-icono" aria-hidden="true"></i></a></th>',
        clase, aria, activo, href, etiqueta, icono,
    )


@register.filter
def rol(usuario):
    """Rol del usuario para mostrar: Superusuario, Administrador, Cajero o Sin rol."""
    if usuario.is_superuser:
        return 'Superusuario'
    nombres = {g.name for g in usuario.groups.all()}
    for nombre in ('Administrador', 'Cajero'):
        if nombre in nombres:
            return nombre
    return 'Sin rol'
