from django import forms
from finance.models import AutoRepaymentSetting

class AutoRepaymentSettingForm(forms.ModelForm):
    class Meta:
        model = AutoRepaymentSetting
        fields = ['is_enabled', 'execution_time', 'frequency', 'grace_period_days']
        widgets = {
            'execution_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'frequency': forms.Select(attrs={'class': 'form-select'}),
            'grace_period_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }