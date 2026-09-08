# hardware/services.py
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Count, Q, F, Value, Case, When, IntegerField, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    Product, Sale, SaleItem, StockTransaction,
    Purchase, PurchaseItem, Category, Supplier, Customer
)


# ============================================================
# DASHBOARD STATS
# ============================================================
def get_dashboard_stats():
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    # Stock calculation using ledger
    products = Product.objects.annotate(
        inflow=Coalesce(
            Sum('ledger__quantity',
                filter=Q(ledger__transaction_type='PURCHASE')
            ),
            Value(0, output_field=DecimalField())
        ),
        outflow=Coalesce(
            Sum('ledger__quantity',
                filter=Q(ledger__transaction_type='SALE')
            ),
            Value(0, output_field=DecimalField())
        )
    ).annotate(
        calculated_stock=F('inflow') - F('outflow')
    )

    inventory_value_expr = ExpressionWrapper(
        F('calculated_stock') * F('cost_price'),
        output_field=DecimalField(max_digits=14, decimal_places=2)
    )

    stats = products.aggregate(
        total_value=Sum(inventory_value_expr),
        low_stock_count=Sum(
            Case(
                When(calculated_stock__lte=F('reorder_level'), then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        )
    )

    # Today's sales
    todays_sales = Sale.objects.filter(
        date__date=today
    ).aggregate(
        total=Coalesce(Sum('total_amount'), Decimal('0.00'))
    )['total']

    # Monthly revenue
    monthly_revenue = Sale.objects.filter(
        date__date__gte=start_of_month,
        date__date__lte=today
    ).aggregate(
        total=Coalesce(Sum('total_amount'), Decimal('0.00'))
    )['total']

    total_sales_count = Sale.objects.count()

    # Recent transactions (using StockTransaction, fallback to SaleItem)
    recent_transactions = StockTransaction.objects.select_related('product').order_by('-created_at')[:10]
    if not recent_transactions:
        from .models import SaleItem
        recent_transactions = SaleItem.objects.select_related('product', 'sale').order_by('-sale__date')[:10]

    return {
        'total_products': Product.objects.count(),
        'inventory_value': stats['total_value'] or Decimal('0.00'),
        'low_stock_count': stats['low_stock_count'] or 0,
        'todays_sales': todays_sales,
        'todays_revenue': todays_sales,
        'monthly_revenue': monthly_revenue,
        'total_sales_count': total_sales_count,
        'recent_transactions': recent_transactions,
    }


# ============================================================
# PRODUCT WITH OPENING STOCK
# ============================================================
def create_product_with_opening_stock(data, opening_qty, user):
    """
    Creates a product and initializes its stock via a ledger transaction.
    """
    product = Product.objects.create(**data)
    if opening_qty > 0:
        StockTransaction.objects.create(
            product=product,
            quantity=opening_qty,
            transaction_type='ADJUSTMENT',
            reference_id='INITIAL',
            created_by=user,
            remarks='Opening stock'
        )
    return product


# ============================================================
# PURCHASE CREATION (with stock update)
# ============================================================
def create_purchase(supplier, items_data, invoice_number, user):
    """
    items_data: list of dicts like {'product': ProductObj, 'qty': 5, 'cost': 100}
    """
    with transaction.atomic():
        total = sum(i['qty'] * i['cost'] for i in items_data)
        purchase = Purchase.objects.create(
            invoice_number=invoice_number,
            supplier=supplier,
            total_amount=total
        )

        for item in items_data:
            PurchaseItem.objects.create(
                purchase=purchase,
                product=item['product'],
                quantity=item['qty'],
                cost=item['cost']
            )

            StockTransaction.objects.create(
                product=item['product'],
                quantity=item['qty'],
                transaction_type='PURCHASE',
                reference_id=invoice_number,
                created_by=user,
                remarks=f"Purchase {invoice_number}"
            )

        return purchase


# ============================================================
# POINT‑OF‑SALE SALE (IMMEDIATE, CASH)
# ============================================================
def secure_process_sale(cart_items, customer, payment_method, cashier, status='paid'):
    """
    Process a sale: create sale, sale items, update stock, and record stock transactions.
    If status is 'paid' (default), stock is deducted immediately.
    If status is 'pending', stock is NOT deducted – must be done later via webhook.
    """
    with transaction.atomic():
        total = Decimal('0')
        for item in cart_items:
            total += item['price'] * item['qty']

        sale = Sale.objects.create(
            customer=customer,
            total_amount=total,
            payment_method=payment_method,
            cashier=cashier,
            status=status,
            phone_number=cart_items[0].get('phone_number') if cart_items else None,
        )

        for item in cart_items:
            SaleItem.objects.create(
                sale=sale,
                product=item['product'],
                quantity=item['qty'],
                price=item['price']
            )

            # Only deduct stock if status is 'paid'
            if status == 'paid':
                product = item['product']
                # Lock row to prevent race conditions
                product = Product.objects.select_for_update().get(id=product.id)
                if product.current_stock < item['qty']:
                    raise ValueError(f"Insufficient stock for {product.name}. Available: {product.current_stock}")
                product.current_stock -= item['qty']
                product.save()

                StockTransaction.objects.create(
                    product=product,
                    quantity=-item['qty'],  # negative for sales
                    transaction_type='SALE',
                    reference_id=str(sale.id),
                    created_by=cashier,
                    remarks=f"Sale #{sale.id}"
                )

        return sale


# ============================================================
# CREATE PENDING SALE (for mobile money, no stock deduction)
# ============================================================
def create_pending_sale(cart_items, cashier, phone_number, total_amount):
    """
    Create a sale with status 'pending' – no stock deduction.
    Used for mobile money payments before confirmation.
    """
    with transaction.atomic():
        sale = Sale.objects.create(
            customer=None,
            total_amount=total_amount,
            payment_method='MOBILE_MONEY',
            cashier=cashier,
            status='pending',
            phone_number=phone_number,
        )
        for item in cart_items:
            SaleItem.objects.create(
                sale=sale,
                product=item['product'],
                quantity=item['qty'],
                price=item['price']
            )
        # Stock NOT deducted – will be done in webhook when payment confirmed
        return sale


# ============================================================
# PROFIT REPORT
# ============================================================
def get_profit_report(start_date, end_date):
    """
    Calculates total Sales, COGS, and Gross Profit for a period.
    """
    data = SaleItem.objects.filter(
        sale__date__range=[start_date, end_date]
    ).aggregate(
        total_revenue=Sum(F('quantity') * F('price')),
        total_cogs=Sum(F('quantity') * F('product__cost_price'))
    )

    revenue = data['total_revenue'] or Decimal('0')
    cogs = data['total_cogs'] or Decimal('0')
    gross_profit = revenue - cogs

    return {
        'revenue': revenue,
        'cogs': cogs,
        'gross_profit': gross_profit,
        'margin': (gross_profit / revenue * 100) if revenue > 0 else 0
    }


# ============================================================
# SIGNAL: UPDATE PRODUCT STOCK ON STOCK TRANSACTION
# ============================================================
@receiver(post_save, sender=StockTransaction)
def update_product_stock(sender, instance, created, **kwargs):
    """
    Whenever a StockTransaction is created, update the product's current_stock.
    """
    if created:
        product = instance.product
        # For SALE transactions, quantity is already negative (if we stored negative)
        # but to be safe, we'll add/subtract based on transaction type.
        if instance.transaction_type == 'PURCHASE':
            product.current_stock += instance.quantity
        elif instance.transaction_type == 'SALE':
            # We store negative quantity in sale transactions, so add it (which subtracts)
            product.current_stock += instance.quantity  # instance.quantity is negative
        elif instance.transaction_type in ('ADJUSTMENT', 'RETURN'):
            # Adjustments and returns: add quantity (positive)
            product.current_stock += instance.quantity
        # If you use positive quantities for sales, change accordingly.
        product.save()