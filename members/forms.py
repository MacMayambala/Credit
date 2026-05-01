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