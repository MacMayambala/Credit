from .models import Product, StockTransaction

from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from .models import Product, StockTransaction

from django.db.models import Sum, F, Case, When, Value, DecimalField, IntegerField
from .models import Product

from django.db.models import Sum, F, Case, When, Value, DecimalField, IntegerField
from django.db.models.functions import Coalesce
from .models import Product

from django.db.models import Sum, F, Case, When, Value, DecimalField, IntegerField, ExpressionWrapper
from django.db.models.functions import Coalesce
from .models import Product


def get_dashboard_stats():
    # 1. Stock calculation
    products = Product.objects.annotate(
        inflow=Coalesce(
            Sum('ledger__quantity',
                filter=Case(
                    When(ledger__transaction_type='PURCHASE', then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ),
            Value(0),
            output_field=IntegerField()
        ),
        outflow=Coalesce(
            Sum('ledger__quantity',
                filter=Case(
                    When(ledger__transaction_type='SALE', then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ),
            Value(0),
            output_field=IntegerField()
        ),
    ).annotate(
        calculated_stock=F('inflow') - F('outflow')
    )

    # 2. Proper typed multiplication (IMPORTANT FIX)
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
            ),
            output_field=IntegerField()
        )
    )

    return {
        'total_products': Product.objects.count(),
        'inventory_value': stats['total_value'] or 0,
        'low_stock_items': stats['low_stock_count'] or 0,
    }

# hardware/services.py
from .models import Product, StockTransaction

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
            user=user
        )
    return product


from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StockTransaction


from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StockTransaction


@receiver(post_save, sender=StockTransaction)
def update_product_stock(sender, instance, created, **kwargs):
    if created:
        product = instance.product
        # Deduct stock for Sales; add stock for Purchases
        if instance.transaction_type == 'SALE':
            product.current_stock -= instance.quantity
        elif instance.transaction_type == 'PURCHASE':
            product.current_stock += instance.quantity
        elif instance.transaction_type == 'ADJUSTMENT':
            # For adjustments, you might want to handle this differently
            product.current_stock += instance.quantity
        elif instance.transaction_type == 'RETURN':
            product.current_stock += instance.quantity
        product.save()

from django.contrib.auth.models import User
from django.db import transaction
from .models import StockTransaction, Purchase, PurchaseItem

def create_purchase(supplier, items_data, invoice_number, user):
    """
    items_data: list of dicts like {'product': ProductObj, 'qty': 5, 'cost': 100}
    """
    with transaction.atomic():
        # 1. Create the Purchase Header
        total = sum(i['qty'] * i['cost'] for i in items_data)
        purchase = Purchase.objects.create(
            invoice_number=invoice_number, 
            supplier=supplier, 
            total_amount=total
        )
        
        # 2. Create Items and trigger the Ledger
        for item in items_data:
            PurchaseItem.objects.create(
                purchase=purchase, 
                product=item['product'], 
                quantity=item['qty'], 
                cost=item['cost']
            )
            
            # This triggers the StockTransaction which updates product stock via signals
            StockTransaction.objects.create(
                product=item['product'],
                quantity=item['qty'],
                transaction_type='PURCHASE',
                reference_id=invoice_number,
                created_by=user
            )

from django.db import transaction
from .models import Sale, SaleItem, StockTransaction

def process_pos_sale(cart_items, customer, payment_method, user):
    """
    cart_items: list of {'product': obj, 'qty': int, 'price': decimal}
    """
    with transaction.atomic():
        # 1. Create Sale Header
        total_amount = sum(item['qty'] * item['price'] for item in cart_items)
        sale = Sale.objects.create(
            customer=customer, 
            total_amount=total_amount, 
            payment_method=payment_method,
            cashier=user
        )
        
        # 2. Process Items and Inventory
        for item in cart_items:
            # Check for stock availability
            if item['product'].current_stock < item['qty']:
                raise ValueError(f"Not enough stock for {item['product'].name}")
                
            SaleItem.objects.create(sale=sale, product=item['product'], quantity=item['qty'], price=item['price'])
            
            # Record in Ledger (Triggers stock deduction signal)
            StockTransaction.objects.create(
                product=item['product'],
                quantity=item['qty'],
                transaction_type='SALE',
                reference_id=sale.id,
                created_by=user
            )
        return sale
    


from django.db import transaction
# Assuming your finance app has a model like 'Transaction' or 'LedgerEntry'
from finance.models import Transaction 

def finalize_sale_and_finance(sale, payment_method):
    with transaction.atomic():
        # 1. Update the sale status
        sale.status = 'COMPLETED'
        sale.save()
        
        # 2. Record in Finance App (Double-entry logic)
        Transaction.objects.create(
            amount=sale.total_amount,
            account_type='REVENUE',
            description=f"Sale Receipt #{sale.id}",
            payment_method=payment_method,
            date=sale.date
        )



from django.db.models import Sum, F
from .models import SaleItem

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
    
    revenue = data['total_revenue'] or 0
    cogs = data['total_cogs'] or 0
    gross_profit = revenue - cogs
    
    return {
        'revenue': revenue,
        'cogs': cogs,
        'gross_profit': gross_profit,
        'margin': (gross_profit / revenue * 100) if revenue > 0 else 0
    }



from django.db import transaction
from .models import Product, Sale, SaleItem, StockTransaction

def secure_process_sale(cart_items, customer, payment_method, user):
    """
    cart_items: list of dicts like {'product': ProductObj, 'qty': Decimal, 'price': Decimal}
    """
    with transaction.atomic():
        # 1. Calculate total amount
        total_amount = sum(item['qty'] * item['price'] for item in cart_items)
        
        # 2. Create Sale Header
        sale = Sale.objects.create(
            customer=customer,
            total_amount=total_amount,
            payment_method=payment_method,
            cashier=user
        )
        
        # 3. Process each item with row-level locking
        for item in cart_items:
            # Lock the product row to prevent race conditions during stock deduction
            product = Product.objects.select_for_update().get(id=item['product'].id)
            
            if product.current_stock < item['qty']:
                raise ValueError(f"Insufficient stock for {product.name}. Available: {product.current_stock}")
            
            # Create Sale Item
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=item['qty'],
                price=item['price']
            )
            
            # Create Ledger Entry (This will trigger the signal to update current_stock)
            StockTransaction.objects.create(
                product=product,
                quantity=item['qty'],
                transaction_type='SALE',
                reference_id=str(sale.id),
                created_by=user,
                remarks=f"Sale transaction for invoice {sale.id}"
            )
            
        return sale



from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StockTransaction

@receiver(post_save, sender=StockTransaction)
def update_product_stock(sender, instance, created, **kwargs):
    if created:
        product = instance.product
        # Deduct stock for Sales; add stock for Purchases
        if instance.transaction_type == 'SALE':
            product.current_stock -= instance.quantity
        elif instance.transaction_type == 'PURCHASE':
            product.current_stock += instance.quantity
        product.save()