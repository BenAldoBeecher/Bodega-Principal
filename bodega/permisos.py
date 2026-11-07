from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def es_admin(user):
    """True si el usuario es superusuario o pertenece al grupo Administrador."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name='Administrador').exists()


def rol_usuario(user):
    return 'Administrador' if es_admin(user) else 'Operador'


def admin_required(view_func):
    """Exige sesión iniciada y rol Administrador."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not es_admin(request.user):
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)

    return wrapper
