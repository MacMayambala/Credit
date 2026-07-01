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


#############################################################################################################################


import datetime
from decimal import Decimal
from django.db.models import Sum, Q, F, Count, Avg, Case, When, Value, DecimalField, fields, Max, IntegerField
from django.db.models.functions import Coalesce, Cast
from django.db.models.expressions import RawSQL
from django.utils import timezone
from .models import (
    Member, SavingsAccount, Loan, Installment, Transaction, Repayment, 
    GeneralLedger, ChartOfAccount, TransactionReversal, SMSTransaction
)

class FinancialReportingService:
    """
    Enterprise-grade ledger aggregation engine delivering IFRS-compliant analytics, 
    regulatory ratios, and financial metrics.
    """

    @staticmethod
    def get_interest_income_data(filters=None):
        filters = filters or {}
        queryset = Loan.objects.select_related('member', 'officer').all()

        # Apply standard operational filters
        if 'start_date' in filters and 'end_date' in filters:
            queryset = queryset.filter(disbursed_date__range=[filters['start_date'], filters['end_date']])
        if 'officer' in filters:
            queryset = queryset.filter(officer_id=filters['officer'])
        if 'product' in filters:
            queryset = queryset.filter(product_type=filters['product'])

        # Calculate using the explicit balances on your Loan Model
        report_data = queryset.annotate(
            interest_receivable=F('interest_balance'),
            principal_receivable=F('principal_balance'),
            total_remaining_balance=F('principal_balance') + F('interest_balance')
        )

        totals = report_data.aggregate(
            total_principal_remaining=Coalesce(Sum('principal_balance'), Value(0, output_field=DecimalField())),
            total_interest_remaining=Coalesce(Sum('interest_balance'), Value(0, output_field=DecimalField())),
            total_outstanding=Coalesce(Sum('principal_balance') + Sum('interest_balance'), Value(0, output_field=DecimalField()))
        )

        return {'records': report_data, 'totals': totals}

    @staticmethod
    def calculate_ifrs9_ecl():
        """
        Computes Expected Credit Losses (ECL) under the IFRS 9 multi-stage framework.
        Stage 1: Performing (<30 days overdue) -> 12-month ECL
        Stage 2: Underperforming (30-90 days overdue) -> Lifetime ECL
        Stage 3: Non-performing (>90 days overdue) -> Credit Impaired (Default)
        """
        today = timezone.now().date()
        today_str = today.strftime('%Y-%m-%d')
        
        active_loans = Loan.objects.filter(status__in=['approved', 'arrears'], is_active=True).annotate(
            days_overdue=Coalesce(
                Max(Case(
                    When(
                        installments__paid=False, 
                        installments__due_date__lt=today, 
                        then=Cast(
                            RawSQL("julianday(%s) - julianday(finance_installment.due_date)", [today_str]),
                            output_field=IntegerField()
                        )
                    ),
                    default=Value(0),
                    output_field=IntegerField()
                )),
                Value(0),
                output_field=IntegerField()
            )
        )

        # Baseline Risk Parameters (Calibrated via historical migration matrices)
        pds = {'stage_1': Decimal('0.015'), 'stage_2': Decimal('0.080'), 'stage_3': Decimal('0.450')}
        lgd = Decimal('0.45')  # Loss Given Default (reflecting security haircuts)

        ecl_summary = active_loans.annotate(
            stage=Case(
                When(days_overdue__lte=30, then=Value('STAGE_1')),
                When(days_overdue__lte=90, then=Value('STAGE_2')),
                default=Value('STAGE_3'),
                output_field=fields.CharField()
            )
        ).annotate(
            ecl_amount=Case(
                When(stage='STAGE_1', then=(F('principal_balance') + F('interest_balance')) * pds['stage_1'] * lgd),
                When(stage='STAGE_2', then=(F('principal_balance') + F('interest_balance')) * pds['stage_2'] * lgd),
                default=(F('principal_balance') + F('interest_balance')) * pds['stage_3'] * lgd,
                output_field=DecimalField(max_digits=18, decimal_places=2)
            )
        )

        return ecl_summary

    @staticmethod
    def get_loan_aging_summary():
        """
        Groups outstanding balances across defined maturity/arrears risk buckets.
        """
        today = timezone.now().date()
        today_str = today.strftime('%Y-%m-%d')
        loans = Loan.objects.filter(status__in=['approved', 'arrears'], is_active=True)
        
        aging_buckets = loans.annotate(
            days_overdue=Coalesce(
                Max(Case(
                    When(
                        installments__paid=False, 
                        installments__due_date__lt=today, 
                        then=Cast(
                            RawSQL("julianday(%s) - julianday(finance_installment.due_date)", [today_str]),
                            output_field=IntegerField()
                        )
                    ),
                    default=Value(0),
                    output_field=IntegerField()
                )),
                Value(0),
                output_field=IntegerField()
            )
        ).annotate(
            bucket=Case(
                When(days_overdue=0, then=Value('Current')),
                When(days_overdue__lte=30, then=Value('1-30 Days')),
                When(days_overdue__lte=60, then=Value('31-60 Days')),
                When(days_overdue__lte=90, then=Value('61-90 Days')),
                When(days_overdue__lte=180, then=Value('91-180 Days')),
                default=Value('180+ Days'),
                output_field=fields.CharField()
            )
        ).values('bucket').annotate(
            volume=Sum('principal_balance') + Sum('interest_balance'),
            count=Count('id'),
            interest_arrears=Sum('installments__interest_portion', filter=Q(installments__paid=False))
        ).order_by('bucket')

        return list(aging_buckets)

    @staticmethod
    def get_regulatory_ratios():
        """
        Calculates capital adequacy, liquidity, and asset quality metrics 
        against central bank statutory mandates.
        """
        total_assets = GeneralLedger.objects.filter(account__account_type='asset').aggregate(bal=Sum('debit') - Sum('credit'))['bal'] or Decimal('0.00')
        liquid_assets = GeneralLedger.objects.filter(account__account_type='asset', account__parent__isnull=False).aggregate(bal=Sum('debit')-Sum('credit'))['bal'] or Decimal('0.00')
        total_deposits = SavingsAccount.objects.aggregate(bal=Sum('balance'))['bal'] or Decimal('0.00')
        core_capital = GeneralLedger.objects.filter(account__account_type='equity').aggregate(bal=Sum('credit')-Sum('debit'))['bal'] or Decimal('0.00')

        total_loans = Loan.objects.filter(status__in=['approved', 'arrears'], is_active=True).aggregate(bal=Sum('principal_balance') + Sum('interest_balance'))['bal'] or Decimal('0.00')
        
        today = timezone.now().date()
        npl_loans = Loan.objects.filter(
            status__in=['approved', 'arrears'], 
            is_active=True,
            installments__paid=False, 
            installments__due_date__lt=today - datetime.timedelta(days=90)
        ).distinct().aggregate(bal=Sum('principal_balance') + Sum('interest_balance'))['bal'] or Decimal('0.00')

        par_30_loans = Loan.objects.filter(
            status__in=['approved', 'arrears'], 
            is_active=True,
            installments__paid=False, 
            installments__due_date__lt=today - datetime.timedelta(days=30)
        ).distinct().aggregate(bal=Sum('principal_balance') + Sum('interest_balance'))['bal'] or Decimal('0.00')

        if total_deposits == 0: total_deposits = Decimal('1.00')
        if total_assets == 0: total_assets = Decimal('1.00')

        return {
            'liquidity_ratio': (liquid_assets / total_deposits) * 100,
            'capital_adequacy_ratio': (core_capital / total_assets) * 100,
            'npl_ratio': (npl_loans / total_loans) * 100 if total_loans > 0 else Decimal('0.00'),
            'portfolio_at_risk_30': (par_30_loans / total_loans) * 100 if total_loans > 0 else Decimal('0.00')
        }

    @staticmethod
    def get_treasury_liquidity_forecast():
        """
        Generates a 30-day structural liquidity profile matching asset inflows 
        (scheduled collections) against anticipated liabilities.
        """
        today = timezone.now().date()
        forecast = []
        for i in range(30):
            target_date = today + datetime.timedelta(days=i)
            inflows = Installment.objects.filter(due_date=target_date, paid=False).aggregate(total=Sum('principal_portion') + Sum('interest_portion'))['total'] or Decimal(0)
            outflows_estimated = Transaction.objects.filter(type='withdrawal').aggregate(avg_wd=Avg('amount'))['avg_wd'] or Decimal(0)
            
            forecast.append({
                'date': target_date.strftime('%Y-%m-%d'),
                'inflow': float(inflows),
                'outflow': float(outflows_estimated),
                'net_position': float(inflows - outflows_estimated)
            })
        return forecast


#############################################################################################################
from decimal import Decimal
from django.db import transaction
from .models import SavingsAccount, Transaction, AccountingEngine

class FinancialTransactionService:
    @staticmethod
    @transaction.atomic
    def record_deposit(member, amount, receipt_ref, date=None):
        """Debit Cash (Asset), Credit Member Savings (Liability)."""
        savings = SavingsAccount.objects.select_for_update().get(member=member)
        savings.balance += amount
        savings.save()

        tx = Transaction.objects.create(
            member=member, amount=amount, type='deposit', reference=receipt_ref
        )
        
        # 1000: Cash/Bank Account, 2000: Member Savings Account
        AccountingEngine.post_ledger_entry("1000", "Member Deposit", receipt_ref, amount, 0, tx, date)
        AccountingEngine.post_ledger_entry("2000", "Member Deposit", receipt_ref, 0, amount, tx, date)
        return tx

    @staticmethod
    @transaction.atomic
    def record_withdrawal(member, amount, receipt_ref, date=None):
        """Debit Member Savings (Liability), Credit Cash (Asset)."""
        savings = SavingsAccount.objects.select_for_update().get(member=member)
        if savings.balance < amount:
            raise ValueError("Insufficient funds.")
        
        savings.balance -= amount
        savings.save()

        tx = Transaction.objects.create(
            member=member, amount=amount, type='withdrawal', reference=receipt_ref
        )
        
        AccountingEngine.post_ledger_entry("2000", "Member Withdrawal", receipt_ref, amount, 0, tx, date)
        AccountingEngine.post_ledger_entry("1000", "Member Withdrawal", receipt_ref, 0, amount, tx, date)
        return tx
    
    
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal


def apply_monthly_penalty(loan):
    """
    Applies monthly penalty once per month based on outstanding total due.
    """

    if loan.penalty_type != "monthly_once":
        return 0

    today = date.today()

    # If never applied before
    if not loan.last_penalty_date:
        should_charge = True
    else:
        next_due_date = loan.last_penalty_date + relativedelta(months=1)
        should_charge = today >= next_due_date

    if not should_charge:
        return 0

    # OUTSTANDING = NOT principal only
    outstanding = loan.principal_balance + loan.interest_balance

    penalty_amount = (outstanding * loan.penalty_rate) / Decimal("100")

    loan.accumulated_penalty += penalty_amount
    loan.last_penalty_date = today

    loan.save(update_fields=[
        "accumulated_penalty",
        "last_penalty_date"
    ])

    return penalty_amount