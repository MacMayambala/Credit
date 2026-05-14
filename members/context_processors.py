def module_permissions(request):
    if request.user.is_authenticated:
        # Get the names of all modules assigned to this user
        allowed = request.user.profile.allowed_modules.values_list('name', flat=True)
        return {
            'allowed_modules': list(allowed)
        }
    return {'allowed_modules': []}