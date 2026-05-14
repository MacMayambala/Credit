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
    


from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Module

class StaffRegistrationForm(forms.ModelForm):
    # We manually add the modules field since it's not in the User model
    allowed_modules = forms.ModelMultipleChoiceField(
        queryset=Module.objects.all(),
        required=False,
        label="Feature Modules",
        help_text="Hold Ctrl (Cmd) to select multiple"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'groups', 'is_staff']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If we are editing an existing user, load their current modules
        if self.instance and self.instance.pk:
            try:
                self.fields['allowed_modules'].initial = self.instance.profile.allowed_modules.all()
            except UserProfile.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=commit)
        # This part handles saving the modules to the Profile
        if commit:
            # Ensure profile exists
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.allowed_modules.set(self.cleaned_data['allowed_modules'])
        return user