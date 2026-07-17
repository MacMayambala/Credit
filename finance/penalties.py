# finance/penalties.py
from decimal import Decimal
from django.utils import timezone

def calculate_penalty(installment):
    """
    Calculate the penalty for a single installment using its loan's penalty rule.
    Returns Decimal (quantized to 2 decimal places).
    """
    loan = installment.loan
    rule = getattr(loan, 'penalty_rule', None)
    if installment.penalty_waived:
        return Decimal('0.00')

    if not rule:
        # Fallback to loan's old fields (if any) – you can implement a fallback
        return Decimal('0.00')

    # If there is an override on the rule, use it directly
    if rule.override_penalty is not None:
        return rule.override_penalty

    return rule.get_penalty_for_installment(installment)