def navigation(request):
    return {"is_manager": request.user.is_authenticated and (request.user.is_superuser or request.user.groups.filter(name="Pengelola").exists())}
