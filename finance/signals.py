# finance/ledger.py
import threading
from decimal import Decimal
from django.db import transaction as db_transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Transaction, ChartOfAccount, AccountingEngine

# ============================================================
# Thread-local flag to disable ledger processing temporarily
# ============================================================
_ledger_processing_disabled = threading.local()

def disable_ledger_processing():
    _ledger_processing_disabled.active = True

def enable_ledger_processing():
    _ledger_processing_disabled.active = False

def is_ledger_processing_disabled():
    return getattr(_ledger_processing_disabled, 'active', False)


# ============================================================
# Core ledger processing – uses leaf accounts from your COA
# ============================================================
def process_transaction_to_ledger(member_tx):
    """
    Posts double-entry ledger entries for member transactions.
    Uses:
      - Cash on Hand (1120) – asset
      - Member Savings (2100) – liability
      - Loans to Members (1210) – asset
      - Interest Income (4100) – income
    """
    try:
        with db_transaction.atomic():
            cash_account = ChartOfAccount.objects.get(code='1120')      # Cash on Hand
            savings_account = ChartOfAccount.objects.get(code='2100')   # Member Savings (liability)
            loan_asset_account = ChartOfAccount.objects.get(code='1210') # Loans to Members (asset)
            user_name = member_tx.created_by.get_full_name() if member_tx.created_by else 'System'

            if member_tx.type == 'deposit':
                # Debit Cash, Credit Savings
                AccountingEngine.post_ledger_entry(
                    account_code=cash_account.code,
                    description=f"Cash Deposit - {user_name}",
                    reference=member_tx.reference,
                    debit=member_tx.amount,
                    credit=Decimal('0.00'),
                    transaction_obj=member_tx,
                    date_context=member_tx.timestamp.date()
                )
                AccountingEngine.post_ledger_entry(
                    account_code=savings_account.code,
                    description="Liability Increase - Savings Deposit",
                    reference=member_tx.reference,
                    debit=Decimal('0.00'),
                    credit=member_tx.amount,
                    transaction_obj=member_tx,
                    date_context=member_tx.timestamp.date()
                )

            elif member_tx.type == 'withdrawal':
                # Credit Cash, Debit Savings
                AccountingEngine.post_ledger_entry(
                    account_code=cash_account.code,
                    description=f"Cash Withdrawal - {user_name}",
                    reference=member_tx.reference,
                    debit=Decimal('0.00'),
                    credit=member_tx.amount,
                    transaction_obj=member_tx,
                    date_context=member_tx.timestamp.date()
                )
                AccountingEngine.post_ledger_entry(
                    account_code=savings_account.code,
                    description="Liability Decrease - Withdrawal",
                    reference=member_tx.reference,
                    debit=member_tx.amount,
                    credit=Decimal('0.00'),
                    transaction_obj=member_tx,
                    date_context=member_tx.timestamp.date()
                )

            elif member_tx.type == 'disbursement':
                # Credit Cash, Debit Loan Asset
                AccountingEngine.post_ledger_entry(
                    account_code=cash_account.code,
                    description=f"Loan Disbursement - Ref: {member_tx.reference}",
                    reference=member_tx.reference,
                    debit=Decimal('0.00'),
                    credit=member_tx.amount,
                    transaction_obj=member_tx,
                    date_context=member_tx.timestamp.date()
                )
                AccountingEngine.post_ledger_entry(
                    account_code=loan_asset_account.code,
                    description="Asset Increase - New Loan Issued",
                    reference=member_tx.reference,
                    debit=member_tx.amount,
                    credit=Decimal('0.00'),
                    transaction_obj=member_tx,
                    date_context=member_tx.timestamp.date()
                )

            elif member_tx.type == 'repayment':
                # This branch is used only if the signal is not disabled (e.g., manual cash repayment).
                # For savings-based repayments, Repayment.save() handles this directly.
                AccountingEngine.post_ledger_entry(
                    account_code=cash_account.code,
                    description=f"Loan Repayment (cash) - {user_name}",
                    reference=member_tx.reference,
                    debit=member_tx.amount,
                    credit=Decimal('0.00'),
                    transaction_obj=member_tx,
                    date_context=member_tx.timestamp.date()
                )
                AccountingEngine.post_ledger_entry(
                    account_code=loan_asset_account.code,
                    description="Asset Decrease - Loan Principal Paid",
                    reference=member_tx.reference,
                    debit=Decimal('0.00'),
                    credit=member_tx.amount,
                    transaction_obj=member_tx,
                    date_context=member_tx.timestamp.date()
                )

            # Add other types (reversal, journal, penalty) as needed

    except ChartOfAccount.DoesNotExist as e:
        print(f"Error: Ensure required accounts (1120, 2100, 1210, 4100) exist. {e}")
    except Exception as e:
        print(f"Error processing ledger: {e}")
        raise


# ============================================================
# Signal – respects the thread‑local flag
# ============================================================
@receiver(post_save, sender=Transaction)
def trigger_accounting_update(sender, instance, created, **kwargs):
    if created and not is_ledger_processing_disabled():
        process_transaction_to_ledger(instance)