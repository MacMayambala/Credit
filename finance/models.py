import random
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from members.models import Member

# =========================================================
# 1. CONFIGURATION & ACCOUNTING SYSTEM MODELS
# =========================================================

class SystemSetting(models.Model):
    """Global configuration for back-dating actions."""
    enable_back_dating = models.BooleanField(
        default=False, 
        help_text="If enabled, Manually set dates for deposits and repayments can be used."
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
        verbose_name = "Global Setting"
        verbose_name_plural = "Global Settings"

    def __str__(self):
        return "System Configuration"

    def save(self, *args, **kwargs):
        if not self.pk and GlobalSettings.objects.exists():
            return 
        super().save(*args, **kwargs)


class ChartOfAccount(models.Model):
    """Standard structural node for general ledger tracking."""
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

# finance/models.py
class SavingsAccount(models.Model):
    """Primary ledger balance account representing real capital for members."""
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='savings')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # We add a Python property here so you can still call .account_number 
    # anywhere in your code without storing it twice in the database!
    @property
    def account_number(self):
        return self.member.member_number

    def __str__(self):
        return f"{self.member.first_name} - Account: {self.account_number} | Balance: {self.balance}"

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

    guarantor_1_name = models.CharField(max_length=255, verbose_name="Guarantor 1 Name")
    guarantor_1_phone = models.CharField(max_length=20, verbose_name="Guarantor 1 Phone")
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

    def __str__(self):
        return f"{self.loan_reference or f'LN-{self.id}'} - {self.member.first_name} {self.member.last_name}"

    @property
    def balance(self):
        return (self.principal_balance or 0) + (self.interest_balance or 0)


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
    def total_due(self):
        return (self.principal_portion or 0) + (self.interest_portion or 0) + (self.penalty_amount or 0)

    def __str__(self):
        return f"Inst {self.id} - Due: {self.due_date} (Remaining: {self.amount_remaining})"


# =========================================================
# 3. TRANSACTION ENGINE LOGS & REVERSALS
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
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='transactions_created'
    )

    def __str__(self):
        return f"{self.type.upper()} - {self.amount} ({self.reference})"


class TransactionReversal(models.Model):
    """Audit footprint logging explicit transaction changes."""
    original_transaction = models.OneToOneField(
        Transaction, 
        on_delete=models.CASCADE, 
        related_name='reversal_details'
    )
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True
    )
    reversal_time = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()
    
    def __str__(self):
        return f"Reversal of {self.original_transaction.reference}"


class GeneralLedger(models.Model):
    """Double-entry general tracking node mapped directly to core transactions."""
    date = models.DateField(default=timezone.now)
    account = models.ForeignKey(
        ChartOfAccount, 
        on_delete=models.PROTECT,
        related_name='ledger_entries'
    )
    description = models.CharField(max_length=200)
    reference = models.CharField(max_length=100, blank=True, null=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    transaction = models.ForeignKey(
        Transaction, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='ledger_entries'
    )

    class Meta:
        ordering = ['date', 'id']
        verbose_name = "General Ledger"
        verbose_name_plural = "General Ledger Entries"

    def __str__(self):
        return f"{self.date} - {self.account.name} | Dr:{self.debit} Cr:{self.credit}"


class Repayment(models.Model):
    """Explicit wrapper around programmatic waterfall repayments."""
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    date_paid = models.DateTimeField(default=timezone.now)
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            try:
                savings = self.loan.member.savings 
            except AttributeError:
                raise ValidationError("Member does not have an active savings account.")

            repayment_amount = Decimal(str(self.amount_paid))

            if savings.balance < repayment_amount:
                raise ValidationError(f"Insufficient Savings: UGX {savings.balance:,.0f}")

            savings.balance -= repayment_amount
            savings.save()

            loan_obj = self.loan
            remaining_to_apply = repayment_amount

            if loan_obj.interest_balance > 0:
                interest_cut = min(remaining_to_apply, loan_obj.interest_balance)
                loan_obj.interest_balance -= interest_cut
                remaining_to_apply -= interest_cut

            if remaining_to_apply > 0:
                principal_cut = min(remaining_to_apply, loan_obj.principal_balance)
                loan_obj.principal_balance -= principal_cut
                remaining_to_apply -= principal_cut

            unpaid_insts = loan_obj.installments.filter(paid=False).order_by('due_date')
            temp_payment_pool = repayment_amount
            
            for inst in unpaid_insts:
                if temp_payment_pool <= 0:
                    break
                
                payment_to_this_inst = min(temp_payment_pool, inst.amount_remaining)
                inst.amount_remaining -= payment_to_this_inst
                temp_payment_pool -= payment_to_this_inst
                
                if inst.amount_remaining <= 0:
                    inst.paid = True
                inst.save()

            today = timezone.now().date()
            overdue_exists = loan_obj.installments.filter(due_date__lt=today, paid=False).exists()
            if not overdue_exists and loan_obj.status == 'arrears':
                loan_obj.status = 'approved'

            if loan_obj.principal_balance <= 0 and loan_obj.interest_balance <= 0:
                loan_obj.status = 'closed'
                loan_obj.is_active = False

            loan_obj.save()

            if not self.receipt_number:
                self.receipt_number = f"RCP-{random.randint(10000, 99999)}"

            Transaction.objects.create(
                member=self.loan.member,
                amount=repayment_amount,
                type='repayment',
                reference=f"LOAN-PYMT-#{self.receipt_number}",
                loan=self.loan
            )

            super().save(*args, **kwargs)

    def __str__(self):
        return f"Repayment {self.receipt_number} - {self.loan.member.last_name}"


# =========================================================
# 4. COMMUNICATIONS & NOTIFICATIONS METRICS
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


# =========================================================
# 5. AMORTIZATION & SWEEP CORE UTILITY FUNCTIONS
# =========================================================

def generate_schedule(loan):
    """Generates schedule installments and initializes amount_remaining."""
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


@transaction.atomic
def process_repayment(loan_id):
    """Engine to deduct money from savings for automated batch processing sweeps."""
    try:
        loan = Loan.objects.select_for_update().get(
            id=loan_id, 
            status__in=['approved', 'arrears'], 
            is_active=True
        )
    except Loan.DoesNotExist:
        return False

    try:
        savings = SavingsAccount.objects.select_for_update().get(member=loan.member)
    except SavingsAccount.DoesNotExist:
        return False
    
    if savings.balance <= 0:
        return False

    inst = loan.installments.filter(paid=False).order_by('due_date').first()
    
    if inst:
        collectible_amount = min(savings.balance, inst.amount_remaining)
        if collectible_amount <= 0:
            return False

        savings.balance -= collectible_amount
        savings.save()

        remaining_to_deduct = collectible_amount
        
        if loan.interest_balance > 0:
            interest_deduction = min(remaining_to_deduct, loan.interest_balance)
            loan.interest_balance -= interest_deduction
            remaining_to_deduct -= interest_deduction
            
        if remaining_to_deduct > 0:
            loan.principal_balance -= remaining_to_deduct

        if collectible_amount >= inst.amount_remaining:
            inst.amount_remaining = 0
            inst.paid = True
        else:
            inst.amount_remaining -= collectible_amount
        inst.save()

        today = timezone.now().date()
        still_has_overdue = loan.installments.filter(
            due_date__lt=today, 
            paid=False
        ).exists()

        if not still_has_overdue and loan.status == 'arrears':
            loan.status = 'approved'

        if loan.principal_balance <= 0 and loan.interest_balance <= 0:
            loan.principal_balance = 0
            loan.interest_balance = 0
            loan.is_active = False
            loan.status = 'closed'
        loan.save()

        Transaction.objects.create(
            member=loan.member, 
            amount=collectible_amount, 
            type='repayment',
            reference=f"Loan Repayment: {loan.loan_reference}",
            loan=loan
        )
        return True
            
    return False