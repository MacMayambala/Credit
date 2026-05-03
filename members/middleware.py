# members/middleware.py
from django.shortcuts import redirect
from django.conf import settings
from django.urls import resolve, Resolver404

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Allow authenticated users immediately
        if request.user.is_authenticated:
            return self.get_response(request)

        # 2. Safely resolve the URL name
        try:
            resolver_match = resolve(request.path_info)
            url_name = resolver_match.url_name
            # Optional: Check if it's a Django Admin path
            is_admin = request.path.startswith('/admin/')
        except Resolver404:
            url_name = None
            is_admin = False
        
        # 3. Define exempted URL names
        exempt_urls = [
            'login',          
            'logout',         
            'password_reset',
            'password_reset_done',
            'password_reset_confirm',
            'password_reset_complete',
        ]

        # 4. The Logic Check
        # Exempt if: it's in the list OR starts with /auth/ OR it's the admin login
        if (url_name in exempt_urls or 
            request.path.startswith('/auth/') or 
            is_admin):
            return self.get_response(request)

        # 5. Otherwise, redirect to login
        return redirect(settings.LOGIN_URL)