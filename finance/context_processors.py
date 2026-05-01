from django.db.models import Sum
from .models import Loan, SMSConfig, SavingsAccount

def sacco_stats(request):
    """
    Context processor for SACCO statistics shown in the top stat bar.
    Updated to support split-balance schema (Principal + Interest).
    """
    if not request.user.is_authenticated:
        return {}

    # === Arrears / Portfolio (Fixed for Split Balance) ===
    # We sum both new fields to replace the old 'balance' sum
    loan_balances = Loan.objects.filter(
        status='approved'
    ).aggregate(
        p_bal=Sum('principal_balance'),
        i_bal=Sum('interest_balance')
    )
    
    total_arrears = (loan_balances['p_bal'] or 0) + (loan_balances['i_bal'] or 0)

    # === Interest Profit (YTD) ===
    total_principal = Loan.objects.filter(
        status='approved'
    ).aggregate(Sum('principal_amount'))['principal_amount__sum'] or 0

    total_payable = Loan.objects.filter(
        status='approved'
    ).aggregate(Sum('total_payable'))['total_payable__sum'] or 0

    total_profit = total_payable - total_principal

    # === Active Loans ===
    active_loans = Loan.objects.filter(status='approved').count()

    # === Global Savings (Optional but recommended) ===
    total_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or 0

    # === SMS Credits ===
    try:
        sms_conf, created = SMSConfig.objects.get_or_create(
            id=1, # Explicit ID often helps with get_or_create in singleton configs
            defaults={
                'balance': 0.00,
                'cost_per_sms': 100.00
            }
        )
        sms_credits = sms_conf.remaining_messages
    except Exception as e:
        sms_credits = 0

    return {
        'total_arrears': total_arrears,
        'total_profit': total_profit,
        'sms_credits': sms_credits,
        'active_loans': active_loans,
        'total_savings': total_savings,
    }