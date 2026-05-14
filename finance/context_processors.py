from django.db.models import Sum
from .models import Loan, SMSConfig, SavingsAccount, GeneralLedger

def sacco_stats(request):
    if not request.user.is_authenticated:
        return {}

    is_admin = request.user.groups.filter(name='Admin').exists()
    if not (is_admin or request.user.is_superuser):
        return {}

    # 1. Total Arrears (Money currently out with members)
    loan_balances = Loan.objects.filter(status='approved').aggregate(
        p_bal=Sum('principal_balance'),
        i_bal=Sum('interest_balance')
    )
    total_arrears = (loan_balances['p_bal'] or 0) + (loan_balances['i_bal'] or 0)

    # 2. Total Earnings (Expected Interest Profit)
    loan_sums = Loan.objects.filter(status='approved').aggregate(
        principal=Sum('principal_amount'),
        payable=Sum('total_payable')
    )
    total_profit = (loan_sums['payable'] or 0) - (loan_sums['principal'] or 0)

    # 3. Total Savings (Liability to the SACCO)
    total_savings = SavingsAccount.objects.aggregate(total=Sum('balance'))['total'] or 0

    # 4. CALCULATING CASH POSITION
    # Method A: Balance Sheet Approach
    # Cash = (Total Savings + Total Interest Collected) - (Total Principal Out)
    # If you have a General Ledger, it's better to sum 'Cash' type accounts:
    
    cash_on_hand = GeneralLedger.objects.filter(
        account__account_type='asset', 
        account__name__icontains='Cash' # Or a specific 'Cash at Hand' category
    ).aggregate(
        balance=Sum('debit') - Sum('credit')
    )['balance'] or 0

    # If you don't use the Ledger for this yet, use a derived calculation:
    # net_cash = total_savings - total_arrears (Simplified)
    net_cash = cash_on_hand if cash_on_hand > 0 else (total_savings - (loan_balances['p_bal'] or 0))

    # 5. SMS Credits
    try:
        sms_conf = SMSConfig.objects.first()
        sms_credits = sms_conf.remaining_messages
    except:
        sms_credits = 0

    return {
        'total_arrears': total_arrears,
        'total_profit': total_profit,
        'net_cash': net_cash,
        'sms_credits': sms_credits,
        'active_loans': Loan.objects.filter(status='approved').count(),
        'total_savings': total_savings,
        'show_stat_bar': True,
    }