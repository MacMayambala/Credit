from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from decimal import Decimal
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from decimal import Decimal
from django.db import models   # <-- ADD THIS

from .models import (
    SavingsAccount, Loan, Installment, Transaction,
    Repayment, SMSConfig, SMSTransaction,
    ChartOfAccount, GeneralLedger,
    SystemSetting, GlobalSettings,
    ManualPenalty, LoanPenaltyRule
)

from .models import (
    SavingsAccount, Loan, Installment, Transaction,
    Repayment, SMSConfig, SMSTransaction,
    ChartOfAccount, GeneralLedger,
    SystemSetting, GlobalSettings,
    ManualPenalty, LoanPenaltyRule  # <-- Import LoanPenaltyRule
)

# ========================
# INLINES
# ========================

class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0
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

# --- NEW: Inline for LoanPenaltyRule inside LoanAdmin ---
class LoanPenaltyRuleInline(admin.StackedInline):
    model = LoanPenaltyRule
    can_delete = False
    extra = 1
    fields = (
        'penalty_type', 'period', 'fixed_amount', 'percentage_rate',
        'grace_period_days', 'max_penalty_cap', 'compound',
        'override_penalty', 'override_applied_by', 'override_date'
    )
    readonly_fields = ('override_applied_by', 'override_date')

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
    inlines = [InstallmentInline, RepaymentInline, LoanPenaltyRuleInline]  # <-- Added inline

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
        colors = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger',
            'closed': 'secondary'
        }
        color = colors.get(obj.status, 'secondary')
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
        if obj.status == 'approved' and not obj.disbursed_date:
            obj.disbursed_date = timezone.now().date()
        super().save_model(request, obj, form, change)

# finance/admin.py
from django.contrib import admin
from .models import Company   # <-- import the model

# finance/admin.py
from django.contrib import admin
from .models import Company   # add this import

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'website', 'updated_at')
    search_fields = ('name', 'email', 'phone')
    readonly_fields = ('updated_at',)

    # Prevent adding more than one company
    def has_add_permission(self, request):
        if Company.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = (
        'loan', 
        'due_date', 
        'principal_portion', 
        'interest_portion', 
        'paid', 
        'combined_penalty',   # <-- new field
        'total_due_display'
    )
    list_filter = ('paid', 'due_date')
    search_fields = ('loan__id', 'loan__member__first_name')

    def combined_penalty(self, obj):
        """
        Show total penalty = calculated (obj.penalty_amount) + manual penalties (not waived)
        """
        calc = obj.penalty_amount or Decimal('0.00')
        manual = obj.manual_penalties.filter(is_waived=False).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        total = calc + manual
        return format_html('UGX {}', f"{int(total):,}")
    combined_penalty.short_description = "Total Penalty"

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


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('id', 'enable_back_dating', 'member_prefix', 'updated_at')
    list_editable = ('enable_back_dating', 'member_prefix')

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.id = 1
        super().save_model(request, obj, form, change)


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not GlobalSettings.objects.exists()
        
    def has_delete_permission(self, request, obj=None):
        return False 


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


# ------------------------------
# CHART OF ACCOUNTS & LEDGER
# ------------------------------
class ChartOfAccountAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'is_active']
    list_filter = ['account_type', 'is_active']
    search_fields = ['code', 'name']
    ordering = ['code']


class GeneralLedgerAdmin(admin.ModelAdmin):
    list_display = ['date', 'account', 'description', 'debit', 'credit']
    list_filter = ['date', 'account']
    search_fields = ['description', 'reference']
    date_hierarchy = 'date'


admin.site.register(ChartOfAccount, ChartOfAccountAdmin)
admin.site.register(GeneralLedger, GeneralLedgerAdmin)


# ------------------------------
# COMPANY (core)
# ------------------------------
# If Company is in core app, you might need to import it.
# Since you have a core/admin.py, we keep it there.
# But if you want it here, uncomment:
# from core.models import Company
# @admin.register(Company)
# class CompanyAdmin(admin.ModelAdmin): ...


# ------------------------------
# MANUAL PENALTY ADMIN
# ------------------------------
@admin.register(ManualPenalty)
class ManualPenaltyAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'loan',
        'installment',
        'amount',
        'reason_short',
        'applied_by',
        'applied_date',
        'is_waived',
    )
    list_filter = ('is_waived', 'applied_date', 'loan__status')
    search_fields = ('loan__loan_reference', 'loan__member__first_name', 'loan__member__last_name', 'reason')
    readonly_fields = ('applied_date',)
    raw_id_fields = ('loan', 'installment', 'applied_by', 'waived_by')
    fieldsets = (
        (None, {'fields': ('loan', 'installment', 'amount', 'reason')}),
        ('Applied By', {'fields': ('applied_by', 'applied_date')}),
        ('Waiver Details', {'fields': ('is_waived', 'waived_by', 'waived_date', 'waiver_reason'), 'classes': ('collapse',)}),
    )

    def reason_short(self, obj):
        return obj.reason[:50] + '…' if len(obj.reason) > 50 else obj.reason
    reason_short.short_description = 'Reason'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('loan', 'installment', 'applied_by', 'waived_by')


# ------------------------------
# LOAN PENALTY RULE ADMIN (NEW)
# ------------------------------
@admin.register(LoanPenaltyRule)
class LoanPenaltyRuleAdmin(admin.ModelAdmin):
    list_display = ('loan', 'penalty_type', 'period', 'percentage_rate', 'fixed_amount', 'grace_period_days')
    search_fields = ('loan__loan_reference', 'loan__member__first_name', 'loan__member__last_name')
    list_filter = ('penalty_type', 'period')
    fields = (
        'loan', 'penalty_type', 'period',
        'fixed_amount', 'percentage_rate',
        'grace_period_days', 'max_penalty_cap', 'compound',
        'override_penalty', 'override_applied_by', 'override_date'
    )
    readonly_fields = ('override_applied_by', 'override_date')