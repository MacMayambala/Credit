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

import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from finance.models import (
    Loan, Installment, SavingsAccount, Transaction, 
    AutoRepaymentSetting, AutoRepaymentLog, DailyRepaymentSummary,
    Repayment  # <-- Added to use the waterfall
)

logger = logging.getLogger(__name__)

class LoanRepaymentEngineService:
    """
    Auto-repayment engine – now processes all overdue installments for a loan
    in a single sweep, using Repayment.save() to allocate the payment.
    """

    @classmethod
    def execute_bulk_auto_repayments(cls) -> dict:
        """
        Scans for loans with overdue installments and processes each loan once.
        Returns a summary dict.
        """
        start_time = timezone.now()
        summary_date = start_time.date()

        config = AutoRepaymentSetting.objects.first()
        if not config or not config.is_enabled:
            logger.info("Automated repayment batch engine skipped (disabled/unconfigured).")
            return {"status": "skipped"}

        # Grace period: only process installments overdue beyond this threshold
        due_threshold = summary_date - timedelta(days=config.grace_period_days)

        # Find all unpaid installments that are overdue
        overdue_installments = Installment.objects.filter(
            paid=False,
            due_date__lte=due_threshold,
            loan__is_active=True,
            loan__status__in=['approved', 'arrears']
        ).select_related('loan', 'loan__member').order_by('loan_id', 'due_date')

        # Get distinct loan IDs
        loan_ids = overdue_installments.values_list('loan_id', flat=True).distinct()

        processed_loans = 0
        total_recovered = Decimal('0.00')
        partial_count = 0
        failed_count = 0
        closed_count = 0

        for loan_id in loan_ids:
            result = cls._process_loan_recovery(loan_id)
            processed_loans += 1
            if result['status'] == 'success':
                total_recovered += result['recovered']
            elif result['status'] == 'partial':
                total_recovered += result['recovered']
                partial_count += 1
            elif result['status'] == 'failed':
                failed_count += 1
            if result.get('loan_closed', False):
                closed_count += 1

        # Update or create daily summary
        summary, _ = DailyRepaymentSummary.objects.get_or_create(date=summary_date)
        summary.total_processed = processed_loans
        summary.total_recovered = total_recovered
        summary.partial_payments = partial_count
        summary.failed_deductions = failed_count
        summary.closed_loans = closed_count
        summary.execution_duration_seconds = (timezone.now() - start_time).total_seconds()
        summary.save()

        return {
            "status": "completed",
            "processed": processed_loans,
            "recovered": float(total_recovered),
            "partial": partial_count,
            "failed": failed_count,
            "closed": closed_count,
        }

    @classmethod
    def _process_loan_recovery(cls, loan_id: int) -> dict:
        """
        Process all overdue installments for a single loan in one atomic transaction.
        Calculates total overdue, deducts from savings once, and creates a single Repayment
        which triggers the waterfall allocation.
        """
        result = {'recovered': Decimal('0.00'), 'status': 'failed', 'loan_closed': False}

        try:
            with transaction.atomic():
                # Lock the loan and savings account
                loan = Loan.objects.select_for_update().get(
                    id=loan_id,
                    is_active=True,
                    status__in=['approved', 'arrears']
                )
                savings = SavingsAccount.objects.select_for_update().get(member=loan.member)

                if savings.balance <= 0:
                    result['status'] = 'failed'
                    cls._create_log(loan, None, savings.balance, Decimal('0.00'), Decimal('0.00'), 'failed')
                    return result

                today = timezone.now().date()

                # Sum total overdue across all unpaid installments
                overdue_total = loan.installments.filter(
                    paid=False,
                    due_date__lte=today
                ).aggregate(
                    total=Coalesce(
                        Sum(
                            F('principal_portion') - F('principal_paid') +
                            F('interest_portion') - F('interest_paid') +
                            F('penalty_amount') - F('penalty_paid')
                        ),
                        Value(Decimal('0.00'), output_field=DecimalField())
                    )
                )['total']

                if overdue_total <= 0:
                    result['status'] = 'failed'
                    cls._create_log(loan, None, savings.balance, Decimal('0.00'), Decimal('0.00'), 'failed')
                    return result

                # Determine how much we can collect (up to total overdue or balance)
                collectible = min(savings.balance, overdue_total)
                if collectible <= 0:
                    result['status'] = 'failed'
                    cls._create_log(loan, None, savings.balance, overdue_total, Decimal('0.00'), 'failed')
                    return result

                # Deduct from savings
                savings.balance -= collectible
                savings.save()

                # Create a single Repayment record – its save() will allocate across installments
                ref = f"AUTO-REPAY-{loan.loan_reference}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                repayment = Repayment(
                    loan=loan,
                    amount_paid=collectible,
                    receipt_number=ref,
                    notes="Auto-repayment – cleared all overdue in one sweep"
                )
                repayment.save()  # This runs the waterfall and ledger updates

                # After allocation, check if loan is now closed
                loan.refresh_from_db()
                if loan.principal_balance <= 0 and loan.interest_balance <= 0:
                    result['loan_closed'] = True

                # Determine status: success if full overdue cleared, else partial
                status = 'success' if collectible >= overdue_total else 'partial'
                result['recovered'] = collectible
                result['status'] = status

                cls._create_log(loan, None, savings.balance + collectible, overdue_total, collectible, status)
                cls._trigger_notification(loan.member, loan, collectible, status)

        except Loan.DoesNotExist:
            logger.warning(f"Loan {loan_id} not found or not active.")
            result['status'] = 'failed'
        except SavingsAccount.DoesNotExist:
            logger.warning(f"Savings account missing for loan {loan_id}.")
            result['status'] = 'failed'
        except Exception as e:
            logger.error(f"Auto-repayment failed for loan {loan_id}: {str(e)}")
            # Try to get loan object for logging (may not exist)
            try:
                loan = Loan.objects.get(id=loan_id)
                cls._create_log(loan, None, Decimal('0.00'), Decimal('0.00'), Decimal('0.00'), 'error', str(e))
            except Loan.DoesNotExist:
                pass
            result['status'] = 'failed'

        return result

    @classmethod
    def _create_log(cls, loan, inst, bal_before, attempted, recovered, status, err=""):
        """Create an AutoRepaymentLog entry."""
        AutoRepaymentLog.objects.create(
            loan=loan,
            installment=inst,  # can be None for loan-level logs
            savings_balance_before=bal_before,
            amount_attempted=attempted,
            amount_recovered=recovered,
            status=status,
            error_message=err[:255] if err else ""
        )

    @classmethod
    def _trigger_notification(cls, member, loan, amount, outcome):
        """
        Send notification (SMS/email) about the auto-repayment.
        Replace with your actual notification service.
        """
        message = f"Dear {member.first_name}, automated loan repayment "
        if outcome == 'success':
            message += f"succeeded. UGX {amount:,.0f} deducted for loan {loan.loan_reference}."
        elif outcome == 'partial':
            message += f"partially succeeded. UGX {amount:,.0f} deducted. Please clear remaining arrears."
        else:
            message += f"failed due to insufficient savings balance."

        logger.info(f"[AUTO-REPAY NOTIFICATION] to {member.phone_number}: {message}")
        # To actually send SMS, integrate with your SMS gateway here.
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