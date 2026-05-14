from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Member

admin.site.register(Member)


from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Module, UserProfile

# Register the Module model normally
@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

# Define an inline for UserProfile
class ProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    filter_horizontal = ('allowed_modules',) # Nice UI for selecting multiple modules

# Extend the default UserAdmin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_modules')

    def get_modules(self, instance):
        # This shows the assigned modules in the user list table
        return ", ".join([m.name for m in instance.profile.allowed_modules.all()])
    get_modules.short_description = 'Modules'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)