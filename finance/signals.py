from django.db import transaction as db_transaction
from .models import Transaction, GeneralLedger, ChartOfAccount

def process_transaction_to_ledger(member_tx):
    """
    Captures Member Transactions and maps them to the Chart of Accounts.
    """
    try:
        with db_transaction.atomic():
            cash_account = ChartOfAccount.objects.get(code='1001')
            user_name = member_tx.created_by.get_full_name() if member_tx.created_by else 'System'
            
            if member_tx.type == 'deposit':
                target_account = ChartOfAccount.objects.get(code='2001')
                GeneralLedger.objects.create(
                    transaction=member_tx,          # ✅ CORRECT field name
                    account=cash_account,
                    debit=member_tx.amount,
                    description=f"Cash Deposit - {user_name}"
                )
                GeneralLedger.objects.create(
                    transaction=member_tx,          # ✅ CORRECT field name
                    account=target_account,
                    credit=member_tx.amount,
                    description="Liability Increase - Savings Deposit"
                )

            elif member_tx.type == 'withdrawal':
                target_account = ChartOfAccount.objects.get(code='2001')
                GeneralLedger.objects.create(
                    transaction=member_tx,
                    account=cash_account,
                    credit=member_tx.amount,
                    description=f"Cash Withdrawal - {user_name}"
                )
                GeneralLedger.objects.create(
                    transaction=member_tx,
                    account=target_account,
                    debit=member_tx.amount,
                    description="Liability Decrease - Withdrawal"
                )

            elif member_tx.type == 'repayment':
                target_account = ChartOfAccount.objects.get(code='1002')
                GeneralLedger.objects.create(
                    transaction=member_tx,
                    account=cash_account,
                    debit=member_tx.amount,
                    description=f"Loan Repayment - {user_name}"
                )
                GeneralLedger.objects.create(
                    transaction=member_tx,
                    account=target_account,
                    credit=member_tx.amount,
                    description="Asset Decrease - Loan Principal Paid"
                )

            elif member_tx.type == 'disbursement':
                target_account = ChartOfAccount.objects.get(code='1002')
                GeneralLedger.objects.create(
                    transaction=member_tx,
                    account=cash_account,
                    credit=member_tx.amount,
                    description=f"Loan Disbursement - Ref: {member_tx.reference}"
                )
                GeneralLedger.objects.create(
                    transaction=member_tx,
                    account=target_account,
                    debit=member_tx.amount,
                    description="Asset Increase - New Loan Issued"
                )

    except ChartOfAccount.DoesNotExist as e:
        print(f"Error: Ensure COA Codes are setup. {e}") 
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Transaction)
def trigger_accounting_update(sender, instance, created, **kwargs):
    if created:
        process_transaction_to_ledger(instance)