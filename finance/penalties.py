from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


def calculate_penalty(installment):
    """
    SACCO-grade penalty calculator.
    Fully configurable per loan agreement.
    """

    loan = installment.loan
    today = timezone.now().date()

    if installment.paid:
        return Decimal("0.00")

    if installment.due_date >= today:
        return Decimal("0.00")

    # =====================================
    # 1. GRACE PERIOD (FROM LOAN SETTINGS)
    # =====================================
    grace_days = getattr(loan, "penalty_grace_days", 0)
    penalty_start_date = installment.due_date + timedelta(days=grace_days)

    if today <= penalty_start_date:
        return Decimal("0.00")

    # =====================================
    # 2. OVERDUE DAYS
    # =====================================
    overdue_days = (today - penalty_start_date).days

    if overdue_days <= 0:
        return Decimal("0.00")

    # =====================================
    # 3. PENALTY TYPE LOGIC
    # =====================================

    # DEFAULT fallback values (safe)
    penalty_type = getattr(loan, "penalty_type", "daily_flat")
    rate = Decimal(str(getattr(loan, "penalty_rate", "1.0")))  # %
    flat_rate = Decimal(str(getattr(loan, "penalty_flat_amount", "0.00")))

    principal_balance = installment.principal_balance
    interest_balance = installment.interest_balance

    base_amount = principal_balance + interest_balance

    # =====================================
    # 4. CALCULATION MODES
    # =====================================

    # A. DAILY FLAT PENALTY
    if penalty_type == "daily_flat":
        return flat_rate * overdue_days

    # B. DAILY PERCENTAGE
    if penalty_type == "daily_percentage":
        return (base_amount * rate / Decimal("100")) * overdue_days

    # C. ONE-TIME FIXED PENALTY
    if penalty_type == "fixed":
        return flat_rate

    # D. COMPOUND DAILY (ADVANCED SACCO MODE)
    if penalty_type == "compound":
        daily = base_amount * (rate / Decimal("100"))
        return daily * overdue_days

    return Decimal("0.00")