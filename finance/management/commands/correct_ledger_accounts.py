# correct_ledger_accounts.py
from django.db import transaction
from django.db.models import Sum
from finance.models import GeneralLedger, ChartOfAccount

# Mapping from wrong account codes to correct leaf accounts
ACCOUNT_MAPPING = {
    '1000': '1120',   # Assets parent → Cash on Hand
    '2000': '2100',   # Liabilities parent → Member Savings
    '1200': '1210',   # Loan Portfolio parent → Loans to Members
    # If you also have entries on 2100 that are interest income, map those to 4100?
    # We'll handle that separately if needed.
}

def recompute_balance_for_account(account_code):
    """Recalculate running balance for all entries of a given account in chronological order."""
    account = ChartOfAccount.objects.get(code=account_code)
    entries = GeneralLedger.objects.filter(account=account).order_by('date', 'id')
    running_balance = 0
    for entry in entries:
        # Determine sign based on account type
        if account.account_type in ['asset', 'expense']:
            running_balance += entry.debit - entry.credit
        else:  # liability, income, equity
            running_balance += entry.credit - entry.debit
        # Update the balance field
        GeneralLedger.objects.filter(pk=entry.pk).update(balance=running_balance)

def correct_entries():
    with transaction.atomic():
        for old_code, new_code in ACCOUNT_MAPPING.items():
            try:
                old_account = ChartOfAccount.objects.get(code=old_code)
                new_account = ChartOfAccount.objects.get(code=new_code)
            except ChartOfAccount.DoesNotExist:
                print(f"⚠️ Account {old_code} or {new_code} not found. Skipping.")
                continue

            # Update all ledger entries from old_account to new_account
            updated_count = GeneralLedger.objects.filter(account=old_account).update(account=new_account)
            print(f"🔄 Moved {updated_count} entries from {old_code} to {new_code}")

    # After moving, recompute balances for each new account
    for new_code in ACCOUNT_MAPPING.values():
        try:
            recompute_balance_for_account(new_code)
            print(f"✅ Recalculated balance for account {new_code}")
        except ChartOfAccount.DoesNotExist:
            print(f"⚠️ Account {new_code} not found, can't recompute.")

    # Also recompute any other accounts that might have been affected (e.g., if entries were moved out)
    for old_code in ACCOUNT_MAPPING.keys():
        try:
            recompute_balance_for_account(old_code)
            print(f"✅ Recalculated balance for account {old_code} (should now be zero)")
        except ChartOfAccount.DoesNotExist:
            pass

if __name__ == "__main__":
    print("🚀 Starting ledger correction...")
    correct_entries()
    print("✅ Correction complete.")