from django.db import transaction as db_transaction
from .models import Transaction, LedgerEntry, ChartOfAccount

def process_transaction_to_ledger(member_tx):
    """
    Captures Member Transactions and maps them to the Chart of Accounts.
    This ensures your Inflows/Outflows are always in sync with Member actions.
    """
    try:
        with db_transaction.atomic():
            # 1. Get the Core Cash Account (The 'Vault')
            cash_account = ChartOfAccount.objects.get(code='1001')
            
            # 2. Logic mapping based on your T_TYPES
            if member_tx.type == 'deposit':
                # INFLOW: Cash increases (Debit), Savings Liability increases (Credit)
                target_account = ChartOfAccount.objects.get(code='2001') # Member Savings
                
                LedgerEntry.objects.create(
                    member_transaction=member_tx,
                    account=cash_account,
                    debit=member_tx.amount,
                    description=f"Cash Deposit - {member_tx.member.user.get_full_name()}"
                )
                LedgerEntry.objects.create(
                    member_transaction=member_tx,
                    account=target_account,
                    credit=member_tx.amount,
                    description=f"Liability Increase - Savings Deposit"
                )

            elif member_tx.type == 'withdrawal':
                # OUTFLOW: Cash decreases (Credit), Savings Liability decreases (Debit)
                target_account = ChartOfAccount.objects.get(code='2001')
                
                LedgerEntry.objects.create(
                    member_transaction=member_tx,
                    account=cash_account,
                    credit=member_tx.amount,
                    description=f"Cash Withdrawal - {member_tx.member.user.get_full_name()}"
                )
                LedgerEntry.objects.create(
                    member_transaction=member_tx,
                    account=target_account,
                    debit=member_tx.amount,
                    description=f"Liability Decrease - Withdrawal"
                )

            elif member_tx.type == 'repayment':
                # INFLOW: Cash increases (Debit), Loan Asset decreases (Credit)
                target_account = ChartOfAccount.objects.get(code='1002') # Loan Portfolio
                
                LedgerEntry.objects.create(
                    member_transaction=member_tx,
                    account=cash_account,
                    debit=member_tx.amount,
                    description=f"Loan Repayment - {member_tx.member.user.get_full_name()}"
                )
                LedgerEntry.objects.create(
                    member_transaction=member_tx,
                    account=target_account,
                    credit=member_tx.amount,
                    description=f"Asset Decrease - Loan Principal Paid"
                )

            elif member_tx.type == 'disbursement':
                # OUTFLOW: Cash decreases (Credit), Loan Asset increases (Debit)
                target_account = ChartOfAccount.objects.get(code='1002')
                
                LedgerEntry.objects.create(
                    member_transaction=member_tx,
                    account=cash_account,
                    credit=member_tx.amount,
                    description=f"Loan Disbursement - Ref: {member_tx.reference}"
                )
                LedgerEntry.objects.create(
                    member_transaction=member_tx,
                    account=target_account,
                    debit=member_tx.amount,
                    description=f"Asset Increase - New Loan Issued"
                )

    except ChartOfAccount.DoesNotExist as e:
        print(f"Error: Ensure COA Codes are setup. {e}")




from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Transaction)
def trigger_accounting_update(sender, instance, created, **kwargs):
    if created:
        process_transaction_to_ledger(instance)