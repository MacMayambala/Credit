
from django import forms

class FinancialReportFilterForm(forms.Form):
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    branch = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Branch Code'}))
    product = forms.ChoiceField(required=False, choices=[('', 'All Products'), ('PERSONAL', 'Personal'), ('BUSINESS', 'Business'), ('AGRI', 'Agriculture')], widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    risk_category = forms.ChoiceField(required=False, choices=[('', 'All Risk Statuses'), ('PERFORMING', 'Performing'), ('WATCH', 'Watch'), ('SUBSTANDARD', 'Substandard'), ('DOUBTFUL', 'Doubtful'), ('LOSS', 'Loss')], widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))



import django_filters
from .models import GeneralLedger, ChartOfAccount

class LedgerFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    account_type = django_filters.ChoiceFilter(field_name='account__account_type', choices=ChartOfAccount.ACCOUNT_TYPES)
    
    class Meta:
        model = GeneralLedger
        fields = ['account', 'account_type']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allows for 'Only Non-Zero' logic
        self.filters['only_non_zero'] = django_filters.BooleanFilter(method='filter_non_zero', label="Only Non-Zero Accounts")

    def filter_non_zero(self, queryset, name, value):
        if value:
            return queryset.exclude(debit=0, credit=0)
        return queryset