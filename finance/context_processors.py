# finance/context_processors.py

from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import Coalesce
from .models import Loan, SMSConfig, SavingsAccount, GeneralLedger, Company

def sacco_stats(request):
    if not request.user.is_authenticated:
        return {}

    active_loans_qs = Loan.objects.filter(
        status__in=['approved', 'arrears', 'defaulted'],
        is_active=True
    )
    ledger_totals = GeneralLedger.objects.filter(
        account__account_type='asset',
        account__name__icontains='cash'
    ).aggregate(
        debits=Coalesce(Sum('debit'), Decimal('0.00')),
        credits=Coalesce(Sum('credit'), Decimal('0.00')),
    )
    loan_balances = active_loans_qs.aggregate(
        principal_balance=Coalesce(Sum('principal_balance'), Decimal('0.00')),
        interest_balance=Coalesce(Sum('interest_balance'), Decimal('0.00')),
    )

    total_outstanding_loans = loan_balances['principal_balance'] + loan_balances['interest_balance']
    cash_on_hand = ledger_totals['debits'] - ledger_totals['credits']
    total_savings = SavingsAccount.objects.aggregate(
        total=Coalesce(Sum('balance'), Decimal('0.00'))
    )['total']

    sms_conf = SMSConfig.objects.first()
    sms_credits = sms_conf.remaining_messages if sms_conf else 0

    return {
        "show_stat_bar": True,
        "total_outstanding_loans": total_outstanding_loans,
        "expected_interest_income": loan_balances['interest_balance'],
        "total_savings": total_savings,
        "cash_on_hand": cash_on_hand,
        "sms_credits": sms_credits,
        "active_loans": active_loans_qs.count(),
        "arrears_loans": Loan.objects.filter(status='arrears').count(),
        "defaulted_loans": Loan.objects.filter(status='defaulted').count(),
        "liquidity_ratio": 0,
    }

def company_context(request):
    """
    Makes the Company instance available globally.
    """
    return {
        'company': Company.get_company()
    }