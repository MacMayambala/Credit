from django import forms
from finance.models import AutoRepaymentSetting, ChartOfAccount

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



# finance/forms.py
from django import forms
from decimal import Decimal
from .models import ChartOfAccount

# finance/forms.py
from django import forms
from decimal import Decimal
from .models import ChartOfAccount

from decimal import Decimal
from django import forms
from .models import ChartOfAccount


# finance/forms.py
from django import forms
from decimal import Decimal
from .models import ChartOfAccount

# ============================================================
# 3. JOURNAL ENTRY FORM (fully enhanced)
# ============================================================
class JournalEntryForm(forms.Form):
    debit_account = forms.ModelChoiceField(
        queryset=ChartOfAccount.objects.filter(is_active=True),
        label="Debit Account",
        widget=forms.Select(
            attrs={
                'class': 'form-select',
                'data-placeholder': '– Select an account –',
            }
        ),
        help_text="The account that increases (or decreases if liability/income/equity).",
    )
    credit_account = forms.ModelChoiceField(
        queryset=ChartOfAccount.objects.filter(is_active=True),
        label="Credit Account",
        widget=forms.Select(
            attrs={
                'class': 'form-select',
                'data-placeholder': '– Select an account –',
            }
        ),
        help_text="The account that decreases (or increases if liability/income/equity).",
    )
    amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.01'),
        label="Amount (UGX)",
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00',
            }
        ),
        help_text="Enter the transaction amount in Uganda Shillings.",
    )
    description = forms.CharField(
        max_length=200,
        label="Description",
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Brief description of the journal entry…',
            }
        ),
        help_text="A clear description of the transaction.",
    )
    reference = forms.CharField(
        max_length=100,
        required=False,
        label="Reference (optional)",
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Optional reference (e.g., INV-123)',
            }
        ),
        help_text="If left blank, a system reference will be generated automatically.",
    )
    date = forms.DateField(
        required=False,
        label="Entry Date (optional)",
        widget=forms.DateInput(
            attrs={
                'type': 'date',
                'class': 'form-control',
                'data-date-format': 'Y-m-d',
                'placeholder': 'YYYY-MM-DD',
            }
        ),
        help_text="Defaults to today.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove inline style attributes; we rely on the CSS theme.
        # Add any additional customisation if needed.
        pass