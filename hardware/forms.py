from django import forms
from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'product_code',
            'name',
            'category',
            'cost_price',
            'selling_price',
            'reorder_level',
        ]

        widgets = {
            'product_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto or manual code'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'cost_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'reorder_level': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Low stock alert level'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        cost = cleaned_data.get("cost_price")
        selling = cleaned_data.get("selling_price")

        if cost and selling and selling < cost:
            raise forms.ValidationError(
                "Selling price cannot be lower than cost price."
            )

        return cleaned_data
    


from django import forms
from .models import Product, Purchase, PurchaseItem, Supplier


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'product_code',
            'name',
            'category',
            'cost_price',
            'selling_price',
            'reorder_level',
        ]

        widgets = {
            'product_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto or manual code'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'cost_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'reorder_level': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Low stock alert level'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        cost = cleaned_data.get("cost_price")
        selling = cleaned_data.get("selling_price")

        if cost and selling and selling < cost:
            raise forms.ValidationError(
                "Selling price cannot be lower than cost price."
            )

        return cleaned_data


class PurchaseForm(forms.ModelForm):
    """Form for creating a purchase order with items"""
    
    class Meta:
        model = Purchase
        fields = ['supplier', 'invoice_number']
        widgets = {
            'supplier': forms.Select(attrs={
                'class': 'form-select',
                'style': 'border-radius: 12px;'
            }),
            'invoice_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter invoice number',
                'style': 'border-radius: 12px;'
            }),
        }


class PurchaseItemForm(forms.ModelForm):
    """Form for adding items to a purchase order"""
    
    class Meta:
        model = PurchaseItem
        fields = ['product', 'quantity', 'cost']
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-select',
                'style': 'border-radius: 12px;'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Quantity',
                'step': '1',
                'min': '1',
                'style': 'border-radius: 12px;'
            }),
            'cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cost per unit',
                'step': '0.01',
                'min': '0',
                'style': 'border-radius: 12px;'
            }),
        }