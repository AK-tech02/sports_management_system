from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

# Which roles may manage each area. Everyone logged in can view.
PERMS = {
    'players': {'admin', 'coach'},
    'teams': {'admin', 'coach'},
    'tournaments': {'admin', 'organizer'},
    'venues': {'admin', 'organizer'},
    'stats': {'admin', 'coach', 'organizer'},
    'notify': {'admin', 'organizer'},
    'reports': {'admin', 'organizer', 'coach'},
}


def get_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return 'admin'
    profile = getattr(user, 'profile', None)
    return profile.role if profile else 'player'


def deny(request):
    messages.error(request, 'Your role does not have permission to do that.')
    return redirect('dashboard')


def need(area):
    def deco(fn):
        @wraps(fn)
        def wrapper(request, *a, **k):
            if get_role(request.user) not in PERMS[area]:
                return deny(request)
            return fn(request, *a, **k)
        return login_required(wrapper)
    return deco
