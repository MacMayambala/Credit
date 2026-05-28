
from django import forms

class FinancialReportFilterForm(forms.Form):
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    branch = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Branch Code'}))
    product = forms.ChoiceField(required=False, choices=[('', 'All Products'), ('PERSONAL', 'Personal'), ('BUSINESS', 'Business'), ('AGRI', 'Agriculture')], widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    risk_category = forms.ChoiceField(required=False, choices=[('', 'All Risk Statuses'), ('PERFORMING', 'Performing'), ('WATCH', 'Watch'), ('SUBSTANDARD', 'Substandard'), ('DOUBTFUL', 'Doubtful'), ('LOSS', 'Loss')], widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))