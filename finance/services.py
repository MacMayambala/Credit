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
        from decimal import Decimal
        
        start_time = timezone.now()
        summary_date = start_time.date()
        
        summary, _ = DailyRepaymentSummary.objects.get_or_create(date=summary_date)
        config = AutoRepaymentSetting.objects.first()
        
        if not config or not config.is_enabled:
            logger.info("Automated repayment batch engine skipped. (Disabled/Unconfigured)")
            return {"status": "skipped"}

        # ---- FIX: Ensure all Decimal fields are Decimal, not float ----
        summary.total_recovered = Decimal(str(summary.total_recovered or 0))
        # (total_processed is integer, no issue)

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
            
            # Ensure recovered is Decimal
            recovered = result.get('recovered', Decimal('0.00'))
            if not isinstance(recovered, Decimal):
                try:
                    recovered = Decimal(str(recovered))
                except:
                    recovered = Decimal('0.00')
            
            # Now both are Decimal, safe to add
            summary.total_recovered += recovered
            
            if result['status'] == 'success':
                pass 
            elif result['status'] == 'partial':
                summary.partial_payments += 1
            elif result['status'] == 'failed':
                summary.failed_deductions += 1
            
            if result.get('loan_closed', False):
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
        from decimal import Decimal
        from .models import AccountingEngine  # Import AccountingEngine
        
        loan = installment.loan
        member = loan.member
        result = {'recovered': Decimal('0.00'), 'status': 'failed', 'loan_closed': False}

        try:
            with transaction.atomic():
                # Acquire explicit PostgreSQL row-level locks on relevant balances
                savings_acc = SavingsAccount.objects.select_for_update().get(member=member)
                loan_locked = Loan.objects.select_for_update().get(pk=loan.pk)
                inst_locked = Installment.objects.select_for_update().get(pk=installment.pk)

                bal_before = savings_acc.balance
                
                # Calculate amount due
                amount_due = (
                    (inst_locked.principal_portion or Decimal('0.00')) + 
                    (inst_locked.interest_portion or Decimal('0.00')) +
                    (inst_locked.penalty_amount or Decimal('0.00'))
                )

                if bal_before <= 0:
                    cls._create_log(loan_locked, inst_locked, bal_before, amount_due, Decimal('0.00'), 'failed')
                    cls._trigger_notification(member, loan_locked, Decimal('0.00'), 'failed')
                    return result

                # Determine legal recovery boundaries (Partial vs Full)
                recovered_amount = min(bal_before, amount_due)
                result['recovered'] = recovered_amount

                # Track allocations for ledger entries
                penalty_deduction = Decimal('0.00')
                interest_deduction = Decimal('0.00')
                principal_deduction = Decimal('0.00')

                # Wallet Balance Deduction
                savings_acc.balance -= recovered_amount
                savings_acc.save()

                # Process Financial Ledger Allocation: Penalty -> Interest -> Principal
                remaining_allocation = recovered_amount
                
                # 1. Deduct Penalty
                penalty_balance = inst_locked.penalty_amount - inst_locked.penalty_paid
                if penalty_balance > 0 and remaining_allocation > 0:
                    penalty_deduction = min(remaining_allocation, penalty_balance)
                    inst_locked.penalty_paid += penalty_deduction
                    remaining_allocation -= penalty_deduction

                # 2. Deduct Interest
                interest_balance = inst_locked.interest_portion - inst_locked.interest_paid
                if interest_balance > 0 and remaining_allocation > 0:
                    interest_deduction = min(remaining_allocation, interest_balance)
                    loan_locked.interest_balance -= interest_deduction
                    inst_locked.interest_paid += interest_deduction
                    remaining_allocation -= interest_deduction

                # 3. Deduct Principal
                principal_balance = inst_locked.principal_portion - inst_locked.principal_paid
                if principal_balance > 0 and remaining_allocation > 0:
                    principal_deduction = min(remaining_allocation, principal_balance)
                    loan_locked.principal_balance -= principal_deduction
                    inst_locked.principal_paid += principal_deduction
                    remaining_allocation -= principal_deduction

                # Update operational targets
                if inst_locked.balance <= 0:
                    inst_locked.paid = True
                inst_locked.save()

                # Evaluate closure parameters
                if loan_locked.principal_balance <= 0 and loan_locked.interest_balance <= 0:
                    loan_locked.status = 'closed'
                    loan_locked.is_active = False
                    result['loan_closed'] = True
                elif loan_locked.status == 'arrears' and inst_locked.paid:
                    loan_locked.status = 'approved'
                
                loan_locked.save()

                # Inject System Audit Ledger Transaction entries
                ref_code = f"AUTO-REPAY-{loan_locked.loan_reference}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                
                # Create the transaction record
                tx_obj = Transaction.objects.create(
                    member=member,
                    loan=loan_locked,
                    amount=recovered_amount,
                    type='repayment',
                    reference=ref_code,
                    timestamp=timezone.now(),
                    created_by=None
                )

                # =====================================================
                # POST TO GENERAL LEDGER (DOUBLE-ENTRY)
                # =====================================================
                
                # 1. Debit: Savings Account (Liability decreases)
                AccountingEngine.post_ledger_entry(
                    account_code="2000",  # Member Savings / Liability
                    description=f"Auto-repayment deduction for loan {loan_locked.loan_reference}",
                    reference=ref_code,
                    debit=recovered_amount,  # Debit liability decreases it
                    credit=Decimal('0.00'),
                    transaction_obj=tx_obj,
                    date_context=timezone.now().date()
                )

                # 2. Credit: Loan Receivable (Asset decreases)
                if principal_deduction > 0:
                    AccountingEngine.post_ledger_entry(
                        account_code="1200",  # Loan Receivable / Asset
                        description=f"Principal recovery on loan {loan_locked.loan_reference}",
                        reference=ref_code,
                        debit=Decimal('0.00'),
                        credit=principal_deduction,  # Credit asset decreases it
                        transaction_obj=tx_obj,
                        date_context=timezone.now().date()
                    )

                # 3. Credit: Interest Income (Income increases)
                if interest_deduction > 0:
                    AccountingEngine.post_ledger_entry(
                        account_code="2100",  # Interest Income / Revenue
                        description=f"Interest income recognized on loan {loan_locked.loan_reference}",
                        reference=ref_code,
                        debit=Decimal('0.00'),
                        credit=interest_deduction,  # Credit income increases it
                        transaction_obj=tx_obj,
                        date_context=timezone.now().date()
                    )

                # 4. Credit: Penalty Income (Income increases)
                if penalty_deduction > 0:
                    AccountingEngine.post_ledger_entry(
                        account_code="2200",  # Penalty Income / Revenue
                        description=f"Penalty income recognized on loan {loan_locked.loan_reference}",
                        reference=ref_code,
                        debit=Decimal('0.00'),
                        credit=penalty_deduction,  # Credit income increases it
                        transaction_obj=tx_obj,
                        date_context=timezone.now().date()
                    )

                # Evaluate Execution Status Labels for Notifications
                final_status = 'success' if inst_locked.paid else 'partial'
                result['status'] = final_status

                cls._create_log(loan_locked, inst_locked, bal_before, amount_due, recovered_amount, final_status)
                cls._trigger_notification(member, loan_locked, recovered_amount, final_status)

        except Exception as system_exception:
            logger.error(f"Auto-Repayment Exception encountered on Installment {installment.id}: {str(system_exception)}")
            cls._create_log(loan, installment, Decimal('0.00'), Decimal('0.00'), Decimal('0.00'), 'error', str(system_exception))

        return result

    @classmethod
    def _create_log(cls, loan, inst, bal_before, attempted, recovered, status, err=""):
        from decimal import Decimal
        AutoRepaymentLog.objects.create(
            loan=loan, 
            installment=inst, 
            savings_balance_before=bal_before,
            amount_attempted=attempted, 
            amount_recovered=recovered, 
            status=status, 
            error_message=err
        )

    @classmethod
    def _trigger_notification(cls, member, loan, amount, outcome):
        """
        Placeholder dispatch hook interface matching architectural standards.
        Replace implementation details with your target notification gateway APIs.
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
# finance/services.py
import uuid
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Sum, Q
from .models import Transaction, SavingsAccount, Member, Loan, Installment

logger = logging.getLogger(__name__)


# finance/services.py
import uuid
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Sum, Q
from .models import Transaction, SavingsAccount, Member, Loan, Installment

logger = logging.getLogger(__name__)


def generate_transaction_ref(prefix="TXN"):
    """
    Generate a unique transaction reference.
    Format: {prefix}-{8 character hex}
    Example: DEP-A1B2C3D4
    """
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def process_repayment(loan_id):
    """
    Process auto-repayment for a loan using available funds.
    
    Args:
        loan_id: ID of the loan to process
        
    Returns:
        Decimal: Total amount cleared from arrears, or None if no repayment
    """
    try:
        loan = Loan.objects.get(id=loan_id)
        member = loan.member
        
        # Get savings balance
        savings = SavingsAccount.objects.filter(member=member).first()
        if not savings or savings.balance <= 0:
            return Decimal('0')
        
        # Get overdue installments
        overdue_installments = Installment.objects.filter(
            loan=loan,
            paid=False,
            due_date__lte=timezone.now().date()
        ).order_by('due_date')
        
        if not overdue_installments.exists():
            return Decimal('0')
        
        total_cleared = Decimal('0')
        
        with db_transaction.atomic():
            for installment in overdue_installments:
                if savings.balance <= 0:
                    break
                    
                amount_due = (installment.principal_portion or Decimal('0')) + (installment.interest_portion or Decimal('0'))
                amount_to_pay = min(amount_due, savings.balance)
                
                if amount_to_pay > 0:
                    # Mark installment as paid
                    installment.paid = True
                    installment.paid_date = timezone.now().date()
                    installment.save()
                    
                    # Deduct from savings
                    savings.balance -= amount_to_pay
                    savings.save()
                    
                    total_cleared += amount_to_pay
                    
                    # Create repayment transaction
                    Transaction.objects.create(
                        member=member,
                        loan=loan,
                        amount=amount_to_pay,
                        type='repayment',
                        reference=f"REP-{loan.loan_reference}-{installment.installment_number}",
                        timestamp=timezone.now(),
                        created_by=None  # Auto-repayment has no creator
                    )
        
        return total_cleared
        
    except Loan.DoesNotExist:
        logger.error(f"Loan {loan_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error processing repayment for loan {loan_id}: {str(e)}")
        return None


class FinancialTransactionService:
    """Service class for handling financial transactions"""
    
    

    @staticmethod
    def record_deposit(member, amount, receipt_ref, date=None, created_by=None):
        """
        Record a deposit transaction for a member.
        """
        print("\n--- FinancialTransactionService.record_deposit ---")
        print(f"Member: {member.get_full_name()} (ID: {member.id})")
        print(f"Amount: {amount}")
        print(f"Receipt Ref: {receipt_ref}")
        
        if date is None:
            date = timezone.now()
            print(f"Date set to now: {date}")
        
        with db_transaction.atomic():
            print("Creating transaction record...")
            # Create transaction record
            transaction = Transaction.objects.create(
                member=member,
                loan=None,
                amount=amount,
                type='deposit',
                timestamp=date,
                reference=receipt_ref,
                is_reversed=False,
                created_by=created_by
            )
            print(f"Transaction created with ID: {transaction.id}")
            
            # Update savings balance
            print("Updating savings balance...")
            savings, created = SavingsAccount.objects.get_or_create(
                member=member,
                defaults={'balance': Decimal('0.00')}
            )
            print(f"Savings account - Created: {created}, Balance before: {savings.balance}")
            
            savings.balance += amount
            savings.save()
            print(f"Savings account - Balance after: {savings.balance}")
            
            # Update member's last transaction date - REMOVED because field doesn't exist
            # member.last_transaction_date = date
            # member.save(update_fields=['last_transaction_date'])
            
            print("--- record_deposit completed successfully ---\n")
            return transaction
    
    @staticmethod
    def record_withdrawal(member, amount, reference, date=None, created_by=None):
        """
        Record a withdrawal transaction for a member.
        
        Args:
            member: Member instance
            amount: Decimal amount
            reference: String reference
            date: Optional datetime (defaults to now)
            created_by: User who created the transaction
            
        Returns:
            Transaction: The created transaction record
        """
        if date is None:
            date = timezone.now()
        
        with db_transaction.atomic():
            # Check sufficient balance
            savings = SavingsAccount.objects.filter(member=member).first()
            if not savings or savings.balance < amount:
                raise ValueError(f"Insufficient balance. Available: {savings.balance if savings else 0}")
            
            # Create transaction record
            transaction = Transaction.objects.create(
                member=member,
                loan=None,
                amount=amount,
                type='withdrawal',
                timestamp=date,
                reference=reference,
                is_reversed=False,
                created_by=created_by
            )
            
            # Update savings balance
            savings.balance -= amount
            savings.save()
            
            # Update member's last transaction date
            member.last_transaction_date = date
            member.save(update_fields=['last_transaction_date'])
            
            return transaction
    
    @staticmethod
    def record_loan_disbursement(member, loan, amount, reference, date=None, created_by=None):
        """
        Record a loan disbursement transaction.
        
        Args:
            member: Member instance
            loan: Loan instance
            amount: Decimal amount
            reference: String reference
            date: Optional datetime (defaults to now)
            created_by: User who created the transaction
            
        Returns:
            Transaction: The created transaction record
        """
        if date is None:
            date = timezone.now()
        
        with db_transaction.atomic():
            # Create transaction record
            transaction = Transaction.objects.create(
                member=member,
                loan=loan,
                amount=amount,
                type='disbursement',
                timestamp=date,
                reference=reference,
                is_reversed=False,
                created_by=created_by
            )
            
            # Update savings balance (disbursement increases balance)
            savings = SavingsAccount.objects.filter(member=member).first()
            if savings:
                savings.balance += amount
                savings.save()
            
            return transaction
    
    @staticmethod
    def get_member_balance(member):
        """
        Get the current balance for a member.
        
        Args:
            member: Member instance
            
        Returns:
            Decimal: Current balance
        """
        savings = SavingsAccount.objects.filter(member=member).first()
        return savings.balance if savings else Decimal('0')
    
    @staticmethod
    def get_transaction_summary(member, start_date=None, end_date=None):
        """
        Get transaction summary for a member within date range.
        
        Args:
            member: Member instance
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            dict: Summary with total deposits, withdrawals, and count
        """
        queryset = Transaction.objects.filter(member=member)
        
        if start_date:
            queryset = queryset.filter(timestamp__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__date__lte=end_date)
        
        summary = queryset.aggregate(
            total_deposits=Sum('amount', filter=Q(type='deposit')),
            total_withdrawals=Sum('amount', filter=Q(type='withdrawal')),
            total_repayments=Sum('amount', filter=Q(type='repayment')),
        )
        
        return {
            'total_deposits': summary['total_deposits'] or Decimal('0'),
            'total_withdrawals': summary['total_withdrawals'] or Decimal('0'),
            'total_repayments': summary['total_repayments'] or Decimal('0'),
            'total_transactions': queryset.count()
        }
    
    @staticmethod
    def get_transactions_by_type(member, transaction_type):
        """
        Get all transactions of a specific type for a member.
        
        Args:
            member: Member instance
            transaction_type: String transaction type ('deposit', 'withdrawal', etc.)
            
        Returns:
            QuerySet: Filtered transactions
        """
        return Transaction.objects.filter(
            member=member,
            type=transaction_type
        ).order_by('-timestamp')
    
    @staticmethod
    def reverse_transaction(transaction_id, reason="", reversed_by=None):
        """
        Reverse a transaction.
        
        Args:
            transaction_id: ID of the transaction to reverse
            reason: Reason for reversal
            reversed_by: User performing the reversal
            
        Returns:
            Transaction: The reversed transaction
        """
        with db_transaction.atomic():
            original = Transaction.objects.get(id=transaction_id)
            
            if original.is_reversed:
                raise ValueError("Transaction already reversed")
            
            # Reverse the effect on savings balance
            savings = SavingsAccount.objects.filter(member=original.member).first()
            if savings:
                if original.type == 'deposit':
                    savings.balance -= original.amount
                elif original.type == 'withdrawal':
                    savings.balance += original.amount
                elif original.type == 'disbursement':
                    savings.balance -= original.amount
                savings.save()
            
            # Mark original as reversed
            original.is_reversed = True
            original.save()
            
            # Create reversal transaction
            reversal = Transaction.objects.create(
                member=original.member,
                loan=original.loan,
                amount=original.amount,
                type='repayment',  # Or create a 'reversal' type if added to choices
                timestamp=timezone.now(),
                reference=f"REV-{original.reference}",
                is_reversed=False,
                created_by=reversed_by
            )
            
            return reversal