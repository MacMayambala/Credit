from django import forms
from .models import Member

class MemberKYCForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ['id_front', 'signature']
        widgets = {
            'id_front': forms.FileInput(attrs={'class': 'form-control'}),
            'signature': forms.FileInput(attrs={'class': 'form-control'}),
        }



from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Module

class StaffForm(forms.ModelForm):
    # Manually adding the modules field to this form
    allowed_modules = forms.ModelMultipleChoiceField(
        queryset=Module.objects.all(),
        required=False,
        label="Feature Modules",
        widget=forms.SelectMultiple()
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'groups', 'is_staff']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill modules if we are updating an existing user
        if self.instance and self.instance.pk:
            try:
                self.fields['allowed_modules'].initial = self.instance.profile.allowed_modules.all()
            except UserProfile.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            # Save the modules to the associated UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.allowed_modules.set(self.cleaned_data['allowed_modules'])
        return user