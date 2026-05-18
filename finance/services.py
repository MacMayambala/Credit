import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from finance.models import (
    Loan, Installment, SavingsAccount, Transaction, 
    AutoRepaymentSetting, AutoRepaymentLog, DailyRepaymentSummary
)

logger = logging.getLogger(__name__)

class LoanRepaymentEngineService:
    """
    Rigorously parses active historical and current loan parameters, executing 
    isolated atomic wallet collections from associated savings accounts.
    """

    @classmethod
    def execute_bulk_auto_repayments(cls) -> dict:
        """
        Scans, isolates, and sequentially processes due installments against configurations.
        Optimized for large transaction loops.
        """
        start_time = timezone.now()
        summary_date = start_time.date()
        
        summary, _ = DailyRepaymentSummary.objects.get_or_create(date=summary_date)
        config = AutoRepaymentSetting.objects.first()
        
        if not config or not config.is_enabled:
            logger.info("Automated repayment batch engine skipped. (Disabled/Unconfigured)")
            return {"status": "skipped"}

        # Calculate grace period window cut-off
        due_threshold = summary_date - timedelta(days=config.grace_period_days)

        # Bulk fetch target processing pipeline elements minimizing database strain
        installments = Installment.objects.filter(
            paid=False,
            due_date__lte=due_threshold,
            loan__is_active=True,
            loan__status__in=['approved', 'arrears']
        ).select_related('loan', 'loan__member').order_by('due_date')

        for inst in installments:
            summary.total_processed += 1
            result = cls._process_single_installment_recovery(inst)
            
            # Aggregate Daily Metrics
            summary.total_recovered += result['recovered']
            if result['status'] == 'success':
                pass 
            elif result['status'] == 'partial':
                summary.partial_payments += 1
            elif result['status'] == 'failed':
                summary.failed_deductions += 1
            
            if result['loan_closed']:
                summary.closed_loans += 1

        end_time = timezone.now()
        summary.execution_duration_seconds = (end_time - start_time).total_seconds()
        summary.save()
        
        return {"status": "completed", "processed": summary.total_processed}

    @classmethod
    def _process_single_installment_recovery(cls, installment: Installment) -> dict:
        """
        Atomically executes collection operations on an individual loan installment record.
        """
        loan = installment.loan
        member = loan.member
        result = {'recovered': Decimal('0.00'), 'status': 'failed', 'loan_closed': False}

        try:
            with transaction.atomic():
                # Acquire explicit PostgreSQL row-level locks on relevant balances to block API race conditions
                savings_acc = SavingsAccount.objects.select_for_update().get(member=member)
                loan_locked = Loan.objects.select_for_update().get(pk=loan.pk)
                inst_locked = Installment.objects.select_for_update().get(pk=installment.pk)

                bal_before = savings_acc.balance
                due_amount = inst_locked.amount_remaining

                if bal_before <= 0:
                    cls._create_log(loan_locked, inst_locked, bal_before, due_amount, Decimal('0.00'), 'failed')
                    cls._trigger_notification(member, loan_locked, Decimal('0.00'), 'failed')
                    return result

                # Determine legal recovery boundaries (Partial vs Full)
                recovered_amount = min(bal_before, due_amount)
                result['recovered'] = recovered_amount

                # Wallet Balance Deduction
                savings_acc.balance -= recovered_amount
                savings_acc.save()

                # Process Financial Ledger Allocation: Interest Balance First, Then Principal Balance
                remaining_allocation = recovered_amount
                
                # 1. Deduct Interest
                interest_deduction = min(remaining_allocation, loan_locked.interest_balance)
                loan_locked.interest_balance -= interest_deduction
                inst_locked.interest_portion -= interest_deduction
                remaining_allocation -= interest_deduction

                # 2. Deduct Principal
                principal_deduction = min(remaining_allocation, loan_locked.principal_balance)
                loan_locked.principal_balance -= principal_deduction
                inst_locked.principal_portion -= principal_deduction
                remaining_allocation -= principal_deduction

                # Update operational targets
                inst_locked.amount_remaining -= recovered_amount
                if inst_locked.amount_remaining <= 0:
                    inst_locked.paid = True
                inst_locked.save()

                # Evaluate closure parameters
                if loan_locked.principal_balance <= 0 and loan_locked.interest_balance <= 0:
                    loan_locked.status = 'closed'
                    loan_locked.is_active = False
                    result['loan_closed'] = True
                elif loan_locked.status == 'arrears' and inst_locked.paid:
                    # Optional verification fallback check to restore normal status bounds
                    loan_locked.status = 'approved'
                
                loan_locked.save()

                # Inject System Audit Ledger Transaction entries
                ref_code = f"AUTO-REPAY-{loan_locked.loan_reference}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                Transaction.objects.create(
                    member=member,
                    loan=loan_locked,
                    amount=recovered_amount,
                    type='repayment',
                    reference=ref_code,
                    timestamp=timezone.now()
                )

                # Evaluate Execution Status Labels for Notifications
                final_status = 'success' if inst_locked.paid else 'partial'
                result['status'] = final_status

                cls._create_log(loan_locked, inst_locked, bal_before, due_amount, recovered_amount, final_status)
                cls._trigger_notification(member, loan_locked, recovered_amount, final_status)

        except Exception as system_exception:
            logger.error(f"Auto-Repayment Exception encountered on Installment {installment.id}: {str(system_exception)}")
            cls._create_log(loan, installment, Decimal('0.00'), Decimal('0.00'), Decimal('0.00'), 'error', str(system_exception))

        return result

    @classmethod
    def _create_log(cls, loan, inst, bal_before, attempted, recovered, status, err=""):
        AutoRepaymentLog.objects.create(
            loan=loan, installment=inst, savings_balance_before=bal_before,
            amount_attempted=attempted, amount_recovered=recovered, status=status, error_message=err
        )

    @classmethod
    def _trigger_notification(cls, member, loan, amount, outcome):
        """
        Placeholder dispatch hook interface matching architectural standards.
        Replace implementation details with your target notification gateway APIs (e.g., Africa's Talking).
        """
        message = f"Dear {member.first_name}, automated loan repayment "
        if outcome == 'success':
            message += f"succeeded. Shs {amount:,} deducted for loan {loan.loan_reference}."
        elif outcome == 'partial':
            message += f"partially succeeded. Shs {amount:,} deducted. Please clear outstanding amounts."
        else:
            message += f"failed due to insufficient savings balances on your account."
        
        logger.info(f"[SMS Notification Outbox Push] to {member.phone_number}: {message}")