import json
import csv
import uuid
from decimal import Decimal
from datetime import datetime, timedelta

from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import F, Value, Sum, Case, When, IntegerField, DecimalField, ExpressionWrapper, Count, Q
from django.db.models.functions import Coalesce, TruncDate
from django.views.generic import TemplateView, CreateView, ListView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from django.utils import timezone

from .models import Product, Customer, Sale, Purchase, StockTransaction, Category, Supplier, SaleItem
from .services import get_dashboard_stats, secure_process_sale
from .forms import ProductForm


# ==================== DASHBOARD ====================
class DashboardView(TemplateView):
    template_name = 'hardware/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_dashboard_stats())
        return context


# ==================== CATEGORY CRUD ====================
class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'hardware/category_list.html'
    context_object_name = 'categories'
    ordering = ['name']


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    fields = ['name', 'slug']
    template_name = 'hardware/category_form.html'
    success_url = reverse_lazy('hardware:category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Category created successfully!')
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    fields = ['name', 'slug']
    template_name = 'hardware/category_form.html'
    success_url = reverse_lazy('hardware:category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Category updated successfully!')
        return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'hardware/category_confirm_delete.html'
    success_url = reverse_lazy('hardware:category_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Category deleted successfully!')
        return super().delete(request, *args, **kwargs)


# ==================== PRODUCT CRUD ====================
class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'hardware/product_form.html'
    success_url = reverse_lazy('hardware:product_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Product'
        context['is_edit'] = False
        return context

    def form_valid(self, form):
        if not form.instance.product_code:
            form.instance.product_code = f"PRD-{self.request.user.id}-{Product.objects.count() + 1}"
        messages.success(self.request, 'Product created successfully!')
        return super().form_valid(form)


class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'hardware/product_form.html'
    success_url = reverse_lazy('hardware:product_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Product'
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Product updated successfully!')
        return super().form_valid(form)


class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    template_name = 'hardware/product_confirm_delete.html'
    success_url = reverse_lazy('hardware:product_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Product deleted successfully!')
        return super().delete(request, *args, **kwargs)


class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'hardware/product_list.html'
    context_object_name = 'products'
    ordering = ['-created_at']

    def get_queryset(self):
        return Product.objects.all()


# ==================== SUPPLIER CRUD ====================
class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'hardware/supplier_list.html'
    context_object_name = 'suppliers'
    ordering = ['name']


class SupplierCreateView(LoginRequiredMixin, CreateView):
    model = Supplier
    fields = ['name', 'contact_person', 'phone', 'email']
    template_name = 'hardware/supplier_form.html'
    success_url = reverse_lazy('hardware:supplier_list')

    def form_valid(self, form):
        messages.success(self.request, 'Supplier created successfully!')
        return super().form_valid(form)


class SupplierUpdateView(LoginRequiredMixin, UpdateView):
    model = Supplier
    fields = ['name', 'contact_person', 'phone', 'email']
    template_name = 'hardware/supplier_form.html'
    success_url = reverse_lazy('hardware:supplier_list')

    def form_valid(self, form):
        messages.success(self.request, 'Supplier updated successfully!')
        return super().form_valid(form)


class SupplierDeleteView(LoginRequiredMixin, DeleteView):
    model = Supplier
    template_name = 'hardware/supplier_confirm_delete.html'
    success_url = reverse_lazy('hardware:supplier_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Supplier deleted successfully!')
        return super().delete(request, *args, **kwargs)


# ==================== PURCHASE CRUD ====================
class PurchaseListView(LoginRequiredMixin, ListView):
    model = Purchase
    template_name = 'hardware/purchase_list.html'
    context_object_name = 'purchases'
    ordering = ['-date']


class PurchaseCreateView(LoginRequiredMixin, CreateView):
    model = Purchase
    fields = ['supplier', 'invoice_number']
    template_name = 'hardware/purchase_form.html'
    success_url = reverse_lazy('hardware:purchase_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.filter(is_active=True)
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Purchase order created successfully!')
        return super().form_valid(form)


class PurchaseUpdateView(LoginRequiredMixin, UpdateView):
    model = Purchase
    fields = ['supplier', 'invoice_number']
    template_name = 'hardware/purchase_form.html'
    success_url = reverse_lazy('hardware:purchase_list')

    def form_valid(self, form):
        messages.success(self.request, 'Purchase order updated successfully!')
        return super().form_valid(form)


class PurchaseDeleteView(LoginRequiredMixin, DeleteView):
    model = Purchase
    template_name = 'hardware/purchase_confirm_delete.html'
    success_url = reverse_lazy('hardware:purchase_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Purchase order deleted successfully!')
        return super().delete(request, *args, **kwargs)


# ==================== SALES LIST ====================
class SalesListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'hardware/sales_list.html'
    context_object_name = 'sales'
    ordering = ['-date']

    def get_queryset(self):
        return Sale.objects.all().select_related('customer', 'cashier').prefetch_related('items__product')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        total_sales = Sale.objects.count()
        total_revenue = Sale.objects.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        today = timezone.now().date()
        today_sales = Sale.objects.filter(date__date=today)
        today_count = today_sales.count()
        today_revenue = today_sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        context.update({
            'total_sales': total_sales,
            'total_revenue': total_revenue,
            'today_sales': today_count,
            'today_revenue': today_revenue,
        })
        return context


# ==================== REPORTS ====================
class ReportView(LoginRequiredMixin, TemplateView):
    template_name = 'hardware/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        report_type = self.request.GET.get('report_type', 'sales')
        payment_method = self.request.GET.get('payment_method', 'all')
        
        context['report_type'] = report_type
        context['payment_method'] = payment_method
        context['start_date'] = start_date
        context['end_date'] = end_date
        
        if not start_date:
            start_date = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            context['start_date'] = start_date
        if not end_date:
            end_date = timezone.now().strftime('%Y-%m-%d')
            context['end_date'] = end_date
        
        if report_type == 'sales':
            context['report_data'] = self.get_sales_report(start_date, end_date, payment_method)
        elif report_type == 'products':
            context['report_data'] = self.get_products_report()
        elif report_type == 'inventory':
            context['report_data'] = self.get_inventory_report()
        elif report_type == 'customers':
            context['report_data'] = self.get_customers_report(start_date, end_date)
        elif report_type == 'daily':
            context['report_data'] = self.get_daily_report(start_date, end_date)
        elif report_type == 'tax':
            context['report_data'] = self.get_tax_report(start_date, end_date)
        else:
            context['report_data'] = self.get_sales_report(start_date, end_date, payment_method)
        
        return context

    def get_sales_report(self, start_date, end_date, payment_method):
        sales = Sale.objects.filter(date__date__gte=start_date, date__date__lte=end_date)
        
        if payment_method != 'all':
            sales = sales.filter(payment_method=payment_method)
        
        total_sales = sales.count()
        total_revenue = sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        avg_sale = total_revenue / total_sales if total_sales > 0 else Decimal('0')
        
        payment_breakdown = sales.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-total')
        
        daily_breakdown = sales.annotate(
            date_only=TruncDate('date')
        ).values('date_only').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('-date_only')[:30]
        
        top_products = SaleItem.objects.filter(
            sale__date__date__gte=start_date,
            sale__date__date__lte=end_date
        ).values('product__name', 'product__id').annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('price'))
        ).order_by('-total_revenue')[:10]
        
        return {
            'total_sales': total_sales,
            'total_revenue': total_revenue,
            'avg_sale': avg_sale,
            'payment_breakdown': payment_breakdown,
            'daily_breakdown': daily_breakdown,
            'top_products': top_products,
            'sales': sales[:50]
        }

    def get_products_report(self):
        products = Product.objects.annotate(
            total_sales=Sum('saleitem__quantity'),
            total_revenue=Sum(F('saleitem__quantity') * F('saleitem__price')),
            total_cost=Sum(F('saleitem__quantity') * F('cost_price')),
            profit=Sum(F('saleitem__quantity') * F('saleitem__price')) - 
                   Sum(F('saleitem__quantity') * F('cost_price'))
        ).filter(total_sales__gt=0).order_by('-total_revenue')
        
        total_products = Product.objects.count()
        active_products = Product.objects.filter(is_active=True).count()
        
        return {
            'products': products[:50],
            'total_products': total_products,
            'active_products': active_products,
            'top_seller': products.first()
        }

    def get_inventory_report(self):
        products = Product.objects.annotate(
            total_purchased=Sum(
                'ledger__quantity',
                filter=Q(ledger__transaction_type='PURCHASE')
            ),
            total_sold=Sum(
                'ledger__quantity',
                filter=Q(ledger__transaction_type='SALE')
            )
        ).all()
        
        low_stock = Product.objects.filter(current_stock__lte=F('reorder_level')).count()
        out_of_stock = Product.objects.filter(current_stock=0).count()
        
        total_inventory_value = Product.objects.aggregate(
            total=Sum(F('current_stock') * F('cost_price'))
        )['total'] or Decimal('0')
        
        return {
            'products': products[:50],
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'total_inventory_value': total_inventory_value
        }

    def get_customers_report(self, start_date, end_date):
        customers = Customer.objects.annotate(
            total_purchases=Count('sale'),
            total_spent=Sum('sale__total_amount')
        ).filter(total_purchases__gt=0).order_by('-total_spent')
        
        return {
            'customers': customers[:20],
            'total_customers': Customer.objects.count()
        }

    def get_daily_report(self, start_date, end_date):
        daily_data = Sale.objects.filter(
            date__date__gte=start_date,
            date__date__lte=end_date
        ).annotate(
            date_only=TruncDate('date')
        ).values('date_only').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('date_only')
        
        return {
            'daily_data': daily_data,
            'total_days': daily_data.count()
        }

    def get_tax_report(self, start_date, end_date):
        sales = Sale.objects.filter(date__date__gte=start_date, date__date__lte=end_date)
        total_revenue = sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Use Decimal for tax calculation to avoid type errors
        tax_rate = Decimal('0.18')
        tax_amount = total_revenue * tax_rate
        
        return {
            'total_revenue': total_revenue,
            'tax_rate': tax_rate * Decimal('100'),
            'tax_amount': tax_amount,
            'sales_count': sales.count()
        }


# ==================== EXPORT REPORT ====================
@login_required
def export_report_csv(request):
    report_type = request.GET.get('report_type', 'sales')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    
    if report_type == 'sales':
        writer.writerow(['Receipt #', 'Date', 'Customer', 'Payment Method', 'Amount'])
        sales = Sale.objects.filter(
            date__date__gte=start_date,
            date__date__lte=end_date
        ) if start_date and end_date else Sale.objects.all()
        
        for sale in sales:
            writer.writerow([
                str(sale.id)[:8],
                sale.date.strftime('%Y-%m-%d %H:%M'),
                sale.customer.name if sale.customer else 'N/A',
                sale.payment_method,
                str(sale.total_amount)
            ])
    
    elif report_type == 'products':
        writer.writerow(['Product Code', 'Product Name', 'Category', 'Price', 'Stock'])
        for product in Product.objects.all():
            writer.writerow([
                product.product_code,
                product.name,
                product.category.name if product.category else 'N/A',
                str(product.selling_price),
                str(product.current_stock)
            ])
    
    elif report_type == 'inventory':
        writer.writerow(['Product', 'Stock', 'Reorder Level', 'Status'])
        for product in Product.objects.all():
            status = 'Healthy'
            if product.current_stock <= 0:
                status = 'Out of Stock'
            elif product.current_stock <= product.reorder_level:
                status = 'Low Stock'
            
            writer.writerow([
                product.name,
                str(product.current_stock),
                str(product.reorder_level),
                status
            ])
    
    return response


# ==================== POS & CHECKOUT ====================
class POSView(PermissionRequiredMixin, TemplateView):
    template_name = 'hardware/pos.html'
    permission_required = 'hardware.add_sale'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.filter(is_active=True).select_related('category')
        context['customers'] = Customer.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            cart_items_data = data.get('cart', [])
            customer_id = data.get('customer_id')
            payment_method = data.get('payment_method', 'CASH')

            if not cart_items_data:
                return JsonResponse({'status': 'error', 'message': 'Cart is empty'}, status=400)

            product_ids = [item['id'] for item in cart_items_data]
            products = Product.objects.in_bulk(product_ids)

            cart_items = []
            for item in cart_items_data:
                product = products.get(item['id'])
                if not product:
                    return JsonResponse({'status': 'error', 'message': f"Product not found: {item['id']}"}, status=400)
                qty = Decimal(str(item.get('qty', 1)))
                if qty <= 0:
                    return JsonResponse({'status': 'error', 'message': f"Invalid quantity for {product.name}"}, status=400)
                cart_items.append({'product': product, 'qty': qty, 'price': Decimal(str(product.selling_price))})

            customer = None
            if customer_id:
                customer = Customer.objects.filter(id=customer_id).first()

            sale = secure_process_sale(cart_items, customer, payment_method, request.user)
            return JsonResponse({'status': 'success', 'sale_id': str(sale.id)})

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def pos_checkout_view(request):
    try:
        data = json.loads(request.body)
        print("Received data:", data)

        cart_data = data.get("cart", [])
        payment_method = data.get("payment_method", "CASH")

        if not cart_data:
            return JsonResponse({"status": "error", "message": "Cart is empty"}, status=400)

        cart_items = []

        for item in cart_data:
            product_id = item.get("id")
            qty = Decimal(str(item.get("qty", 1)))
            
            print(f"Looking for product with ID: {product_id}")
            
            try:
                if isinstance(product_id, str):
                    product = Product.objects.get(id=product_id)
                else:
                    product = Product.objects.get(id=str(product_id))
            except Product.DoesNotExist:
                print(f"Product not found with ID: {product_id}")
                return JsonResponse({
                    "status": "error",
                    "message": f"Product not found: {product_id}"
                }, status=400)

            if qty <= 0:
                return JsonResponse({
                    "status": "error",
                    "message": "Invalid quantity"
                }, status=400)

            if product.current_stock < qty:
                return JsonResponse({
                    "status": "error",
                    "message": f"Insufficient stock for {product.name}. Available: {product.current_stock}"
                }, status=400)

            cart_items.append({
                "product": product,
                "qty": qty,
                "price": Decimal(str(product.selling_price))
            })

        sale = secure_process_sale(cart_items, None, payment_method, request.user)

        return JsonResponse({
            "status": "success",
            "sale_id": str(sale.id)
        })

    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON data"
        }, status=400)
        
    except ValueError as e:
        print(f"Value Error: {e}")
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=400)
        
    except Exception as e:
        import traceback
        print(f"Unexpected error: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }, status=500)


# ==================== RECEIPT ====================
def receipt_view(request, sale_id):
    try:
        sale = Sale.objects.get(id=uuid.UUID(str(sale_id)))
    except (ValueError, Sale.DoesNotExist):
        try:
            sale = Sale.objects.get(id=int(sale_id))
        except (ValueError, Sale.DoesNotExist, TypeError):
            raise Http404("Sale not found")
    
    items = sale.items.select_related("product")
    
    return render(request, "hardware/receipt.html", {
        "sale": sale,
        "items": items
    })


# ==================== DAILY CASH BOOK ====================
def daily_cash_book(request, date):
    report = Sale.objects.filter(date__date=date).values('payment_method').annotate(
        total=Sum('total_amount')
    )
    return report



# ==================== REPORTS ====================
class ReportListView(LoginRequiredMixin, TemplateView):
    template_name = 'hardware/reports_index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reports'] = [
            {'name': 'Journal Report', 'url': 'hardware:journal_report', 'description': 'A list of all journal transactions'},
            {'name': 'General Ledger Report', 'url': 'hardware:general_ledger_report', 'description': 'A list of all journal transactions showing opening, list of transactions and closing balancing per account'},
            {'name': 'Trial Balance Report', 'url': 'hardware:trial_balance_report', 'description': 'A list of all the nominal general ledger Account balances'},
            {'name': 'Budget Report', 'url': 'hardware:budget_report', 'description': 'A detailed report showing budgeted and actual amounts'},
            {'name': 'List Of Transactions Report', 'url': 'hardware:transactions_report', 'description': 'A list of all transactions'},
            {'name': 'Profit Loss Report', 'url': 'hardware:profit_loss_report', 'description': 'Profit Loss Current year Earnings at a given date'},
            {'name': 'Sales Report', 'url': 'hardware:sales_report', 'description': 'List of all sales transactions'},
            {'name': 'Till Sheet', 'url': 'hardware:till_sheet_report', 'description': "List of Teller's over the counter transactions"},
            {'name': 'Audit Trail', 'url': 'hardware:audit_trail_report', 'description': 'A list of all system Users and backdated transactions'},
        ]
        return context


class GeneralLedgerReportView(LoginRequiredMixin, TemplateView):
    template_name = 'hardware/reports/general_ledger.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        account_id = self.request.GET.get('account')
        only_non_zero = self.request.GET.get('only_non_zero', 'off')
        only_with_transactions = self.request.GET.get('only_with_transactions', 'off')
        
        # Default to today if no date range provided
        if not start_date:
            start_date = timezone.now().strftime('%Y-%m-%d')
        if not end_date:
            end_date = timezone.now().strftime('%Y-%m-%d')
        
        context['start_date'] = start_date
        context['end_date'] = end_date
        context['account_id'] = account_id
        context['only_non_zero'] = only_non_zero
        context['only_with_transactions'] = only_with_transactions
        
        # Get all accounts
        accounts = Category.objects.all()
        context['accounts'] = accounts
        
        # Get transactions for the date range
        transactions = Sale.objects.filter(date__date__gte=start_date, date__date__lte=end_date)
        
        if account_id:
            # Filter by account if selected
            pass  # You'd need to add account field to sales or use a different model
        
        context['transactions'] = transactions[:100]  # Limit for display
        context['total_transactions'] = transactions.count()
        context['total_amount'] = transactions.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        return context


class TrialBalanceReportView(LoginRequiredMixin, TemplateView):
    template_name = 'hardware/reports/trial_balance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all products with their balances
        products = Product.objects.annotate(
            total_sales=Sum('saleitem__quantity'),
            total_revenue=Sum(F('saleitem__quantity') * F('saleitem__price')),
            total_cost=Sum(F('saleitem__quantity') * F('cost_price')),
            profit=Sum(F('saleitem__quantity') * F('saleitem__price')) - 
                   Sum(F('saleitem__quantity') * F('cost_price'))
        )
        
        context['accounts'] = products
        context['total_debit'] = products.aggregate(total=Sum('total_cost'))['total'] or Decimal('0')
        context['total_credit'] = products.aggregate(total=Sum('total_revenue'))['total'] or Decimal('0')
        context['total_balance'] = context['total_credit'] - context['total_debit']
        
        return context


class SalesReportView(LoginRequiredMixin, TemplateView):
    template_name = 'hardware/reports/sales_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if not start_date:
            start_date = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = timezone.now().strftime('%Y-%m-%d')
        
        sales = Sale.objects.filter(date__date__gte=start_date, date__date__lte=end_date)
        
        context['start_date'] = start_date
        context['end_date'] = end_date
        context['sales'] = sales
        context['total_sales'] = sales.count()
        context['total_revenue'] = sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        return context


class TillSheetReportView(LoginRequiredMixin, TemplateView):
    template_name = 'hardware/reports/till_sheet.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if not start_date:
            start_date = timezone.now().strftime('%Y-%m-%d')
        if not end_date:
            end_date = timezone.now().strftime('%Y-%m-%d')
        
        # Get cash transactions by cashier
        transactions = Sale.objects.filter(
            date__date__gte=start_date,
            date__date__lte=end_date,
            payment_method='CASH'
        ).select_related('cashier')
        
        # Group by cashier
        cashier_data = {}
        for sale in transactions:
            cashier_name = sale.cashier.get_full_name() or sale.cashier.username
            if cashier_name not in cashier_data:
                cashier_data[cashier_name] = {
                    'count': 0,
                    'total': Decimal('0'),
                    'sales': []
                }
            cashier_data[cashier_name]['count'] += 1
            cashier_data[cashier_name]['total'] += sale.total_amount
            cashier_data[cashier_name]['sales'].append(sale)
        
        context['start_date'] = start_date
        context['end_date'] = end_date
        context['cashier_data'] = cashier_data
        context['total_transactions'] = transactions.count()
        context['total_amount'] = transactions.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        return context


class AuditTrailReportView(LoginRequiredMixin, TemplateView):
    template_name = 'hardware/reports/audit_trail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all users
        from django.contrib.auth.models import User
        users = User.objects.all()
        
        # Get recent transactions
        recent_transactions = Sale.objects.all().order_by('-date')[:100]
        
        context['users'] = users
        context['transactions'] = recent_transactions
        context['total_users'] = users.count()
        context['total_transactions'] = Sale.objects.count()
        
        return context


# ==================== EXPORT REPORT ====================
@login_required
def export_report_csv(request):
    report_type = request.GET.get('report_type', 'sales')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    
    if report_type == 'sales':
        writer.writerow(['Receipt #', 'Date', 'Customer', 'Payment Method', 'Amount'])
        sales = Sale.objects.filter(
            date__date__gte=start_date,
            date__date__lte=end_date
        ) if start_date and end_date else Sale.objects.all()
        
        for sale in sales:
            writer.writerow([
                str(sale.id)[:8],
                sale.date.strftime('%Y-%m-%d %H:%M'),
                sale.customer.name if sale.customer else 'N/A',
                sale.payment_method,
                str(sale.total_amount)
            ])
    
    elif report_type == 'products':
        writer.writerow(['Product Code', 'Product Name', 'Category', 'Price', 'Stock'])
        for product in Product.objects.all():
            writer.writerow([
                product.product_code,
                product.name,
                product.category.name if product.category else 'N/A',
                str(product.selling_price),
                str(product.current_stock)
            ])
    
    return response
