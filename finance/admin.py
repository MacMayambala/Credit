from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from decimal import Decimal

from .models import (
    SavingsAccount, Loan, Installment, Transaction,
    Repayment, SMSConfig, SMSTransaction,
    ChartOfAccount, GeneralLedger
)

# ========================
# INLINES
# ========================

class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0
    # Updated to use principal_portion and interest_portion instead of 'amount'
    readonly_fields = ('due_date', 'principal_portion', 'interest_portion', 'paid', 'penalty_amount', 'total_due_display')
    can_delete = False
    fields = ('due_date', 'principal_portion', 'interest_portion', 'paid', 'penalty_amount', 'total_due_display')

    def total_due_display(self, obj):
        try:
            return format_html('<strong>UGX {}</strong>', f"{int(obj.total_due):,}")
        except:
            return "UGX 0"
    total_due_display.short_description = "Total Due"


class RepaymentInline(admin.TabularInline):
    model = Repayment
    extra = 0
    readonly_fields = ('receipt_number', 'date_paid')
    fields = ('amount_paid', 'date_paid', 'receipt_number', 'notes')


# ========================
# ADMIN CLASSES
# ========================

@admin.register(SavingsAccount)
class SavingsAccountAdmin(admin.ModelAdmin):
    list_display = ('member', 'balance_formatted')
    search_fields = ('member__first_name', 'member__last_name', 'member__member_number')
    readonly_fields = ('balance',)

    def balance_formatted(self, obj):
        amount = obj.balance or Decimal('0')
        return format_html('<strong>UGX {}</strong>', f"{int(amount):,}")
    balance_formatted.short_description = "Balance"


# /home/mac/whoweare/credit/credit/finance/admin.py

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'member_link', 
        'officer', 
        'principal_amount', 
        'status_badge', 
        'principal_balance_formatted', 
        'interest_balance_formatted',
        'disbursed_date', 
        'is_active'
    )
    list_filter = ('status', 'is_active', 'start_date', 'officer')
    search_fields = ('id', 'member__first_name', 'member__last_name', 'member__member_number')
    
    readonly_fields = ('total_payable', 'principal_balance', 'interest_balance')
    inlines = [InstallmentInline, RepaymentInline]

    fieldsets = (
        ("Loan Information", {
            'fields': ('member', 'officer', 'principal_amount', 'interest_rate', 
                       'period_months', 'start_date', 'disbursed_date')
        }),
        ("Status", {
            'fields': ('status', 'is_active')
        }),
        ("Financial Summary", {
            'fields': ('total_payable', 'principal_balance', 'interest_balance'),
            'classes': ('collapse',)
        }),
    )

    def member_link(self, obj):
        if not obj.member:
            return "No Member"
        return format_html(
            '<a href="/admin/members/member/{}/change/">{} {}</a>',
            obj.member.id,
            obj.member.first_name or '',
            obj.member.last_name or ''
        )
    member_link.short_description = "Member"

    def status_badge(self, obj):
        # Professional color mapping for SACCO statuses
        colors = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger',
            'closed': 'secondary'
        }
        color = colors.get(obj.status, 'secondary')
        
        # FIX: Check if the method exists before calling it to prevent AttributeError
        if hasattr(obj, 'get_status_display'):
            display_text = obj.get_status_display()
        else:
            display_text = str(obj.status).upper() if obj.status else 'UNKNOWN'

        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, 
            display_text
        )
    status_badge.short_description = "Status"

    def principal_balance_formatted(self, obj):
        amount = obj.principal_balance or Decimal('0')
        return format_html('UGX {}', f"{int(amount):,}")
    principal_balance_formatted.short_description = "Principal Bal"

    def interest_balance_formatted(self, obj):
        amount = obj.interest_balance or Decimal('0')
        return format_html('UGX {}', f"{int(amount):,}")
    interest_balance_formatted.short_description = "Interest Bal"

    def save_model(self, request, obj, form, change):
        # Automatically set disbursed_date when status changes to approved
        if obj.status == 'approved' and not obj.disbursed_date:
            obj.disbursed_date = timezone.now().date()
        super().save_model(request, obj, form, change)

    def principal_balance_formatted(self, obj):
        amount = obj.principal_balance or Decimal('0')
        return format_html('UGX {}', f"{int(amount):,}")
    principal_balance_formatted.short_description = "Principal Bal"

    def interest_balance_formatted(self, obj):
        amount = obj.interest_balance or Decimal('0')
        return format_html('UGX {}', f"{int(amount):,}")
    interest_balance_formatted.short_description = "Interest Bal"

    def save_model(self, request, obj, form, change):
        # Automatically set disbursed_date when status changes to approved
        if obj.status == 'approved' and not obj.disbursed_date:
            obj.disbursed_date = timezone.now().date()
        super().save_model(request, obj, form, change)


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    # Removed 'amount' to use split principal/interest fields
    list_display = ('loan', 'due_date', 'principal_portion', 'interest_portion', 'paid', 'penalty_amount', 'total_due_display')
    list_filter = ('paid', 'due_date')
    search_fields = ('loan__id', 'loan__member__first_name')

    def total_due_display(self, obj):
        try:
            return format_html('UGX {}', f"{int(obj.total_due):,}")
        except:
            return "UGX 0"
    total_due_display.short_description = "Total Due"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'member', 'type', 'amount_formatted', 'reference')
    list_filter = ('type', 'timestamp')
    search_fields = ('member__first_name', 'member__last_name', 'reference')
    date_hierarchy = 'timestamp'

    def amount_formatted(self, obj):
        amount = obj.amount or Decimal('0')
        return format_html('UGX {}', f"{int(amount):,}")
    amount_formatted.short_description = "Amount"

from django.contrib import admin
from .models import SystemSetting

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('id', 'enable_back_dating', 'updated_at')
    list_editable = ('enable_back_dating',)
    
    def has_add_permission(self, request):
        # Prevent creating multiple setting rows. 
        # If one exists, don't allow adding another.
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting the configuration row
        return False

    # Optional: Force the ID to be 1 to match your model's .get_or_create(id=1)
    def save_model(self, request, obj, form, change):
        obj.id = 1
        super().save_model(request, obj, form, change)


@admin.register(Repayment)
class RepaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'loan', 'amount_paid', 'date_paid')
    list_filter = ('date_paid',)
    search_fields = ('receipt_number', 'loan__member__first_name')


@admin.register(SMSConfig)
class SMSConfigAdmin(admin.ModelAdmin):
    list_display = ('balance', 'cost_per_sms', 'remaining_messages', 'updated_at')
    readonly_fields = ('remaining_messages', 'updated_at')


@admin.register(SMSTransaction)
class SMSTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'amount', 'performed_by', 'created_at')
    list_filter = ('transaction_type', 'created_at')


# finance/admin.py
from django.contrib import admin
from .models import ChartOfAccount, GeneralLedger

class ChartOfAccountAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'is_active']   # Changed from 'category'
    list_filter = ['account_type', 'is_active']                    # Changed from 'category'
    search_fields = ['code', 'name']
    ordering = ['code']


class GeneralLedgerAdmin(admin.ModelAdmin):
    list_display = ['date', 'account', 'description', 'debit', 'credit']
    list_filter = ['date', 'account']
    search_fields = ['description', 'reference']
    date_hierarchy = 'date'


admin.site.register(ChartOfAccount, ChartOfAccountAdmin)
admin.site.register(GeneralLedger, GeneralLedgerAdmin)