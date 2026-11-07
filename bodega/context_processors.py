from .permisos import es_admin, rol_usuario


def roles(request):
    user = getattr(request, 'user', None)
    autenticado = bool(user and user.is_authenticated)
    return {
        'es_admin': es_admin(user) if autenticado else False,
        'rol': rol_usuario(user) if autenticado else '',
    }
