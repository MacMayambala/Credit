from django.db import models, transaction
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.conf import settings
from members.models import Member

class SavingsAccount(models.Model):
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='savings')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.member.first_name} - Savings: {self.balance}"
from django.db import models
from django.utils import timezone
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.db import models
from django.utils import timezone
from decimal import Decimal

# In finance/models.py
# finance/models.py

class SystemSetting(models.Model):
    """Global configuration for the SACCO system."""
    enable_back_dating = models.BooleanField(
        default=False, 
        help_text="If enabled, Admins can manually set the date for deposits and repayments."
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

from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.models import User
from members.models import Member


class Loan(models.Model):
    # ==================== BASIC LOAN INFO ====================
    member = models.ForeignKey(
        Member, 
        on_delete=models.CASCADE, 
        related_name='loans'
    )
    officer = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='loans_disbursed'
    )

    loan_reference = models.CharField(
        max_length=20, 
        unique=True, 
        null=True, 
        blank=True,
        help_text="Unique alphanumeric loan reference (e.g., LN-ABC1234567)"
    )

    # ==================== LOAN FINANCIAL DETAILS ====================
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Rate in percentage (e.g., 12.5)")
    period_months = models.IntegerField()

    start_date = models.DateField(default=timezone.now)
    disbursed_date = models.DateField(null=True, blank=True)

    # Financial Calculations (auto-calculated)
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    principal_balance = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    interest_balance = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)

    # ==================== LOAN PRODUCT & TYPE ====================
    PRODUCT_CHOICES = [
        ('personal', 'Personal Loan'),
        ('business', 'Business Loan'),
        ('salary', 'Salary Advance'),
        ('group', 'Group Loan'),
        ('emergency', 'Emergency Loan'),
        ('asset', 'Asset Finance'),
    ]

    product_type = models.CharField(
        max_length=20, 
        choices=PRODUCT_CHOICES, 
        default='personal',
        verbose_name="Loan Product"
    )

    purpose = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Loan Purpose / Description"
    )

    # ==================== GUARANTORS ====================
   # Guarantor 1
    guarantor_1_name = models.CharField(
        max_length=255, 
        verbose_name="Guarantor 1 Name"
    )
    guarantor_1_phone = models.CharField(
        max_length=20, 
        verbose_name="Guarantor 1 Phone"
    )

    # Guarantor 2 (Optional)
    guarantor_2_name = models.CharField(
        max_length=255, 
        null=True, 
        blank=True, 
        verbose_name="Guarantor 2 Name"
    )
    guarantor_2_phone = models.CharField(
        max_length=20, 
        null=True, 
        blank=True, 
        verbose_name="Guarantor 2 Phone"
    )

    # ==================== COLLATERAL ====================
    collateral_type = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name="Collateral Type (e.g., Land, Vehicle, House)"
    )
    collateral_value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Estimated Collateral Value"
    )
    collateral_description = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Collateral Details"
    )

    # ==================== LOCATION & CONTACT ====================
    location = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name="Business / Physical Location"
    )
    contact_person = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name="Contact Person (if different from member)"
    )
    contact_phone = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        verbose_name="Contact Phone Number"
    )

    # ==================== STATUS & DATES ====================
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('arrears', 'In Arrears'),  # <--- Add this
        ('rejected', 'Rejected'),
        ('closed', 'Closed'),
        ('defaulted', 'Defaulted'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=False)

    # ==================== METADATA ====================
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
        """Total outstanding balance"""
        return (self.principal_balance or 0) + (self.interest_balance or 0)


from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
import random

# Ensure your Member model in members/models.py remains as is, 
# but update these in finance/models.py

class Installment(models.Model):
    loan = models.ForeignKey('Loan', on_delete=models.CASCADE, related_name='installments')
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

class Transaction(models.Model):
    T_TYPES = (
        ('deposit', 'Deposit'), 
        ('withdrawal', 'Withdrawal'),
        ('disbursement', 'Loan Disbursement'),
        ('repayment', 'Loan Repayment'),
        ('penalty', 'Penalty')  
    )
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    # ADD THIS FIELD:
    loan = models.ForeignKey(Loan, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=20, choices=T_TYPES) # Keep as 'type'
    timestamp = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=100, blank=True, null=True) # Keep as 'reference'
    is_reversed = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='transactions_created'
    )

    
class TransactionReversal(models.Model):
    """Audit log for reversed transactions"""
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
# -------------------------
# CORE UTILITY FUNCTIONS
# -------------------------
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from decimal import Decimal
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
import calendar

from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.db import transaction
from .models import Installment, Loan, SavingsAccount, Transaction

def generate_schedule(loan):
    """Generates schedule and initializes amount_remaining."""
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
            amount_remaining=total_inst_due, # CRITICAL FIX
            paid=False
        )
        rem_p -= curr_p

    loan.principal_balance = principal_total
    loan.interest_balance = total_interest
    loan.save()

@transaction.atomic
def process_repayment(loan_id):
    """Automated engine used by the Management Command."""
    from .models import Loan, SavingsAccount, Transaction
    
    try:
        # select_for_update prevents two processes from charging the same loan at once
        loan = Loan.objects.select_for_update().get(id=loan_id, is_active=True)
        savings = SavingsAccount.objects.select_for_update().get(member=loan.member)
    except Exception:
        return False

    if savings.balance <= 0:
        return False

    # Get the oldest unpaid installment
    inst = loan.installments.filter(paid=False).order_by('due_date').first()
    
    if inst:
        # Determine how much we can actually take
        collectible = min(savings.balance, inst.amount_remaining)
        if collectible <= 0:
            return False

        # Apply to savings and loan balances
        savings.balance -= collectible
        savings.save()

        # Deduct from loan totals
        rem = collectible
        if loan.interest_balance > 0:
            int_cut = min(rem, loan.interest_balance)
            loan.interest_balance -= int_cut
            rem -= int_cut
        if rem > 0:
            loan.principal_balance -= rem

        # Update installment record
        inst.amount_remaining -= collectible
        if inst.amount_remaining <= 0:
            inst.paid = True
        inst.save()

        # Update loan status
        if loan.principal_balance <= 0 and loan.interest_balance <= 0:
            loan.status = 'closed'
            loan.is_active = False
        loan.save()

        Transaction.objects.create(
            member=loan.member,
            amount=collectible,
            type='repayment',
            reference=f"AUTO-SWEEP-{loan.loan_reference}"
        )
        return True
    return False
from decimal import Decimal
from django.db import transaction

@transaction.atomic
def process_repayment(loan_id):
    """
    Engine to deduct money from savings for the next due installment.
    Correctly handles database fields and manages 'arrears' status recovery.
    """
    try:
        # Select for update prevents race conditions
        # We now include 'arrears' in the allowed statuses to process repayments
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
    
    # 1. SKIP IF NO BALANCE
    if savings.balance <= 0:
        return False

    # 2. Target the oldest unpaid installment
    inst = loan.installments.filter(paid=False).order_by('due_date').first()
    
    if inst:
        # Access property total_due WITHOUT parentheses
        total_due = inst.total_due 
        
        # 3. DETERMINE COLLECTIBLE AMOUNT
        # Use amount_remaining to track what is actually left to pay on this row
        collectible_amount = min(savings.balance, inst.amount_remaining)

        # 4. EXECUTE DEDUCTION
        savings.balance -= collectible_amount
        savings.save()

        # Update actual DB fields
        # Repayment logic: Reduce interest first, then principal
        remaining_to_deduct = collectible_amount
        
        if loan.interest_balance > 0:
            interest_deduction = min(remaining_to_deduct, loan.interest_balance)
            loan.interest_balance -= interest_deduction
            remaining_to_deduct -= interest_deduction
            
        if remaining_to_deduct > 0:
            loan.principal_balance -= remaining_to_deduct

        # 5. INSTALLMENT LOGIC
        if collectible_amount >= inst.amount_remaining:
            inst.amount_remaining = 0
            inst.paid = True
        else:
            inst.amount_remaining -= collectible_amount
        
        inst.save()

        # 6. ARREARS RECOVERY LOGIC
        # After payment, check if there are still any unpaid installments due before today
        today = timezone.now().date()
        still_has_overdue = loan.installments.filter(
            due_date__lt=today, 
            paid=False
        ).exists()

        if not still_has_overdue and loan.status == 'arrears':
            loan.status = 'approved'
            # Note: This switches status back if the member has cleared their backlog

        # 7. FINALIZE LOAN STATUS
        # Check if both balances are cleared
        if loan.principal_balance <= 0 and loan.interest_balance <= 0:
            loan.principal_balance = 0
            loan.interest_balance = 0
            loan.is_active = False
            loan.status = 'closed'
        
        loan.save()

        # 8. RECORD TRANSACTION
        Transaction.objects.create(
            member=loan.member, 
            amount=collectible_amount, 
            type='repayment',
            reference=f"Loan Repayment: {loan.loan_reference}"
        )
        return True
            
    return False

import random
from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError

import random
from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError

import random
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
import random

class Repayment(models.Model):
    loan = models.ForeignKey('Loan', on_delete=models.CASCADE, related_name='repayments')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    date_paid = models.DateTimeField(default=timezone.now)
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # 1. Fetch Savings Account
            try:
                savings = self.loan.member.savings 
            except AttributeError:
                raise ValidationError("Member does not have an active savings account.")

            repayment_amount = Decimal(str(self.amount_paid))

            # 2. Check for sufficient funds
            if savings.balance < repayment_amount:
                raise ValidationError(f"Insufficient Savings: UGX {savings.balance:,.0f}")

            # 3. Deduct from Savings
            savings.balance -= repayment_amount
            savings.save()

            # 4. Update Loan Balances (Interest then Principal)
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

            # 5. WATERFALL LOGIC: Update Installments
            # Fetch unpaid installments ordered by the oldest due date
            unpaid_insts = loan_obj.installments.filter(paid=False).order_by('due_date')
            temp_payment_pool = repayment_amount
            
            for inst in unpaid_insts:
                if temp_payment_pool <= 0:
                    break # No more money to distribute
                
                payment_to_this_inst = min(temp_payment_pool, inst.amount_remaining)
                inst.amount_remaining -= payment_to_this_inst
                temp_payment_pool -= payment_to_this_inst
                
                # ONLY mark as paid if the installment balance is exactly 0
                if inst.amount_remaining <= 0:
                    inst.paid = True
                inst.save()

            # 6. Status Recovery (Move from 'arrears' back to 'approved' if cleared)
            today = timezone.now().date()
            overdue_exists = loan_obj.installments.filter(due_date__lt=today, paid=False).exists()
            if not overdue_exists and loan_obj.status == 'arrears':
                loan_obj.status = 'approved'

            # 7. Check for Loan Closure
            if loan_obj.principal_balance <= 0 and loan_obj.interest_balance <= 0:
                loan_obj.status = 'closed'
                loan_obj.is_active = False

            loan_obj.save()

            # 8. Finalize Receipt & Transaction Log
            if not self.receipt_number:
                self.receipt_number = f"RCP-{random.randint(10000, 99999)}"

            from .models import Transaction # Local import to avoid circularity if needed
            Transaction.objects.create(
                member=self.loan.member,
                amount=repayment_amount,
                type='repayment',
                reference=f"LOAN-PYMT-#{self.receipt_number}"
            )

            super().save(*args, **kwargs)

    def __str__(self):
        return f"Repayment {self.receipt_number} - {self.loan.member.last_name}"
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class SMSConfig(models.Model):
    
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)  # Raw UGX
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
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - UGX {self.amount}"
    
from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal

# ==================== CHART OF ACCOUNTS ====================
class ChartOfAccount(models.Model):
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



# ==================== GENERAL LEDGER ====================
class GeneralLedger(models.Model):
    """Double-entry bookkeeping"""
    date = models.DateField(default=timezone.now)
    
    account = models.ForeignKey(
        'ChartOfAccount', 
        on_delete=models.PROTECT,
        related_name='ledger_entries'
    )
    
    description = models.CharField(max_length=200)
    reference = models.CharField(max_length=100, blank=True, null=True)
    
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    transaction = models.ForeignKey(
        'Transaction', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='ledger_entries'      # ← Explicit related_name
    )

    class Meta:
        ordering = ['date', 'id']
        verbose_name = "General Ledger"
        verbose_name_plural = "General Ledger Entries"

    def __str__(self):
        return f"{self.date} - {self.account.name} | Dr:{self.debit} Cr:{self.credit}"

############################################ACCOUNTING SIGNALS############################################
from django.db import models
from django.conf import settings
from django.utils import timezone

# 1. The Categories for your Chart of Accounts
class AccountCategory(models.TextChoices):
    ASSET = 'ASSET', 'Asset (Items you own / Loans issued)'
    LIABILITY = 'LIABILITY', 'Liability (Member Savings / Debts)'
    EQUITY = 'EQUITY', 'Equity (Capital / Retained Earnings)'
    INCOME = 'INCOME', 'Income (Inflows from interest/fees)'
    EXPENSE = 'EXPENSE', 'Expense (Outflows for operations)'

# # 2. The Chart of Accounts (COA)
# class ChartOfAccount(models.Model):
#     code = models.CharField(max_length=10, unique=True)  # e.g., 1001, 2001, 4001
#     name = models.CharField(max_length=100)              # e.g., Cash at Hand, Member Savings
#     category = models.CharField(max_length=20, choices=AccountCategory.choices)
#     description = models.TextField(blank=True, null=True)
#     is_active = models.BooleanField(default=True)

#     def __str__(self):
#         return f"{self.code} - {self.name}"

#     class Meta:
#         ordering = ['code']

# 3. The General Ledger (The Inflow/Outflow record)
# class LedgerEntry(models.Model):
#     # Link to your EXISTING Transaction model (use 'app_name.Transaction')
#     # Change 'transactions' to whatever app your existing Transaction model is in
#     member_transaction = models.ForeignKey(
#         'finance.Transaction', 
#         on_delete=models.SET_NULL, 
#         null=True, 
#         blank=True,
#         related_name='ledger_entries'
#     )
    
#     account = models.ForeignKey(ChartOfAccount, on_delete=models.CASCADE, related_name='entries')
#     date = models.DateTimeField(default=timezone.now)
    
#     # Professional Accounting uses Debit/Credit columns
#     debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
#     credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
#     description = models.CharField(max_length=255)
#     reference = models.CharField(max_length=100, blank=True, null=True)
    
#     created_by = models.ForeignKey(
#         settings.AUTH_USER_MODEL, 
#         on_delete=models.SET_NULL, 
#         null=True
#     )

#     def __str__(self):
#         return f"{self.date.date()} - {self.account.name} ({self.debit}/{self.credit})"

#     class Meta:
#         verbose_name_plural = "Ledger Entries"
#         ordering = ['-date']

#     @property
#     def amount_display(self):
#         """Helper to show the absolute movement for simple lists"""
#         return self.debit if self.debit > 0 else self.credit