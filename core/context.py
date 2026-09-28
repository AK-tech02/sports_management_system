from .perms import PERMS, get_role


def perms(request):
    role = get_role(request.user)
    return {'role': role, 'can': {k: role in v for k, v in PERMS.items()}}
