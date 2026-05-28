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



from django import forms

class InterestIncomeFilterForm(forms.Form):
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control border-start-0'
        })
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control border-start-0'
        })
    )
    product = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Products'),
            ('BUSINESS', 'Business Loans'),
            ('PERSONAL', 'Personal Loans'),
            ('EMERGENCY', 'Emergency Loans'),
            # Add any other product keys used in your database here
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    risk_category = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Categories'),
            ('PERFORMING', 'Performing (Standard)'),
            ('WATCH', 'Watch (Substandard)'),
            ('DOUBTFUL', 'Doubtful'),
            ('LOSS', 'Loss'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )