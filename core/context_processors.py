def user_groups(request):
    """Expone banderas de grupo al contexto de todos los templates."""
    is_administrador = False
    is_cajero = False

    if request.user.is_authenticated:
        group_names = set(request.user.groups.values_list('name', flat=True))
        is_administrador = 'Administrador' in group_names or request.user.is_superuser
        is_cajero = 'Cajero' in group_names

    return {
        'is_administrador': is_administrador,
        'is_cajero': is_cajero,
    }
