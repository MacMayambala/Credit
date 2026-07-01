from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from finance.models import Loan, SavingsAccount, Transaction
from finance.services.schedule_engine import LoanScheduleEngine
from finance.penalties import calculate_penalty
from finance.models import AccountingEngine


class LoanLifecycleService:
    """
    Central orchestration engine for loan lifecycle management.
    Prevents duplication, race conditions, and invalid state transitions.
    """

    # =========================================================
    # 1. LOAN APPROVAL
    # =========================================================
    @staticmethod
    @transaction.atomic
    def approve_loan(loan: Loan, approved_by=None):
        """
        Approve loan and generate repayment schedule.
        """

        loan = Loan.objects.select_for_update().get(pk=loan.pk)

        if loan.status != "pending":
            return {"status": "skipped", "reason": "Loan already processed"}

        loan.status = "approved"
        loan.is_active = True
        loan.save(update_fields=["status", "is_active"])

        # Generate schedule
        schedule_result = LoanScheduleEngine.generate(loan)

        return {
            "status": "approved",
            "schedule": schedule_result
        }

    # =========================================================
    # 2. LOAN DISBURSEMENT
    # =========================================================
    @staticmethod
    @transaction.atomic
    def disburse_loan(loan: Loan, receipt_ref: str):
        """
        Release loan funds to member savings account.
        """

        loan = Loan.objects.select_for_update().get(pk=loan.pk)

        if loan.status != "approved":
            return {"status": "failed", "reason": "Loan not approved"}

        savings = SavingsAccount.objects.select_for_update().get(member=loan.member)

        amount = loan.principal_amount

        # Credit member savings (liability increases)
        savings.balance += amount
        savings.save()

        tx = Transaction.objects.create(
            member=loan.member,
            loan=loan,
            amount=amount,
            type="disbursement",
            reference=receipt_ref
        )

        # Ledger entries (double entry)
        AccountingEngine.post_ledger_entry(
            "1000", "Loan Disbursement", receipt_ref, amount, 0, tx
        )
        AccountingEngine.post_ledger_entry(
            "2000", "Loan Disbursement", receipt_ref, 0, amount, tx
        )

        loan.disbursed_date = timezone.now().date()
        loan.save(update_fields=["disbursed_date"])

        return {"status": "disbursed", "amount": str(amount)}

    # =========================================================
    # 3. LOAN CLOSURE CHECK
    # =========================================================
    @staticmethod
    @transaction.atomic
    def evaluate_loan_closure(loan: Loan):
        """
        Auto-close loan if fully settled.
        """

        loan = Loan.objects.select_for_update().get(pk=loan.pk)

        total_outstanding = loan.principal_balance + loan.interest_balance

        if total_outstanding > 0:
            return {"status": "active", "outstanding": str(total_outstanding)}

        loan.status = "closed"
        loan.is_active = False
        loan.save(update_fields=["status", "is_active"])

        return {"status": "closed"}
    