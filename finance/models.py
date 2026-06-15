import random
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from dateutil.relativedelta import relativedelta
from members.models import Member

# =========================================================
# 1. CONFIGURATION & ACCOUNTING SYSTEM MODELS
# =========================================================

class SystemSetting(models.Model):
    """Global configuration for back-dating actions."""
    enable_back_dating = models.BooleanField(
        default=False, 
        help_text="If enabled, manually set dates for deposits and repayments can be used."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Setting"

    def __str__(self):
        return f"Back-Dating: {'Enabled' if self.enable_back_dating else 'Disabled'}"

    @classmethod
    def is_backdate_allowed(cls):
        setting, _ = cls.objects.get_or_create(id=1)
        return setting.enable_back_dating


class GlobalSettings(models.Model):
    """Global security configurations like 2FA enforcement."""
    enable_global_2fa = models.BooleanField(
        default=True,
        verbose_name="Enable Global 2FA",
        help_text="If checked, all users must verify via 2FA. If unchecked, 2FA is skipped."
    )

    class Meta:
        verbose_name = "System Configuration"
        verbose_name_plural = "Global Settings"

    def __str__(self):
        return "System Configuration"

    def save(self, *args, **kwargs):
        if not self.pk and GlobalSettings.objects.exists():
            return
        super().save(*args, **kwargs)


class ChartOfAccount(models.Model):
    """Standard structural node for general ledger tracking matching IFRS taxonomy."""
    ACCOUNT_TYPES = (
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('equity', 'Equity'),
    )
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']
        verbose_name = "Chart of Account"

    def __str__(self):
        return f"{self.code} - {self.name} ({self.account_type})"


# =========================================================
# 2. CORE FINANCIAL WALLET & CORE LOAN ENTITIES
# =========================================================

class SavingsAccount(models.Model):
    """Primary ledger balance account representing real capital for members."""
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='savings')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    @property
    def account_number(self):
        return self.member.member_number

    def __str__(self):
        return f"{self.member.first_name} - Account: {self.account_number} | Balance: {self.balance}"


from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
# Assuming your Member model is in the same app or imported correctly
from .models import Member 

class Loan(models.Model):
    """Loan issuance ledger containing structural states and tracking parameters."""
    PRODUCT_CHOICES = [
        ('personal', 'Personal Loan'),
        ('business', 'Business Loan'),
        ('salary', 'Salary Advance'),
        ('group', 'Group Loan'),
        ('emergency', 'Emergency Loan'),
        ('asset', 'Asset Finance'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('arrears', 'In Arrears'),
        ('rejected', 'Rejected'),
        ('closed', 'Closed'),
        ('defaulted', 'Defaulted'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='loans')
    officer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='loans_disbursed'
    )
    loan_reference = models.CharField(
        max_length=20, unique=True, null=True, blank=True,
        help_text="Unique alphanumeric loan reference (e.g., LN-ABC1234567)"
    )
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage rate (e.g., 12.5)")
    period_months = models.IntegerField()
    start_date = models.DateField(default=timezone.now)
    disbursed_date = models.DateField(null=True, blank=True)

    total_payable = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    principal_balance = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    interest_balance = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)

    product_type = models.CharField(max_length=20, choices=PRODUCT_CHOICES, default='personal', verbose_name="Loan Product")
    purpose = models.TextField(blank=True, null=True, verbose_name="Loan Purpose / Description")

    guarantor_1_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Guarantor 1 Name")
    guarantor_1_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Guarantor 1 Phone")
    guarantor_2_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Guarantor 2 Name")
    guarantor_2_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Guarantor 2 Phone")

    collateral_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Collateral Type")
    collateral_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Estimated Collateral Value")
    collateral_description = models.TextField(blank=True, null=True, verbose_name="Collateral Details")

    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="Business / Physical Location")
    contact_person = models.CharField(max_length=100, blank=True, null=True, verbose_name="Contact Person")
    contact_phone = models.CharField(max_length=15, blank=True, null=True, verbose_name="Contact Phone Number")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Loan"
        verbose_name_plural = "Loans"

    def save(self, *args, **kwargs):
        """Calculate totals and initial balances before saving."""
        if not self.total_payable or self.total_payable == 0:
            interest_amount = (self.principal_amount * (self.interest_rate / Decimal('100'))) * (self.period_months / Decimal('12'))
            self.total_payable = self.principal_amount + interest_amount
            # Initialize balances to full amount on creation
            self.principal_balance = self.principal_amount
            self.interest_balance = interest_amount
            
        super().save(*args, **kwargs)


    # Add to Loan class
    def get_active_interest_due(self):
        """Calculates interest for all installments that have reached their due date."""
        today = timezone.now().date()
        return self.installments.filter(
            due_date__lte=today, 
            paid=False
        ).aggregate(total=Sum('interest_portion'))['total'] or Decimal('0.00')

    def get_current_principal_due(self):
        """Calculates principal for installments that have reached their due date."""
        today = timezone.now().date()
        return self.installments.filter(
            due_date__lte=today, 
            paid=False
        ).aggregate(total=Sum('principal_portion'))['total'] or Decimal('0.00')

    def __str__(self):
        return f"{self.loan_reference or f'LN-{self.id}'} - {self.member.first_name} {self.member.last_name}"

    @property
    def balance(self):
        return (self.principal_balance or Decimal('0')) + (self.interest_balance or Decimal('0'))


class Installment(models.Model):
    """Amortization segments representing planned repayments."""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='installments')
    due_date = models.DateField()
    amount_remaining = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    principal_portion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_portion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid = models.BooleanField(default=False)

    @property
    def is_active(self):
        """Interest is only active if the date has arrived."""
        return timezone.now().date() >= self.due_date

    @property
    def interest_due(self):
        """Returns interest only if the installment is active."""
        return self.interest_portion if self.is_active else Decimal('0.00')

    @property
    def total_due(self):
        return (self.principal_portion or 0) + (self.interest_portion or 0) + (self.penalty_amount or 0)

    def __str__(self):
        return f"Inst {self.id} - Due: {self.due_date} (Remaining: {self.amount_remaining})"


# =========================================================
# 3. TRANSACTION ENGINE LOGS, REVERSALS & DOUBLE-ENTRY
# =========================================================

class Transaction(models.Model):
    """Individual system action tracking financial entry modifications."""
    T_TYPES = (
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('disbursement', 'Loan Disbursement'),
        ('repayment', 'Loan Repayment'),
        ('penalty', 'Penalty')
    )
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    loan = models.ForeignKey(Loan, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=20, choices=T_TYPES)
    timestamp = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=100, blank=True, null=True)
    is_reversed = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='transactions_created'
    )

    def __str__(self):
        return f"{self.type.upper()} - {self.amount} ({self.reference})"


class TransactionReversal(models.Model):
    """Audit footprint logging explicit transaction changes."""
    original_transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name='reversal_details'
    )
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    reversal_time = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()

    def __str__(self):
        return f"Reversal of {self.original_transaction.reference}"


class GeneralLedger(models.Model):
    """Double-entry general tracking node mapped directly to core transactions."""
    date = models.DateField(default=timezone.now)
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT, related_name='ledger_entries')
    description = models.CharField(max_length=200)
    reference = models.CharField(max_length=100, blank=True, null=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    transaction = models.ForeignKey(
        Transaction, null=True, blank=True, on_delete=models.SET_NULL, related_name='ledger_entries'
    )

    class Meta:
        ordering = ['date', 'id']
        verbose_name = "General Ledger"
        verbose_name_plural = "General Ledger Entries"
    
    class Meta:
        indexes = [
            # Speeds up date-range filters combined with account lookups
            models.Index(fields=['date', 'account']), 
        ]
    def __str__(self):
        return f"{self.date} - {self.account.name} | Dr:{self.debit} Cr:{self.credit}"


class AccountingEngine:
    """Automated operational runtime pipelines handling standard double-entry bookkeeping transactions."""
    
    @staticmethod
    def post_ledger_entry(account_code, description, reference, debit, credit, transaction_obj, date_context=None):
        try:
            account = ChartOfAccount.objects.get(code=account_code)
        except ChartOfAccount.DoesNotExist:
            raise ValidationError(f"Configuration Critical Failure: ChartOfAccount code {account_code} does not exist.")

        last_entry = GeneralLedger.objects.filter(account=account).order_by('-date', '-id').first()
        current_running_balance = last_entry.balance if last_entry else Decimal('0.00')

        if account.account_type in ['asset', 'expense']:
            new_running_balance = current_running_balance + Decimal(str(debit)) - Decimal(str(credit))
        else: # liability, income, equity
            new_running_balance = current_running_balance + Decimal(str(credit)) - Decimal(str(debit))

        return GeneralLedger.objects.create(
            date=date_context or timezone.now().date(),
            account=account,
            description=description,
            reference=reference,
            debit=debit,
            credit=credit,
            balance=new_running_balance,
            transaction=transaction_obj
        )


class Repayment(models.Model):
    """Explicit wrapper around programmatic waterfall repayments."""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    date_paid = models.DateTimeField(default=timezone.now)
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.pk and not self.receipt_number:
            self.receipt_number = f"RCP-{random.randint(10000, 99999)}"

        with transaction.atomic():
            loan_obj = Loan.objects.select_for_update().get(id=self.loan.id)
            try:
                savings = SavingsAccount.objects.select_for_update().get(member=loan_obj.member)
            except SavingsAccount.DoesNotExist:
                raise ValidationError("Member does not possess an active savings pocket.")

            repayment_pool = Decimal(str(self.amount_paid))
            if savings.balance < repayment_pool:
                raise ValidationError(f"Insufficient funds inside Savings Account. Balance: UGX {savings.balance:,.0f}")

            # 1. Deduct from Member Savings
            savings.balance -= repayment_pool
            savings.save()

            # 2. Allocate across Interest and Principal Balances
            allocated_interest = Decimal('0.00')
            allocated_principal = Decimal('0.00')

            if loan_obj.interest_balance > 0:
                allocated_interest = min(repayment_pool, loan_obj.interest_balance)
                loan_obj.interest_balance -= allocated_interest
                repayment_pool -= allocated_interest

            if repayment_pool > 0 and loan_obj.principal_balance > 0:
                allocated_principal = min(repayment_pool, loan_obj.principal_balance)
                loan_obj.principal_balance -= allocated_principal
                repayment_pool -= allocated_principal

            # 3. Clear off Installment records chronologically
            temp_pool = Decimal(str(self.amount_paid))
            unpaid_installments = loan_obj.installments.filter(paid=False).order_by('due_date')
            for inst in unpaid_installments:
                if temp_pool <= 0:
                    break
                payment_to_inst = min(temp_pool, inst.amount_remaining)
                inst.amount_remaining -= payment_to_inst
                temp_pool -= payment_to_inst
                if inst.amount_remaining <= 0:
                    inst.paid = True
                inst.save()

            # 4. Status Update Checks
            today = timezone.now().date()
            overdue_exists = loan_obj.installments.filter(due_date__lt=today, paid=False).exists()
            if not overdue_exists and loan_obj.status == 'arrears':
                loan_obj.status = 'approved'
            if loan_obj.principal_balance <= 0 and loan_obj.interest_balance <= 0:
                loan_obj.status = 'closed'
                loan_obj.is_active = False
            loan_obj.save()

            # 5. Create core system log transaction
            tx_log = Transaction.objects.create(
                member=loan_obj.member,
                amount=self.amount_paid,
                type='repayment',
                reference=f"LOAN-PYMT-#{self.receipt_number}",
                loan=loan_obj,
                timestamp=self.date_paid
            )

            # =========================================================
            # INTEGRATED SYSTEM DOUBLE-ENTRY LEDGER POSTING
            # =========================================================
            # Entry 1: Reduce SACCO liability to the member (Debit Savings account)
            AccountingEngine.post_ledger_entry(
                account_code="2000",
                description=f"Savings withdrawal for Loan Repayment {loan_obj.loan_reference}",
                reference=self.receipt_number,
                debit=self.amount_paid,
                credit=Decimal('0.00'),
                transaction_obj=tx_log,
                date_context=self.date_paid.date()
            )

            # Entry 2: Reduce SACCO loan portfolio outstanding balances (Credit Loan Asset)
            if allocated_principal > 0:
                AccountingEngine.post_ledger_entry(
                    account_code="1200",
                    description=f"Principal Recovery on Loan {loan_obj.loan_reference}",
                    reference=self.receipt_number,
                    debit=Decimal('0.00'),
                    credit=allocated_principal,
                    transaction_obj=tx_log,
                    date_context=self.date_paid.date()
                )

            # Entry 3: Recognize real income generated from operations (Credit Income Statement)
            if allocated_interest > 0:
                AccountingEngine.post_ledger_entry(
                    account_code="2100",
                    description=f"Interest Income Recognized on Loan {loan_obj.loan_reference}",
                    reference=self.receipt_number,
                    debit=Decimal('0.00'),
                    credit=allocated_interest,
                    transaction_obj=tx_log,
                    date_context=self.date_paid.date()
                )

            super().save(*args, **kwargs)

    def __str__(self):
        return f"Repayment {self.receipt_number} - {self.loan.member.last_name}"


# =========================================================
# 4. BATCH PROCESSING ENGINE & UTILITY RECONCILIATION
# =========================================================

@transaction.atomic
def process_repayment(loan_id):
    """Engine to safely deduct money from savings for automated batch processing sweeps."""
    try:
        loan = Loan.objects.select_for_update().get(id=loan_id, status__in=['approved', 'arrears'], is_active=True)
    except Loan.DoesNotExist:
        return False

    try:
        savings = SavingsAccount.objects.select_for_update().get(member=loan.member)
    except SavingsAccount.DoesNotExist:
        return False

    if savings.balance <= 0:
        return False

    inst = loan.installments.filter(paid=False).order_by('due_date').first()
    if not inst:
        return False

    collectible_amount = min(savings.balance, inst.amount_remaining)
    if collectible_amount <= 0:
        return False

    # Execute utilizing the safe transaction wrapper block
    receipt_ref = f"AUTO-{random.randint(10000, 99999)}"
    repayment_instance = Repayment(
        loan=loan,
        amount_paid=collectible_amount,
        receipt_number=receipt_ref,
        notes="Automated system sweep optimization protocol run."
    )
    repayment_instance.save()
    return True


# =========================================================
# 5. IFRS COMPLIANT FINANCIAL REPORTING LAYER ENGINE
# =========================================================

class FinancialStatementEngine:
    """Compiles real-time multi-dimensional financial positions balancing to the cent."""

    @staticmethod
    def get_balance_sheet():
        """Generates dynamic Statement of Financial Position assets vs liabilities."""
        assets = GeneralLedger.objects.filter(account__account_type='asset').aggregate(
            total=Coalesce(Sum('debit') - Sum('credit'), Decimal('0.00'))
        )['total']

        liabilities = GeneralLedger.objects.filter(account__account_type='liability').aggregate(
            total=Coalesce(Sum('credit') - Sum('debit'), Decimal('0.00'))
        )['total']

        income = GeneralLedger.objects.filter(account__account_type='income').aggregate(
            total=Coalesce(Sum('credit') - Sum('debit'), Decimal('0.00'))
        )['total']

        expenses = GeneralLedger.objects.filter(account__account_type='expense').aggregate(
            total=Coalesce(Sum('debit') - Sum('credit'), Decimal('0.00'))
        )['total']

        retained_earnings = income - expenses
        total_equity_and_liabilities = liabilities + retained_earnings

        return {
            "assets": assets,
            "liabilities": liabilities,
            "retained_earnings": retained_earnings,
            "total_equity_and_liabilities": total_equity_and_liabilities,
            "is_balanced": assets == total_equity_and_liabilities
        }

    @staticmethod
    def get_income_statement():
        """Compiles real profit or loss performance metrics across operational income/expense types."""
        total_income = GeneralLedger.objects.filter(account__account_type='income').aggregate(
            total=Coalesce(Sum('credit') - Sum('debit'), Decimal('0.00'))
        )['total']

        total_expense = GeneralLedger.objects.filter(account__account_type='expense').aggregate(
            total=Coalesce(Sum('debit') - Sum('credit'), Decimal('0.00'))
        )['total']

        return {
            "gross_revenue": total_income,
            "operating_expenses": total_expense,
            "net_surplus": total_income - total_expense
        }


# =========================================================
# 6. COMMUNICATIONS & NOTIFICATIONS METRICS
# =========================================================

class SMSConfig(models.Model):
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    cost_per_sms = models.DecimalField(max_digits=8, decimal_places=2, default=100.00)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SMS Config - Balance: UGX {self.balance}"

    @property
    def remaining_messages(self):
        return int(self.balance // self.cost_per_sms)


class SMSTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('TOPUP', 'Top-up'),
        ('REMINDER', 'Arrears Reminder'),
        ('OTHER', 'Other'),
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.TextField(blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - UGX {self.amount}"


def generate_schedule(loan):
    """Generates schedule installments and initializes amount_remaining structures."""
    if not loan.total_payable or loan.period_months <= 0:
        return
    principal_total = Decimal(str(loan.principal_amount))
    total_payable = Decimal(str(loan.total_payable))
    total_interest = total_payable - principal_total

    monthly_p = (principal_total / loan.period_months).quantize(Decimal('0.01'))
    monthly_i = (total_interest / loan.period_months).quantize(Decimal('0.01'))
    rem_p = principal_total

    for i in range(loan.period_months):
        due_date = loan.start_date + relativedelta(months=i + 1)
        curr_p = rem_p if i == loan.period_months - 1 else monthly_p
        curr_p = min(curr_p, rem_p)
        total_inst_due = curr_p + monthly_i

        Installment.objects.create(
            loan=loan,
            due_date=due_date,
            principal_portion=curr_p,
            interest_portion=monthly_i,
            amount_remaining=total_inst_due,
            paid=False
        )
        rem_p -= curr_p

    loan.principal_balance = principal_total
    loan.interest_balance = total_interest
    loan.save()


# =========================================================
# 7. AUTO-REPAYMENT SYSTEM SETTINGS LOGGERS
# =========================================================

class AutoRepaymentSetting(models.Model):
    FREQUENCY_CHOICES = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    is_enabled = models.BooleanField(default=False, verbose_name="Enable Auto Repayments")
    execution_time = models.TimeField(default="22:00:00", verbose_name="Execution Time")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='daily')
    grace_period_days = models.PositiveIntegerField(default=0, verbose_name="Grace Period (Days)")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Auto Repayment Setting"
        verbose_name_plural = "Auto Repayment Settings"

    def save(self, *args, **kwargs):
        if not self.pk and AutoRepaymentSetting.objects.exists():
            raise ValueError("Only one global AutoRepaymentSetting configuration instance can exist.")
        super().save(*args, **kwargs)
        try:
            from finance.tasks import sync_scheduler_to_celery_beat
            sync_scheduler_to_celery_beat(self)
        except ImportError:
            pass

    def __str__(self):
        return f"Auto-Repayment Config [Status: {self.is_enabled} | {self.execution_time}]"


class AutoRepaymentLog(models.Model):
    STATUS_CHOICES = [
        ('success', 'Full Success'),
        ('partial', 'Partial Payment'),
        ('failed', 'Failed / Insufficient Funds'),
        ('error', 'System Execution Exception')
    ]
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="repayment_logs")
    installment = models.ForeignKey(Installment, on_delete=models.SET_NULL, null=True, blank=True)
    savings_balance_before = models.DecimalField(max_digits=12, decimal_places=2)
    amount_attempted = models.DecimalField(max_digits=12, decimal_places=2)
    amount_recovered = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, db_index=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']


class DailyRepaymentSummary(models.Model):
    date = models.DateField(unique=True, db_index=True)
    total_processed = models.PositiveIntegerField(default=0)
    total_recovered = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    failed_deductions = models.PositiveIntegerField(default=0)
    partial_payments = models.PositiveIntegerField(default=0)
    closed_loans = models.PositiveIntegerField(default=0)
    execution_duration_seconds = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-date']