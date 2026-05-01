# members/middleware.py
from django.shortcuts import redirect
from django.conf import settings
from django.urls import resolve

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Get the name of the current URL being accessed
        url_name = resolve(request.path_info).url_name
        
        # 2. Define URLs that MUST be accessible without logging in
        # We must exempt login and allauth/social views to avoid redirect loops
        exempt_urls = [
            'account_login',
            'account_signup',
            'account_reset_password',
            # Add any other public landing pages here
        ]

        # 3. If user is not authenticated and trying to access a protected page
        if not request.user.is_authenticated:
            if url_name not in exempt_urls and not request.path.startswith('/auth/'):
                return redirect(settings.LOGIN_URL)

        return self.get_response(request)