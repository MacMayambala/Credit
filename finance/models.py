import random
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone

from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from dateutil.relativedelta import relativedelta
from members.models import Member   
# core/models.py
from django.db import models
from django.utils import timezone

class Company(models.Model):
    """
    Singleton model to store company-wide information.
    """
    name = models.CharField(max_length=100, default="MAC Technologies")
    tagline = models.CharField(max_length=200, blank=True, default="Core Banking & Financial Services")
    logo = models.ImageField(upload_to='company/', blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, default="+256 700 000 000")
    email = models.EmailField(blank=True, default="mmayambala@schooladmin.tech")
    website = models.URLField(blank=True, default="www.schooladmin.tech")
    address = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Company"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one record exists
        if not self.pk and Company.objects.exists():
            raise ValueError("There is already a Company record. Update it instead.")
        super().save(*args, **kwargs)

    @classmethod
    def get_company(cls):
        """Return the company instance, creating a default one if none exists."""
        company, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'name': 'MAC Technologies',
                'tagline': 'Core Banking & Financial Services',
                'phone': '+256 776 203 790',
                'email': 'mmayambala@schooladmin.tech',
                'website': 'www.schooladmin.tech',
            }
        )
        return company

# =========================================================
# 1. CONFIGURATION & ACCOUNTING SYSTEM MODELS
# =========================================================

class SystemSetting(models.Model):
    """Global configuration stored as key-value pairs."""

    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255, blank=True, null=True)

    # Backdating flag (kept for system use)
    enable_back_dating = models.BooleanField(
        default=False,
        help_text="If enabled, manually set dates for deposits and repayments can be used."
    )
    member_prefix = models.CharField(
        max_length=10,
        default="KAL",
        help_text="Prefix used for member numbers (e.g. KAL, ABC)"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Setting"

    def __str__(self):
        return f"{self.key}: {self.value}"

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
    member = models.OneToOneField(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='savings'
    )
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


from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.conf import settings




class Loan(models.Model):
    # ==============================
    # CHOICES (defined as tuples)
    # ==============================
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

    REPAYMENT_FREQUENCY = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('manual', 'Manual'),
    ]

    # ==============================
    # FIELDS
    # ==============================
    repayment_frequency = models.CharField(
        max_length=10,
        choices=REPAYMENT_FREQUENCY,
        default='monthly'
    )
    term_value = models.PositiveIntegerField(default=1)
    member = models.ForeignKey('members.Member', on_delete=models.CASCADE, related_name='loans')
    officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    loan_reference = models.CharField(max_length=20, unique=True, null=True, blank=True)

    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    period_months = models.IntegerField(default=1)
    start_date = models.DateField(default=timezone.now)
    disbursed_date = models.DateField(null=True, blank=True)
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    principal_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_CHOICES,
        default='personal'
    )
    purpose = models.TextField(blank=True, null=True)

    guarantor_1_name = models.CharField(max_length=255, null=True, blank=True)
    guarantor_1_phone = models.CharField(max_length=20, null=True, blank=True)
    guarantor_2_name = models.CharField(max_length=255, null=True, blank=True)
    guarantor_2_phone = models.CharField(max_length=20, null=True, blank=True)

    collateral_type = models.CharField(max_length=100, blank=True, null=True)
    collateral_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    collateral_description = models.TextField(blank=True, null=True)

    location = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=15, blank=True, null=True)

    # Legacy penalty fields (deprecated, but kept for now)
    last_penalty_date = models.DateField(null=True, blank=True)
    penalty_flat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    penalty_type = models.CharField(
        max_length=25,
        choices=[
            ('daily_flat', 'Daily Flat'),
            ('daily_percentage', 'Daily Percentage'),
            ('fixed', 'Fixed Penalty'),
            ('compound', 'Compound Penalty'),
            ('monthly_once', 'Monthly Once'),
        ],
        default='daily_flat'
    )
    penalty_frequency = models.CharField(
        max_length=10,
        choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')],
        default='monthly'
    )
    penalty_rate = models.DecimalField(max_digits=6, decimal_places=2, default=1.0)
    penalty_grace_days = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ==============================
    # META
    # ==============================
    class Meta:
        permissions = [
            ('can_apply_loan', 'Can apply for a loan'),
            ('can_approve_loan', 'Can approve a loan'),
            ('can_disburse_loan', 'Can disburse a loan'),
            ('can_apply_manual_penalty', 'Can manually apply penalty'),
            ('can_waive_penalty', 'Can waive penalties'),
        ]

    # ==============================
    # METHODS
    # ==============================
    def save(self, *args, **kwargs):
        if not self.total_payable or self.total_payable == 0:
            interest_amount = self.principal_amount * (self.interest_rate / Decimal('100'))
            self.total_payable = self.principal_amount + interest_amount
            self.principal_balance = self.principal_amount
            self.interest_balance = interest_amount
        super().save(*args, **kwargs)

    # (keep your analytics methods – they are fine)

    # ==============================
    # ANALYTICS METHODS
    # ==============================
    def get_active_interest_due(self):
        total = Decimal('0.00')
        for inst in self.installments.filter(due_date__lte=timezone.now().date()):
            total += inst.interest_portion - inst.interest_paid
        return total

    def get_current_principal_due(self):
        total = Decimal('0.00')
        for inst in self.installments.filter(due_date__lte=timezone.now().date()):
            total += inst.principal_portion - inst.principal_paid
        return total

    @property
    def arrears_balance(self):
        today = timezone.now().date()
        return sum(inst.balance for inst in self.installments.filter(due_date__lt=today))

    @property
    def completion_percentage(self):
        total_due = self.total_payable
        remaining = self.principal_balance + self.interest_balance
        if total_due <= 0:
            return 0
        return round(((total_due - remaining) / total_due) * 100, 2)

    @property
    def balance(self):
        return (self.principal_balance or Decimal('0')) + (self.interest_balance or Decimal('0'))

    def __str__(self):
        return f"{self.loan_reference or f'LN-{self.id}'} - {self.member}"

from decimal import Decimal
from django.db import models
from django.utils import timezone


class Installment(models.Model):
    loan = models.ForeignKey('Loan', on_delete=models.CASCADE, related_name='installments')
    due_date = models.DateField()

    principal_portion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_portion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    principal_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    interest_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    penalty_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    paid = models.BooleanField(default=False)

    def refresh_penalty(self):
        from finance.penalties import calculate_penalty
        new_penalty = calculate_penalty(self)
        if self.penalty_amount != new_penalty:
            self.penalty_amount = new_penalty
            self.save(update_fields=["penalty_amount"])

    @property
    def principal_balance(self):
        return max(Decimal('0.00'), self.principal_portion - self.principal_paid)

    @property
    def interest_balance(self):
        return max(Decimal('0.00'), self.interest_portion - self.interest_paid)

    @property
    def penalty_balance(self):
        return max(Decimal('0.00'), self.penalty_amount - self.penalty_paid)

    @property
    def amount_due(self):
        return self.principal_portion + self.interest_portion + self.penalty_amount

    @property
    def amount_paid(self):
        return self.principal_paid + self.interest_paid + self.penalty_paid

    @property
    def balance(self):
        return self.principal_balance + self.interest_balance + self.penalty_balance

    @property
    def get_total_penalty(self):
        """Returns total penalty (calculated + manual) for this installment."""
        from finance.penalties import calculate_penalty
        calc = calculate_penalty(self)
        manual = self.manual_penalties.filter(is_waived=False).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        return calc + manual

    @property
    def is_active(self):
        return timezone.now().date() >= self.due_date

    @property
    def is_overdue(self):
        return timezone.now().date() > self.due_date and self.balance > 0

    def save(self, *args, **kwargs):
        self.paid = (self.balance <= Decimal('0.00'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Inst #{self.id} | Loan {self.loan_id} | Due {self.due_date} | Bal {self.balance}"
# =========================================================
# 3. TRANSACTION ENGINE LOGS, REVERSALS & DOUBLE-ENTRY
# =========================================================

# finance/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from members.models import Member  # Import from members app

class Transaction(models.Model):
    """Individual system action tracking financial entry modifications."""
    T_TYPES = (
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('disbursement', 'Loan Disbursement'),
        ('repayment', 'Loan Repayment'),
        ('penalty', 'Penalty'),
        ('reversal', 'Reversal'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    )
    
    member = models.ForeignKey(
        Member,  # Now Member is imported
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    
    loan = models.ForeignKey(
        'Loan', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='transactions'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    type = models.CharField(max_length=20, choices=T_TYPES, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    reference = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    is_reversed = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transactions_created'
    )
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions_reversed'
    )
    reversal_reason = models.TextField(blank=True, null=True)
    reversal_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.type.upper()} - {self.amount} ({self.reference})"
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['member', 'type']),
            models.Index(fields=['reference']),
            models.Index(fields=['timestamp']),
        ]

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
        if self.pk:
            return super().save(*args, **kwargs)

        if not self.receipt_number:
            self.receipt_number = f"RCP-{random.randint(10000,99999)}"

        with transaction.atomic():

            loan_obj = Loan.objects.select_for_update().get(pk=self.loan.pk)

            try:
                savings = SavingsAccount.objects.select_for_update().get(
                    member=loan_obj.member
                )
            except SavingsAccount.DoesNotExist:
                raise ValidationError(
                    "Member does not possess an active savings pocket."
                )

            repayment_pool = Decimal(str(self.amount_paid))

            if savings.balance < repayment_pool:
                raise ValidationError(
                    f"Insufficient funds. Balance: UGX {savings.balance:,.0f}"
                )

            # --------------------------------------------------
            # 1. Deduct savings
            # --------------------------------------------------
            savings.balance -= repayment_pool
            savings.save(update_fields=["balance"])

            allocated_interest = Decimal("0.00")
            allocated_principal = Decimal("0.00")
            allocated_penalty = Decimal("0.00")

            # --------------------------------------------------
            # 2. Waterfall
            # Oldest installment first
            # Penalty -> Interest -> Principal
            # --------------------------------------------------

            installments = (
                loan_obj.installments
                .select_for_update()
                .filter(paid=False)
                .order_by("due_date", "id")
            )

            for inst in installments:

                if repayment_pool <= 0:
                    break

                penalty_remaining = max(
                    Decimal("0.00"),
                    inst.penalty_amount - inst.penalty_paid
                )

                interest_remaining = max(
                    Decimal("0.00"),
                    inst.interest_portion - inst.interest_paid
                )

                principal_remaining = max(
                    Decimal("0.00"),
                    inst.principal_portion - inst.principal_paid
                )

                # -----------------------------------------
                # Penalty
                # -----------------------------------------
                if penalty_remaining > 0 and repayment_pool > 0:

                    pay = min(repayment_pool, penalty_remaining)

                    inst.penalty_paid += pay
                    repayment_pool -= pay
                    allocated_penalty += pay

                    penalty_remaining -= pay

                # -----------------------------------------
                # Interest
                # -----------------------------------------
                if interest_remaining > 0 and repayment_pool > 0:

                    pay = min(repayment_pool, interest_remaining)

                    inst.interest_paid += pay
                    repayment_pool -= pay
                    allocated_interest += pay

                    interest_remaining -= pay

                # -----------------------------------------
                # Principal
                # -----------------------------------------
                if principal_remaining > 0 and repayment_pool > 0:

                    pay = min(repayment_pool, principal_remaining)

                    inst.principal_paid += pay
                    repayment_pool -= pay
                    allocated_principal += pay

                    principal_remaining -= pay

                remaining_total = (
                    (inst.penalty_amount - inst.penalty_paid)
                    + (inst.interest_portion - inst.interest_paid)
                    + (inst.principal_portion - inst.principal_paid)
                )

                inst.amount_remaining = max(
                    Decimal("0.00"),
                    remaining_total
                )

                if inst.amount_remaining <= Decimal("0.00"):
                    inst.paid = True

                inst.save()

            # --------------------------------------------------
            # 3. Update Loan Balances
            # --------------------------------------------------

            loan_obj.interest_balance = max(
                Decimal("0.00"),
                loan_obj.interest_balance - allocated_interest
            )

            loan_obj.principal_balance = max(
                Decimal("0.00"),
                loan_obj.principal_balance - allocated_principal
            )

            # --------------------------------------------------
            # 4. Loan Status
            # --------------------------------------------------

            today = timezone.now().date()

            overdue_exists = loan_obj.installments.filter(
                due_date__lt=today,
                paid=False
            ).exists()

            if overdue_exists:
                loan_obj.status = "arrears"
            elif loan_obj.status != "closed":
                loan_obj.status = "approved"

            if (
                loan_obj.principal_balance <= 0 and
                loan_obj.interest_balance <= 0
            ):
                loan_obj.status = "closed"
                loan_obj.is_active = False

            loan_obj.save()

            # --------------------------------------------------
            # 5. Transaction Log
            # --------------------------------------------------

            tx_log = Transaction.objects.create(
                member=loan_obj.member,
                amount=self.amount_paid,
                type="repayment",
                reference=f"LOAN-PYMT-{self.receipt_number}",
                loan=loan_obj,
                timestamp=self.date_paid
            )

            # --------------------------------------------------
            # 6. Ledger Entries
            # --------------------------------------------------

            AccountingEngine.post_ledger_entry(
                account_code="2000",
                description=f"Savings withdrawal for Loan Repayment {loan_obj.loan_reference}",
                reference=self.receipt_number,
                debit=self.amount_paid,
                credit=Decimal("0.00"),
                transaction_obj=tx_log,
                date_context=self.date_paid.date()
            )

            if allocated_principal > 0:

                AccountingEngine.post_ledger_entry(
                    account_code="1200",
                    description=f"Principal Recovery on Loan {loan_obj.loan_reference}",
                    reference=self.receipt_number,
                    debit=Decimal("0.00"),
                    credit=allocated_principal,
                    transaction_obj=tx_log,
                    date_context=self.date_paid.date()
                )

            if allocated_interest > 0:

                AccountingEngine.post_ledger_entry(
                    account_code="2100",
                    description=f"Interest Income Recognized on Loan {loan_obj.loan_reference}",
                    reference=self.receipt_number,
                    debit=Decimal("0.00"),
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


from datetime import timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.db import transaction

def generate_schedule(loan):
    """
    Generates installments for the loan based on repayment_frequency and term_value.
    Interest is split equally across all installments.
    """
    if loan.installments.exists():
        return  # prevent duplicate schedules

    frequency = loan.repayment_frequency
    plan_length = loan.term_value

    if plan_length <= 0:
        return

    principal_total = loan.principal_amount
    total_interest = loan.total_payable - principal_total

    principal_per = (principal_total / Decimal(plan_length)).quantize(Decimal('0.01'))
    interest_per = (total_interest / Decimal(plan_length)).quantize(Decimal('0.01'))

    remaining_principal = principal_total
    current_date = loan.start_date

    with transaction.atomic():
        for i in range(plan_length):
            # Date calculation
            if frequency == 'daily':
                current_date += timedelta(days=1)
            elif frequency == 'weekly':
                current_date += timedelta(weeks=1)
            elif frequency == 'monthly':
                current_date += relativedelta(months=1)
            elif frequency == 'manual':
                raise ValueError("Manual loans require explicit installment creation")
            else:
                raise ValueError(f"Unknown frequency: {frequency}")

            # Last installment absorbs rounding errors
            principal_portion = remaining_principal if i == plan_length - 1 else principal_per

            Installment.objects.create(
                loan=loan,
                due_date=current_date,
                principal_portion=principal_portion,
                interest_portion=interest_per,
            )

            remaining_principal -= principal_portion

    # Re-save loan to update any dependent fields (optional)
    loan.save()

from decimal import Decimal
from django.utils import timezone

def calculate_penalty(installment):
    """
    Calculates penalty based on loan rules + overdue status.
    """

    loan = installment.loan
    rule = getattr(loan, "penalty_rule", None)

    if not rule:
        return Decimal("0.00")

    today = timezone.now().date()

    if installment.due_date >= today:
        return Decimal("0.00")

    days_overdue = (today - installment.due_date).days

    # Apply grace period
    days_overdue -= rule.grace_period_days

    if days_overdue <= 0:
        return Decimal("0.00")

    penalty = Decimal("0.00")

    # -------------------------
    # FIXED PENALTY
    # -------------------------
    if rule.penalty_type == "fixed":
        penalty = rule.fixed_amount

    # -------------------------
    # PERCENTAGE PENALTY
    # -------------------------
    elif rule.penalty_type == "percentage":
        penalty = (installment.balance * rule.percentage_rate / Decimal("100"))

    # -------------------------
    # DAILY PENALTY
    # -------------------------
    elif rule.penalty_type == "daily":
        penalty = rule.daily_penalty_amount * days_overdue

    # -------------------------
    # CAP CHECK
    # -------------------------
    if rule.max_penalty_cap > 0:
        penalty = min(penalty, rule.max_penalty_cap)

    return penalty.quantize(Decimal("0.01"))
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

class LoanPenaltyRule(models.Model):
    """Defines penalty rules per loan – flexible and auditable."""
    PENALTY_TYPE = (
        ('fixed', 'Fixed amount per period'),
        ('percentage', 'Percentage of overdue amount per period'),
        ('daily_flat', 'Daily flat amount'),
        ('daily_percentage', 'Daily percentage of overdue amount'),
    )
    PERIOD_CHOICES = (
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
    )

    loan = models.OneToOneField('Loan', on_delete=models.CASCADE, related_name='penalty_rule')

    penalty_type = models.CharField(max_length=20, choices=PENALTY_TYPE, default='percentage')
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default='monthly',
                              help_text="How often the penalty is applied (e.g., monthly for percentage)")

    fixed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       help_text="Used for fixed or daily_flat")
    percentage_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                          help_text="Percentage rate (e.g., 5 for 5%)")

    grace_period_days = models.PositiveIntegerField(default=0,
                                                    help_text="Days after due date before penalty starts")
    max_penalty_cap = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                          help_text="Maximum penalty per period (0 = unlimited)")

    # Whether to apply penalty on existing penalty (compound)
    compound = models.BooleanField(default=False,
                                   help_text="If True, penalty is calculated on principal+interest+previous penalty")

    # For manual overrides – if set, this rule is ignored and the fixed override amount is used
    override_penalty = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                           help_text="If set, this exact amount is used as penalty (manual override)")
    override_applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                            null=True, blank=True, related_name='penalty_overrides')
    override_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Penalty Rule for {self.loan.loan_reference}"

    def get_penalty_for_installment(self, installment):
        """
        Calculate penalty for a single installment based on this rule.
        Returns Decimal.
        """
        today = timezone.now().date()
        due_date = installment.due_date
        if due_date >= today:
            return Decimal('0.00')

        # Days overdue after grace
        days_overdue = (today - due_date).days - self.grace_period_days
        if days_overdue <= 0:
            return Decimal('0.00')

        # Base overdue amount – the amount that is overdue (principal + interest)
        overdue_amount = installment.principal_portion + installment.interest_portion
        if self.compound:
            overdue_amount += installment.penalty_amount  # include existing penalty if compounding

        # Number of periods (for monthly/weekly/daily)
        if self.period == 'daily':
            periods = days_overdue
        elif self.period == 'weekly':
            periods = days_overdue // 7
        else:  # monthly
            periods = days_overdue // 30  # approximation (or you can use dateutil.relativedelta for exact months)

        if periods <= 0:
            return Decimal('0.00')

        penalty = Decimal('0.00')

        if self.penalty_type == 'fixed':
            penalty = self.fixed_amount * periods
        elif self.penalty_type == 'percentage':
            penalty = overdue_amount * (self.percentage_rate / Decimal('100')) * periods
        elif self.penalty_type == 'daily_flat':
            penalty = self.fixed_amount * days_overdue  # daily flat, period is effectively daily
        elif self.penalty_type == 'daily_percentage':
            penalty = overdue_amount * (self.percentage_rate / Decimal('100')) * days_overdue

        # Apply cap per period (if any)
        if self.max_penalty_cap > 0:
            penalty = min(penalty, self.max_penalty_cap * periods)  # cap per period multiplied by periods

        return penalty.quantize(Decimal('0.01'))



# finance/models.py
from django.db import models
from django.conf import settings

class ManualPenalty(models.Model):
    loan = models.ForeignKey('Loan', on_delete=models.CASCADE, related_name='manual_penalties')
    installment = models.ForeignKey(
        'Installment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manual_penalties'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()

    # ✅ Unique related_name for each to avoid clash
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='manual_penalties_applied'   # <-- unique
    )
    applied_date = models.DateTimeField(auto_now_add=True)

    is_waived = models.BooleanField(default=False)

    waived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manual_penalties_waived'    # <-- unique
    )
    waived_date = models.DateTimeField(null=True, blank=True)
    waiver_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"ManualPenalty #{self.id} on {self.loan.loan_reference}"