from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import (
    Customer,
    Category,
    Product,
    Supplier,
    StockTransaction,
    Purchase,
    PurchaseItem,
    Sale,
    SaleItem
)

# =========================
# CUSTOMER
# =========================
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email')
    search_fields = ('name', 'phone', 'email')


# =========================
# CATEGORY
# =========================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)


# =========================
# PRODUCT
# =========================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'product_code',
        'name',
        'category',
        'cost_price',
        'selling_price',
        'reorder_level',
        'is_active',
    )

    list_filter = ('category', 'is_active')
    search_fields = ('product_code', 'name')
    ordering = ('name',)


# =========================
# SUPPLIER
# =========================
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'email', 'balance')
    search_fields = ('name', 'phone', 'email')


# =========================
# STOCK TRANSACTIONS (LEDGER)
# =========================
@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'product',
        'transaction_type',
        'quantity',
        'reference_id',
        'created_by',
        'created_at',
    )

    list_filter = ('transaction_type', 'created_at')
    search_fields = ('product__name', 'reference_id')
    readonly_fields = ('created_at',)


# =========================
# PURCHASE ITEMS INLINE
# =========================
class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1


# =========================
# PURCHASE
# =========================
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'supplier', 'date', 'total_amount')
    search_fields = ('invoice_number', 'supplier__name')
    list_filter = ('date',)
    inlines = [PurchaseItemInline]


# =========================
# SALE ITEMS INLINE
# =========================
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1


# =========================
# SALE
# =========================
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'cashier', 'payment_method', 'total_amount', 'date')
    search_fields = ('customer__name', 'cashier__username')
    list_filter = ('payment_method', 'date')
    inlines = [SaleItemInline]