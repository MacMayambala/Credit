from enum import member

from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import (
    Installment, Loan, Member, Repayment, SavingsAccount, SystemSetting, Transaction, TransactionReversal, 
    process_repayment, generate_schedule
)
from .models import Loan, LoanPenaltyRule, Member, Installment
# finance/views.py
import json
import random
import string
import logging
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from .models import (
    Loan,
    Member,
    Installment,
    LoanPenaltyRule,          # <-- add this
    generate_schedule,
           # if you have these helpers
)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, F, Q, DecimalField, ExpressionWrapper, Window
from django.db.models.functions import Coalesce, ExtractMonth, TruncMonth  # Add TruncMonth here
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import User
from django_celery_beat.models import PeriodicTask

from .models import (
    Installment, Loan, Member, SavingsAccount, Transaction, 
    Repayment, TransactionReversal, SystemSetting, GeneralLedger,
    ChartOfAccount, AutoRepaymentSetting, AutoRepaymentLog, DailyRepaymentSummary
)
from .services import (
    FinancialTransactionService, process_repayment, generate_transaction_ref,
    LoanRepaymentEngineService
)
from .forms import AutoRepaymentSettingForm
from .utils import send_bulk_arrears_reminders, generate_schedule

logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from decimal import Decimal
from django.db.models import Sum
from .models import (
    Installment, Loan, Member, SavingsAccount, Transaction, 
    process_repayment, generate_schedule
)

from django.db.models import Sum, F
from .models import Loan, Member, SavingsAccount

import json
from django.shortcuts import render
from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from .models import Loan, Member, SavingsAccount, Transaction

import json
from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.shortcuts import render

from .models import Member, SavingsAccount, Loan, Transaction


import json
from django.db.models.functions import ExtractMonth
from django.db.models import Sum
from django.shortcuts import render

from .models import Loan, Transaction


import json
from django.db.models import Sum, DecimalField
from django.db.models.functions import ExtractMonth, Cast
from django.shortcuts import render
from .models import Member, Loan, SavingsAccount, Transaction

import json
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from django.db.models import Sum, F, Q
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models.functions import ExtractMonth

from .models import (
    Installment, Loan, Member, SavingsAccount, Transaction, 
    Repayment, process_repayment, generate_schedule
)
from .utils import send_bulk_arrears_reminders

# ========================
# DASHBOARD & REGISTRY
# ========================
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

import string
import random
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import Sum, F, Q, DecimalField
from django.db.models.functions import ExtractMonth, Cast
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError

from .models import (
    Installment, Loan, Member, SavingsAccount, Transaction, 
    Repayment, TransactionReversal, SystemSetting,
    process_repayment, generate_schedule
)
from .utils import send_bulk_arrears_reminders, generate_transaction_ref

# ========================
# UTILITIES & DECORATORS
# ========================

def allowed_users(allowed_roles=[]):
    """
    RBAC View Decorator to check user groups.
    """
    def decorator(view_func):
        def wrapper_func(request, *args, **kwargs):
            group = None
            if request.user.groups.exists():
                group = request.user.groups.all()[0].name

            if group in allowed_roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            else:
                raise PermissionDenied  # Shows 403 Forbidden
        return wrapper_func
    return decorator


def generate_loan_ref(length=10):
    """Generates a random uppercase alphanumeric string for loans"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


# ========================
# CORE CORE SACCO VIEWS
# ========================

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from finance.models import SavingsAccount, Loan, Transaction, Member
from django.db.models.functions import ExtractMonth
# finance/views.py – dashboard view (fully updated)
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.db.models.functions import ExtractMonth

from finance.models import (
    SavingsAccount, Loan, Transaction, Member,
    GeneralLedger, ChartOfAccount
)
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.db.models.functions import ExtractMonth

from finance.models import (
    SavingsAccount, Loan, Transaction, Member,
    GeneralLedger, ChartOfAccount, Installment
)

@login_required
def dashboard(request):
    """
    Main SACCO Dashboard with updated split-balance aggregation
    and a true Interest Yield percentage.
    """
    today = timezone.now().date()
    one_year_ago = today - relativedelta(years=1)

    # ============================================================
    # 1. SUMMARY WIDGETS
    # ============================================================

    # Total Savings
    total_savings = SavingsAccount.objects.aggregate(total=Sum('balance'))['total'] or 0

    # Total Active Loans (principal_balance + interest_balance)
    loan_stats = Loan.objects.filter(is_active=True).aggregate(
        p_bal=Sum('principal_balance'),
        i_bal=Sum('interest_balance')
    )
    total_loans = (loan_stats['p_bal'] or 0) + (loan_stats['i_bal'] or 0)

    # ============================================================
    # Interest Earned in the last 12 months (from GeneralLedger)
    # ============================================================
    try:
        # Your ChartOfAccount code for Interest Income is '2100' (as seen in Repayment.save())
        interest_account = ChartOfAccount.objects.get(code='2100')
        interest_last_year = GeneralLedger.objects.filter(
            account=interest_account,
            date__gte=one_year_ago
        ).aggregate(total=Sum('credit'))['total'] or 0
    except ChartOfAccount.DoesNotExist:
        # Fallback: sum interest_paid from Installment model
        interest_last_year = Installment.objects.filter(
            loan__is_active=True,
            due_date__gte=one_year_ago
        ).aggregate(total=Sum('interest_paid'))['total'] or 0

    # ============================================================
    # Interest Yield (annualized) = (interest_last_year / total_loans) * 100
    # ============================================================
    if total_loans > 0:
        interest_yield = (interest_last_year / total_loans) * 100
    else:
        interest_yield = 0

    # Keep the raw amount for display if needed (e.g., in a tooltip)
    total_interest = interest_last_year

    # Counts
    total_members = Member.objects.count()
    active_loans_count = Loan.objects.filter(is_active=True).count()
    recent_loans = Loan.objects.select_related('member').order_by('-start_date')[:10]

    # ============================================================
    # 2. CHART DATA (Monthly trends for last 12 months)
    # ============================================================

    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    savings_trend = [0] * 12
    loan_trend = [0] * 12

    # Savings deposits per month
    savings_data = Transaction.objects.filter(
        type='deposit',
        timestamp__gte=one_year_ago
    ).annotate(month=ExtractMonth('timestamp')).values('month').annotate(total=Sum('amount'))

    for entry in savings_data:
        if entry['month'] and 1 <= entry['month'] <= 12:
            savings_trend[entry['month'] - 1] = float(entry['total'])

    # Loan disbursements per month
    loan_data = Loan.objects.filter(
        start_date__gte=one_year_ago,
        status='approved'
    ).annotate(month=ExtractMonth('start_date')).values('month').annotate(total=Sum('principal_amount'))

    for entry in loan_data:
        if entry['month'] and 1 <= entry['month'] <= 12:
            loan_trend[entry['month'] - 1] = float(entry['total'])

    # ============================================================
    # 3. CONTEXT
    # ============================================================

    context = {
        'total_savings': total_savings,
        'total_loans': total_loans,
        'total_interest': total_interest,          # UGX amount earned last year
        'interest_yield': interest_yield,          # percentage
        'total_members': total_members,
        'active_loans_count': active_loans_count,
        'loans': recent_loans,
        'chart_labels': labels,
        'chart_savings': savings_trend,
        'chart_loans': loan_trend,
        'today': today,
    }

    return render(request, 'finance/dashboard.html', context)


@login_required
def loan_list(request):
    """Master Loan Registry with split-balance analytics"""
    loans = Loan.objects.select_related('member').all().order_by('-id')
    total_disbursed = loans.aggregate(Sum('principal_amount'))['principal_amount__sum'] or 0
    
    portfolio_stats = loans.aggregate(
        p_total=Sum('principal_balance'),
        i_total=Sum('interest_balance')
    )
    total_outstanding = (portfolio_stats['p_total'] or 0) + (portfolio_stats['i_total'] or 0)
    active_count = loans.filter(is_active=True).count()

    context = {
        'loans': loans,
        'total_disbursed': total_disbursed,
        'total_outstanding': total_outstanding,
        'active_count': active_count,
    }
    return render(request, 'finance/loan_list.html', context)


from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from django.db.models import Sum
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from .models import Loan, Installment, Repayment, ManualPenalty
from .utils import generate_schedule  # assuming you have this utility

# finance/views.py
# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .models import Loan, ManualPenalty

# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .models import Loan, ManualPenalty
from .utils import generate_schedule   # if you have it; otherwise import from models

# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import Loan, ManualPenalty
from .utils import generate_schedule   # if you have this in utils.py; adjust if needed


# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import Loan, ManualPenalty
from .utils import generate_schedule   # adjust import if needed

# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import Loan, ManualPenalty
from .utils import generate_schedule   # adjust if you have it elsewhere


# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta
import math   # for ceil in penalty calculation

from .models import Loan, ManualPenalty
from .utils import generate_schedule   # or from .models import generate_schedule
from finance.penalties import calculate_penalty   # ensure this import works
# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import Loan, ManualPenalty
from .utils import generate_schedule   # or import from wherever you have it
from finance.penalties import calculate_penalty   # your penalty calculator

# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .models import Loan, ManualPenalty
from .utils import generate_schedule
from finance.penalties import calculate_penalty

# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import Loan, ManualPenalty
from .utils import generate_schedule
from finance.penalties import calculate_penalty


# finance/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import Loan, ManualPenalty
from .utils import generate_schedule
from finance.penalties import calculate_penalty
from .models import SMSConfig


@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(Loan.objects.select_related('member', 'officer'), pk=pk)
    today = timezone.now().date()

    # Generate schedule if missing
    if not loan.installments.exists():
        generate_schedule(loan)

    # Due amounts for banner
    active_due = loan.installments.filter(paid=False, due_date__lte=today).aggregate(
        total_interest=Sum('interest_portion'),
        total_principal=Sum('principal_portion')
    )
    interest_due = active_due['total_interest'] or Decimal('0.00')
    principal_due = active_due['total_principal'] or Decimal('0.00')
    total_due_now = (interest_due + principal_due).quantize(Decimal('0.01'))

    total_paid = loan.repayments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
    total_payable = loan.total_payable or Decimal('0')

    disbursement_date = loan.disbursed_date or loan.start_date
    end_date = disbursement_date + relativedelta(months=loan.period_months) if disbursement_date else None

    # --- Build enriched schedule (combines calculated + manual penalties) ---
    # We build a list of dictionaries with the same keys as the original installment object,
    # so the template can still use inst.xxx without changes.
    schedule = []
    for inst in loan.installments.all().order_by('due_date'):
        # Calculated penalty from the rule
        calc_penalty = calculate_penalty(inst) or Decimal('0.00')

        # Manual penalties (not waived) for this installment
        manual_total = inst.manual_penalties.filter(is_waived=False).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        total_penalty = calc_penalty + manual_total

        # Balances
        principal_bal = inst.principal_balance
        interest_bal = inst.interest_balance
        total_balance = principal_bal + interest_bal + total_penalty

        schedule.append({
            'id': inst.id,
            'due_date': inst.due_date,
            'principal_portion': inst.principal_portion,
            'interest_portion': inst.interest_portion,
            'penalty_amount': total_penalty,          # <-- this will show combined penalty
            'balance': total_balance,                 # <-- this will include penalty
            'paid': inst.paid,
            'is_overdue': inst.is_overdue,
        })

    # Manual penalties (for the card)
    manual_penalties = loan.manual_penalties.filter(is_waived=False).order_by('-applied_date')
    total_manual_penalty = manual_penalties.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    sms_config = SMSConfig.objects.first()
    sms_balance = sms_config.balance if sms_config else 0

    context = {
        'loan': loan,
        'sms_balance': sms_balance,
        'principal_balance': loan.principal_balance,
        'interest_due': interest_due,
        'principal_due': principal_due,
        'total_due_now': total_due_now,
        'schedule': schedule,                         # <-- reusing the same variable name
        'repayments': loan.repayments.all().order_by('-date_paid'),
        'total_paid': total_paid.quantize(Decimal('0.01')),
        'total_payable': total_payable,
        'disbursement_date': disbursement_date,
        'end_date': end_date,
        'today': today,
        'manual_penalties': manual_penalties,
        'total_manual_penalty': total_manual_penalty,
    }

    return render(request, 'finance/loan_detail.html', context)
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

# ========================
# Local Imports
# ========================
from .models import Loan, generate_schedule
from .utils import generate_loan_ref   # Make sure this exists in finance/utils.py


from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

# Local imports
from .models import Loan, generate_schedule
from .utils import generate_loan_ref


from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Loan, generate_schedule
from .utils import generate_loan_ref


@login_required
def apply_loan(request, member_id=None):
    """
    Clean & Modern Loan Application View - Uses term_value + repayment_frequency
    Integrated with LoanPenaltyRule for flexible penalties.
    """
    members = Member.objects.all().order_by('first_name')
    selected_member = None

    if member_id:
        selected_member = get_object_or_404(Member, id=member_id)

    if request.method == "POST":
        try:
            member = get_object_or_404(Member, id=request.POST.get('member') or member_id)

            # === Required Fields ===
            principal = Decimal(request.POST.get('principal_amount') or '0')
            interest_rate = Decimal(request.POST.get('interest_rate') or '0')
            term_value = int(request.POST.get('term_value') or 1)
            repayment_frequency = request.POST.get('repayment_frequency', 'monthly')

            # Validation
            if principal <= 0:
                messages.error(request, "Principal amount must be greater than zero.")
                return render(request, 'finance/apply_loan.html', {
                    'members': members, 'selected_member': selected_member
                })

            if term_value < 1:
                messages.error(request, "Term Value must be at least 1.")
                return render(request, 'finance/apply_loan.html', {
                    'members': members, 'selected_member': selected_member
                })

            start_date_str = request.POST.get('start_date')
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else timezone.now().date()

            with transaction.atomic():
                ref_code = generate_loan_ref()

                # --- FIXED: Flat interest calculation (no multiplication by term_value) ---
                # Interest = Principal × (Rate / 100)
                total_interest = (principal * (interest_rate / Decimal('100'))).quantize(Decimal('0.01'))
                total_payable = principal + total_interest

                # --- Create Loan (deprecating old penalty fields) ---
                loan = Loan(
                    member=member,
                    officer=request.user,
                    loan_reference=ref_code,

                    principal_amount=principal,
                    interest_rate=interest_rate,
                    term_value=term_value,
                    repayment_frequency=repayment_frequency,
                    start_date=start_date,

                    total_payable=total_payable,
                    principal_balance=principal,
                    interest_balance=total_interest,

                    status='pending',
                    is_active=False,

                    # Other fields
                    product_type=request.POST.get('product_type', 'personal'),
                    purpose=request.POST.get('purpose', ''),

                    guarantor_1_name=request.POST.get('guarantor_1_name', ''),
                    guarantor_1_phone=request.POST.get('guarantor_1_phone', ''),
                    guarantor_2_name=request.POST.get('guarantor_2_name') or None,
                    guarantor_2_phone=request.POST.get('guarantor_2_phone') or None,

                    collateral_type=request.POST.get('collateral_type', ''),
                    collateral_value=Decimal(request.POST.get('collateral_value') or '0'),
                    collateral_description=request.POST.get('collateral_description', ''),
                    location=request.POST.get('location', ''),
                    contact_person=request.POST.get('contact_person', ''),
                    contact_phone=request.POST.get('contact_phone', ''),

                    # Old penalty fields (will be overridden by LoanPenaltyRule)
                    penalty_type=request.POST.get('penalty_type', 'daily_flat'),
                    penalty_rate=Decimal(request.POST.get('penalty_rate') or '1.0'),
                    penalty_flat_amount=Decimal(request.POST.get('penalty_flat_amount') or '1000'),
                    penalty_grace_days=int(request.POST.get('penalty_grace_days') or '0'),

                    notes=request.POST.get('notes', ''),
                )

                loan.save()

                # --- Create the Penalty Rule ---
                penalty_type = request.POST.get('penalty_type', 'daily_flat')
                penalty_rate = Decimal(request.POST.get('penalty_rate') or '0')
                penalty_flat_amount = Decimal(request.POST.get('penalty_flat_amount') or '1000')
                penalty_grace_days = int(request.POST.get('penalty_grace_days') or '0')
                max_penalty_cap = Decimal(request.POST.get('max_penalty_cap') or '0')
                compound = request.POST.get('compound') == 'true'

                # Map period (default to monthly, but could be derived from frequency)
                frequency_to_period = {
                    'monthly': 'monthly',
                    'weekly': 'weekly',
                    'daily': 'daily',
                    'manual': 'monthly',  # fallback
                }
                period = frequency_to_period.get(repayment_frequency, 'monthly')

                # Map penalty_type to the rule's choices
                rule_penalty_type = penalty_type
                if penalty_type == 'compound':
                    rule_penalty_type = 'percentage'  # but set compound True

                penalty_rule = LoanPenaltyRule.objects.create(
                    loan=loan,
                    penalty_type=rule_penalty_type,
                    period=period,
                    fixed_amount=penalty_flat_amount,
                    percentage_rate=penalty_rate,
                    grace_period_days=penalty_grace_days,
                    max_penalty_cap=max_penalty_cap,
                    compound=compound,
                )

                # Generate installments (splits total interest equally across term)
                generate_schedule(loan)

                messages.success(request, f"Loan {ref_code} created successfully!")
                return redirect('dashboard')

        except ValueError as ve:
            messages.error(request, f"Invalid data entered: {str(ve)}")
        except Exception as e:
            messages.error(request, f"Error creating loan: {str(e)}")

    # GET Request
    context = {
        'members': members,
        'selected_member': selected_member,
        'product_choices': Loan.PRODUCT_CHOICES,
    }
    return render(request, 'finance/apply_loan.html', context)
@login_required
@transaction.atomic
def approve_loan(request, pk, action):
    loan = get_object_or_404(Loan.objects.select_for_update(), pk=pk)

    if action == 'approve':
        if loan.status == 'approved' or loan.is_active:
            messages.info(request, "This loan has already been approved and disbursed.")
            return redirect('loan_detail', pk=loan.id)

        try:
            # ---- Ensure savings account exists ----
            savings, created = SavingsAccount.objects.get_or_create(member=loan.member)
            # Lock the row for update to prevent race conditions
            savings = SavingsAccount.objects.select_for_update().get(id=savings.id)

            principal = Decimal(str(loan.principal_amount))

            # Update loan status
            loan.status = 'approved'
            loan.is_active = True
            if not loan.disbursed_date:
                loan.disbursed_date = timezone.now().date()
            loan.save()

            # Generate schedule if missing
            if not loan.installments.exists():
                generate_schedule(loan)

            # ---- Disburse to savings ----
            savings.balance += principal
            savings.save()

            # ---- Create transaction with member ----
            ref = generate_transaction_ref("DSB")
            Transaction.objects.create(
                member=loan.member,
                amount=principal,
                type='disbursement',
                reference=ref,
                timestamp=timezone.now(),
                created_by=request.user,
            )

            messages.success(
                request,
                f"Loan {loan.id} approved successfully. Reference {ref}: UGX {principal:,.0f} disbursed to savings."
            )

        except Exception as e:
            messages.error(request, f"Error during approval: {str(e)}")
            return redirect('loan_detail', pk=loan.id)

    elif action == 'reject':
        if loan.status != 'pending':
            messages.error(request, "Only pending loans can be rejected.")
            return redirect('loan_detail', pk=loan.id)

        loan.status = 'rejected'
        loan.is_active = False
        loan.save()
        messages.warning(request, f"Loan {loan.id} has been rejected.")

    return redirect('loan_detail', pk=loan.id)

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Member, SavingsAccount, SystemSetting, Loan
from .services import FinancialTransactionService # Ensure this is created
from .utils import generate_transaction_ref


# finance/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import uuid
import logging

from .models import Member, Loan, SystemSetting, Transaction, SavingsAccount
from .services import FinancialTransactionService, process_repayment, generate_transaction_ref

logger = logging.getLogger(__name__)


# finance/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import logging

from .models import Member, Loan, SystemSetting, Transaction, SavingsAccount, Installment
from .services import FinancialTransactionService, process_repayment, generate_transaction_ref

logger = logging.getLogger(__name__)

# finance/views.py

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone

from .models import (
    Member, SavingsAccount, Transaction, SystemSetting, 
    Company, Loan, Installment
)
from .services import (
    FinancialTransactionService, 
    generate_transaction_ref, 
    process_repayment
)

# finance/views.py

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone

from .models import (
    Member, SavingsAccount, Transaction, SystemSetting, 
    Company, Loan, Installment
)
from .services import (
    FinancialTransactionService, 
    generate_transaction_ref, 
    process_repayment
)


# ============================================================
# RECEIPT VIEW (new)
# ============================================================

@login_required
def view_receipt(request):
    """
    Display the receipt stored in session.
    Expects 'deposit_receipt' or 'withdrawal_receipt' in session.
    """
    receipt = request.session.get('deposit_receipt') or request.session.get('withdrawal_receipt')
    
    if not receipt or not receipt.get('show'):
        messages.warning(request, "No receipt to display.")
        return redirect('dashboard')  # fallback URL
    
    # Clear the session flag after displaying
    if 'deposit_receipt' in request.session:
        del request.session['deposit_receipt']
    if 'withdrawal_receipt' in request.session:
        del request.session['withdrawal_receipt']
    
    context = {
        'receipt': receipt['data'],
        'company': Company.get_company(),  # ensure this method exists
    }
    return render(request, 'finance/receipt.html', context)


# ============================================================
# DEPOSIT VIEW – FULL COPY‑PASTE (with mobile money support)
# ============================================================
# Add these imports at the top of finance/views.py if not already present

import re
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone

from .models import Member, SavingsAccount, Transaction, Loan, SystemSetting
from .services import process_repayment, generate_transaction_ref
from hardware.marzpay import initiate_collection   # Adjust if your marzpay is elsewhere


# ============================================================
# HELPER: Normalize phone number to international format
# ============================================================
def normalize_phone(phone):
    """
    Convert a local Ugandan phone number to international format.
    Examples:
        '0700123456'  -> '+256700123456'
        '700123456'   -> '+256700123456'
        '256700123456' -> '+256700123456'
        '+256700123456' -> '+256700123456'
    """
    if not phone:
        return ''
    # Remove spaces, dashes, parentheses, dots
    phone = re.sub(r'[\s\-\(\)\.]', '', phone)
    # If it starts with '0', replace with +256
    if phone.startswith('0'):
        phone = '+256' + phone[1:]
    # If it starts with '256' (without +), add +
    elif phone.startswith('256') and not phone.startswith('+'):
        phone = '+' + phone
    # If no '+' at all, assume Uganda
    elif not phone.startswith('+'):
        phone = '+256' + phone
    return phone


# ============================================================
# DEPOSIT SAVINGS VIEW (Cash + Mobile Money)
# ============================================================
# finance/views.py – full deposit_savings view (fixed)

import re
import json
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone

from .models import Member, SavingsAccount, Transaction, Loan, SystemSetting
from .services import process_repayment, generate_transaction_ref
from hardware.marzpay import initiate_collection


def normalize_phone(phone):
    if not phone:
        return ''
    phone = re.sub(r'[\s\-\(\)\.]', '', phone)
    if phone.startswith('0'):
        phone = '+256' + phone[1:]
    elif phone.startswith('256') and not phone.startswith('+'):
        phone = '+' + phone
    elif not phone.startswith('+'):
        phone = '+256' + phone
    return phone


@login_required
@transaction.atomic
def deposit_savings(request, member_id):
    member = get_object_or_404(Member, id=member_id)
    backdate_allowed = SystemSetting.is_backdate_allowed()
    savings, _ = SavingsAccount.objects.get_or_create(member=member)
    previous_balance = savings.balance

    if request.method == "POST":
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            amount_raw = data.get('amount', '0')
            payment_method = data.get('payment_method', 'CASH')
            phone_number = data.get('phone_number', '').strip()
            custom_date = data.get('back_date')
        else:
            amount_raw = request.POST.get('amount', '0').strip()
            payment_method = request.POST.get('payment_method', 'CASH')
            phone_number = request.POST.get('phone_number', '').strip()
            custom_date = request.POST.get('back_date')

        try:
            amount = Decimal(amount_raw).quantize(Decimal('1.00'), rounding=ROUND_HALF_UP)
        except (ValueError, InvalidOperation):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Invalid amount.'})
            messages.error(request, "Invalid amount.")
            return redirect('deposit_savings', member_id=member.id)

        if amount <= 0:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Amount must be greater than zero.'})
            messages.error(request, "Amount must be greater than zero.")
            return redirect('deposit_savings', member_id=member.id)

        # ================================================================
        # CASH DEPOSIT (immediate)
        # ================================================================
        if payment_method == 'CASH':
            ref = generate_transaction_ref("DEP")
            txn_timestamp = custom_date if (backdate_allowed and custom_date) else timezone.now()

            transaction_obj = Transaction.objects.create(
                member=member,
                amount=amount,
                type='deposit',
                reference=ref,
                timestamp=txn_timestamp,
                created_by=request.user,
                payment_method='CASH',
                status='completed'
            )

            savings.balance += amount
            savings.save()

            arrears_cleared = Decimal('0')
            active_loan = Loan.objects.filter(member=member, is_active=True).first()
            if active_loan:
                overdue_inst = active_loan.installments.filter(paid=False, due_date__lte=timezone.now().date())
                if overdue_inst.exists():
                    process_repayment(active_loan.id)
                    arrears_cleared = amount

            receipt_data = {
                'receipt_id': ref,
                'date': txn_timestamp.strftime('%d %b, %Y %H:%M'),
                'member_name': f"{member.first_name} {member.last_name}",
                'member_id': str(member.member_number or member.id),
                'member_pk': member.id,
                'processed_by': request.user.get_full_name() or request.user.username,
                'amount': str(amount),
                'prev_balance': str(previous_balance),
                'new_balance': str(savings.balance),
                'arrears_cleared': str(arrears_cleared),
                'payment_method': 'Cash Deposit',
                'status': 'COMPLETED',
                'type': 'deposit',
                'timestamp': txn_timestamp.isoformat(),
                'description': 'Savings Deposit' + (' (with auto-repayment)' if arrears_cleared > 0 else ''),
            }
            request.session['deposit_receipt'] = {'data': receipt_data, 'show': True}
            request.session.modified = True
            messages.success(request, f"Deposit {ref} of UGX {amount:,.0f} processed successfully.")
            return redirect('view_receipt')

        # ================================================================
        # MOBILE MONEY DEPOSIT (pending) – FIXED with UUID
        # ================================================================
        elif payment_method == 'MOBILE_MONEY':
            if not phone_number:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'Phone number is required.'})
                messages.error(request, "Phone number is required for mobile money.")
                return redirect('deposit_savings', member_id=member.id)

            phone_number = normalize_phone(phone_number)

            # --- Use a valid UUID as reference ---
            ref = str(uuid.uuid4())

            transaction_obj = Transaction.objects.create(
                member=member,
                amount=amount,
                type='deposit',
                reference=ref,
                timestamp=timezone.now(),
                created_by=request.user,
                payment_method='MOBILE_MONEY',
                phone_number=phone_number,
                status='pending',
            )

            try:
                response = initiate_collection(
                    phone_number=phone_number,
                    amount=amount,
                    reference=ref,
                    description=f"Deposit to {member.get_full_name()} - {ref}",
                    metadata={"member_id": str(member.id), "transaction_ref": ref}
                )
                transaction_obj.payment_reference = response.get('transaction_id') or response.get('id')
                transaction_obj.marzpay_response = response
                transaction_obj.save()

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'pending',
                        'transaction_id': str(transaction_obj.id),
                        'reference': ref,
                        'message': 'Payment initiated. Please confirm on your phone.'
                    })
                messages.info(request, "Payment initiated. Please confirm on your phone.")
                return redirect('deposit_savings', member_id=member.id)

            except Exception as e:
                transaction_obj.delete()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': str(e)})
                messages.error(request, f"Mobile money initiation failed: {str(e)}")
                return redirect('deposit_savings', member_id=member.id)

        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Invalid payment method.'})
            messages.error(request, "Invalid payment method.")
            return redirect('deposit_savings', member_id=member.id)

    return render(request, 'finance/deposit.html', {
        'member': member,
        'backdate_allowed': backdate_allowed,
        'savings_balance': savings.balance,
    })
# ============================================================
# WITHDRAWAL VIEW
# ============================================================

@login_required
@transaction.atomic
def withdraw_savings(request, member_id):
    """
    Handles member withdrawals with atomic ledger updates.
    """
    member = get_object_or_404(Member, id=member_id)
    savings = SavingsAccount.objects.select_for_update().get_or_create(member=member)[0]
    backdate_allowed = SystemSetting.is_backdate_allowed()
    previous_balance = savings.balance  # capture before withdrawal

    if request.method == 'POST':
        amount_raw = request.POST.get('amount', '0').strip()
        custom_date = request.POST.get('back_date')
        
        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                messages.error(request, "Withdrawal amount must be greater than zero.")
            elif savings.balance < amount:
                messages.error(request, f"Insufficient funds. Current balance: UGX {savings.balance:,.0f}")
            else:
                ref = generate_transaction_ref("WTH")
                txn_timestamp = custom_date if (backdate_allowed and custom_date) else timezone.now()

                # Delegate to the Service Layer for Ledger integrity
                FinancialTransactionService.record_withdrawal(
                    member=member,
                    amount=amount,
                    reference=ref,
                    date=txn_timestamp
                )

                # Refresh to get new balance
                member.refresh_from_db()
                new_balance = member.savings.balance if hasattr(member, 'savings') else Decimal('0')

                # Prepare receipt data
                receipt_data = {
                    'receipt_id': ref,
                    'date': txn_timestamp.strftime('%d %b, %Y %H:%M'),
                    'member_name': f"{member.first_name} {member.last_name}",
                    'member_id': str(member.member_number or member.id),
                    'member_pk': member.id,
                    'processed_by': request.user.get_full_name() or request.user.username,
                    'amount': str(amount),
                    'prev_balance': str(previous_balance),
                    'new_balance': str(new_balance),
                    'arrears_cleared': '0',   # no arrears cleared on withdrawal
                    'payment_method': 'Cash Withdrawal',
                    'status': 'COMPLETED',
                    'type': 'withdrawal',
                    'timestamp': txn_timestamp.isoformat(),
                    'description': 'Savings Withdrawal',
                }

                # Store receipt in session
                request.session['withdrawal_receipt'] = {
                    'data': receipt_data,
                    'show': True
                }
                request.session.modified = True

                messages.success(request, f"Withdrawal {ref} of UGX {amount:,.0f} successful.")
                # Redirect to receipt view
                return redirect('view_receipt')

        except Exception as e:
            messages.error(request, f"Error processing withdrawal: {str(e)}")

    return render(request, 'finance/withdraw_form.html', {
        'member': member,
        'savings': savings,
        'backdate_allowed': backdate_allowed
    })


@login_required
def member_statement(request, member_id):
    """Detailed individual ledger statement"""
    member = get_object_or_404(Member, id=member_id)
    transactions = Transaction.objects.filter(member=member).order_by('-timestamp')
    savings = SavingsAccount.objects.filter(member=member).first()
    
    return render(request, 'finance/statement.html', {
        'member': member,
        'transactions': transactions,
        'savings': savings
    })



@login_required
def arrears_report(request):
    """Portfolio at Risk (PAR) Report"""
    today = timezone.now().date()
    overdue_installments = Installment.objects.filter(
        paid=False, 
        due_date__lt=today
    ).select_related('loan__member').order_by('due_date')

    total_at_risk = overdue_installments.aggregate(
        total_sum=Sum(F('principal_portion') + F('interest_portion') + F('penalty_amount'))
    )['total_sum'] or 0

    return render(request, 'finance/arrears.html', {
        'overdue': overdue_installments,
        'total_at_risk': total_at_risk,
        'today': today
    })
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from .models import Loan
from members.models import Member
from .models import SavingsAccount # Assuming this is your savings model path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from .models import Member, Loan

import string
import random
from django.contrib.auth.decorators import login_required

import string
import random
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import Member, Loan

import string
import random
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import Member, Loan

def generate_loan_ref(length=10):
    """Generates a random uppercase alphanumeric string"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from decimal import Decimal
from .models import Loan, Member
# Ensure you have your generate_loan_ref helper imported



from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Loan



from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from .models import Loan, Repayment
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from .models import Loan, Repayment, SavingsAccount

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from .models import Loan, Repayment, SavingsAccount

from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from decimal import Decimal

from .models import Loan, SavingsAccount


from decimal import Decimal
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.db.models import Sum

from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.db.models import Sum
from dateutil.relativedelta import relativedelta   # Add this if not installed: pip install python-dateutil

from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import Loan, ManualPenalty
from .utils import generate_schedule
from finance.penalties import calculate_penalty

from decimal import Decimal
from datetime import timedelta
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import Loan, ManualPenalty
from .utils import generate_schedule
from finance.penalties import calculate_penalty

@login_required
def loan_detail(request, pk):
    """
    Comprehensive loan detail view – displays full financial summary,
    amortization schedule with combined penalties, manual penalties list,
    and repayment history.
    """
    loan = get_object_or_404(Loan.objects.select_related('member', 'officer'), pk=pk)
    today = timezone.now().date()

    # ---- 1. Generate schedule if missing ----
    if not loan.installments.exists():
        generate_schedule(loan)

    # ---- 2. Compute due amounts for the banner ----
    active_due = loan.installments.filter(paid=False, due_date__lte=today).aggregate(
        total_interest=Sum('interest_portion'),
        total_principal=Sum('principal_portion')
    )
    interest_due = active_due['total_interest'] or Decimal('0.00')
    principal_due = active_due['total_principal'] or Decimal('0.00')
    total_due_now = (interest_due + principal_due).quantize(Decimal('0.01'))

    # ---- 3. Total paid & total payable ----
    total_paid = loan.repayments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
    total_payable = loan.total_payable or Decimal('0')

    # ---- 4. Dates ----
    disbursement_date = loan.disbursed_date or loan.start_date
    term_value = getattr(loan, 'term_value', 0)
    frequency = getattr(loan, 'repayment_frequency', 'monthly')
    period_months = getattr(loan, 'period_months', 0)

    # Compute end date based on repayment frequency
    if disbursement_date and term_value > 0:
        if frequency == 'monthly':
            end_date = disbursement_date + relativedelta(months=term_value)
        elif frequency == 'weekly':
            end_date = disbursement_date + timedelta(weeks=term_value)
        elif frequency == 'daily':
            end_date = disbursement_date + timedelta(days=term_value)
        else:  # manual or fallback
            if period_months:
                end_date = disbursement_date + relativedelta(months=period_months)
            else:
                end_date = None
    else:
        end_date = None

    # ---- 5. Build schedule_data (combines calculated + manual penalties) ----
    schedule_data = []
    for inst in loan.installments.all().order_by('due_date'):
        calc_penalty = calculate_penalty(inst) or Decimal('0.00')
        manual_total = inst.manual_penalties.filter(is_waived=False).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        total_penalty = calc_penalty + manual_total

        principal_bal = inst.principal_balance
        interest_bal = inst.interest_balance
        total_balance = principal_bal + interest_bal + total_penalty

        schedule_data.append({
            'id': inst.id,
            'due_date': inst.due_date,
            'principal_portion': inst.principal_portion,
            'interest_portion': inst.interest_portion,
            'penalty_amount': total_penalty,
            'balance': total_balance,
            'paid': inst.paid,
            'is_overdue': inst.is_overdue,
        })

    # ---- 6. Manual penalties (active, not waived) ----
    manual_penalties = loan.manual_penalties.filter(is_waived=False).order_by('-applied_date')
    total_manual_penalty = manual_penalties.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # ---- 7. Recent repayments ----
    repayments = loan.repayments.all().order_by('-date_paid')[:10]

    # ---- 8. Additional context (savings, address) ----
    savings_balance = getattr(loan.member, 'savings', None)
    savings_balance = savings_balance.balance if savings_balance else Decimal('0.00')
    member = loan.member
    member_address = f"{member.village}, {member.parish}, {member.district}".strip(', ')

    # ---- 9. Build context ----
    context = {
        'loan': loan,
        'principal_balance': loan.principal_balance,
        'interest_balance': loan.interest_balance,
        'interest_due': interest_due,
        'principal_due': principal_due,
        'total_due_now': total_due_now,
        'schedule_data': schedule_data,
        'repayments': repayments,
        'total_paid': total_paid.quantize(Decimal('0.01')),
        'total_payable': total_payable,
        'disbursement_date': disbursement_date,
        'end_date': end_date,
        'today': today,
        'manual_penalties': manual_penalties,
        'total_manual_penalty': total_manual_penalty,
        'savings_balance': savings_balance,
        'member_address': member_address,
        'officer': loan.officer,
        'period_months': period_months,  # fallback value
    }

    return render(request, 'finance/loan_detail.html', context)

from django.shortcuts import render
from django.db.models import Sum
from .models import Loan

def loan_list(request):
    """Master Loan Registry with split-balance analytics"""
    loans = Loan.objects.select_related('member').all().order_by('-id')
    total_disbursed = loans.aggregate(Sum('principal_amount'))['principal_amount__sum'] or 0
    
    portfolio_stats = loans.aggregate(
        p_total=Sum('principal_balance'),
        i_total=Sum('interest_balance')
    )
    total_outstanding = (portfolio_stats['p_total'] or 0) + (portfolio_stats['i_total'] or 0)
    active_count = loans.filter(is_active=True).count()

    context = {
        'loans': loans,
        'total_disbursed': total_disbursed,
        'total_outstanding': total_outstanding,
        'active_count': active_count,
    }
    return render(request, 'finance/loan_list.html', context)

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from .models import Loan, Repayment

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from decimal import Decimal

import decimal
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from .models import Member, Loan, Repayment

from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import ValidationError

from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import ValidationError

from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from.utils import generate_transaction_ref

@login_required
@transaction.atomic
def receive_payment(request, loan_id):
    if request.method != "POST":
        return redirect('loan_detail', pk=loan_id)

    loan = get_object_or_404(Loan.objects.select_for_update(), id=loan_id)
    
    # Permission check: Only staff can backdate, and only if global setting is ON
    backdate_allowed = SystemSetting.is_backdate_allowed()

    if loan.status not in ['approved', 'arrears']:
        messages.error(request, "Repayments are only accepted for active loans.")
        return redirect('loan_detail', pk=loan_id)

    try:
        current_balance = Decimal(str(loan.principal_balance + loan.interest_balance))
        if current_balance <= 0:
            messages.warning(request, "This loan is already fully paid.")
            return redirect('loan_detail', pk=loan_id)

        # Get form data
        principal = Decimal(request.POST.get('principal', '0').strip() or '0')
        interest = Decimal(request.POST.get('interest', '0').strip() or '0')
        penalty = Decimal(request.POST.get('penalty', '0').strip() or '0')
        custom_date = request.POST.get('back_date')
        notes = request.POST.get('notes', '').strip()

        total_payment = principal + interest + penalty

        if total_payment <= 0:
            messages.error(request, "Total payment must be greater than zero.")
            return redirect('loan_detail', pk=loan_id)

        # Determine Payment Date
        txn_timestamp = timezone.now()
        if backdate_allowed and custom_date:
            txn_timestamp = custom_date

        ref = generate_transaction_ref("PAY")

        # ✅ Create ONLY the Repayment – it will handle Transaction & Ledger
        # The Repayment.save() method already creates a Transaction and posts ledger entries.
        # Do NOT create a Transaction manually here – it would cause duplication.
        Repayment.objects.create(
            loan=loan,
            amount_paid=total_payment,
            receipt_number=ref,
            date_paid=txn_timestamp, 
            notes=notes if notes else None,
        )

        # ❌ REMOVED: Manual Transaction.objects.create – it's duplicated inside Repayment.save()
        # Transaction.objects.create(...)   <-- DELETE THIS LINE

        messages.success(request, f"Payment {ref} recorded and allocated successfully.")

    except (ValueError, InvalidOperation):
        messages.error(request, "Invalid payment amounts entered.")
    except Exception as e:
        messages.error(request, f"Error processing payment: {str(e)}")

    return redirect('loan_detail', pk=loan_id)

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from .models import Loan, Transaction, SavingsAccount


from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from .utils import send_bulk_arrears_reminders


@login_required
def reject_loan(request, loan_id):
    """
    Rejects a pending loan application.
    """
    loan = get_object_or_404(Loan, id=loan_id)
    if loan.status == 'pending':
        loan.status = 'rejected'
        loan.is_active = False
        loan.save()
        messages.error(request, f"Loan application #LN-{loan.id} has been rejected.")
    else:
        messages.warning(request, "Only pending loans can be rejected.")
        
    return redirect('member_profile', member_id=loan.member.id)



from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from .utils import send_bulk_arrears_reminders


@login_required
def bulk_sms_reminder_view(request):
    """Bulk send arrears reminders"""
    sent, failed = send_bulk_arrears_reminders(request)

    if sent > 0:
        messages.success(request, f"Successfully sent {sent} arrears reminders.")
    if failed > 0:
        messages.warning(request, f"Failed to send {failed} reminders.")
    if sent == 0 and failed == 0:
        messages.info(request, "No members with arrears were found.")

    return redirect('arrears_report')   # Change to your preferred redirect



from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from .models import SavingsAccount, Transaction, Member
from decimal import Decimal, ROUND_HALF_UP

from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from .models import Member, SavingsAccount, Transaction, SystemSetting
# Assuming these utility functions exist in your project
# from .utils import generate_transaction_ref 


# finance/views.py
from django.shortcuts import render
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q
from django.db.models.functions import Coalesce
from datetime import datetime
from dateutil.relativedelta import relativedelta
from .models import Loan, Member, SavingsAccount, Transaction, Installment, Repayment, ChartOfAccount
from django.contrib.auth.decorators import login_required

from django.shortcuts import render
from django.db.models import Sum, F, Q
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date
from .models import Loan, SavingsAccount, Transaction, Installment


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from finance.models import (
    Loan, Installment, SavingsAccount, Company
)

@login_required
def reports_dashboard(request):
    """
    Central Reports Dashboard – Financial Intelligence.
    Computes real-time KPIs from the database.
    """
    today = timezone.now().date()
    company = Company.get_company()

    # ============================================================
    # 1. Gross Loan Portfolio (active loans only)
    # ============================================================
    loan_stats = Loan.objects.filter(is_active=True).aggregate(
        p_bal=Sum('principal_balance'),
        i_bal=Sum('interest_balance')
    )
    total_loan_portfolio = (loan_stats['p_bal'] or 0) + (loan_stats['i_bal'] or 0)

    # ============================================================
    # 2. Active Loan Accounts
    # ============================================================
    active_loans_count = Loan.objects.filter(is_active=True).count()

    # ============================================================
    # 3. Portfolio at Risk (PAR > 30 days)
    # ============================================================
    cutoff_date = today - timedelta(days=30)
    overdue_installments = Installment.objects.filter(
        loan__is_active=True,
        due_date__lt=cutoff_date,
        paid=False
    )

    # Sum the outstanding balance across overdue installments
    # Using the same formula as Installment.balance property
    par_30_balance = overdue_installments.aggregate(
        total=Coalesce(
            Sum(
                F('principal_portion') - F('principal_paid') +
                F('interest_portion') - F('interest_paid') +
                F('penalty_amount') - F('penalty_paid')
            ),
            Value(Decimal('0.00'), output_field=DecimalField())
        )
    )['total'] or 0

    if total_loan_portfolio > 0:
        par_30 = (par_30_balance / total_loan_portfolio) * 100
    else:
        par_30 = 0

    # ============================================================
    # 4. PAR Change (month-over-month) – placeholder (0 for now)
    # ============================================================
    par_change = 0

    # ============================================================
    # 5. Liquidity Ratio (proxy: total savings / total loans)
    # ============================================================
    total_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or 0

    if total_loan_portfolio > 0:
        liquidity_ratio = (total_savings / total_loan_portfolio) * 100
    else:
        liquidity_ratio = 0

    # ============================================================
    # 6. Context – ready for the template
    # ============================================================
    context = {
        'par_30': par_30,
        'par_change': par_change,
        'liquidity_ratio': liquidity_ratio,
        'active_loans_count': active_loans_count,
        'total_loan_portfolio': total_loan_portfolio,
        'company': company,
        'today': today,
    }

    return render(request, 'finance/reports/reports_dashboard.html', context)


from django.db.models import Sum, F
from decimal import Decimal
from decimal import Decimal
from django.shortcuts import render
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from datetime import date
from django.contrib.auth.models import User

def loan_portfolio_report(request):
    """Fixed Loan Portfolio Report"""

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    officer_id = request.GET.get('officer')

    # Base Query
    loans = Loan.objects.select_related('member', 'officer').filter(
        status__in=['approved', 'active', 'closed']
    ).order_by('-disbursed_date', '-start_date')

    # Apply filters
    if start_date:
        loans = loans.filter(disbursed_date__gte=start_date)
    if end_date:
        loans = loans.filter(disbursed_date__lte=end_date)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    today = date.today()
    report_data = []

    for loan in loans:
        p_bal = Decimal(str(loan.principal_balance or 0))
        i_bal = Decimal(str(loan.interest_balance or 0))

        # Arrears (overdue)
        overdue = loan.installments.filter(paid=False, due_date__lt=today)
        principal_in_arrears = overdue.aggregate(
            total=Coalesce(Sum('principal_portion'), Decimal('0'))
        )['total']

        # Total Due (including today)
        total_due_today = loan.installments.filter(
            paid=False, due_date__lte=today
        ).aggregate(
            total=Coalesce(Sum(F('principal_portion') + F('interest_portion')), Decimal('0'))
        )['total']

        penalty_due = overdue.aggregate(
            total=Coalesce(Sum('penalty_amount'), Decimal('0'))
        )['total']

        report_data.append({
            'borrower': f"{loan.member.first_name} {loan.member.last_name}",
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
            'account_number': loan.member.member_number,
            'contact': loan.member.phone_number,
            'loan_disbursed': Decimal(str(loan.principal_amount or 0)),
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'principal_balance': p_bal,
            'interest_balance': i_bal,
            'principal_in_arrears': principal_in_arrears,
            'total_dues': total_due_today + penalty_due,
            'par': p_bal if principal_in_arrears > 0 else Decimal('0'),
        })

    # ====================== CALCULATE TOTALS ======================
    total_disbursed = sum(item['loan_disbursed'] for item in report_data)
    total_outstanding = sum(item['principal_balance'] + item['interest_balance'] for item in report_data)
    total_par = sum(item['par'] for item in report_data)

    context = {
        'report_data': report_data,
        'today': today,
        'officers': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),

        # Summary Cards
        'total_disbursed': total_disbursed,
        'total_outstanding': total_outstanding,
        'total_par': total_par,

        # For backward compatibility with your old template if needed
        'total_p_bal': sum(item['principal_balance'] for item in report_data),
    }

    return render(request, 'finance/reports/loan_portfolio.html', context)

from django.db.models import Sum, Q, F
from decimal import Decimal
from datetime import date
from django.shortcuts import render
from django.db.models import Sum, F
from django.utils import timezone
from decimal import Decimal
from .models import Loan, Installment # Ensure User is imported if using for officers

from decimal import Decimal
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import Coalesce


def calculate_aging(loan, today):
    """Determines classification based on days past due (DPD)"""
    oldest_unpaid = loan.installments.filter(paid=False, due_date__lt=today).order_by('due_date').first()
    if not oldest_unpaid:
        return "Performing"
    
    days_past_due = (today - oldest_unpaid.due_date).days
    if days_past_due <= 30: return "Watch"
    if days_past_due <= 90: return "Substandard"
    if days_past_due <= 180: return "Doubtful"
    return "Loss"
# ====================================================================
# SAVINGS ACCOUNTS REPORT
# ====================================================================
@login_required
def savings_accounts_report(request):
    """
    A list of Savings accounts and balances.
    Columns: Product, Status, Available Balance, Account No, Name,
    Last Transaction Date, Open Date, Closed Date, Actual Balance,
    Email, Phone, Savings Officer.
    """
    # ---- 1. Get filters ----
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    search_query = request.GET.get('search_query') or request.POST.get('search_query')

    # ---- 2. Base queryset ----
    savings_accounts = SavingsAccount.objects.select_related('member').all()

    # ---- 3. Apply filters ----
    if date_from:
        savings_accounts = savings_accounts.filter(member__date_joined__gte=date_from)
    if date_to:
        savings_accounts = savings_accounts.filter(member__date_joined__lte=date_to)
    if officer_id:
        # Assuming officer is stored on Member or UserProfile? Use loan officer as proxy.
        savings_accounts = savings_accounts.filter(
            member__loans__officer_id=officer_id
        ).distinct()
    if search_query:
        savings_accounts = savings_accounts.filter(
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(member__member_number__icontains=search_query) |
            Q(member__phone_number__icontains=search_query)
        )

    # ---- 4. Build data ----
    data = []
    total_balance = Decimal('0.00')

    for savings in savings_accounts:
        member = savings.member

        # ---- Last transaction date ----
        last_tx = Transaction.objects.filter(member=member).order_by('-timestamp').first()
        last_tx_date = last_tx.timestamp.date() if last_tx else None

        # ---- Status (active if balance > 0, else inactive) ----
        status = 'Active' if savings.balance > 0 else 'Inactive'

        # ---- Product (placeholder – can be extended with a SavingsProduct model) ----
        product = 'Savings'  # or get from savings.product_type if exists

        # ---- Savings Officer (use loan officer as proxy, or first loan's officer) ----
        officer = member.loans.first().officer if member.loans.exists() else None
        officer_name = officer.get_full_name() if officer else 'N/A'

        row = {
            'account_no': savings.account_number or member.member_number,
            'name': member.get_full_name(),
            'last_transaction_date': last_tx_date,
            'open_date': member.date_joined,
            'closed_date': None,  # no closed date on SavingsAccount, set if exists
            'actual_balance': savings.balance,
            'available_balance': savings.balance,  # same as actual
            'email': member.email or 'N/A',
            'phone': member.phone_number,
            'officer': officer_name,
            'status': status,
            'product': product,
        }
        data.append(row)
        total_balance += savings.balance

    # ---- 5. KPI cards ----
    kpi_cards = [
        {'icon': 'bi-wallet2', 'value': f'{len(data):,}', 'label': 'Total Accounts', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_balance:,.0f}', 'label': 'Total Balance', 'type': 'success'},
        {'icon': 'bi-people', 'value': f'{len(set(item["officer"] for item in data if item["officer"] != "N/A"))}', 'label': 'Active Officers', 'type': 'secondary'},
    ]

    # ---- 6. Summary totals ----
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_balance,
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    # ---- 7. Totals for table footer ----
    totals = {
        'available_balance': total_balance,
        'actual_balance': total_balance,
    }

    # ---- 8. Columns ----
    all_columns = [
        {'key': 'product', 'label': 'Product', 'align': 'left'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'available_balance', 'label': 'Available Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'account_no', 'label': 'Account No', 'align': 'left'},
        {'key': 'name', 'label': 'Name', 'align': 'left'},
        {'key': 'last_transaction_date', 'label': 'Last Transaction Date', 'align': 'center', 'type': 'date'},
        {'key': 'open_date', 'label': 'Open Date', 'align': 'center', 'type': 'date'},
        {'key': 'closed_date', 'label': 'Closed Date', 'align': 'center', 'type': 'date'},
        {'key': 'actual_balance', 'label': 'Actual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'email', 'label': 'Email', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'officer', 'label': 'Savings Officer', 'align': 'left'},
    ]

    # ---- 9. Column selection ----
    selected_keys = get_selected_columns(request, 'savings_accounts', all_columns)
    columns = [col for col in all_columns if col['key'] in selected_keys]

    # ---- 10. Context ----
    context = _get_base_context(request, {
        'report_title': 'Savings Accounts Report',
        'report_type': 'savings_accounts',
        'columns': columns,
        'all_columns': all_columns,
        'selected_column_keys': selected_keys,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
        'search_query': search_query,
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)
def savings_report(request):
    """Savings Report"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    txs = Transaction.objects.select_related('member')

    if start_date:
        txs = txs.filter(timestamp__date__gte=start_date)
    if end_date:
        txs = txs.filter(timestamp__date__lte=end_date)

    total_deposits = txs.filter(type='deposit').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    total_withdrawals = txs.filter(type='withdrawal').aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    current_total_savings = SavingsAccount.objects.aggregate(Sum('balance'))['balance__sum'] or Decimal('0')

    context = {
        'transactions': txs.order_by('-timestamp'),
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'current_total_savings': current_total_savings,
        'net_movement': total_deposits - total_withdrawals,
    }

    return render(request, 'finance/reports/savings_report.html', context)


from django.shortcuts import render
from django.db.models import Sum, Q
from decimal import Decimal

from django.shortcuts import render
from django.db.models import Sum
from decimal import Decimal
from .models import Transaction  # Ensure your imports are correct
from django.shortcuts import render
from django.db.models import Sum
from decimal import Decimal
from .models import Transaction

def cash_flow_statement(request):
    """
    Cash Flow Statement using double-entry paths:
    Transaction -> GeneralLedger -> ChartOfAccount
    """
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # 1. Filter Transactions by type
    inflow_qs = Transaction.objects.filter(type__in=['deposit', 'repayment'])
    outflow_qs = Transaction.objects.filter(type__in=['withdrawal', 'disbursement'])

    # 2. Apply Date Filters
    if start_date:
        inflow_qs = inflow_qs.filter(timestamp__date__gte=start_date)
        outflow_qs = outflow_qs.filter(timestamp__date__gte=start_date)
    if end_date:
        inflow_qs = inflow_qs.filter(timestamp__date__lte=end_date)
        outflow_qs = outflow_qs.filter(timestamp__date__lte=end_date)

    # 3. Calculate Summary Totals
    total_inflows = inflow_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_outflows = outflow_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    net_cash_flow = total_inflows - total_outflows

    # 4. Group by ChartOfAccount via GeneralLedger
    # We use the full path: generalledger__account__name
    inflow_accounts = inflow_qs.values(
        'generalledger__account__code', 
        'generalledger__account__name'
    ).annotate(
        total_amount=Sum('amount')
    ).order_by('-total_amount')

    outflow_accounts = outflow_qs.values(
        'generalledger__account__code', 
        'generalledger__account__name'
    ).annotate(
        total_amount=Sum('amount')
    ).order_by('-total_amount')

    context = {
        'total_inflows': total_inflows,
        'total_outflows': total_outflows,
        'net_cash_flow': net_cash_flow,
        'inflow_accounts': inflow_accounts,
        'outflow_accounts': outflow_accounts,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'finance/reports/cash_flow.html', context)


def chart_of_accounts(request):
    """Chart of Accounts"""
    from .models import ChartOfAccount
    accounts = ChartOfAccount.objects.filter(is_active=True).order_by('code')
    
    context = {'accounts': accounts}
    return render(request, 'finance/reports/chart_of_accounts.html', context)



from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from .models import Transaction, TransactionReversal, SavingsAccount

@login_required
@transaction.atomic
def reverse_transaction(request, transaction_id):
    # 1. Permission Check
    if not request.user.is_staff:
        messages.error(request, "You do not have permission to reverse transactions.")
        return redirect('dashboard')

    # 2. Get Transaction with Row-Level Locking
    txn = get_object_or_404(Transaction.objects.select_for_update(), id=transaction_id)
    
    if txn.is_reversed:
        messages.warning(request, "This transaction has already been reversed.")
        return redirect('member_profile', member_id=txn.member.id)

    if request.method == "POST":
        reason = request.POST.get('reason')
        if not reason:
            messages.error(request, "A reason for reversal is required.")
            return render(request, 'finance/reverse_confirm.html', {'txn': txn})

        # 3. Update Member Savings Balance
        savings = get_object_or_404(SavingsAccount.objects.select_for_update(), member=txn.member)
        
        # Determine the contra-type based on the original transaction
        # If they deposited, we must "withdraw" to fix balance, and vice-versa.
        if txn.type == 'deposit':
            savings.balance -= txn.amount
            contra_type = 'withdrawal'
        elif txn.type == 'withdrawal':
            savings.balance += txn.amount
            contra_type = 'deposit'
        else:
            # Handle other types like 'repayment' or 'penalty' if necessary
            messages.error(request, f"Reversal for type {txn.type} not configured.")
            return redirect('member_profile', member_id=txn.member.id)
        
        savings.save()

        # 4. Mark original transaction as reversed
        txn.is_reversed = True
        txn.save()

        # 5. Create the Contra-Entry (The "Correction" Transaction)
        # Note: We removed 'notes' because it's not in your model.
        # We use your existing choices ('deposit'/'withdrawal') for the type.
        Transaction.objects.create(
            member=txn.member,
            amount=txn.amount,
            type=contra_type, 
            reference=f"REV-{txn.id}",
            created_by=request.user
        )

        # 6. Create the Audit Log (The 'reason' is stored here)
        TransactionReversal.objects.create(
            original_transaction=txn,
            reversed_by=request.user,
            reason=reason
        )

        messages.success(request, f"Transaction reversed successfully. Balance updated.")
        return redirect('member_profile', member_id=txn.member.id)

    return render(request, 'finance/reverse_confirm.html', {'txn': txn})



from django.shortcuts import render, get_object_or_404
from .models import Loan, Transaction
from decimal import Decimal
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from .models import Loan, Transaction, ManualPenalty
from .utils import generate_schedule
from finance.penalties import calculate_penalty

@login_required
def loan_details(request, loan_id):
    """
    Comprehensive loan detail view – provides full financial summary,
    amortization schedule with combined penalties, manual penalties list,
    and recent repayment transactions.
    """
    loan = get_object_or_404(Loan.objects.select_related('member', 'officer'), id=loan_id)
    today = timezone.now().date()

    # 1. Generate schedule if missing
    if not loan.installments.exists():
        generate_schedule(loan)

    # 2. Compute due amounts for the banner
    active_due = loan.installments.filter(paid=False, due_date__lte=today).aggregate(
        total_interest=Sum('interest_portion'),
        total_principal=Sum('principal_portion')
    )
    interest_due = active_due['total_interest'] or Decimal('0.00')
    principal_due = active_due['total_principal'] or Decimal('0.00')
    total_due_now = (interest_due + principal_due).quantize(Decimal('0.01'))

    # 3. Total paid & total payable
    total_paid = loan.repayments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
    total_payable = loan.total_payable or Decimal('0')

    # 4. Disbursement & maturity dates
    disbursement_date = loan.disbursed_date or loan.start_date
    end_date = disbursement_date + relativedelta(months=loan.period_months) if disbursement_date else None

    # 5. Build schedule_data (combines calculated + manual penalties)
    schedule_data = []
    for inst in loan.installments.all().order_by('due_date'):
        calc_penalty = calculate_penalty(inst) or Decimal('0.00')
        manual_total = inst.manual_penalties.filter(is_waived=False).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        total_penalty = calc_penalty + manual_total

        principal_bal = inst.principal_balance
        interest_bal = inst.interest_balance
        total_balance = principal_bal + interest_bal + total_penalty

        schedule_data.append({
            'id': inst.id,
            'due_date': inst.due_date,
            'principal_portion': inst.principal_portion,
            'interest_portion': inst.interest_portion,
            'penalty_amount': total_penalty,
            'balance': total_balance,
            'paid': inst.paid,
            'is_overdue': inst.is_overdue,
        })

    # 6. Manual penalties (active, not waived)
    manual_penalties = loan.manual_penalties.filter(is_waived=False).order_by('-applied_date')
    total_manual_penalty = manual_penalties.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # 7. Recent repayment transactions (for the loan or member)
    repayments = Transaction.objects.filter(
        member=loan.member,
        type='repayment',
        loan=loan
    ).order_by('-timestamp')[:10]
    sms_config = SMSConfig.objects.first()
    sms_balance = sms_config.balance if sms_config else 0
    
    # 8. Context
    context = {
        'loan': loan,
        'sms_balance': sms_balance,
        'principal_balance': loan.principal_balance,
        'interest_due': interest_due,
        'principal_due': principal_due,
        'total_due_now': total_due_now,
        'schedule_data': schedule_data,
        'repayments': repayments,
        'total_paid': total_paid.quantize(Decimal('0.01')),
        'total_payable': total_payable,
        'disbursement_date': disbursement_date,
        'end_date': end_date,
        'today': today,
        'manual_penalties': manual_penalties,
        'total_manual_penalty': total_manual_penalty,
    }

    return render(request, 'finance/loan_details.html', context)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum

# Updated imports - using GeneralLedger instead of LedgerEntry
from .models import (
    GeneralLedger, 
    ChartOfAccount,
    # AccountCategory is removed because we are using account_type
)


@login_required
def accounting_dashboard(request):
    """Simple dashboard"""
    inflows = GeneralLedger.objects.filter(
        account__code='1001', 
        debit__gt=0
    ).aggregate(total=Sum('debit'))['total'] or 0

    outflows = GeneralLedger.objects.filter(
        account__code='1001', 
        credit__gt=0
    ).aggregate(total=Sum('credit'))['total'] or 0

    context = {
        'total_inflow': inflows,
        'total_outflow': outflows,
        'net_cash': inflows - outflows,
        'recent_entries': GeneralLedger.objects.select_related('account').order_by('-date')[:10]
    }
    return render(request, 'accounting/ledger.html', context)


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import GeneralLedger, ChartOfAccount

from django.db.models import Sum
from datetime import datetime

from django.db.models import Sum

from django.db.models import Sum, Window, F
from django.shortcuts import render
from .models import GeneralLedger, ChartOfAccount

from django.db.models import Sum, Window, F
from django.shortcuts import render
from .models import GeneralLedger, ChartOfAccount

from django.shortcuts import render
from django.db.models import Sum, Window, F
from django.utils import timezone
from .models import GeneralLedger, ChartOfAccount

def general_ledger(request):
    # Base QuerySet
    queryset = GeneralLedger.objects.select_related('account').all().order_by('date', 'id')

    # Get data from POST, default to empty string if not present
    start_date = request.POST.get('start_date') or None
    end_date = request.POST.get('end_date') or None
    account_id = request.POST.get('account_id') or None

    # Apply filters
    if start_date:
        queryset = queryset.filter(date__gte=start_date)
    if end_date:
        queryset = queryset.filter(date__lte=end_date)
    if account_id:
        queryset = queryset.filter(account_id=account_id)

    # Annotate transactions
    transactions = queryset.annotate(
        running_balance=Window(
            expression=Sum(F('credit') - F('debit')),
            order_by=F('date').asc(),
            partition_by=F('account_id')
        )
    )

    totals = transactions.aggregate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    )

    return render(request, 'accounting/ledger.html', {
        'transactions': transactions,
        'total_debit': totals['total_debit'] or 0,
        'total_credit': totals['total_credit'] or 0,
        'start_date': start_date or '',
        'end_date': end_date or '',
        'selected_account': account_id or '',
        'all_accounts': ChartOfAccount.objects.all(),
    })
@login_required
def chart_of_accounts(request):
    """List Chart of Accounts grouped by type"""
    grouped_accounts = {}
    for account_type, label in ChartOfAccount.ACCOUNT_TYPES:
        grouped_accounts[label] = ChartOfAccount.objects.filter(
            account_type=account_type, 
            is_active=True
        )

    context = {
        'grouped_accounts': grouped_accounts,
        'title': 'Chart of Accounts'
    }
    return render(request, 'accounting/coa_list.html', context)

from decimal import Decimal

from decimal import Decimal
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ChartOfAccount, GeneralLedger

from decimal import Decimal
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ChartOfAccount, GeneralLedger

@login_required
def record_expense(request):
    if request.method == "POST":
        account_id = request.POST.get('account')
        amount_raw = request.POST.get('amount')
        desc = request.POST.get('description')

        try:
            amount = Decimal(amount_raw)
            expense_account = ChartOfAccount.objects.get(id=account_id)
            cash_account = ChartOfAccount.objects.get(code='1001') 

            with transaction.atomic():
                # Entry 1: Debit the Expense
                GeneralLedger.objects.create(
                    account=expense_account,
                    debit=amount,
                    description=desc,
                )
                # Entry 2: Credit the Cash
                GeneralLedger.objects.create(
                    account=cash_account,
                    credit=amount,
                    description=f"Payment for: {desc}",
                )

            messages.success(request, f"Expense of UGX {amount:,.0f} recorded successfully.")
            return redirect('general_ledger')

        except ChartOfAccount.DoesNotExist:
            messages.error(request, "Required account missing (Check if Cash Account 1001 exists).")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    # Fixed: Filter matches the lowercase 'expense' in your ACCOUNT_TYPES
    expense_accounts = ChartOfAccount.objects.filter(account_type='expense')
    
    return render(request, 'accounting/expense_form.html', {
        'expense_accounts': expense_accounts
    })

from decimal import Decimal
from django.db import transaction

@login_required
def record_inflow(request):
    """Record Income with Double Entry (Debit Cash, Credit Income)"""
    if request.method == "POST":
        account_id = request.POST.get('account')
        amount_raw = request.POST.get('amount')
        desc = request.POST.get('description')

        try:
            amount = Decimal(amount_raw)
            income_account = ChartOfAccount.objects.get(id=account_id)
            # Ensure this code matches your 'Cash' account in the DB
            cash_account = ChartOfAccount.objects.get(code='1001') 

            with transaction.atomic():
                # CREDIT the Income Account (Increases Income)
                GeneralLedger.objects.create(
                    account=income_account,
                    credit=amount,
                    debit=0,
                    description=desc,
                )
                # DEBIT the Cash Account (Increases Asset)
                GeneralLedger.objects.create(
                    account=cash_account,
                    debit=amount,
                    credit=0,
                    description=f"Received: {desc}",
                )

            messages.success(request, f"Inflow of UGX {amount:,.0f} recorded.")
            return redirect('general_ledger')
            
        except ChartOfAccount.DoesNotExist:
            messages.error(request, "Account error: Ensure Income and Cash accounts exist.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    context = {
        # FIXED: Changed 'category' to 'account_type' and 'INCOME' to 'income'
        'income_accounts': ChartOfAccount.objects.filter(account_type='income'),
        'title': 'Record Inflow'
    }
    return render(request, 'accounting/inflow_form.html', context)
@login_required
def create_chart_of_account(request):
    if request.method == "POST":
        # Capture all fields from the POST request
        code = request.POST.get('code')
        name = request.POST.get('name')
        account_type = request.POST.get('account_type') # This was the missing piece
        parent_id = request.POST.get('parent')
        description = request.POST.get('description')

        # Basic Validation
        if not account_type:
            messages.error(request, "Please select an account type.")
        elif ChartOfAccount.objects.filter(code=code).exists():
            messages.error(request, f"Account code {code} already exists!")
        else:
            try:
                parent = ChartOfAccount.objects.get(id=parent_id) if parent_id else None
                
                ChartOfAccount.objects.create(
                    code=code,
                    name=name,
                    account_type=account_type, # Passing the string 'asset', 'income', etc.
                    parent=parent,
                    description=description
                )
                messages.success(request, f"Account '{name}' (Code: {code}) has been added.")
                return redirect('general_ledger') # Or your COA list view
            except Exception as e:
                messages.error(request, f"Error creating account: {str(e)}")

    context = {
        'account_types': ChartOfAccount.ACCOUNT_TYPES,
        'parent_accounts': ChartOfAccount.objects.filter(parent=None),
        'title': 'Add New Ledger Account'
    }
    return render(request, 'accounting/coa_form.html', context)
@login_required
def edit_chart_of_account(request, pk):
    account = get_object_or_404(ChartOfAccount, pk=pk)

    if request.method == "POST":
        code = request.POST.get('code')
        name = request.POST.get('name')
        selected_type = request.POST.get('category') # Match the HTML 'name'
        description = request.POST.get('description')

        if ChartOfAccount.objects.filter(code=code).exclude(pk=pk).exists():
            messages.error(request, f"Account code {code} is already taken!")
        else:
            account.code = code
            account.name = name
            account.account_type = selected_type
            account.description = description
            account.save()
            
            messages.success(request, f"Account '{name}' updated successfully.")
            return redirect('chart_of_accounts')

    context = {
        'account': account,
        'account_types': ChartOfAccount.ACCOUNT_TYPES,
        'title': f'Edit {account.name}'
    }
    return render(request, 'accounting/coa_edit_form.html', context)


@login_required
def accounts_hub(request):
    # Get total counts and high-level balances
    total_accounts = ChartOfAccount.objects.count()
    total_inflow = GeneralLedger.objects.filter(account__account_type='income').aggregate(Sum('credit'))['credit__sum'] or 0
    total_outflow = GeneralLedger.objects.filter(account__account_type='expense').aggregate(Sum('debit'))['debit__sum'] or 0
    
    # Recent activity for the mini-table
    recent_transactions = GeneralLedger.objects.select_related('account').order_by('-date')[:5]

    context = {
        'total_accounts': total_accounts,
        'total_inflow': total_inflow,
        'total_outflow': total_outflow,
        'recent_transactions': recent_transactions,
        'net_profit': total_inflow - total_outflow,
    }
    return render(request, 'accounting/accounts_hub.html', context)



from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_celery_beat.models import PeriodicTask
from finance.models import AutoRepaymentSetting, AutoRepaymentLog, DailyRepaymentSummary
from finance.forms import AutoRepaymentSettingForm
from finance.services import LoanRepaymentEngineService

@login_required
def auto_repayment_dashboard(request):
    config, _ = AutoRepaymentSetting.objects.get_or_create(id=1)
    
    if request.method == 'POST':
        if 'save_settings' in request.POST:
            form = AutoRepaymentSettingForm(request.POST, instance=config)
            if form.is_valid():
                form.instance.updated_by = request.user
                form.save()
                messages.success(request, "Scheduler settings synchronized successfully.")
                return redirect('auto_repayment_dashboard')
        
        elif 'manual_execution_trigger' in request.POST:
            # Trigger manual overrides directly inline safely
            res = LoanRepaymentEngineService.execute_bulk_auto_repayments()
            messages.success(request, f"Manual repayment routine complete. Summary output parsed.")
            return redirect('auto_repayment_dashboard')

    else:
        form = AutoRepaymentSettingForm(instance=config)

    # Fetch status tracking data for dashboards
    celery_task = PeriodicTask.objects.filter(task='finance.tasks.run_automated_loan_repayments').first()
    logs = AutoRepaymentLog.objects.all()[:15]
    summaries = DailyRepaymentSummary.objects.all()[:7]

    context = {
        'form': form,
        'config': config,
        'celery_task': celery_task,
        'logs': logs,
        'summaries': summaries
    }
    return render(request, 'finance/auto_repayment_dashboard.html', context)






##########################################################################################################################


import json
import datetime
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from .services import FinancialReportingService
from .filters import FinancialReportFilterForm
from .exports import ReportingExportEngine

import json
import datetime
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from .services import FinancialReportingService
from .filters import FinancialReportFilterForm
from .exports import ReportingExportEngine

class ExecutiveCEODashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'reports/dashboard.html'
    permission_required = 'reports.view_executive_dashboard'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ratios = FinancialReportingService.get_regulatory_ratios()
        aging = FinancialReportingService.get_loan_aging_summary()
        
        # Build core system metrics
        context['kpis'] = ratios
        context['aging_summary'] = aging
        context['interest_data'] = FinancialReportingService.get_interest_income_data()
        
        # Format metrics into JSON structures for serialization into Chart.js/ApexCharts interfaces
        context['chart_aging_labels'] = json.dumps([item['bucket'] for item in aging])
        context['chart_aging_volumes'] = json.dumps([float(item['volume']) for item in aging])
        return context


class InterestIncomeReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'reports/interest_report.html'
    permission_required = 'reports.view_financial_reports'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FinancialReportFilterForm(self.request.GET or None)
        filters = {}
        if form.is_valid():
            filters = {k: v for k, v in form.cleaned_data.items() if v}
            
        report_data = FinancialReportingService.get_interest_income_data(filters)
        context['records'] = report_data['records']
        context['totals'] = report_data['totals']
        context['filter_form'] = form
        return context


class TreasuryDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/treasury_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forecast = FinancialReportingService.get_treasury_liquidity_forecast()
        context['forecast_raw'] = forecast
        context['forecast_json'] = json.dumps(forecast)
        return context


import datetime
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from django.http import HttpResponse

# Ensure proper relative/explicit imports matching your local app structure
from .services import FinancialReportingService


import datetime
from django.views.generic import View
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin

from .services import FinancialReportingService
from .forms import InterestIncomeFilterForm
from .exports import ReportingExportEngine  # Adjust path to your ReportingExportEngine location

import datetime
from django.views.generic import View
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin



class InterestIncomeReportView(LoginRequiredMixin, View):
    """
    Unified Ledger View Engine. Handles real-time HTML data filtering, 
    and intercepts format parameters to serve binary Excel/PDF document extensions.
    """
    template_name = 'reports/interest_report.html'

    def get(self, request, *args, **kwargs):
        # 1. Initialize filter framework with query parameters
        form = InterestIncomeFilterForm(request.GET or None)
        filters = {}
        if form.is_valid():
            filters = {k: v for k, v in form.cleaned_data.items() if v}
        
        # 2. Extract calculations dataset matrix from our reporting engine
        reporting_payload = FinancialReportingService.get_interest_income_data(filters)
        records = reporting_payload['records']
        totals = reporting_payload['totals']

        # 3. Intercept binary export requests before rendering HTML templates
        export_type = request.GET.get('format', '').lower()
        if export_type in ['excel', 'pdf']:
            
            # Unified data verification columns array layout block
            columns = [
                'Date', 'Member No', 'Customer Name', 'Loan Ref', 
                'Product', 'Principal Remaining', 'Interest Remaining', 'Total Outstanding Balance'
            ]
            
            dataset = []
            for item in records:
                # Fallback safe date capture framework execution block
                d_date = getattr(item, 'disbursed_date', None) or getattr(item, 'start_date', None)
                if isinstance(d_date, (datetime.date, datetime.datetime)):
                    date_str = d_date.strftime('%Y-%m-%d')
                else:
                    date_str = str(d_date) if d_date else "N/A"
                
                # Protect computations against Null positions using float-safe fallback operations
                principal_rem = float(item.principal_receivable) if item.principal_receivable else 0.0
                interest_rem = float(item.interest_receivable) if item.interest_receivable else 0.0
                total_outstanding = float(item.total_remaining_balance) if item.total_remaining_balance else 0.0
                
                dataset.append([
                    date_str,
                    item.member.member_number,
                    f"{item.member.first_name} {item.member.last_name}",
                    item.loan_reference or f"LN-{item.id}",
                    str(item.product_type).upper() if item.product_type else "STANDARD",
                    principal_rem,
                    interest_rem,
                    total_outstanding
                ])
            
            # Forward processed data payloads using the exact engine signatures expected
            if export_type == 'excel':
                # Takes exactly 3 positional arguments
                return ReportingExportEngine.generate_excel('interest', columns, dataset)
            elif export_type == 'pdf':
                # Takes exactly 4 positional arguments
                return ReportingExportEngine.generate_pdf('interest', columns, dataset, request.user)

        # 4. Fallback to serving standard HTML template framework if no valid format parameter intercepted
        return render(request, self.template_name, {
            'filter_form': form,
            'records': records,
            'totals': totals
        })



############################################################################
import datetime
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum, F, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse

# Adjust these imports to match your structural app directory layout
from finance.models import Loan, Installment  

import datetime
from django.db.models import Q, Sum, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from finance.models import Installment  # Adjust this import to your actual app structure

import datetime
from decimal import Decimal  # <-- Added for strict type safety
from django.db.models import Q, Sum, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from finance.models import Installment 

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from datetime import datetime, date, timedelta
from decimal import Decimal

from .models import Installment


from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum, F, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from datetime import datetime, date, timedelta
from decimal import Decimal

from .models import Installment


from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum, F, Value, DecimalField, IntegerField, ExpressionWrapper
from django.db.models.functions import Coalesce
from datetime import datetime, date, timedelta
from decimal import Decimal

from .models import Installment


from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum, F, Value, DecimalField, IntegerField, ExpressionWrapper
from django.db.models.functions import Coalesce
from datetime import datetime, date, timedelta
from decimal import Decimal

from .models import Installment


import datetime
from datetime import date, datetime, timedelta

from decimal import Decimal

from django.db.models import (
    Q, F, Value, Sum, DecimalField, IntegerField,
    ExpressionWrapper
)
from django.db.models.functions import Coalesce, Now
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from finance.models import Installment


class LoansInArrearsReportView(LoginRequiredMixin, ListView):
    """
    Fixed Arrears Report (Type-safe + Production-ready)
    """
    model = Installment
    template_name = 'finance/arrears.html'
    context_object_name = 'overdue'
    paginate_by = 50

    def get_queryset(self):
        search_query = self.request.GET.get('search_query', '').strip()
        date_at_str = self.request.GET.get('date_at', '').strip()
        sort_by = self.request.GET.get('sort_by', '')

        try:
            target_date = datetime.strptime(date_at_str, '%Y-%m-%d').date() if date_at_str else date.today()
        except ValueError:
            target_date = date.today()

        queryset = Installment.objects.filter(
            paid=False,
            due_date__lt=target_date,
            loan__status__in=['approved', 'arrears']
        ).select_related('loan', 'loan__member', 'loan__officer')

        if search_query:
            queryset = queryset.filter(
                Q(loan__member__first_name__icontains=search_query) |
                Q(loan__member__last_name__icontains=search_query) |
                Q(loan__member__member_number__icontains=search_query) |
                Q(loan__loan_reference__icontains=search_query)
            )

        # =========================================================
        # FIXED ANNOTATIONS (NO TYPE CONFLICTS)
        # =========================================================
        queryset = queryset.annotate(
            arrears_amount=ExpressionWrapper(
                Coalesce(F('principal_portion') - F('principal_paid'), Value(0)) +
                Coalesce(F('interest_portion') - F('interest_paid'), Value(0)) +
                Coalesce(F('penalty_amount') - F('penalty_paid'), Value(0)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),

            # SAFE DAYS OVERDUE (FIXED)
            days_overdue=ExpressionWrapper(
                Now() - F('due_date'),
                output_field=DecimalField()  # duration-safe fallback
            )
        )

        # Sorting
        if sort_by == 'days':
            queryset = queryset.order_by('-due_date')
        elif sort_by == 'amount':
            queryset = queryset.order_by('-arrears_amount')
        else:
            queryset = queryset.order_by('-due_date')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_queryset = self.get_queryset()

        date_at_str = self.request.GET.get('date_at', '').strip()

        try:
            target_date = datetime.strptime(date_at_str, '%Y-%m-%d').date() if date_at_str else date.today()
        except ValueError:
            target_date = date.today()

        watchlist_barrier = target_date - timedelta(days=30)
        substandard_barrier = target_date - timedelta(days=60)

        totals = base_queryset.aggregate(
            total=Coalesce(
                Sum('arrears_amount'),
                Value(0),
                output_field=DecimalField()
            ),

            watchlist=Coalesce(
                Sum('arrears_amount', filter=Q(due_date__gte=watchlist_barrier)),
                Value(0),
                output_field=DecimalField()
            ),

            substandard=Coalesce(
                Sum('arrears_amount', filter=Q(due_date__lt=watchlist_barrier, due_date__gte=substandard_barrier)),
                Value(0),
                output_field=DecimalField()
            ),

            doubtful=Coalesce(
                Sum('arrears_amount', filter=Q(due_date__lt=substandard_barrier)),
                Value(0),
                output_field=DecimalField()
            )
        )

        active_portfolio_total = Installment.objects.filter(
            loan__status__in=['approved', 'arrears']
        ).aggregate(
            gross=Coalesce(
                Sum(F('principal_portion') + F('interest_portion')),
                Value(0),
                output_field=DecimalField()
            )
        )['gross'] or Decimal('1.0')

        total_at_risk = totals['total']
        par_rate = (total_at_risk / active_portfolio_total * Decimal('100')) if active_portfolio_total > 0 else Decimal('0')

        context.update({
            'total_at_risk': total_at_risk,
            'watchlist_total': totals['watchlist'],
            'substandard_total': totals['substandard'],
            'doubtful_total': totals['doubtful'],
            'par_rate': round(float(par_rate), 2),
            'today': target_date,
        })

        return context


# finance/views.py
import random
from decimal import Decimal
from datetime import datetime, date, timedelta
from django.db.models import Sum, Q, F, Count, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import render
from django.http import FileResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from .models import (
    Loan, Installment, Member, SystemSetting, GeneralLedger, ChartOfAccount,
    SavingsAccount, Transaction, Company, SMSConfig
)
from .utils import generate_excel_report

User = get_user_model()


# ====================================================================
# CONTEXT BUILDERS & HELPERS
# ====================================================================

def get_report_context(request):
    """
    Builds the report context based on POST/GET filters.
    Returns a dict with columns, data, totals, KPIs, etc.
    """
    context = {}

    # 1. Extract filters
    date_from = request.POST.get('date_from') or request.GET.get('date_from')
    date_to = request.POST.get('date_to') or request.GET.get('date_to')
    officer_id = request.POST.get('officer') or request.GET.get('officer')
    status = request.POST.get('status') or request.GET.get('status')

    # 2. Base queryset – use your actual model (Loan)
    qs = Loan.objects.select_related('member', 'officer')

    if date_from:
        qs = qs.filter(disbursed_date__gte=date_from)
    if date_to:
        qs = qs.filter(disbursed_date__lte=date_to)
    if officer_id:
        qs = qs.filter(officer_id=officer_id)
    if status:
        qs = qs.filter(status=status)

    # 3. Define columns (must match the keys in data rows)
    columns = [
        {'key': 'loan_reference', 'label': 'Loan Reference'},
        {'key': 'member_name', 'label': 'Member'},
        {'key': 'principal', 'label': 'Principal', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'interest_balance', 'label': 'Interest Balance', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'total_balance', 'label': 'Total Balance', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'status', 'label': 'Status', 'type': 'status'},
        {'key': 'disbursed_date', 'label': 'Disbursed', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer'},
    ]

    # 4. Build data rows
    data = []
    total_principal = Decimal('0.00')
    total_interest = Decimal('0.00')
    total_balance = Decimal('0.00')

    for loan in qs:
        principal = loan.principal_amount or Decimal('0.00')
        interest = loan.interest_balance or Decimal('0.00')
        balance = principal + interest

        data.append({
            'loan_reference': loan.loan_reference or f"LN-{loan.id}",
            'member_name': loan.member.get_full_name() if loan.member else 'N/A',
            'principal': principal,
            'interest_balance': interest,
            'total_balance': balance,
            'status': loan.get_status_display(),
            'disbursed_date': loan.disbursed_date,
            'officer': loan.officer.get_full_name() if loan.officer else 'N/A',
        })

        total_principal += principal
        total_interest += interest
        total_balance += balance

    # 5. Totals dictionary
    totals = {
        'principal': total_principal,
        'interest_balance': total_interest,
        'total_balance': total_balance,
    }

    # 6. KPIs
    record_count = len(data)
    kpi_cards = [
        {'label': 'Total Loans', 'value': record_count, 'icon': 'bi-file-earmark-text', 'type': 'info'},
        {'label': 'Total Principal', 'value': f"UGX {total_principal:,.0f}", 'icon': 'bi-cash', 'type': 'success'},
        {'label': 'Total Interest', 'value': f"UGX {total_interest:,.0f}", 'icon': 'bi-percent', 'type': 'warning'},
        {'label': 'Total Balance', 'value': f"UGX {total_balance:,.0f}", 'icon': 'bi-wallet2', 'type': 'danger'},
    ]

    # 7. Aging Summary (optional)
    aging_summary = []

    # 8. Summary totals (extra stats)
    summary_totals = {
        'total_records': record_count,
        'total_amount': total_balance,
        'total_paid': Decimal('0.00'),
        'outstanding': total_balance,
        'recovery_rate': 0,
        'par_30': 0,
    }

    # 9. Officer list for filter dropdown
    officer_list = User.objects.filter(is_active=True).order_by('first_name', 'last_name')

    # 10. Company info – FROM DATABASE
    company = Company.get_company()

    # 11. Build the final context
    context.update({
        'columns': columns,
        'data': data,
        'totals': totals,
        'has_data': bool(data),
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'aging_summary': aging_summary,
        'report_title': 'Loan Portfolio Report',
        'company': company,
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'selected_status': status,
        'officer_list': officer_list,
        'officer_name': dict(officer_list.values_list('id', 'username')).get(int(officer_id) if officer_id else None),
        'generated_date': timezone.now().strftime('%d %b %Y %H:%M'),
        'generated_by': request.user.get_full_name() if request.user.is_authenticated else 'System',
    })

    return context


def generate_excel_report(columns, data, report_title="Report", company_name="Company", totals=None):
    """
    Generate an Excel workbook from report columns and data.
    Optionally add a totals row.
    """
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = report_title[:31]

    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1632af", end_color="1632af", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    cell_alignment = Alignment(horizontal="left", vertical="center")
    number_alignment = Alignment(horizontal="right", vertical="center")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Optional title row
    row = 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(columns))
    ws.cell(row=row, column=1).value = f"{company_name} - {report_title}"
    ws.cell(row=row, column=1).font = Font(bold=True, size=14)
    ws.cell(row=row, column=1).alignment = Alignment(horizontal="center")
    row += 1

    # Headers
    for col_idx, col in enumerate(columns, start=1):
        cell = ws.cell(row=row, column=col_idx, value=col.get('label', col.get('key', '')))
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    row += 1

    # Data rows
    for data_row in data:
        for col_idx, col in enumerate(columns, start=1):
            key = col.get('key')
            value = data_row.get(key, '-')

            # Format based on type
            if col.get('type') == 'currency':
                try:
                    value = f"{float(value):,.0f}"
                except (ValueError, TypeError):
                    pass
            elif col.get('type') == 'date' and value:
                if hasattr(value, 'strftime'):
                    value = value.strftime('%d %b, %Y')
                else:
                    value = str(value)
            elif col.get('type') == 'status':
                value = str(value)

            cell = ws.cell(row=row, column=col_idx, value=value)
            cell.border = border
            if col.get('align') == 'right' or col.get('type') == 'currency':
                cell.alignment = number_alignment
            else:
                cell.alignment = cell_alignment
        row += 1

    # -------------------------
    # TOTALS ROW (if totals provided)
    # -------------------------
    if totals:
        ws.cell(row=row, column=1, value="TOTALS").font = Font(bold=True)
        ws.cell(row=row, column=1).alignment = Alignment(horizontal="center")

        for col_idx, col in enumerate(columns, start=1):
            if col.get('total') and col.get('key') in totals:
                total_val = totals[col['key']]
                if col.get('type') == 'currency':
                    try:
                        total_val = f"{float(total_val):,.0f}"
                    except (ValueError, TypeError):
                        pass
                else:
                    total_val = str(total_val)

                cell = ws.cell(row=row, column=col_idx, value=total_val)
                cell.font = Font(bold=True)
                cell.border = border
                if col.get('align') == 'right' or col.get('type') == 'currency':
                    cell.alignment = number_alignment
                else:
                    cell.alignment = cell_alignment

        row += 1

    # Auto-size columns
    for col_idx in range(1, len(columns) + 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 18

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ====================================================================
# EXPORT VIEW
# ====================================================================

def export_report_excel(request):
    context = get_report_context(request)

    columns = context.get('columns', [])
    data = context.get('data', [])
    totals = context.get('totals', {})
    report_title = context.get('report_title', 'Report')

    # --- Safely get company name (handle dict, object, or None) ---
    company = context.get('company')
    if isinstance(company, dict):
        company_name = company.get('name', 'Company')
    elif hasattr(company, 'name'):
        company_name = company.name
    else:
        company_name = 'Company'

    excel_file = generate_excel_report(
        columns=columns,
        data=data,
        report_title=report_title,
        company_name=company_name,
        totals=totals
    )

    filename = (
        f"{report_title.replace(' ', '_')}_"
        f"{context.get('generated_date', 'now').replace(' ', '_').replace(':', '')}.xlsx"
    )
    response = FileResponse(
        excel_file,
        as_attachment=True,
        filename=filename,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    return response

# ====================================================================
# REPORT VIEWS – ALL USING Company.get_company()
# ====================================================================

@login_required
def loan_report(request):
    """Professional Loan Portfolio Report with Filters"""
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    officer_id = request.GET.get('officer')
    status = request.GET.get('status')

    loans = Loan.objects.select_related('member', 'officer').prefetch_related('repayments')

    if date_from:
        loans = loans.filter(disbursed_date__gte=date_from)
    if date_to:
        loans = loans.filter(disbursed_date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)
    if status:
        loans = loans.filter(status=status)

    loans = loans.annotate(
        paid_amount=Sum('repayments__amount_paid', default=0),
        total_balance=F('principal_balance') + F('interest_balance'),
    )

    data = []
    total_amount = Decimal('0')
    total_paid = Decimal('0')
    total_balance = Decimal('0')

    for loan in loans:
        balance = loan.total_balance or Decimal('0')
        paid = loan.paid_amount or Decimal('0')

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}".strip(),
            'member_no': loan.member.member_number or str(loan.member.id),
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'amount': loan.principal_amount,
            'paid': paid,
            'balance': balance,
            'status': loan.status,
            'date': loan.disbursed_date or loan.start_date,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })

        total_amount += loan.principal_amount or Decimal('0')
        total_paid += paid
        total_balance += balance

    recovery_rate = round((total_paid / total_amount * 100), 1) if total_amount > 0 else 0
    par_30 = round((total_balance / total_amount * 100), 1) if total_amount > 0 else 0
    total_records = len(data)

    columns = [
        {'key': 'member', 'label': 'Member Name', 'align': 'left'},
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Reference', 'align': 'left'},
        {'key': 'amount', 'label': 'Amount (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'paid', 'label': 'Paid (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'balance', 'label': 'Balance (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'date', 'label': 'Date', 'align': 'center', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]

    kpi_cards = [
        {'icon': 'bi-people', 'value': f'{total_records:,}', 'label': 'Total Loans'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_amount:,.0f}', 'label': 'Total Portfolio', 'type': 'success'},
        {'icon': 'bi-check-circle', 'value': f'{recovery_rate}%', 'label': 'Recovery Rate', 'type': 'info'},
        {'icon': 'bi-exclamation-triangle', 'value': f'{par_30}%', 'label': 'PAR 30', 'type': 'warning'},
    ]

    summary_totals = {
        'total_records': total_records,
        'total_amount': total_amount,
        'total_paid': total_paid,
        'outstanding': total_balance,
        'recovery_rate': recovery_rate,
        'par_30': par_30,
    }

    officer_list = User.objects.filter(is_active=True).order_by('first_name', 'last_name')

    context = {
        'company': Company.get_company(),
        'report_title': 'Loan Portfolio Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': date_from or 'All',
        'date_to': date_to or 'All',
        'officer': officer_id or 'All Officers',
        'status': status or 'All Status',
        'columns': columns,
        'data': data,
        'totals': {
            'amount': total_amount,
            'paid': total_paid,
            'balance': total_balance,
        },
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'officer_list': officer_list,
    }

    return render(request, 'finance/reports/base_report.html', context)


@login_required
def member_report(request):
    """Member Report"""
    members = Member.objects.all().order_by('member_number')

    data = []
    total_savings = Decimal('0')
    total_loans = Decimal('0')

    for member in members:
        savings = SavingsAccount.objects.filter(member=member).first()
        savings_balance = savings.balance if savings else Decimal('0')
        total_loans_balance = member.loans.filter(is_active=True).aggregate(
            total=Sum('principal_balance') + Sum('interest_balance')
        )['total'] or Decimal('0')

        status = getattr(member, 'status', 'active')
        status_display = 'Active' if status == 'active' else 'Inactive'

        data.append({
            'member_no': member.member_number,
            'name': f"{member.first_name} {member.last_name}",
            'phone': member.phone_number,
            'email': member.email or '—',
            'savings': savings_balance,
            'loans': total_loans_balance,
            'joined': member.date_joined,
            'status': status_display,
        })

        total_savings += savings_balance
        total_loans += total_loans_balance

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'name', 'label': 'Member Name', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'email', 'label': 'Email', 'align': 'left'},
        {'key': 'savings', 'label': 'Savings (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'loans', 'label': 'Loans (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'joined', 'label': 'Joined', 'align': 'center', 'type': 'date'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
    ]

    totals = {
        'savings': total_savings,
        'loans': total_loans,
    }

    kpi_cards = [
        {'icon': 'bi-people', 'value': f'{len(data):,}', 'label': 'Total Members'},
        {'icon': 'bi-wallet2', 'value': f'UGX {total_savings:,.0f}', 'label': 'Total Savings', 'type': 'success'},
        {'icon': 'bi-bank', 'value': f'UGX {total_loans:,.0f}', 'label': 'Total Loans', 'type': 'info'},
    ]

    context = {
        'company': Company.get_company(),
        'report_title': 'Member Registry Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': 'All',
        'date_to': 'All',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'has_data': len(data) > 0,
        'summary_totals': {
            'total_records': len(data),
            'total_amount': total_savings + total_loans,
            'total_paid': total_savings,
            'outstanding': total_loans,
            'recovery_rate': '100',
            'par_30': '0',
        },
    }

    return render(request, 'finance/reports/base_report.html', context)


@login_required
def savings_report(request):
    """Savings Report"""
    savings_accounts = SavingsAccount.objects.select_related('member').all()

    data = []
    total_balance = Decimal('0')

    for savings in savings_accounts:
        data.append({
            'member': f"{savings.member.first_name} {savings.member.last_name}",
            'member_no': savings.member.member_number,
            'phone': savings.member.phone_number,
            'balance': savings.balance,
            'account_no': savings.account_number if hasattr(savings, 'account_number') else 'N/A',
            'status': 'Active' if savings.balance > 0 else 'Inactive',
        })
        total_balance += savings.balance

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member Name', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'account_no', 'label': 'Account No', 'align': 'left'},
        {'key': 'balance', 'label': 'Balance (UGX)', 'align': 'right', 'type': 'currency', 'total': True},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
    ]

    totals = {'balance': total_balance}

    context = {
        'company': Company.get_company(),
        'report_title': 'Savings Summary Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': 'All',
        'date_to': 'All',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': [
            {'icon': 'bi-wallet2', 'value': f'{len(data):,}', 'label': 'Total Accounts'},
            {'icon': 'bi-currency-dollar', 'value': f'UGX {total_balance:,.0f}', 'label': 'Total Savings', 'type': 'success'},
            {'icon': 'bi-people', 'value': f'{len(data):,}', 'label': 'Active Members', 'type': 'info'},
        ],
        'summary_totals': {
            'total_records': len(data),
            'total_amount': total_balance,
            'total_paid': total_balance,
            'outstanding': 0,
            'recovery_rate': '100',
            'par_30': '0',
        },
    }

    return render(request, 'finance/reports/base_report.html', context)


@login_required
def financial_report(request):
    """Financial Performance Report (Income/Expense summary)"""
    from datetime import date, timedelta

    if request.method == "POST":
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
    else:
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

    if not date_from:
        date_from = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = date.today().strftime('%Y-%m-%d')

    transactions = Transaction.objects.filter(
        timestamp__date__gte=date_from,
        timestamp__date__lte=date_to
    )

    total_income = transactions.filter(
        Q(type='deposit') | Q(type='repayment') | Q(type='interest_payment')
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    total_expenses = transactions.filter(
        Q(type='withdrawal') | Q(type='disbursement') | Q(type='penalty')
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    net_profit = total_income - total_expenses

    monthly_data = transactions.annotate(
        month=TruncMonth('timestamp')
    ).values('month').annotate(
        income=Sum('amount', filter=Q(type__in=['deposit', 'repayment', 'interest_payment'])),
        expense=Sum('amount', filter=Q(type__in=['withdrawal', 'disbursement', 'penalty']))
    ).order_by('month')

    data = []
    for entry in monthly_data:
        data.append({
            'month': entry['month'].strftime('%b %Y') if entry['month'] else 'N/A',
            'income': entry['income'] or Decimal('0'),
            'expense': entry['expense'] or Decimal('0'),
            'profit': (entry['income'] or Decimal('0')) - (entry['expense'] or Decimal('0')),
        })

    columns = [
        {'key': 'month', 'label': 'Month', 'align': 'left'},
        {'key': 'income', 'label': 'Income (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'expense', 'label': 'Expenses (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'profit', 'label': 'Net Profit (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
    ]

    totals = {
        'income': total_income,
        'expense': total_expenses,
        'profit': net_profit,
    }

    kpi_cards = [
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_income:,.0f}', 'label': 'Total Income', 'type': 'success'},
        {'icon': 'bi-cash', 'value': f'UGX {total_expenses:,.0f}', 'label': 'Total Expenses', 'type': 'danger'},
        {'icon': 'bi-graph-up', 'value': f'UGX {net_profit:,.0f}', 'label': 'Net Profit', 'type': 'info'},
    ]

    context = {
        'company': Company.get_company(),
        'report_title': 'Financial Performance Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': date_from,
        'date_to': date_to,
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'has_data': len(data) > 0,
        'summary_totals': {
            'total_records': len(data),
            'total_amount': total_income + total_expenses,
            'total_paid': total_income,
            'outstanding': total_expenses,
            'recovery_rate': 'N/A',
            'par_30': 'N/A',
        },
    }

    return render(request, 'finance/reports/base_report.html', context)


from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from .models import Loan, Transaction, Company

@login_required
def officer_report(request):
    """Officer Performance Report with PAR 1 & PAR 30 - Credit Officers only"""
    
    # ---- Only include active users who are in the "Credit Officer" group ----
    officers = User.objects.filter(
        is_active=True,
        groups__name='Credit Officer'
    ).order_by('first_name', 'last_name')

    data = []
    total_loans = Decimal('0')
    total_disbursed = Decimal('0')
    total_collected = Decimal('0')
    total_outstanding = Decimal('0')
    total_par_1 = Decimal('0')
    total_par_30 = Decimal('0')

    today = date.today()

    for officer in officers:
        loans = Loan.objects.filter(officer=officer)
        loan_count = loans.count()
        disbursed_amount = loans.aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')

        collections = Transaction.objects.filter(
            type='repayment',
            loan__officer=officer
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        active_count = loans.filter(is_active=True).count()

        par_1_amount = Decimal('0')
        par_30_amount = Decimal('0')
        outstanding_principal = Decimal('0')

        for loan in loans:
            p_bal = loan.principal_balance or Decimal('0')
            outstanding_principal += p_bal

            unpaid_installments = loan.installments.filter(paid=False, due_date__lt=today)
            if unpaid_installments.exists():
                oldest_due = unpaid_installments.earliest('due_date').due_date
                days_overdue = (today - oldest_due).days

                if days_overdue >= 1:
                    par_1_amount += p_bal
                if days_overdue >= 30:
                    par_30_amount += p_bal

        # Calculate percentages and round to 2 decimal places
        par_1_percent = round((par_1_amount / outstanding_principal * 100), 2) if outstanding_principal > 0 else 0
        par_30_percent = round((par_30_amount / outstanding_principal * 100), 2) if outstanding_principal > 0 else 0
        performance = round((collections / disbursed_amount * 100), 2) if disbursed_amount > 0 else 0

        data.append({
            'officer': officer.get_full_name() or officer.username,
            'loan_count': loan_count,
            'active_count': active_count,
            'disbursed': disbursed_amount,
            'collected': collections,
            'outstanding': outstanding_principal,
            'par_1_amount': par_1_amount,
            'par_1_percent': par_1_percent,
            'par_30_amount': par_30_amount,
            'par_30_percent': par_30_percent,
            'performance': performance,
        })

        total_loans += loan_count
        total_disbursed += disbursed_amount
        total_collected += collections
        total_outstanding += outstanding_principal
        total_par_1 += par_1_amount
        total_par_30 += par_30_amount

    # Round totals
    total_par_1_percent = round((total_par_1 / total_outstanding * 100), 2) if total_outstanding > 0 else 0
    total_par_30_percent = round((total_par_30 / total_outstanding * 100), 2) if total_outstanding > 0 else 0
    total_performance = round((total_collected / total_disbursed * 100), 2) if total_disbursed > 0 else 0

    columns = [
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
        {'key': 'loan_count', 'label': 'Total Loans', 'align': 'center'},
        {'key': 'active_count', 'label': 'Active', 'align': 'center'},
        {'key': 'disbursed', 'label': 'Disbursed (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'collected', 'label': 'Collected (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'outstanding', 'label': 'Outstanding (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'par_1_amount', 'label': 'PAR 1 (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'par_1_percent', 'label': 'PAR 1 %', 'align': 'right', 'total': True},
        {'key': 'par_30_amount', 'label': 'PAR 30 (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'par_30_percent', 'label': 'PAR 30 %', 'align': 'right', 'total': True},
        {'key': 'performance', 'label': 'Performance %', 'align': 'right', 'total': True},
    ]

    totals = {
        'disbursed': total_disbursed,
        'collected': total_collected,
        'outstanding': total_outstanding,
        'par_1_amount': total_par_1,
        'par_1_percent': total_par_1_percent,
        'par_30_amount': total_par_30,
        'par_30_percent': total_par_30_percent,
        'performance': total_performance,
    }

    kpi_cards = [
        {'icon': 'bi-person-badge', 'value': f'{len(data)}', 'label': 'Total Officers', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_disbursed:,.0f}', 'label': 'Total Disbursed', 'type': 'success'},
        {'icon': 'bi-cash-stack', 'value': f'UGX {total_collected:,.0f}', 'label': 'Total Collected', 'type': 'info'},
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {total_par_30:,.0f}', 'label': 'Total PAR 30', 'type': 'danger'},
    ]

    context = {
        'company': Company.get_company(),
        'report_title': 'Officer Performance Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': 'All',
        'date_to': 'All',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'has_data': len(data) > 0,
        'summary_totals': {
            'total_records': len(data),
            'total_amount': total_disbursed,
            'total_paid': total_collected,
            'outstanding': total_outstanding,
            'recovery_rate': f'{total_performance:.2f}',
            'par_30': f'{total_par_30_percent:.2f}',
        },
    }

    return render(request, 'finance/reports/base_report.html', context)
@login_required
def accounting_report(request):
    """Accounting Report - General Ledger Summary"""
    ledger_entries = GeneralLedger.objects.select_related('account').all().order_by('account__code')

    data = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')

    for entry in ledger_entries:
        data.append({
            'account_code': entry.account.code,
            'account_name': entry.account.name,
            'account_type': entry.account.get_account_type_display(),
            'debit': entry.debit,
            'credit': entry.credit,
            'balance': entry.balance,
        })
        total_debit += entry.debit
        total_credit += entry.credit

    columns = [
        {'key': 'account_code', 'label': 'Account Code', 'align': 'left'},
        {'key': 'account_name', 'label': 'Account Name', 'align': 'left'},
        {'key': 'account_type', 'label': 'Type', 'align': 'left'},
        {'key': 'debit', 'label': 'Debit (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'credit', 'label': 'Credit (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'balance', 'label': 'Balance (UGX)', 'align': 'right', 'type': 'currency', 'prefix': 'UGX '},
    ]

    totals = {
        'debit': total_debit,
        'credit': total_credit,
        'balance': total_debit - total_credit,
    }

    kpi_cards = [
        {'icon': 'bi-journal-text', 'value': f'{len(data)}', 'label': 'Total Accounts', 'type': 'info'},
        {'icon': 'bi-arrow-down', 'value': f'UGX {total_debit:,.0f}', 'label': 'Total Debit', 'type': 'danger'},
        {'icon': 'bi-arrow-up', 'value': f'UGX {total_credit:,.0f}', 'label': 'Total Credit', 'type': 'success'},
    ]

    context = {
        'company': Company.get_company(),
        'report_title': 'Accounting Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': 'All',
        'date_to': 'All',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'has_data': len(data) > 0,
        'summary_totals': {
            'total_records': len(data),
            'total_amount': total_debit + total_credit,
            'total_paid': total_credit,
            'outstanding': total_debit,
            'recovery_rate': 'N/A',
            'par_30': 'N/A',
        },
    }

    return render(request, 'finance/reports/base_report.html', context)


@login_required
def audit_report(request):
    """Audit Trail Report"""
    transactions = Transaction.objects.all().order_by('-timestamp')[:100]

    data = []
    for tx in transactions:
        data.append({
            'timestamp': tx.timestamp,
            'user': tx.created_by.get_full_name() if tx.created_by else 'System',
            'type': tx.get_type_display(),
            'amount': tx.amount,
            'reference': tx.reference,
            'is_reversed': 'Yes' if tx.is_reversed else 'No',
            'status': 'Reversed' if tx.is_reversed else 'Active',
        })

    columns = [
        {'key': 'timestamp', 'label': 'Date & Time', 'align': 'center', 'type': 'date'},
        {'key': 'user', 'label': 'User', 'align': 'left'},
        {'key': 'type', 'label': 'Transaction Type', 'align': 'left'},
        {'key': 'amount', 'label': 'Amount (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'reference', 'label': 'Reference', 'align': 'left'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
    ]

    totals = {
        'amount': transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0'),
    }

    kpi_cards = [
        {'icon': 'bi-clock-history', 'value': f'{len(data)}', 'label': 'Total Transactions', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["amount"]:,.0f}', 'label': 'Total Volume', 'type': 'success'},
        {'icon': 'bi-person', 'value': f'{len(set(tx.created_by_id for tx in transactions if tx.created_by))}', 'label': 'Active Users', 'type': 'secondary'},
    ]

    context = {
        'company': Company.get_company(),
        'report_title': 'Audit Trail Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': 'All',
        'date_to': 'All',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'has_data': len(data) > 0,
        'summary_totals': {
            'total_records': len(data),
            'total_amount': totals['amount'],
            'total_paid': 'N/A',
            'outstanding': 'N/A',
            'recovery_rate': 'N/A',
            'par_30': 'N/A',
        },
    }

    return render(request, 'finance/reports/base_report.html', context)


@login_required
def inventory_report(request):
    """Inventory Report - Products and Stock Levels"""
    try:
        from hardware.models import Product, Category
        products = Product.objects.select_related('category').all()
        has_inventory = True
    except ImportError:
        products = []
        has_inventory = False

    data = []
    total_value = Decimal('0')
    total_stock = 0

    if has_inventory:
        for product in products:
            stock_value = (product.current_stock or 0) * (product.cost_price or 0)
            data.append({
                'product_code': product.product_code,
                'product_name': product.name,
                'category': product.category.name if product.category else 'Uncategorized',
                'stock': product.current_stock or 0,
                'cost_price': product.cost_price or 0,
                'selling_price': product.selling_price or 0,
                'stock_value': stock_value,
                'status': 'Low Stock' if (product.current_stock or 0) <= (product.reorder_level or 5) else 'Healthy',
            })
            total_value += stock_value
            total_stock += (product.current_stock or 0)
    else:
        data = [{'message': 'Inventory module not installed'}]

    columns = [
        {'key': 'product_code', 'label': 'Product Code', 'align': 'left'},
        {'key': 'product_name', 'label': 'Product Name', 'align': 'left'},
        {'key': 'category', 'label': 'Category', 'align': 'left'},
        {'key': 'stock', 'label': 'Stock', 'align': 'center'},
        {'key': 'cost_price', 'label': 'Cost (UGX)', 'align': 'right', 'type': 'currency', 'prefix': 'UGX '},
        {'key': 'selling_price', 'label': 'Sell (UGX)', 'align': 'right', 'type': 'currency', 'prefix': 'UGX '},
        {'key': 'stock_value', 'label': 'Value (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
    ]

    totals = {'stock_value': total_value}

    kpi_cards = [
        {'icon': 'bi-boxes', 'value': f'{len(data)}', 'label': 'Total Products', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_value:,.0f}', 'label': 'Inventory Value', 'type': 'success'},
        {'icon': 'bi-box', 'value': f'{total_stock:,}', 'label': 'Total Stock Units', 'type': 'secondary'},
    ]

    context = {
        'company': Company.get_company(),
        'report_title': 'Inventory Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': 'All',
        'date_to': 'All',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'has_data': len(data) > 0,
        'summary_totals': {
            'total_records': len(data),
            'total_amount': total_value,
            'total_paid': 'N/A',
            'outstanding': 'N/A',
            'recovery_rate': 'N/A',
            'par_30': 'N/A',
        },
    }

    return render(request, 'finance/reports/base_report.html', context)


@login_required
def interest_report(request):
    """Interest Income Report"""
    from datetime import date, timedelta

    if request.method == "POST":
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
    else:
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

    if not date_from:
        date_from = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = date.today().strftime('%Y-%m-%d')

    loans = Loan.objects.filter(
        disbursed_date__gte=date_from,
        disbursed_date__lte=date_to,
        status__in=['approved', 'active', 'closed']
    ).select_related('member', 'officer')

    data = []
    total_principal = Decimal('0')
    total_interest_charged = Decimal('0')
    total_interest_paid = Decimal('0')
    total_interest_balance = Decimal('0')

    for loan in loans:
        interest_charged = loan.installments.aggregate(total=Sum('interest_portion'))['total'] or Decimal('0')
        interest_paid = loan.installments.aggregate(total=Sum('interest_paid'))['total'] or Decimal('0')
        interest_balance = loan.interest_balance or Decimal('0')

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'principal': loan.principal_amount,
            'interest_charged': interest_charged,
            'interest_paid': interest_paid,
            'interest_balance': interest_balance,
            'status': loan.status,
            'disbursed_date': loan.disbursed_date or loan.start_date,
        })

        total_principal += loan.principal_amount
        total_interest_charged += interest_charged
        total_interest_paid += interest_paid
        total_interest_balance += interest_balance

    columns = [
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Reference', 'align': 'left'},
        {'key': 'principal', 'label': 'Principal (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_charged', 'label': 'Interest Charged (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_paid', 'label': 'Interest Paid (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'disbursed_date', 'label': 'Disbursed', 'align': 'center', 'type': 'date'},
    ]

    totals = {
        'principal': total_principal,
        'interest_charged': total_interest_charged,
        'interest_paid': total_interest_paid,
        'interest_balance': total_interest_balance,
    }

    kpi_cards = [
        {'icon': 'bi-percent', 'value': f'UGX {total_interest_charged:,.0f}', 'label': 'Total Interest Charged', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_interest_paid:,.0f}', 'label': 'Interest Paid', 'type': 'success'},
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {total_interest_balance:,.0f}', 'label': 'Interest Outstanding', 'type': 'warning'},
    ]

    context = {
        'company': Company.get_company(),
        'report_title': 'Interest Income Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': date_from,
        'date_to': date_to,
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'has_data': len(data) > 0,
        'summary_totals': {
            'total_records': len(data),
            'total_amount': total_principal,
            'total_paid': total_interest_paid,
            'outstanding': total_interest_balance,
            'recovery_rate': (total_interest_paid / total_interest_charged * 100) if total_interest_charged > 0 else 0,
            'par_30': 'N/A',
        },
    }

    return render(request, 'finance/reports/base_report.html', context)


@login_required
def loan_portfolio_reports(request):
    """Loan Portfolio Report - Comprehensive loan portfolio analytics"""
    from datetime import date

    if request.method == "POST":
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        officer_id = request.POST.get('officer')
    else:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        officer_id = request.GET.get('officer')

    loans = Loan.objects.select_related('member', 'officer').filter(
        status__in=['approved', 'active', 'closed']
    ).order_by('-disbursed_date', '-start_date')

    if start_date:
        loans = loans.filter(disbursed_date__gte=start_date)
    if end_date:
        loans = loans.filter(disbursed_date__lte=end_date)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    today = date.today()
    report_data = []

    for loan in loans:
        p_bal = Decimal(str(loan.principal_balance or 0))
        i_bal = Decimal(str(loan.interest_balance or 0))

        overdue = loan.installments.filter(paid=False, due_date__lt=today)
        principal_in_arrears = overdue.aggregate(
            total=Coalesce(Sum('principal_portion'), Decimal('0'))
        )['total']

        total_due_today = loan.installments.filter(
            paid=False, due_date__lte=today
        ).aggregate(
            total=Coalesce(Sum(F('principal_portion') + F('interest_portion')), Decimal('0'))
        )['total']

        penalty_due = overdue.aggregate(
            total=Coalesce(Sum('penalty_amount'), Decimal('0'))
        )['total']

        report_data.append({
            'borrower': f"{loan.member.first_name} {loan.member.last_name}",
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
            'account_number': loan.member.member_number,
            'contact': loan.member.phone_number,
            'loan_disbursed': Decimal(str(loan.principal_amount or 0)),
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'principal_balance': p_bal,
            'interest_balance': i_bal,
            'principal_in_arrears': principal_in_arrears,
            'total_dues': total_due_today + penalty_due,
            'par': p_bal if principal_in_arrears > 0 else Decimal('0'),
        })

    total_disbursed = sum(item['loan_disbursed'] for item in report_data)
    total_outstanding = sum(item['principal_balance'] + item['interest_balance'] for item in report_data)
    total_par = sum(item['par'] for item in report_data)

    columns = [
        {'key': 'borrower', 'label': 'Borrower', 'align': 'left'},
        {'key': 'account_number', 'label': 'Account No', 'align': 'left'},
        {'key': 'loan_disbursed', 'label': 'Disbursed (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_balance', 'label': 'Principal (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_in_arrears', 'label': 'Arrears (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_dues', 'label': 'Total Due (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'par', 'label': 'PAR (UGX)', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
        {'key': 'disbursement_date', 'label': 'Disbursed Date', 'align': 'center', 'type': 'date'},
    ]

    totals = {
        'loan_disbursed': total_disbursed,
        'principal_balance': total_outstanding,
        'interest_balance': sum(item['interest_balance'] for item in report_data),
        'principal_in_arrears': sum(item['principal_in_arrears'] for item in report_data),
        'total_dues': sum(item['total_dues'] for item in report_data),
        'par': total_par,
    }

    kpi_cards = [
        {'icon': 'bi-bank', 'value': f'UGX {total_disbursed:,.0f}', 'label': 'Total Disbursed', 'type': 'success'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_outstanding:,.0f}', 'label': 'Total Outstanding', 'type': 'info'},
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {total_par:,.0f}', 'label': 'Portfolio at Risk', 'type': 'danger'},
    ]

    context = {
        'company': Company.get_company(),
        'report_title': 'Loan Portfolio Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': start_date or 'All',
        'date_to': end_date or 'All',
        'columns': columns,
        'data': report_data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'has_data': len(report_data) > 0,
        'officer_list': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
        'summary_totals': {
            'total_records': len(report_data),
            'total_amount': total_disbursed,
            'total_paid': total_disbursed - total_outstanding,
            'outstanding': total_outstanding,
            'recovery_rate': ((total_disbursed - total_outstanding) / total_disbursed * 100) if total_disbursed > 0 else 0,
            'par_30': (total_par / total_disbursed * 100) if total_disbursed > 0 else 0,
        },
    }

    return render(request, 'finance/reports/base_report.html', context)




@login_required
def arrears_report(request):
    """Arrears & Delinquency Report with aging buckets"""
    from datetime import datetime

    if request.method == "POST":
        date_at_str = request.POST.get('date_at')
        search_query = request.POST.get('search_query')
    else:
        date_at_str = request.GET.get('date_at')
        search_query = request.GET.get('search_query')

    today = date.today()
    if date_at_str:
        try:
            target_date = datetime.strptime(date_at_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    overdue_installments = Installment.objects.filter(
        paid=False,
        due_date__lt=target_date,
        loan__status__in=['approved', 'active', 'arrears']
    ).select_related('loan', 'loan__member', 'loan__officer')

    if search_query:
        overdue_installments = overdue_installments.filter(
            Q(loan__member__first_name__icontains=search_query) |
            Q(loan__member__last_name__icontains=search_query) |
            Q(loan__member__member_number__icontains=search_query) |
            Q(loan__loan_reference__icontains=search_query)
        )

    overdue_installments = overdue_installments.annotate(
        arrears_amount=(
            Coalesce(F('principal_portion') - F('principal_paid'), Decimal('0')) +
            Coalesce(F('interest_portion') - F('interest_paid'), Decimal('0')) +
            Coalesce(F('penalty_amount') - F('penalty_paid'), Decimal('0'))
        ),
        days_overdue=(target_date - F('due_date'))
    )

    overdue_installments = overdue_installments.order_by('-days_overdue')

    data = []
    total_arrears = Decimal('0')

    for inst in overdue_installments:
        days = (target_date - inst.due_date).days
        data.append({
            'member_no': inst.loan.member.member_number or str(inst.loan.member.id),
            'member_name': f"{inst.loan.member.first_name} {inst.loan.member.last_name}",
            'loan_ref': inst.loan.loan_reference or f"LN-{inst.loan.id}",
            'phone': inst.loan.member.phone_number,
            'due_date': inst.due_date,
            'days_overdue': days,
            'principal_due': inst.principal_portion - inst.principal_paid,
            'interest_due': inst.interest_portion - inst.interest_paid,
            'penalty_due': inst.penalty_amount - inst.penalty_paid,
            'total_due': (inst.principal_portion - inst.principal_paid) +
                         (inst.interest_portion - inst.interest_paid) +
                         (inst.penalty_amount - inst.penalty_paid),
            'officer': inst.loan.officer.get_full_name() if inst.loan.officer else 'System',
        })
        total_arrears += data[-1]['total_due']

    aging_buckets = {
        '1-30_days': Decimal('0'),
        '31-60_days': Decimal('0'),
        '61-90_days': Decimal('0'),
        '91-180_days': Decimal('0'),
        '180_plus': Decimal('0'),
    }

    for item in data:
        days = item['days_overdue']
        amount = item['total_due']
        if 1 <= days <= 30:
            aging_buckets['1-30_days'] += amount
        elif 31 <= days <= 60:
            aging_buckets['31-60_days'] += amount
        elif 61 <= days <= 90:
            aging_buckets['61-90_days'] += amount
        elif 91 <= days <= 180:
            aging_buckets['91-180_days'] += amount
        else:
            aging_buckets['180_plus'] += amount

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member_name', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'due_date', 'label': 'Due Date', 'align': 'center', 'type': 'date'},
        {'key': 'days_overdue', 'label': 'Days Overdue', 'align': 'center'},
        {'key': 'principal_due', 'label': 'Principal Due', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due', 'align': 'right', 'type': 'currency', 'total': True, 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]

    totals = {
        'principal_due': sum(item['principal_due'] for item in data),
        'interest_due': sum(item['interest_due'] for item in data),
        'penalty_due': sum(item['penalty_due'] for item in data),
        'total_due': total_arrears,
    }

    total_outstanding_loans = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).count()

    kpi_cards = [
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {total_arrears:,.0f}', 'label': 'Total Arrears', 'type': 'danger'},
        {'icon': 'bi-clock-history', 'value': f'{len(data):,}', 'label': 'Overdue Installments', 'type': 'warning'},
        {'icon': 'bi-percent', 'value': f'{(total_arrears / (total_outstanding_loans + 1)):.1f}%', 'label': 'Arrears Rate', 'type': 'info'},
    ]

    aging_summary = [
        {'bucket': '1-30 Days', 'amount': aging_buckets['1-30_days']},
        {'bucket': '31-60 Days', 'amount': aging_buckets['31-60_days']},
        {'bucket': '61-90 Days', 'amount': aging_buckets['61-90_days']},
        {'bucket': '91-180 Days', 'amount': aging_buckets['91-180_days']},
        {'bucket': '180+ Days', 'amount': aging_buckets['180_plus']},
    ]

    context = {
        'company': Company.get_company(),
        'report_title': 'Arrears & Delinquency Report',
        'generated_by': request.user.get_full_name() or request.user.username,
        'generated_date': timezone.now().strftime('%d %b, %Y %H:%M'),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'has_data': len(data) > 0,
        'aging_summary': aging_summary,
        'summary_totals': {
            'total_records': len(data),
            'total_amount': total_arrears,
            'total_paid': 'N/A',
            'outstanding': total_arrears,
            'recovery_rate': 'N/A',
            'par_30': f'{(total_arrears / (total_outstanding_loans + 1)):.1f}',
        },
    }

    return render(request, 'finance/reports/base_report.html', context)


# finance/views.py (add/replace this function)

from decimal import Decimal
from django.shortcuts import render
from django.http import FileResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from .models import GeneralLedger, ChartOfAccount, Company
from .utils import generate_excel_report

User = get_user_model()

@login_required
def general_ledger_report(request):
    """
    Professional General Ledger report with date range, account, and account type filters.
    Supports HTML display and Excel export.
    """
    # --- 1. Extract filters from GET or POST ---
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    account_id = request.GET.get('account') or request.POST.get('account')
    account_type = request.GET.get('account_type') or request.POST.get('account_type')
    # Status is included for compatibility with base template – can be used later
    status = request.GET.get('status') or request.POST.get('status')
    # Officer is not used in GL report, but we pass an empty list for the template

    # --- 2. Base queryset ---
    qs = GeneralLedger.objects.select_related('account')

    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if account_id:
        qs = qs.filter(account_id=account_id)
    if account_type:
        qs = qs.filter(account__account_type=account_type)

    # --- 3. Build data rows ---
    data = []
    total_debit = Decimal('0.00')
    total_credit = Decimal('0.00')

    for entry in qs.order_by('date', 'id'):
        data.append({
            'date': entry.date,
            'account_code': entry.account.code,
            'account_name': entry.account.name,
            'description': entry.description,
            'reference': entry.reference or '-',
            'debit': entry.debit,
            'credit': entry.credit,
            'balance': entry.balance,
        })
        total_debit += entry.debit
        total_credit += entry.credit

    # --- 4. Define columns ---
    columns = [
        {'key': 'date', 'label': 'Date', 'type': 'date', 'align': 'center'},
        {'key': 'account_code', 'label': 'Account Code', 'align': 'left'},
        {'key': 'account_name', 'label': 'Account Name', 'align': 'left'},
        {'key': 'description', 'label': 'Description', 'align': 'left'},
        {'key': 'reference', 'label': 'Reference', 'align': 'left'},
        {'key': 'debit', 'label': 'Debit (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'credit', 'label': 'Credit (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'balance', 'label': 'Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
    ]

    totals = {'debit': total_debit, 'credit': total_credit}

    # --- 5. KPIs ---
    kpi_cards = [
        {'label': 'Total Entries', 'value': qs.count(), 'icon': 'bi-list-ul', 'type': 'info'},
        {'label': 'Total Debit', 'value': f"UGX {total_debit:,.0f}", 'icon': 'bi-arrow-down', 'type': 'danger'},
        {'label': 'Total Credit', 'value': f"UGX {total_credit:,.0f}", 'icon': 'bi-arrow-up', 'type': 'success'},
        {'label': 'Net Movement', 'value': f"UGX {abs(total_debit - total_credit):,.0f}", 'icon': 'bi-arrows-vertical', 'type': 'warning'},
    ]

    # --- 6. Summary totals (bottom section) ---
    summary_totals = {
        'total_records': qs.count(),
        'total_amount': total_debit + total_credit,
        'total_paid': total_credit,   # Placeholder, not really applicable
        'outstanding': total_debit,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    # --- 7. Account list for dropdown ---
    account_list = ChartOfAccount.objects.filter(is_active=True).order_by('code')

    # --- 8. Account type choices ---
    account_type_choices = ChartOfAccount.ACCOUNT_TYPES

    # --- 9. Selected values for display in filter badges ---
    selected_account_display = None
    if account_id:
        try:
            acc = ChartOfAccount.objects.get(id=account_id)
            selected_account_display = f"{acc.code} – {acc.name}"
        except ChartOfAccount.DoesNotExist:
            pass

    selected_account_type_display = dict(account_type_choices).get(account_type)

    # --- 10. Officer list (required by base template – empty for GL) ---
    officer_list = User.objects.filter(is_active=True).order_by('first_name', 'last_name')

    # --- 11. Build final context ---
    context = {
        'columns': columns,
        'data': data,
        'totals': totals,
        'has_data': bool(data),
        'kpi_cards': kpi_cards,
        'report_title': 'General Ledger Report',
        'company': Company.get_company(),
        'date_from': date_from,
        'date_to': date_to,
        'selected_account': account_id,
        'selected_account_type': account_type,
        'selected_status': status,               # optional – passed to template
        'selected_account_display': selected_account_display,
        'selected_account_type_display': selected_account_type_display,
        'account_list': account_list,
        'account_type_choices': account_type_choices,
        'officer_list': officer_list,            # for the officer dropdown
        'officer_name': None,                    # not used in GL
        'summary_totals': summary_totals,
        'generated_date': timezone.now().strftime('%d %b %Y %H:%M'),
        'generated_by': request.user.get_full_name() if request.user.is_authenticated else 'System',
    }

    # --- 12. Handle Excel export ---
    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"General_Ledger_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        response = FileResponse(
            excel_file,
            as_attachment=True,
            filename=filename,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        return response

    return render(request, 'finance/reports/base_report.html', context)
def report_view(request):
    """
    Main report view – handles both HTML display and Excel export.
    """
    date_from = request.POST.get('date_from') or request.GET.get('date_from')
    date_to = request.POST.get('date_to') or request.GET.get('date_to')
    officer_id = request.POST.get('officer') or request.GET.get('officer')
    status = request.POST.get('status') or request.GET.get('status')

    qs = Loan.objects.select_related('member', 'officer')

    if date_from:
        qs = qs.filter(disbursed_date__gte=date_from)
    if date_to:
        qs = qs.filter(disbursed_date__lte=date_to)
    if officer_id:
        qs = qs.filter(officer_id=officer_id)
    if status:
        qs = qs.filter(status=status)

    columns = [
        {'key': 'loan_reference', 'label': 'Loan Reference'},
        {'key': 'member_name', 'label': 'Member'},
        {'key': 'principal', 'label': 'Principal', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'interest_balance', 'label': 'Interest Balance', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'total_balance', 'label': 'Total Balance', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'status', 'label': 'Status', 'type': 'status'},
        {'key': 'disbursed_date', 'label': 'Disbursed', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer'},
    ]

    data = []
    total_principal = Decimal('0.00')
    total_interest = Decimal('0.00')
    total_balance = Decimal('0.00')

    for loan in qs:
        principal = loan.principal_amount or Decimal('0.00')
        interest = loan.interest_balance or Decimal('0.00')
        balance = principal + interest

        data.append({
            'loan_reference': loan.loan_reference or f"LN-{loan.id}",
            'member_name': loan.member.get_full_name() if loan.member else 'N/A',
            'principal': principal,
            'interest_balance': interest,
            'total_balance': balance,
            'status': loan.get_status_display(),
            'disbursed_date': loan.disbursed_date,
            'officer': loan.officer.get_full_name() if loan.officer else 'N/A',
        })

        total_principal += principal
        total_interest += interest
        total_balance += balance

    totals = {
        'principal': total_principal,
        'interest_balance': total_interest,
        'total_balance': total_balance,
    }

    record_count = len(data)
    kpi_cards = [
        {'label': 'Total Loans', 'value': record_count, 'icon': 'bi-file-earmark-text', 'type': 'info'},
        {'label': 'Total Principal', 'value': f"UGX {total_principal:,.0f}", 'icon': 'bi-cash', 'type': 'success'},
        {'label': 'Total Interest', 'value': f"UGX {total_interest:,.0f}", 'icon': 'bi-percent', 'type': 'warning'},
        {'label': 'Total Balance', 'value': f"UGX {total_balance:,.0f}", 'icon': 'bi-wallet2', 'type': 'danger'},
    ]

    summary_totals = {
        'total_records': record_count,
        'total_amount': total_balance,
        'total_paid': Decimal('0.00'),
        'outstanding': total_balance,
        'recovery_rate': 0,
        'par_30': 0,
    }

    officer_list = User.objects.filter(is_active=True).order_by('first_name', 'last_name')

    context = {
        'columns': columns,
        'data': data,
        'totals': totals,
        'has_data': bool(data),
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'aging_summary': [],
        'report_title': 'Loan Portfolio Report',
        'company': Company.get_company(),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'selected_status': status,
        'officer_list': officer_list,
        'officer_name': dict(officer_list.values_list('id', 'username')).get(int(officer_id) if officer_id else None),
        'generated_date': timezone.now().strftime('%d %b %Y %H:%M'),
        'generated_by': request.user.get_full_name() if request.user.is_authenticated else 'System',
    }

    if request.POST.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        response = FileResponse(
            excel_file,
            as_attachment=True,
            filename=filename,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        return response

    return render(request, 'finance/reports/base_report.html', context)


# finance/views.py
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Loan, Installment, ManualPenalty
# finance/views.py
from decimal import Decimal
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from .models import Loan, Installment, ManualPenalty


# finance/views.py
from decimal import Decimal
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from .models import Loan, Installment, ManualPenalty

@permission_required('finance.can_apply_manual_penalty')
def apply_manual_penalty(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id)

    if request.method == 'POST':
        amount_str = request.POST.get('amount')
        reason = request.POST.get('reason')
        installment_id = request.POST.get('installment_id')

        # Validate amount
        try:
            amount = Decimal(amount_str)
        except (ValueError, TypeError):
            messages.error(request, "Invalid amount. Please enter a valid number.")
            return redirect('loan_detail', pk=loan.id)

        if amount <= 0:
            messages.error(request, "Amount must be greater than zero.")
            return redirect('loan_detail', pk=loan.id)

        if not reason or reason.strip() == '':
            messages.error(request, "Please provide a reason for the penalty.")
            return redirect('loan_detail', pk=loan.id)

        installment = None
        if installment_id:
            installment = get_object_or_404(Installment, id=installment_id, loan=loan)

        # Create the manual penalty
        penalty = ManualPenalty.objects.create(
            loan=loan,
            installment=installment,
            amount=amount,
            reason=reason,
            applied_by=request.user,
        )

        messages.success(request, f"Manual penalty of UGX {amount:,.2f} applied to loan {loan.loan_reference}.")
        return redirect('loan_detail', pk=loan.id)

    # GET: show form
    installments = loan.installments.filter(paid=False).order_by('due_date')
    context = {
        'loan': loan,
        'installments': installments,
    }
    return render(request, 'finance/apply_manual_penalty.html', context)

@permission_required('finance.can_waive_penalty')
def waive_manual_penalty(request, penalty_id):
    """
    View to waive an active manual penalty.
    """
    penalty = get_object_or_404(ManualPenalty, id=penalty_id)

    if request.method == 'POST':
        reason = request.POST.get('reason')

        if not penalty.is_waived:
            penalty.is_waived = True
            penalty.waived_by = request.user
            penalty.waived_date = timezone.now()
            penalty.waiver_reason = reason
            penalty.save()
            messages.success(request, "Penalty waived successfully.")
        else:
            messages.warning(request, "This penalty has already been waived.")

        return redirect('loan_detail', pk=penalty.loan.id)

    # GET: show confirmation page
    context = {'penalty': penalty}
    return render(request, 'finance/waive_penalty.html', context)



from decimal import Decimal
from django.db.models import Sum, Q, F, Value, Count, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Loan, Installment, Company
from decimal import Decimal
from django.db.models import Sum, Q
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Loan, Company

@login_required
def loan_portfolio_report(request):
    """
    Comprehensive Loan Portfolio Report with classification.
    Filters: date range, officer, product, status, classification, loan_status.
    """
    # Extract filters
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    product = request.GET.get('product') or request.POST.get('product')
    status_filter = request.GET.get('status') or request.POST.get('status')  # 'active', 'pending', etc.
    classification_filter = request.GET.get('classification') or request.POST.get('classification')
    loan_status_filter = request.GET.get('loan_status') or request.POST.get('loan_status')  # 'outstanding' / 'closed'

    # Base queryset
    qs = Loan.objects.select_related('member', 'officer').prefetch_related('installments')

    if date_from:
        qs = qs.filter(disbursed_date__gte=date_from)
    if date_to:
        qs = qs.filter(disbursed_date__lte=date_to)
    if officer_id:
        qs = qs.filter(officer_id=officer_id)
    if product:
        qs = qs.filter(product_type=product)
    if status_filter:
        qs = qs.filter(status=status_filter)

    # Build data
    data = []
    total_disbursed = Decimal('0')
    total_outstanding = Decimal('0')
    total_closed = Decimal('0')

    today = timezone.now().date()

    for loan in qs:
        principal_bal = loan.principal_balance or Decimal('0')
        interest_bal = loan.interest_balance or Decimal('0')
        total_bal = principal_bal + interest_bal

        is_closed = (total_bal == Decimal('0')) or (loan.status == 'closed')

        # Apply loan_status filter (outstanding/closed)
        if loan_status_filter and loan_status_filter != 'all':
            if loan_status_filter == 'outstanding' and is_closed:
                continue
            if loan_status_filter == 'closed' and not is_closed:
                continue

        # Classification
        overdue_inst = loan.installments.filter(paid=False, due_date__lt=today).order_by('due_date').first()
        classification = 'Performing'
        days_overdue = 0
        if overdue_inst:
            days_overdue = (today - overdue_inst.due_date).days
            if days_overdue > 180:
                classification = 'Loss'
            elif days_overdue > 90:
                classification = 'Doubtful'
            elif days_overdue > 30:
                classification = 'Substandard'
            else:
                classification = 'Watch'

        if classification_filter and classification_filter != 'all':
            if classification_filter.lower() != classification.lower():
                continue

        data.append({
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'product': loan.get_product_type_display(),
            'disbursed_date': loan.disbursed_date or loan.start_date,
            'principal': loan.principal_amount,
            'principal_balance': principal_bal,
            'interest_balance': interest_bal,
            'total_balance': total_bal,
            'is_closed': is_closed,
            'status': 'Closed' if is_closed else loan.status.title(),
            'classification': classification,
            'days_overdue': days_overdue,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })

        total_disbursed += loan.principal_amount
        if not is_closed:
            total_outstanding += total_bal
        else:
            total_closed += 1

    # Columns for the table
    columns = [
        {'key': 'loan_ref', 'label': 'Loan Ref'},
        {'key': 'member', 'label': 'Member'},
        {'key': 'member_no', 'label': 'Member No'},
        {'key': 'product', 'label': 'Product'},
        {'key': 'disbursed_date', 'label': 'Disbursed', 'type': 'date'},
        {'key': 'principal', 'label': 'Principal (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'principal_balance', 'label': 'Principal Bal (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'interest_balance', 'label': 'Interest Bal (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'total_balance', 'label': 'Total Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
        {'key': 'classification', 'label': 'Classification', 'align': 'center', 'type': 'status'},
        {'key': 'days_overdue', 'label': 'Days Overdue', 'align': 'center'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'officer', 'label': 'Officer'},
    ]

    # Totals
    totals = {
        'principal': sum(item['principal'] for item in data),
        'principal_balance': sum(item['principal_balance'] for item in data),
        'interest_balance': sum(item['interest_balance'] for item in data),
        'total_balance': sum(item['total_balance'] for item in data),
    }

    # KPIs
    kpi_cards = [
        {'label': 'Total Loans', 'value': len(data), 'icon': 'bi-file-text', 'type': 'info'},
        {'label': 'Total Disbursed', 'value': f"UGX {total_disbursed:,.0f}", 'icon': 'bi-arrow-up', 'type': 'success'},
        {'label': 'Outstanding Balance', 'value': f"UGX {total_outstanding:,.0f}", 'icon': 'bi-currency-dollar', 'type': 'warning'},
        {'label': 'Closed Loans', 'value': total_closed, 'icon': 'bi-check-circle', 'type': 'secondary'},
    ]

    from django.contrib.auth import get_user_model
    User = get_user_model()
    officer_list = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    product_choices = Loan.PRODUCT_CHOICES

    context = {
        'columns': columns,
        'data': data,
        'totals': totals,
        'has_data': bool(data),
        'kpi_cards': kpi_cards,
        'report_title': 'Loan Portfolio Report',
        'company': Company.get_company(),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'selected_product': product,
        'selected_status': status_filter,
        'selected_classification': classification_filter,
        'selected_loan_status': loan_status_filter,
        'officer_list': officer_list,
        'product_choices': product_choices,
        'classification_choices': [
            ('all', 'All Classifications'),
            ('performing', 'Performing'),
            ('watch', 'Watch'),
            ('substandard', 'Substandard'),
            ('doubtful', 'Doubtful'),
            ('loss', 'Loss'),
        ],
        'loan_status_choices': [
            ('all', 'All Loans'),
            ('outstanding', 'Outstanding'),
            ('closed', 'Closed'),
        ],
        'generated_date': timezone.now().strftime('%d %b %Y %H:%M'),
        'generated_by': request.user.get_full_name() if request.user.is_authenticated else 'System',
    }

    return render(request, 'finance/reports/loan_portfolio_report.html', context)


from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from .models import Installment

@permission_required('finance.can_waive_penalty')  # or any suitable permission
def waive_auto_penalty(request, installment_id):
    """
    Waive the auto-calculated penalty for a specific installment.
    Sets penalty_amount to 0 and records who/why.
    """
    installment = get_object_or_404(Installment, id=installment_id)

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "Please provide a reason for waiving the penalty.")
            return redirect('loan_detail', pk=installment.loan.id)

        # Perform the waiver
        installment.penalty_amount = Decimal('0.00')
        installment.penalty_waived = True
        installment.penalty_waived_by = request.user
        installment.penalty_waived_date = timezone.now()
        installment.penalty_waiver_reason = reason
        installment.save(update_fields=[
            'penalty_amount', 'penalty_waived', 'penalty_waived_by',
            'penalty_waived_date', 'penalty_waiver_reason'
        ])

        messages.success(request, f"Penalty for installment #{installment.id} has been waived.")
        return redirect('loan_detail', pk=installment.loan.id)

    # GET: show confirmation form
    return render(request, 'finance/waive_auto_penalty.html', {
        'installment': installment,
        'loan': installment.loan,
    })


# finance/views.py
import random
from decimal import Decimal
from datetime import datetime, date, timedelta
from django.db.models import Sum, Q, F, Count, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import render
from django.http import FileResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User, Group
from .models import (
    Loan, Installment, Member, SystemSetting, GeneralLedger, ChartOfAccount,
    SavingsAccount, Transaction, Company, SMSConfig
)
from .utils import generate_excel_report

User = get_user_model()

# ====================================================================
# HELPER: Generate common context for base_report.html
# ====================================================================
def _get_base_context(request, extra_context):
    from django.contrib.auth import get_user_model
    from finance.models import Company  # adjust import
    User = get_user_model()

    company_obj = Company.objects.first()
    if company_obj:
        company = {
            'name': company_obj.name if company_obj else 'Company',
            'logo': company_obj.logo if company_obj else None,
            'phone': company_obj.phone if company_obj else '',
            'email': company_obj.email if company_obj else '',
            'website': company_obj.website if company_obj else '',
            'tagline': company_obj.tagline if company_obj else '',
        }
    else:
        company = {}

    context = {
        'company': company,
        'generated_date': timezone.now().strftime('%Y-%m-%d %H:%M'),
        'generated_by': request.user.get_full_name() or request.user.username,
        'officer_list': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
        'account_list': [],
        'account_type_choices': [],
    }
    context.update(extra_context)
    return context
# ====================================================================
# 1. LOAN PORTFOLIO REPORT (loan_report)
# ====================================================================
@login_required
def loan_report(request):
    """Professional Loan Portfolio Report with Filters"""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    status = request.GET.get('status') or request.POST.get('status')
    account = request.GET.get('account') or request.POST.get('account')  # not used but kept for consistency

    loans = Loan.objects.select_related('member', 'officer').prefetch_related('repayments')
    if date_from:
        loans = loans.filter(disbursed_date__gte=date_from)
    if date_to:
        loans = loans.filter(disbursed_date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)
    if status:
        loans = loans.filter(status=status)

    loans = loans.annotate(
        paid_amount=Sum('repayments__amount_paid', default=0),
        total_balance=F('principal_balance') + F('interest_balance'),
    )

    data = []
    total_amount = Decimal('0')
    total_paid = Decimal('0')
    total_balance = Decimal('0')

    for loan in loans:
        balance = loan.total_balance or Decimal('0')
        paid = loan.paid_amount or Decimal('0')

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}".strip(),
            'member_no': loan.member.member_number or str(loan.member.id),
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'amount': loan.principal_amount,
            'paid': paid,
            'balance': balance,
            'status': loan.get_status_display(),
            'date': loan.disbursed_date or loan.start_date,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })
        total_amount += loan.principal_amount or Decimal('0')
        total_paid += paid
        total_balance += balance

    recovery_rate = round((total_paid / total_amount * 100), 1) if total_amount > 0 else 0
    par_30 = round((total_balance / total_amount * 100), 1) if total_amount > 0 else 0
    total_records = len(data)

    columns = [
        {'key': 'member', 'label': 'Member Name', 'align': 'left'},
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Reference', 'align': 'left'},
        {'key': 'amount', 'label': 'Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'paid', 'label': 'Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'balance', 'label': 'Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'date', 'label': 'Disbursed', 'align': 'center', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]

    totals = {'amount': total_amount, 'paid': total_paid, 'balance': total_balance}
    kpi_cards = [
        {'icon': 'bi-people', 'value': f'{total_records:,}', 'label': 'Total Loans', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_amount:,.0f}', 'label': 'Total Portfolio', 'type': 'success'},
        {'icon': 'bi-check-circle', 'value': f'{recovery_rate}%', 'label': 'Recovery Rate', 'type': 'info'},
        {'icon': 'bi-exclamation-triangle', 'value': f'{par_30}%', 'label': 'PAR 30', 'type': 'warning'},
    ]
    summary_totals = {
        'total_records': total_records,
        'total_amount': total_amount,
        'total_paid': total_paid,
        'outstanding': total_balance,
        'recovery_rate': recovery_rate,
        'par_30': par_30,
    }

    selected_officer_display = None
    if officer_id:
        try:
            off = User.objects.get(id=officer_id)
            selected_officer_display = off.get_full_name() or off.username
        except User.DoesNotExist:
            pass

    context = _get_base_context(request, {
        'report_title': 'Loan Portfolio Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'selected_status': status,
        'officer_name': selected_officer_display,
        'selected_account': account,  # not used but passed
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 2. MEMBER REPORT (member_report)
# ====================================================================
@login_required
def member_report(request):
    """Member Registry Report"""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    status_filter = request.GET.get('status') or request.POST.get('status')

    members = Member.objects.all().order_by('member_number')
    if date_from:
        members = members.filter(date_joined__gte=date_from)
    if date_to:
        members = members.filter(date_joined__lte=date_to)
    # status filter could be used if Member has a status field – here we ignore

    data = []
    total_savings = Decimal('0')
    total_loans = Decimal('0')

    for member in members:
        savings = SavingsAccount.objects.filter(member=member).first()
        savings_balance = savings.balance if savings else Decimal('0')
        total_loans_balance = member.loans.filter(is_active=True).aggregate(
            total=Sum('principal_balance') + Sum('interest_balance')
        )['total'] or Decimal('0')

        status_display = 'Active'  # placeholder
        data.append({
            'member_no': member.member_number,
            'name': f"{member.first_name} {member.last_name}",
            'phone': member.phone_number,
            'email': member.email or '—',
            'savings': savings_balance,
            'loans': total_loans_balance,
            'joined': member.date_joined,
            'status': status_display,
        })
        total_savings += savings_balance
        total_loans += total_loans_balance

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'name', 'label': 'Member Name', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'email', 'label': 'Email', 'align': 'left'},
        {'key': 'savings', 'label': 'Savings (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'loans', 'label': 'Loans (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'joined', 'label': 'Joined', 'align': 'center', 'type': 'date'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
    ]
    totals = {'savings': total_savings, 'loans': total_loans}
    kpi_cards = [
        {'icon': 'bi-people', 'value': f'{len(data):,}', 'label': 'Total Members', 'type': 'info'},
        {'icon': 'bi-wallet2', 'value': f'UGX {total_savings:,.0f}', 'label': 'Total Savings', 'type': 'success'},
        {'icon': 'bi-bank', 'value': f'UGX {total_loans:,.0f}', 'label': 'Total Loans', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_savings + total_loans,
        'total_paid': total_savings,
        'outstanding': total_loans,
        'recovery_rate': '100',
        'par_30': '0',
    }

    context = _get_base_context(request, {
        'report_title': 'Member Registry Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_status': status_filter,
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 3. SAVINGS REPORT (savings_report)
# ====================================================================
@login_required
def savings_report(request):
    """Savings Summary Report"""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    # Filter by date range on transactions? We'll filter savings accounts by member join date or ignore.

    savings_accounts = SavingsAccount.objects.select_related('member').all()
    # Could filter by date if member has date_joined, but not required

    data = []
    total_balance = Decimal('0')

    for savings in savings_accounts:
        data.append({
            'member': f"{savings.member.first_name} {savings.member.last_name}",
            'member_no': savings.member.member_number,
            'phone': savings.member.phone_number,
            'balance': savings.balance,
            'account_no': savings.account_number if hasattr(savings, 'account_number') else 'N/A',
            'status': 'Active' if savings.balance > 0 else 'Inactive',
        })
        total_balance += savings.balance

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member Name', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'account_no', 'label': 'Account No', 'align': 'left'},
        {'key': 'balance', 'label': 'Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
    ]
    totals = {'balance': total_balance}
    kpi_cards = [
        {'icon': 'bi-wallet2', 'value': f'{len(data):,}', 'label': 'Total Accounts', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_balance:,.0f}', 'label': 'Total Savings', 'type': 'success'},
        {'icon': 'bi-people', 'value': f'{len(data):,}', 'label': 'Active Members', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_balance,
        'total_paid': total_balance,
        'outstanding': 0,
        'recovery_rate': '100',
        'par_30': '0',
    }

    context = _get_base_context(request, {
        'report_title': 'Savings Summary Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 4. FINANCIAL PERFORMANCE REPORT (financial_report)
# ====================================================================
@login_required
def financial_report(request):
    """Income/Expense Financial Performance Report"""
    if request.method == "POST":
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
    else:
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

    if not date_from:
        date_from = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = date.today().strftime('%Y-%m-%d')

    transactions = Transaction.objects.filter(
        timestamp__date__gte=date_from,
        timestamp__date__lte=date_to
    )

    total_income = transactions.filter(
        Q(type='deposit') | Q(type='repayment') | Q(type='interest_payment')
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    total_expenses = transactions.filter(
        Q(type='withdrawal') | Q(type='disbursement') | Q(type='penalty')
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    net_profit = total_income - total_expenses

    monthly_data = transactions.annotate(
        month=TruncMonth('timestamp')
    ).values('month').annotate(
        income=Sum('amount', filter=Q(type__in=['deposit', 'repayment', 'interest_payment'])),
        expense=Sum('amount', filter=Q(type__in=['withdrawal', 'disbursement', 'penalty']))
    ).order_by('month')

    data = []
    for entry in monthly_data:
        data.append({
            'month': entry['month'].strftime('%b %Y') if entry['month'] else 'N/A',
            'income': entry['income'] or Decimal('0'),
            'expense': entry['expense'] or Decimal('0'),
            'profit': (entry['income'] or Decimal('0')) - (entry['expense'] or Decimal('0')),
        })

    columns = [
        {'key': 'month', 'label': 'Month', 'align': 'left'},
        {'key': 'income', 'label': 'Income (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'expense', 'label': 'Expenses (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'profit', 'label': 'Net Profit (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]
    totals = {'income': total_income, 'expense': total_expenses, 'profit': net_profit}
    kpi_cards = [
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_income:,.0f}', 'label': 'Total Income', 'type': 'success'},
        {'icon': 'bi-cash', 'value': f'UGX {total_expenses:,.0f}', 'label': 'Total Expenses', 'type': 'danger'},
        {'icon': 'bi-graph-up', 'value': f'UGX {net_profit:,.0f}', 'label': 'Net Profit', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_income + total_expenses,
        'total_paid': total_income,
        'outstanding': total_expenses,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Financial Performance Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)

# HELPER: Build a single officer row
# --------------------------------------------------------------------
def _build_officer_row(officer, loans, today, date_from, date_to):
    """
    Compute all metrics for one officer and return a dict with the row data.
    """
    from datetime import datetime

    # Convert date strings to date objects if needed
    if isinstance(date_from, str):
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
    if isinstance(date_to, str):
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()

    row = {
        'officer': officer.get_full_name() or officer.username,
        'disbursed_loans': 0,
        'disbursed_amount': Decimal('0'),
        'loans_in_arrears': 0,
        'expected_amount': Decimal('0'),
        'outstanding_loans': 0,
        'outstanding_amount': Decimal('0'),
        'arrears_amount': Decimal('0'),
        'principal_paid': Decimal('0'),
        'principal_prepaid': Decimal('0'),
        'repayment_rate': 0,
        'effective_repayment_rate': 0,
        'arrears_rate_expected': 0,
        'arrears_rate_outstanding': 0,
        'par_1': Decimal('0'),
        'par_30': Decimal('0'),
        'par_1_percent': 0,
        'par_30_percent': 0,
    }

    # ---- Aggregate totals across all loans ----
    total_principal_paid = Decimal('0')
    total_expected = Decimal('0')
    total_collected = Decimal('0')

    for loan in loans:
        # ---- 1. Disbursed in period ----
        if loan.disbursed_date and date_from <= loan.disbursed_date <= date_to:
            row['disbursed_loans'] += 1
            row['disbursed_amount'] += loan.principal_amount or Decimal('0')

        # ---- 2. Outstanding (active with balance >0) ----
        if loan.is_active and loan.status in ['approved', 'active', 'arrears']:
            p_bal = loan.principal_balance or Decimal('0')
            i_bal = loan.interest_balance or Decimal('0')
            if p_bal + i_bal > 0:
                row['outstanding_loans'] += 1
                row['outstanding_amount'] += p_bal + i_bal

            # ---- 3. Arrears (overdue installments) ----
            overdue_inst = loan.installments.filter(paid=False, due_date__lt=today)
            if overdue_inst.exists():
                row['loans_in_arrears'] += 1
                principal_due = overdue_inst.aggregate(
                    total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
                )['total']
                interest_due = overdue_inst.aggregate(
                    total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
                )['total']
                penalty_due = overdue_inst.aggregate(
                    total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
                )['total']
                row['arrears_amount'] += principal_due + interest_due + penalty_due

                # ---- 4. PAR 1 and PAR 30 ----
                # PAR is based on principal balance (not total due)
                oldest_due = overdue_inst.earliest('due_date').due_date
                days = (today - oldest_due).days
                if days >= 1:
                    row['par_1'] += p_bal
                if days >= 30:
                    row['par_30'] += p_bal

        # ---- 5. Principal paid (all installments) ----
        principal_paid_loan = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']
        total_principal_paid += principal_paid_loan

        # ---- 6. Expected amount (principal+interest due in period) ----
        period_inst = loan.installments.filter(
            due_date__gte=date_from,
            due_date__lte=date_to
        )
        expected = period_inst.aggregate(
            total=Coalesce(Sum(F('principal_portion') + F('interest_portion')), Decimal('0'))
        )['total']
        total_expected += expected

        # ---- 7. Collected (repayments) in period ----
        collected = loan.repayments.filter(
            date_paid__date__gte=date_from,
            date_paid__date__lte=date_to
        ).aggregate(
            total=Coalesce(Sum('amount_paid'), Decimal('0'))
        )['total']
        total_collected += collected

    # ---- Set final row values ----
    row['principal_paid'] = total_principal_paid
    row['principal_prepaid'] = total_principal_paid  # same as principal paid

    # Expected and collected for the period
    row['expected_amount'] = total_expected

    # Repayment rate = collected / expected * 100
    if total_expected > 0:
        row['repayment_rate'] = round((total_collected / total_expected) * 100, 2)
    else:
        row['repayment_rate'] = 0

    # Effective repayment rate = collected / disbursed_amount * 100
    if row['disbursed_amount'] > 0:
        row['effective_repayment_rate'] = round((total_collected / row['disbursed_amount']) * 100, 2)
    else:
        row['effective_repayment_rate'] = 0

    # Arrears rate on expected
    if row['expected_amount'] > 0:
        row['arrears_rate_expected'] = round((row['arrears_amount'] / row['expected_amount']) * 100, 2)
    else:
        row['arrears_rate_expected'] = 0

    # Arrears rate on outstanding
    if row['outstanding_amount'] > 0:
        row['arrears_rate_outstanding'] = round((row['arrears_amount'] / row['outstanding_amount']) * 100, 2)
    else:
        row['arrears_rate_outstanding'] = 0

    # PAR percentages
    if row['outstanding_amount'] > 0:
        row['par_1_percent'] = round((row['par_1'] / row['outstanding_amount']) * 100, 2)
        row['par_30_percent'] = round((row['par_30'] / row['outstanding_amount']) * 100, 2)
    else:
        row['par_1_percent'] = 0
        row['par_30_percent'] = 0

    return row

# ====================================================================
# 5. OFFICER PERFORMANCE REPORT (officer_report)
# ====================================================================
# --------------------------------------------------------------------
# OFFICER PERFORMANCE / SUMMARY REPORT
# --------------------------------------------------------------------
# Add at top of views.py
from finance.utils import get_selected_columns, save_column_selection, reset_column_selection

@login_required
def officer_report(request):
    """
    Officer Summary Report with column selection.
    """
    # ---- 1. Handle column selection POST ----
    if request.method == 'POST':
        if 'save_columns' in request.POST:
            selected_keys = request.POST.getlist('columns')
            save_column_selection(request, 'officer', selected_keys)
            # Preserve existing GET parameters (date, officer, etc.)
            query = request.GET.copy()
            return redirect(f"{request.path}?{query.urlencode()}")
        elif 'reset_columns' in request.POST:
            reset_column_selection(request, 'officer')
            return redirect(request.path)

    # ---- 2. Get filters ----
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    today = date.today()
    if not date_from:
        date_from = today.replace(day=1).strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')

    # ---- 3. Get officers ----
    from django.contrib.auth import get_user_model
    User = get_user_model()
    officers = User.objects.filter(
        groups__name='Credit Officer',
        is_active=True
    ).order_by('first_name', 'last_name')
    if not officers.exists():
        officers = User.objects.filter(
            is_active=True,
            id__in=Loan.objects.values_list('officer_id', flat=True).distinct()
        ).order_by('first_name', 'last_name')
    if officer_id:
        officers = officers.filter(id=officer_id)

    # ---- 4. Prefetch loans ----
    officer_ids = list(officers.values_list('id', flat=True))
    all_loans = Loan.objects.filter(
        officer_id__in=officer_ids
    ).select_related('member').prefetch_related('installments', 'repayments')
    loans_by_officer = {}
    for loan in all_loans:
        loans_by_officer.setdefault(loan.officer_id, []).append(loan)

    # ---- 5. Build data ----
    data = []
    totals = {
        'disbursed_loans': 0,
        'disbursed_amount': Decimal('0'),
        'loans_in_arrears': 0,
        'expected_amount': Decimal('0'),
        'outstanding_loans': 0,
        'outstanding_amount': Decimal('0'),
        'arrears_amount': Decimal('0'),
        'principal_paid': Decimal('0'),
        'par_1': Decimal('0'),
        'par_30': Decimal('0'),
    }

    for officer in officers:
        loans = loans_by_officer.get(officer.id, [])
        row = _build_officer_row(officer, loans, today, date_from, date_to)
        data.append(row)
        for key in totals:
            if key in row:
                try:
                    totals[key] += row[key]
                except TypeError:
                    pass

    # ---- 6. Define all columns ----
    all_columns = [
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
        {'key': 'par_1_percent', 'label': 'PAR 1 %', 'align': 'right'},
        {'key': 'disbursed_loans', 'label': 'Disbursed Loans', 'align': 'center', 'total': True},
        {'key': 'par_30_percent', 'label': 'PAR 30 %', 'align': 'right'},
        {'key': 'disbursed_amount', 'label': 'Disbursed Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'loans_in_arrears', 'label': 'Loans in arrears', 'align': 'center', 'total': True},
        {'key': 'expected_amount', 'label': 'Amount Expected (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'outstanding_loans', 'label': 'Outstanding Loans', 'align': 'center', 'total': True},
        {'key': 'outstanding_amount', 'label': 'Outstanding Loan amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'arrears_amount', 'label': 'Arrears amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_paid', 'label': 'Principal Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_prepaid', 'label': 'Principal Prepaid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'repayment_rate', 'label': 'Repayment Rate (%)', 'align': 'right'},
        {'key': 'effective_repayment_rate', 'label': 'Effective Repayment Rate (%)', 'align': 'right'},
        {'key': 'arrears_rate_expected', 'label': 'Arrears Rate On Expected Amt (%)', 'align': 'right'},
        {'key': 'arrears_rate_outstanding', 'label': 'Arrear Rate On Outstanding Bal (%)', 'align': 'right'},
        {'key': 'par_1', 'label': 'PAR 1 (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'par_30', 'label': 'PAR 30 (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]

    # ---- 7. Get selected columns ----
    selected_keys = get_selected_columns(request, 'officer', all_columns)
    # Preserve original order from all_columns
    columns = [col for col in all_columns if col['key'] in selected_keys]

    # ---- 8. KPI cards ----
    kpi_cards = [
        {'icon': 'bi-person-badge', 'value': f'{len(data):,}', 'label': 'Total Officers', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["disbursed_amount"]:,.0f}', 'label': 'Total Disbursed', 'type': 'success'},
        {'icon': 'bi-cash-stack', 'value': f'UGX {totals["outstanding_amount"]:,.0f}', 'label': 'Total Outstanding', 'type': 'warning'},
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {totals["par_30"]:,.0f}', 'label': 'Total PAR 30', 'type': 'danger'},
    ]

    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['disbursed_amount'],
        'total_paid': 'N/A',
        'outstanding': totals['outstanding_amount'],
        'recovery_rate': 'N/A',
        'par_30': f'{(totals["par_30"] / (totals["outstanding_amount"] + 1) * 100):.1f}',
    }

    # ---- 9. Context ----
    context = _get_base_context(request, {
        'report_title': 'Officer Summary Report',
        'columns': columns,
        'all_columns': all_columns,
        'selected_column_keys': selected_keys,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)
# --------------------------------------------------------------------

# ====================================================================
# 6. ACCOUNTING REPORT (accounting_report)
# ====================================================================
@login_required
def accounting_report(request):
    """General Ledger Summary Report"""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    account = request.GET.get('account') or request.POST.get('account')

    qs = GeneralLedger.objects.select_related('account')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if account:
        qs = qs.filter(account_id=account)

    data = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')

    for entry in qs.order_by('account__code', 'date'):
        data.append({
            'account_code': entry.account.code,
            'account_name': entry.account.name,
            'account_type': entry.account.get_account_type_display(),
            'debit': entry.debit,
            'credit': entry.credit,
            'balance': entry.balance,
        })
        total_debit += entry.debit
        total_credit += entry.credit

    columns = [
        {'key': 'account_code', 'label': 'Account Code', 'align': 'left'},
        {'key': 'account_name', 'label': 'Account Name', 'align': 'left'},
        {'key': 'account_type', 'label': 'Type', 'align': 'left'},
        {'key': 'debit', 'label': 'Debit (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'credit', 'label': 'Credit (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'balance', 'label': 'Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
    ]
    totals = {'debit': total_debit, 'credit': total_credit, 'balance': total_debit - total_credit}
    kpi_cards = [
        {'icon': 'bi-journal-text', 'value': f'{len(data)}', 'label': 'Total Accounts', 'type': 'info'},
        {'icon': 'bi-arrow-down', 'value': f'UGX {total_debit:,.0f}', 'label': 'Total Debit', 'type': 'danger'},
        {'icon': 'bi-arrow-up', 'value': f'UGX {total_credit:,.0f}', 'label': 'Total Credit', 'type': 'success'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_debit + total_credit,
        'total_paid': total_credit,
        'outstanding': total_debit,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Accounting Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_account': account,
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 7. AUDIT REPORT (audit_report)
# ====================================================================
@login_required
def audit_report(request):
    """Audit Trail Report (last 100 transactions)"""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    # We'll limit to last 100 unless date filters are applied

    qs = Transaction.objects.select_related('created_by').order_by('-timestamp')
    if date_from:
        qs = qs.filter(timestamp__date__gte=date_from)
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)
    if not date_from and not date_to:
        qs = qs[:100]

    data = []
    for tx in qs:
        data.append({
            'timestamp': tx.timestamp,
            'user': tx.created_by.get_full_name() if tx.created_by else 'System',
            'type': tx.get_type_display(),
            'amount': tx.amount,
            'reference': tx.reference or '-',
            'is_reversed': 'Yes' if tx.is_reversed else 'No',
            'status': 'Reversed' if tx.is_reversed else 'Active',
        })

    columns = [
        {'key': 'timestamp', 'label': 'Date & Time', 'align': 'center', 'type': 'date'},
        {'key': 'user', 'label': 'User', 'align': 'left'},
        {'key': 'type', 'label': 'Transaction Type', 'align': 'left'},
        {'key': 'amount', 'label': 'Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'reference', 'label': 'Reference', 'align': 'left'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
    ]
    totals = {'amount': sum(item['amount'] for item in data) if data else Decimal('0')}
    kpi_cards = [
        {'icon': 'bi-clock-history', 'value': f'{len(data)}', 'label': 'Total Transactions', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["amount"]:,.0f}', 'label': 'Total Volume', 'type': 'success'},
        {'icon': 'bi-person', 'value': f'{len(set(tx.created_by_id for tx in qs if tx.created_by))}', 'label': 'Active Users', 'type': 'secondary'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['amount'],
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Audit Trail Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 8. INVENTORY REPORT (inventory_report)
# ====================================================================
@login_required
def inventory_report(request):
    """Inventory Report - Products and Stock Levels (from hardware app)"""
    try:
        from hardware.models import Product, Category
        products = Product.objects.select_related('category').all()
        has_inventory = True
    except ImportError:
        products = []
        has_inventory = False

    data = []
    total_value = Decimal('0')
    total_stock = 0

    if has_inventory:
        for product in products:
            stock_value = (product.current_stock or 0) * (product.cost_price or 0)
            data.append({
                'product_code': product.product_code,
                'product_name': product.name,
                'category': product.category.name if product.category else 'Uncategorized',
                'stock': product.current_stock or 0,
                'cost_price': product.cost_price or 0,
                'selling_price': product.selling_price or 0,
                'stock_value': stock_value,
                'status': 'Low Stock' if (product.current_stock or 0) <= (product.reorder_level or 5) else 'Healthy',
            })
            total_value += stock_value
            total_stock += (product.current_stock or 0)
    else:
        data = [{'message': 'Inventory module not installed'}]

    columns = [
        {'key': 'product_code', 'label': 'Product Code', 'align': 'left'},
        {'key': 'product_name', 'label': 'Product Name', 'align': 'left'},
        {'key': 'category', 'label': 'Category', 'align': 'left'},
        {'key': 'stock', 'label': 'Stock', 'align': 'center'},
        {'key': 'cost_price', 'label': 'Cost (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'selling_price', 'label': 'Sell (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'stock_value', 'label': 'Value (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
    ]
    totals = {'stock_value': total_value}
    kpi_cards = [
        {'icon': 'bi-boxes', 'value': f'{len(data)}', 'label': 'Total Products', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_value:,.0f}', 'label': 'Inventory Value', 'type': 'success'},
        {'icon': 'bi-box', 'value': f'{total_stock:,}', 'label': 'Total Stock Units', 'type': 'secondary'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_value,
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Inventory Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': has_inventory and bool(data),
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 9. INTEREST INCOME REPORT (interest_report)
# ====================================================================
@login_required
def interest_report(request):
    """Interest Income Report"""
    if request.method == "POST":
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        officer_id = request.POST.get('officer')
        product = request.POST.get('product')
    else:
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        officer_id = request.GET.get('officer')
        product = request.GET.get('product')

    if not date_from:
        date_from = (date.today() - timedelta(days=365)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = date.today().strftime('%Y-%m-%d')

    loans = Loan.objects.filter(
        disbursed_date__gte=date_from,
        disbursed_date__lte=date_to,
        status__in=['approved', 'active', 'closed']
    ).select_related('member', 'officer')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)
    if product:
        loans = loans.filter(product_type=product)

    data = []
    total_principal = Decimal('0')
    total_interest_charged = Decimal('0')
    total_interest_paid = Decimal('0')
    total_interest_balance = Decimal('0')

    for loan in loans:
        interest_charged = loan.installments.aggregate(total=Sum('interest_portion'))['total'] or Decimal('0')
        interest_paid = loan.installments.aggregate(total=Sum('interest_paid'))['total'] or Decimal('0')
        interest_balance = loan.interest_balance or Decimal('0')

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'principal': loan.principal_amount,
            'interest_charged': interest_charged,
            'interest_paid': interest_paid,
            'interest_balance': interest_balance,
            'status': loan.get_status_display(),
            'disbursed_date': loan.disbursed_date or loan.start_date,
        })
        total_principal += loan.principal_amount
        total_interest_charged += interest_charged
        total_interest_paid += interest_paid
        total_interest_balance += interest_balance

    columns = [
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Reference', 'align': 'left'},
        {'key': 'principal', 'label': 'Principal (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_charged', 'label': 'Interest Charged (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_paid', 'label': 'Interest Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'disbursed_date', 'label': 'Disbursed', 'align': 'center', 'type': 'date'},
    ]
    totals = {
        'principal': total_principal,
        'interest_charged': total_interest_charged,
        'interest_paid': total_interest_paid,
        'interest_balance': total_interest_balance,
    }
    kpi_cards = [
        {'icon': 'bi-percent', 'value': f'UGX {total_interest_charged:,.0f}', 'label': 'Total Interest Charged', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_interest_paid:,.0f}', 'label': 'Interest Paid', 'type': 'success'},
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {total_interest_balance:,.0f}', 'label': 'Interest Outstanding', 'type': 'warning'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_principal,
        'total_paid': total_interest_paid,
        'outstanding': total_interest_balance,
        'recovery_rate': (total_interest_paid / total_interest_charged * 100) if total_interest_charged > 0 else 0,
        'par_30': 'N/A',
    }

    selected_officer_display = None
    if officer_id:
        try:
            off = User.objects.get(id=officer_id)
            selected_officer_display = off.get_full_name() or off.username
        except User.DoesNotExist:
            pass

    context = _get_base_context(request, {
        'report_title': 'Interest Income Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': selected_officer_display,
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 10. LOAN PORTFOLIO REPORTS (loan_portfolio_reports)
# ====================================================================
@login_required
def loan_portfolio_reports(request):
    """Comprehensive Loan Portfolio Report with PAR and arrears"""
    if request.method == "POST":
        start_date = request.POST.get('date_from')
        end_date = request.POST.get('date_to')
        officer_id = request.POST.get('officer')
        status = request.POST.get('status')
    else:
        start_date = request.GET.get('date_from')
        end_date = request.GET.get('date_to')
        officer_id = request.GET.get('officer')
        status = request.GET.get('status')

    loans = Loan.objects.select_related('member', 'officer').filter(
        status__in=['approved', 'active', 'closed', 'arrears']
    ).order_by('-disbursed_date', '-start_date')

    if start_date:
        loans = loans.filter(disbursed_date__gte=start_date)
    if end_date:
        loans = loans.filter(disbursed_date__lte=end_date)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)
    if status:
        loans = loans.filter(status=status)

    today = date.today()
    report_data = []

    for loan in loans:
        p_bal = Decimal(str(loan.principal_balance or 0))
        i_bal = Decimal(str(loan.interest_balance or 0))

        overdue = loan.installments.filter(paid=False, due_date__lt=today)
        principal_in_arrears = overdue.aggregate(
            total=Coalesce(Sum('principal_portion'), Decimal('0'))
        )['total']

        total_due_today = loan.installments.filter(
            paid=False, due_date__lte=today
        ).aggregate(
            total=Coalesce(Sum(F('principal_portion') + F('interest_portion')), Decimal('0'))
        )['total']

        penalty_due = overdue.aggregate(
            total=Coalesce(Sum('penalty_amount'), Decimal('0'))
        )['total']

        report_data.append({
            'borrower': f"{loan.member.first_name} {loan.member.last_name}",
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
            'account_number': loan.member.member_number,
            'contact': loan.member.phone_number,
            'loan_disbursed': Decimal(str(loan.principal_amount or 0)),
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'principal_balance': p_bal,
            'interest_balance': i_bal,
            'principal_in_arrears': principal_in_arrears,
            'total_dues': total_due_today + penalty_due,
            'par': p_bal if principal_in_arrears > 0 else Decimal('0'),
        })

    total_disbursed = sum(item['loan_disbursed'] for item in report_data)
    total_outstanding = sum(item['principal_balance'] + item['interest_balance'] for item in report_data)
    total_par = sum(item['par'] for item in report_data)

    columns = [
        {'key': 'borrower', 'label': 'Borrower', 'align': 'left'},
        {'key': 'account_number', 'label': 'Account No', 'align': 'left'},
        {'key': 'loan_disbursed', 'label': 'Disbursed (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_balance', 'label': 'Principal (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_in_arrears', 'label': 'Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_dues', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'par', 'label': 'PAR (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
        {'key': 'disbursement_date', 'label': 'Disbursed Date', 'align': 'center', 'type': 'date'},
    ]
    totals = {
        'loan_disbursed': total_disbursed,
        'principal_balance': total_outstanding,
        'interest_balance': sum(item['interest_balance'] for item in report_data),
        'principal_in_arrears': sum(item['principal_in_arrears'] for item in report_data),
        'total_dues': sum(item['total_dues'] for item in report_data),
        'par': total_par,
    }
    kpi_cards = [
        {'icon': 'bi-bank', 'value': f'UGX {total_disbursed:,.0f}', 'label': 'Total Disbursed', 'type': 'success'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_outstanding:,.0f}', 'label': 'Total Outstanding', 'type': 'info'},
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {total_par:,.0f}', 'label': 'Portfolio at Risk', 'type': 'danger'},
    ]
    summary_totals = {
        'total_records': len(report_data),
        'total_amount': total_disbursed,
        'total_paid': total_disbursed - total_outstanding,
        'outstanding': total_outstanding,
        'recovery_rate': ((total_disbursed - total_outstanding) / total_disbursed * 100) if total_disbursed > 0 else 0,
        'par_30': (total_par / total_disbursed * 100) if total_disbursed > 0 else 0,
    }

    selected_officer_display = None
    if officer_id:
        try:
            off = User.objects.get(id=officer_id)
            selected_officer_display = off.get_full_name() or off.username
        except User.DoesNotExist:
            pass

    context = _get_base_context(request, {
        'report_title': 'Loan Portfolio Report',
        'columns': columns,
        'data': report_data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(report_data),
        'date_from': start_date or 'All',
        'date_to': end_date or 'All',
        'selected_officer': officer_id,
        'officer_name': selected_officer_display,
        'selected_status': status,
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 11. PORTFOLIO STATUS REPORT (portfolio_status_report)
# ====================================================================
# --------------------------------------------------------------------
# 3. Portfolio Status Report
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# 3. Portfolio Status Report
# --------------------------------------------------------------------
@login_required
def portfolio_status_report(request):
    """
    A Status On Outstanding Loans – comprehensive portfolio summary.
    Columns: No, Name, Loan No, Disbursed Amount, Disbursement Date,
    Principal Paid, Interest Paid, Principal Due, Penalty Paid,
    Prepaid Principal, Interest Due, Penalty Due, Total Due,
    Interest Arrears, Principal Arrears, Admin Fees Balance, Status,
    Batch No, Classification, Borrower category, Economic sector,
    Transfer Status, Product, Principal Balance, Interest Balance,
    Penalty Balance, Total Outstanding, Completion Rate,
    Total Accrual Balance.
    """
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    status_filter = request.GET.get('status') or request.POST.get('status')
    search_query = request.GET.get('search_query') or request.POST.get('search_query')

    loans_qs = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).select_related('member', 'officer').prefetch_related('installments', 'repayments')

    if date_from:
        loans_qs = loans_qs.filter(disbursed_date__gte=date_from)
    if date_to:
        loans_qs = loans_qs.filter(disbursed_date__lte=date_to)
    if officer_id:
        loans_qs = loans_qs.filter(officer_id=officer_id)
    if status_filter:
        loans_qs = loans_qs.filter(status=status_filter)
    if search_query:
        loans_qs = loans_qs.filter(
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(member__member_number__icontains=search_query) |
            Q(loan_reference__icontains=search_query)
        )

    today = date.today()
    data = []
    totals = {
        'disbursed_amount': Decimal('0'),
        'principal_paid': Decimal('0'),
        'interest_paid': Decimal('0'),
        'penalty_paid': Decimal('0'),
        'principal_due': Decimal('0'),
        'interest_due': Decimal('0'),
        'penalty_due': Decimal('0'),
        'principal_balance': Decimal('0'),
        'interest_balance': Decimal('0'),
        'penalty_balance': Decimal('0'),
        'total_outstanding': Decimal('0'),
    }

    for loan in loans_qs:
        member = loan.member

        # ---- 1. Aggregate totals across all installments ----
        principal_paid = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']
        interest_paid = loan.installments.aggregate(
            total=Coalesce(Sum('interest_paid'), Decimal('0'))
        )['total']
        penalty_paid = loan.installments.aggregate(
            total=Coalesce(Sum('penalty_paid'), Decimal('0'))
        )['total']

        principal_balance = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_balance = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_balance = loan.installments.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_outstanding = principal_balance + interest_balance + penalty_balance

        # ---- 2. Overdue amounts ----
        overdue_inst = loan.installments.filter(paid=False, due_date__lt=today)
        principal_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_due = principal_due + interest_due + penalty_due

        # ---- 3. Completion Rate (percentage of total payable cleared) ----
        total_payable = loan.total_payable or (loan.principal_amount + loan.principal_amount * loan.interest_rate / 100)
        completion_rate = round(((total_payable - total_outstanding) / total_payable * 100), 2) if total_payable > 0 else 0

        # ---- 4. Classification ----
        if overdue_inst.exists():
            oldest_due = overdue_inst.earliest('due_date').due_date
            days_overdue = (today - oldest_due).days
            if days_overdue > 90:
                classification = 'Loss'
            elif days_overdue > 60:
                classification = 'Doubtful'
            elif days_overdue > 30:
                classification = 'Substandard'
            else:
                classification = 'Watch'
        else:
            classification = 'Performing'

        # ---- 5. Build row ----
        row = {
            'no': member.member_number,
            'name': f"{member.first_name} {member.last_name}",
            'loan_no': loan.loan_reference or f"LN-{loan.id}",
            'disbursed_amount': loan.principal_amount,
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'principal_paid': principal_paid,
            'interest_paid': interest_paid,
            'principal_due': principal_due,
            'penalty_paid': penalty_paid,
            'prepaid_principal': principal_paid,   # same as principal paid
            'interest_due': interest_due,
            'penalty_due': penalty_due,
            'total_due': total_due,
            'interest_arrears': interest_due,
            'principal_arrears': principal_due,
            'admin_fees_balance': Decimal('0.00'),
            'status': loan.get_status_display(),
            'batch_no': '',
            'classification': classification,
            'borrower_category': getattr(member, 'borrower_category', 'N/A'),
            'economic_sector': getattr(member, 'economic_sector', 'N/A'),
            'transfer_status': '',
            'product': loan.get_product_type_display(),
            'principal_balance': principal_balance,
            'interest_balance': interest_balance,
            'penalty_balance': penalty_balance,
            'total_outstanding': total_outstanding,
            'completion_rate': completion_rate,
            'total_accrual_balance': interest_balance,
        }
        data.append(row)

        # Accumulate totals
        for key in totals:
            if key in row:
                totals[key] += row[key]

    # ---- 6. Columns ----
    columns = [
        {'key': 'no', 'label': 'No', 'align': 'left'},
        {'key': 'name', 'label': 'Name', 'align': 'left'},
        {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
        {'key': 'disbursed_amount', 'label': 'Disbursed Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'disbursement_date', 'label': 'Disbursement Date', 'align': 'center', 'type': 'date'},
        {'key': 'principal_paid', 'label': 'Principal Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_paid', 'label': 'Interest Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_paid', 'label': 'Penalty Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'prepaid_principal', 'label': 'Prepaid Principal (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_arrears', 'label': 'Interest Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_arrears', 'label': 'Principal Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'batch_no', 'label': 'Batch No', 'align': 'left'},
        {'key': 'classification', 'label': 'Classification', 'align': 'center'},
        {'key': 'borrower_category', 'label': 'Borrower category', 'align': 'left'},
        {'key': 'economic_sector', 'label': 'Economic sector', 'align': 'left'},
        {'key': 'transfer_status', 'label': 'Transfer Status', 'align': 'left'},
        {'key': 'product', 'label': 'Product', 'align': 'left'},
        {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_balance', 'label': 'Penalty Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_outstanding', 'label': 'Total Outstanding (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'completion_rate', 'label': 'Completion Rate (%)', 'align': 'right'},
        {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]

    # ---- 7. KPI & context ----
    kpi_cards = [
        {'icon': 'bi-pie-chart', 'value': f'{len(data):,}', 'label': 'Active Loans', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["total_outstanding"]:,.0f}', 'label': 'Total Outstanding', 'type': 'warning'},
        {'icon': 'bi-percent', 'value': f'{(totals["total_due"] / (totals["total_outstanding"] + 1) * 100):.1f}%', 'label': 'PAR > 30', 'type': 'danger'},
    ]

    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['disbursed_amount'],
        'total_paid': totals['principal_paid'] + totals['interest_paid'],
        'outstanding': totals['total_outstanding'],
        'recovery_rate': round(((totals['principal_paid'] + totals['interest_paid']) / (totals['disbursed_amount'] + 1) * 100), 1),
        'par_30': round((totals['total_due'] / (totals['total_outstanding'] + 1) * 100), 1),
    }

    context = _get_base_context(request, {
        'report_title': 'Portfolio Status Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'selected_status': status_filter,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)
# ====================================================================
# 12. ARREARS REPORT (arrears_report)
# ====================================================================
from decimal import Decimal
from django.db.models import Q, Sum, F, Value, DecimalField, Func
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import date, datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import FileResponse

from finance.models import Installment, Loan
from finance.penalties import calculate_penalty  # ensure this import exists


from decimal import Decimal
from django.db.models import Q, Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import date, datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import FileResponse

from finance.models import Installment, Loan
from finance.penalties import calculate_penalty          # needed for loan_detail logic


from decimal import Decimal
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import date, datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import FileResponse

from finance.models import Installment, Loan
from finance.penalties import calculate_penalty          # needed for loan_detail logic


@login_required
def arrears_report(request):
    """Arrears & Delinquency Report with aging buckets – true penalty calculation"""
    from datetime import datetime

    if request.method == "POST":
        date_at_str = request.POST.get('date_at')
        search_query = request.POST.get('search_query')
    else:
        date_at_str = request.GET.get('date_at')
        search_query = request.GET.get('search_query')

    today = date.today()
    if date_at_str:
        try:
            target_date = datetime.strptime(date_at_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    # Fetch overdue installments (unpaid and due before target_date)
    overdue_installments = Installment.objects.filter(
        paid=False,
        due_date__lt=target_date,
        loan__status__in=['approved', 'active', 'arrears']
    ).select_related('loan', 'loan__member', 'loan__officer')

    if search_query:
        overdue_installments = overdue_installments.filter(
            Q(loan__member__first_name__icontains=search_query) |
            Q(loan__member__last_name__icontains=search_query) |
            Q(loan__member__member_number__icontains=search_query) |
            Q(loan__loan_reference__icontains=search_query)
        )

    # Build data in Python – using the same penalty calculation as loan_detail
    data = []
    total_arrears = Decimal('0')
    aging_buckets = {
        '1-30_days': Decimal('0'),
        '31-60_days': Decimal('0'),
        '61-90_days': Decimal('0'),
        '91-180_days': Decimal('0'),
        '180_plus': Decimal('0'),
    }

    for inst in overdue_installments:
        days = (target_date - inst.due_date).days

        # === Penalty calculation (mirroring loan_detail) ===
        # Calculated penalty from the rule (fresh, using today's date)
        calc_penalty = calculate_penalty(inst) or Decimal('0.00')
        # Manual penalties (not waived) for this installment
        manual_total = inst.manual_penalties.filter(is_waived=False).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        total_penalty = calc_penalty + manual_total

        # Due amounts
        principal_due = inst.principal_balance          # property: principal_portion - principal_paid
        interest_due = inst.interest_balance            # property: interest_portion - interest_paid
        penalty_due = total_penalty - inst.penalty_paid  # subtract already paid penalty

        total_due = principal_due + interest_due + penalty_due

        data.append({
            'member_no': inst.loan.member.member_number or str(inst.loan.member.id),
            'member_name': f"{inst.loan.member.first_name} {inst.loan.member.last_name}",
            'loan_ref': inst.loan.loan_reference or f"LN-{inst.loan.id}",
            'phone': inst.loan.member.phone_number,
            'due_date': inst.due_date,
            'days_overdue': days,
            'principal_due': principal_due,
            'interest_due': interest_due,
            'penalty_due': penalty_due,
            'total_due': total_due,
            'disbursed_amount': Decimal(str(inst.loan.principal_amount or 0)),
            'officer': inst.loan.officer.get_full_name() if inst.loan.officer else 'System',
        })

        total_arrears += total_due

        # Aging bucket
        if 1 <= days <= 30:
            aging_buckets['1-30_days'] += total_due
        elif 31 <= days <= 60:
            aging_buckets['31-60_days'] += total_due
        elif 61 <= days <= 90:
            aging_buckets['61-90_days'] += total_due
        elif 91 <= days <= 180:
            aging_buckets['91-180_days'] += total_due
        else:
            aging_buckets['180_plus'] += total_due

    # Columns definition
    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member_name', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'due_date', 'label': 'Due Date', 'align': 'center', 'type': 'date'},
        {'key': 'days_overdue', 'label': 'Days Overdue', 'align': 'center'},
        {'key': 'disbursed_amount', 'label': 'Amount Disbursed (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_due', 'label': 'Principal Due', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]

    totals = {
        'disbursed_amount': sum(item['disbursed_amount'] for item in data),
        'principal_due': sum(item['principal_due'] for item in data),
        'interest_due': sum(item['interest_due'] for item in data),
        'penalty_due': sum(item['penalty_due'] for item in data),
        'total_due': total_arrears,
    }

    total_outstanding_loans = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).count()

    kpi_cards = [
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {total_arrears:,.0f}', 'label': 'Total Arrears', 'type': 'danger'},
        {'icon': 'bi-clock-history', 'value': f'{len(data):,}', 'label': 'Overdue Installments', 'type': 'warning'},
        {'icon': 'bi-percent', 'value': f'{(total_arrears / (total_outstanding_loans + 1)):.1f}%', 'label': 'Arrears Rate', 'type': 'info'},
    ]

    aging_summary = [
        {'bucket': '1-30 Days', 'amount': aging_buckets['1-30_days']},
        {'bucket': '31-60 Days', 'amount': aging_buckets['31-60_days']},
        {'bucket': '61-90 Days', 'amount': aging_buckets['61-90_days']},
        {'bucket': '91-180 Days', 'amount': aging_buckets['91-180_days']},
        {'bucket': '180+ Days', 'amount': aging_buckets['180_plus']},
    ]

    summary_totals = {
        'total_records': len(data),
        'total_amount': total_arrears,
        'total_paid': 'N/A',
        'outstanding': total_arrears,
        'recovery_rate': 'N/A',
        'par_30': f'{(total_arrears / (total_outstanding_loans + 1)):.1f}',
    }

    context = _get_base_context(request, {
        'report_title': 'Arrears & Delinquency Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'aging_summary': aging_summary,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)

# ====================================================================
# 13. GENERAL LEDGER REPORT (general_ledger_report)
# ====================================================================
@login_required
def general_ledger_report(request):
    """Professional General Ledger report with date, account, and account type filters."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    account_id = request.GET.get('account') or request.POST.get('account')
    account_type = request.GET.get('account_type') or request.POST.get('account_type')
    status = request.GET.get('status') or request.POST.get('status')  # not used, but kept for consistency

    qs = GeneralLedger.objects.select_related('account')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if account_id:
        qs = qs.filter(account_id=account_id)
    if account_type:
        qs = qs.filter(account__account_type=account_type)

    data = []
    total_debit = Decimal('0.00')
    total_credit = Decimal('0.00')

    for entry in qs.order_by('date', 'id'):
        data.append({
            'date': entry.date,
            'account_code': entry.account.code,
            'account_name': entry.account.name,
            'description': entry.description,
            'reference': entry.reference or '-',
            'debit': entry.debit,
            'credit': entry.credit,
            'balance': entry.balance,
        })
        total_debit += entry.debit
        total_credit += entry.credit

    columns = [
        {'key': 'date', 'label': 'Date', 'type': 'date', 'align': 'center'},
        {'key': 'account_code', 'label': 'Account Code', 'align': 'left'},
        {'key': 'account_name', 'label': 'Account Name', 'align': 'left'},
        {'key': 'description', 'label': 'Description', 'align': 'left'},
        {'key': 'reference', 'label': 'Reference', 'align': 'left'},
        {'key': 'debit', 'label': 'Debit (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'credit', 'label': 'Credit (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'balance', 'label': 'Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
    ]
    totals = {'debit': total_debit, 'credit': total_credit}

    kpi_cards = [
        {'label': 'Total Entries', 'value': qs.count(), 'icon': 'bi-list-ul', 'type': 'info'},
        {'label': 'Total Debit', 'value': f"UGX {total_debit:,.0f}", 'icon': 'bi-arrow-down', 'type': 'danger'},
        {'label': 'Total Credit', 'value': f"UGX {total_credit:,.0f}", 'icon': 'bi-arrow-up', 'type': 'success'},
        {'label': 'Net Movement', 'value': f"UGX {abs(total_debit - total_credit):,.0f}", 'icon': 'bi-arrows-vertical', 'type': 'warning'},
    ]

    summary_totals = {
        'total_records': qs.count(),
        'total_amount': total_debit + total_credit,
        'total_paid': total_credit,
        'outstanding': total_debit,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    selected_account_display = None
    if account_id:
        try:
            acc = ChartOfAccount.objects.get(id=account_id)
            selected_account_display = f"{acc.code} – {acc.name}"
        except ChartOfAccount.DoesNotExist:
            pass

    selected_account_type_display = dict(ChartOfAccount.ACCOUNT_TYPES).get(account_type)

    context = _get_base_context(request, {
        'report_title': 'General Ledger Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_account': account_id,
        'selected_account_type': account_type,
        'selected_status': status,
        'selected_account_display': selected_account_display,
        'selected_account_type_display': selected_account_type_display,
    })

    if request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1':
        excel_file = generate_excel_report(
            columns=context['columns'],
            data=context['data'],
            report_title=context['report_title'],
            company_name=context['company']['name'],
            totals=context['totals']
        )
        filename = f"General_Ledger_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
        return FileResponse(excel_file, as_attachment=True, filename=filename)

    return render(request, 'finance/reports/base_report.html', context)



# finance/views.py (or inside your existing views)
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal
from .models import Transaction, GeneralLedger, ChartOfAccount, AccountingEngine
from .forms import JournalEntryForm

def journal_entry(request):
    if request.method == 'POST':
        form = JournalEntryForm(request.POST)
        if form.is_valid():
            debit_acc = form.cleaned_data['debit_account']
            credit_acc = form.cleaned_data['credit_account']
            amount = form.cleaned_data['amount']
            description = form.cleaned_data['description']
            reference = form.cleaned_data['reference'] or f"JRN-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            entry_date = form.cleaned_data['date'] or timezone.now().date()

            # Prevent self‑debit/credit
            if debit_acc == credit_acc:
                messages.error(request, "Debit and Credit accounts cannot be the same.")
                return render(request, 'finance/journal_entry.html', {'form': form})

            with db_transaction.atomic():
                # 1. Create a Transaction record (type='journal')
                tx = Transaction.objects.create(
                    member=None,          # Not tied to a member – or you could make it optional
                    loan=None,
                    amount=amount,
                    type='journal',
                    reference=reference,
                    timestamp=entry_date,
                    created_by=request.user if request.user.is_authenticated else None,
                )

                # 2. Post Debit entry (increase asset/expense, or decrease liability/income/equity)
                AccountingEngine.post_ledger_entry(
                    account_code=debit_acc.code,
                    description=f"{description} (Debit)",
                    reference=reference,
                    debit=amount,
                    credit=Decimal('0.00'),
                    transaction_obj=tx,
                    date_context=entry_date,
                )

                # 3. Post Credit entry (increase liability/income/equity, or decrease asset/expense)
                AccountingEngine.post_ledger_entry(
                    account_code=credit_acc.code,
                    description=f"{description} (Credit)",
                    reference=reference,
                    debit=Decimal('0.00'),
                    credit=amount,
                    transaction_obj=tx,
                    date_context=entry_date,
                )

            messages.success(request, f"Journal entry posted successfully! Ref: {reference}")
            return redirect('journal_entry')  # or to a list view

    else:
        form = JournalEntryForm()

    return render(request, 'finance/journal_entry.html', {'form': form})


# ====================================================================
# 14. GENERIC REPORT VIEW (report_view) – kept for backward compatibility
# ====================================================================
@login_required
def report_view(request):
    """Generic Loan Report view (same as loan_report, but with different defaults)"""
    # This is essentially a duplicate of loan_report; we can redirect or keep as is.
    # We'll keep it simple: just call loan_report with the same logic.
    return loan_report(request)


from django.http import JsonResponse
from django.http import JsonResponse
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from .models import ChartOfAccount, GeneralLedger

from django.http import JsonResponse
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from .models import ChartOfAccount, GeneralLedger

def account_balance_api(request, account_id):
    try:
        account = ChartOfAccount.objects.get(id=account_id)
    except ChartOfAccount.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Account not found'}, status=404)

    ledger_qs = GeneralLedger.objects.filter(account=account)
    total_debit = ledger_qs.aggregate(total=Coalesce(Sum('debit'), Value(Decimal('0.00'))))['total']
    total_credit = ledger_qs.aggregate(total=Coalesce(Sum('credit'), Value(Decimal('0.00'))))['total']

    if account.account_type in ['asset', 'expense']:
        balance = total_debit - total_credit
    else:  # liability, income, equity
        balance = total_credit - total_debit

    return JsonResponse({
        'success': True,
        'balance': float(balance),
        'account_type': account.get_account_type_display(),
    })

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import Http404

from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# finance/views.py
from datetime import datetime   # add this import
# ... other imports

# finance/views.py
from datetime import datetime  # ensure import

@login_required
def view_receipt(request):
    receipt = request.session.get('deposit_receipt') or request.session.get('withdrawal_receipt')
    if not receipt or not receipt.get('show'):
        messages.warning(request, "No receipt to display.")
        return redirect('dashboard')

    # Clear session
    if 'deposit_receipt' in request.session:
        del request.session['deposit_receipt']
    if 'withdrawal_receipt' in request.session:
        del request.session['withdrawal_receipt']

    receipt_data = receipt['data']

    # Convert timestamp string to datetime object, or use current time as fallback
    timestamp_str = receipt_data.get('timestamp')
    if timestamp_str:
        try:
            receipt_data['timestamp_obj'] = datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            receipt_data['timestamp_obj'] = None
    else:
        receipt_data['timestamp_obj'] = None

    context = {
        'receipt': receipt_data,
        'company': Company.get_company(),
    }
    return render(request, 'finance/receipt.html', context)




# finance/views.py
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import permission_required, login_required
from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal
import requests
import logging

from .models import Loan, SMSConfig, SMSTransaction, Company
from decouple import config

logger = logging.getLogger(__name__)

# SMS cost for a reminder (set to 300 as requested)
SMS_REMINDER_COST = Decimal('300.00')

# finance/views.py – add at the top if missing
import requests
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from decouple import config

from .models import Loan, SMSConfig, SMSTransaction, Company
from .models import Loan  # if not already imported

logger = logging.getLogger(__name__)

# Cost per SMS (as you already defined)
SMS_REMINDER_COST = Decimal('300.00')


@login_required
@permission_required('finance.can_send_sms', raise_exception=True)
def send_loan_reminder(request, loan_id):
    """
    Sends a payment reminder SMS to the member for a specific loan.
    Deducts 300 from SMS wallet.
    Message shows the actual overdue amount (principal + interest + penalty).
    """
    loan = get_object_or_404(Loan, id=loan_id)

    # 1. Check if loan is active (not closed)
    if loan.status in ['closed', 'rejected', 'defaulted']:
        messages.error(request, "This loan is no longer active.")
        return redirect('loan_details', loan_id=loan.id)

    # 2. Check SMS credits
    try:
        sms_config = SMSConfig.objects.get()  # assume singleton
    except SMSConfig.DoesNotExist:
        messages.error(request, "SMS service is not configured.")
        return redirect('loan_details', loan_id=loan.id)

    if sms_config.balance < SMS_REMINDER_COST:
        messages.error(
            request,
            f"Insufficient SMS credits. Required: UGX {SMS_REMINDER_COST:,.0f}, "
            f"Available: UGX {sms_config.balance:,.0f}"
        )
        return redirect('loan_details', loan_id=loan.id)

    # 3. Calculate the actual amount due (overdue installments)
    member = loan.member
    company = Company.get_company()
    today = timezone.now().date()

    # Get overdue installments (unpaid and due date <= today)
    overdue_inst = loan.installments.filter(paid=False, due_date__lte=today)

    if overdue_inst.exists():
        # Sum of balances (principal + interest + penalty) for overdue installments
        total_due = sum(inst.balance for inst in overdue_inst)
        # Earliest overdue due date
        next_due_date = overdue_inst.order_by('due_date').first().due_date
    else:
        # No overdue – fallback to next unpaid installment (if any)
        next_inst = loan.installments.filter(paid=False).order_by('due_date').first()
        if next_inst:
            total_due = next_inst.balance
            next_due_date = next_inst.due_date
        else:
            # No remaining installments – use loan balance as fallback
            total_due = loan.balance
            next_due_date = loan.start_date  # or today

    disbursed_date = loan.disbursed_date or loan.start_date

    # 4. Build the SMS message
    message = (
        f"Dear {member.first_name}, your loan of UGX {loan.principal_amount:,.0f} "
        f"disbursed on {disbursed_date.strftime('%d/%m/%Y')} has a payment due of "
        f"UGX {total_due:,.0f} by {next_due_date.strftime('%d/%m/%Y')}. "
        f"Please pay on time to avoid penalties. Thank you. - {company.name}"
    )

    # Truncate to 160 characters if needed (SpeedaMobile supports up to 160 per SMS)
    if len(message) > 160:
        message = message[:157] + "..."

    # 5. Format phone number
    raw_phone = str(member.phone_number).strip().replace(" ", "").replace("+", "")
    if raw_phone.startswith('0'):
        formatted_phone = '256' + raw_phone[1:]
    else:
        formatted_phone = raw_phone

    # 6. Send via SpeedaMobile API
    api_id = config('SPEEDA_API_ID')
    api_password = config('SPEEDA_API_PASSWORD')
    sender_id = config('SPEEDA_SENDER_ID', default='MACFinTech')

    url = "http://apidocs.speedamobile.com/api/SendSMS"
    payload = {
        "api_id": api_id,
        "api_password": api_password,
        "sms_type": "P",
        "encoding": "T",
        "sender_id": sender_id,
        "phonenumber": formatted_phone,
        "textmessage": message,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("status") == "S":
            # Deduct credits and log transaction
            with db_transaction.atomic():
                config_obj = SMSConfig.objects.select_for_update().get(id=sms_config.id)
                config_obj.balance -= SMS_REMINDER_COST
                config_obj.save()

                SMSTransaction.objects.create(
                    amount=SMS_REMINDER_COST,
                    transaction_type='REMINDER',
                    description=f"Reminder sent for loan {loan.loan_reference} to {member.first_name}",
                    performed_by=request.user
                )

            messages.success(request, f"SMS reminder sent successfully to {member.first_name}.")
        else:
            error_msg = result.get('remarks', 'Unknown API error')
            messages.error(request, f"Failed to send SMS: {error_msg}")

    except requests.RequestException as e:
        logger.error(f"SMS API error for {formatted_phone}: {str(e)}")
        messages.error(request, "Could not connect to SMS gateway. Please try again later.")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        messages.error(request, "An internal error occurred.")

    return redirect('loan_details', loan_id=loan.id)


@login_required
@permission_required('finance.can_send_sms', raise_exception=True)
def send_bulk_arrears_reminders(request):
    """
    Sends a bulk SMS reminder to all members with loans in arrears.
    Message shows the actual overdue amount for each member.
    """
    company = Company.get_company()
    today = timezone.now().date()

    # Get all active loans with status 'arrears'
    arrears_loans = Loan.objects.filter(
        status='arrears',
        is_active=True
    ).select_related('member')

    if not arrears_loans.exists():
        messages.info(request, "No loans are currently in arrears.")
        return redirect('loan_list')

    # Check SMS credits (needed for all messages)
    try:
        sms_config = SMSConfig.objects.get()
    except SMSConfig.DoesNotExist:
        messages.error(request, "SMS service is not configured.")
        return redirect('loan_list')

    # Count total required credits
    total_messages = arrears_loans.count()
    total_cost = total_messages * SMS_REMINDER_COST

    if sms_config.balance < total_cost:
        messages.error(
            request,
            f"Insufficient SMS credits. Need UGX {total_cost:,.0f}, "
            f"Available: UGX {sms_config.balance:,.0f}"
        )
        return redirect('loan_list')

    sent = 0
    failed = 0

    for loan in arrears_loans:
        member = loan.member
        # Calculate overdue amount for this loan
        overdue_inst = loan.installments.filter(paid=False, due_date__lte=today)
        if overdue_inst.exists():
            total_due = sum(inst.balance for inst in overdue_inst)
            next_due_date = overdue_inst.order_by('due_date').first().due_date
        else:
            # Should not happen, but fallback
            next_inst = loan.installments.filter(paid=False).order_by('due_date').first()
            if next_inst:
                total_due = next_inst.balance
                next_due_date = next_inst.due_date
            else:
                # No installments – skip this loan
                failed += 1
                continue

        disbursed_date = loan.disbursed_date or loan.start_date

        # Build personalised message
        message = (
            f"Dear {member.first_name}, your loan of UGX {loan.principal_amount:,.0f} "
            f"disbursed on {disbursed_date.strftime('%d/%m/%Y')} has a payment due of "
            f"UGX {total_due:,.0f} by {next_due_date.strftime('%d/%m/%Y')}. "
            f"Please pay on time to avoid penalties. Thank you. - {company.name}"
        )
        if len(message) > 160:
            message = message[:157] + "..."

        # Format phone number
        raw_phone = str(member.phone_number).strip().replace(" ", "").replace("+", "")
        if raw_phone.startswith('0'):
            formatted_phone = '256' + raw_phone[1:]
        else:
            formatted_phone = raw_phone

        # Call SpeedaMobile API
        api_id = config('SPEEDA_API_ID')
        api_password = config('SPEEDA_API_PASSWORD')
        sender_id = config('SPEEDA_SENDER_ID', default='MACFinTech')
        url = "http://apidocs.speedamobile.com/api/SendSMS"

        payload = {
            "api_id": api_id,
            "api_password": api_password,
            "sms_type": "P",
            "encoding": "T",
            "sender_id": sender_id,
            "phonenumber": formatted_phone,
            "textmessage": message,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result.get("status") == "S":
                # Deduct one SMS cost
                with db_transaction.atomic():
                    config_obj = SMSConfig.objects.select_for_update().get(id=sms_config.id)
                    config_obj.balance -= SMS_REMINDER_COST
                    config_obj.save()

                    SMSTransaction.objects.create(
                        amount=SMS_REMINDER_COST,
                        transaction_type='REMINDER',
                        description=f"Bulk reminder sent to {member.first_name} for loan {loan.loan_reference}",
                        performed_by=request.user
                    )
                sent += 1
            else:
                failed += 1
                logger.error(f"Bulk SMS failed for {formatted_phone}: {result.get('remarks')}")

        except Exception as e:
            failed += 1
            logger.error(f"Bulk SMS error for {formatted_phone}: {str(e)}")

    # Final message
    if sent > 0:
        messages.success(request, f"Bulk SMS reminders sent: {sent} successful, {failed} failed.")
    else:
        messages.error(request, "Bulk SMS reminders failed. Please try again later.")

    return redirect('loan_list')
# ====================================================================
# LOAN REPORTS (all views) – CORRECTED FOR YOUR MODEL
# ====================================================================

from decimal import Decimal
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta   # for maturity report
from django.db.models import Q, Sum, F, Value, DecimalField, Count
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.utils import timezone

from finance.models import Loan, Installment, Member, SavingsAccount, Transaction
from finance.penalties import calculate_penalty          # if needed


# --------------------------------------------------------------------
# 1. Outstanding Loans Report
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# 1. Outstanding Loans Report
# --------------------------------------------------------------------
@login_required
def outstanding_loans_report(request):
    """
    List of outstanding loans with full column set:
    No, Date, Name, Loan No, Phone, Physical Address, Town, Product,
    Amount, Principal Balance, Interest Balance, Interest Due,
    Principal Due, Penalty Due, Total Due, Principal Prepaid,
    Classification, Cleared At, Accrued Interest, Admin Fees Due,
    Admin Fees Balance, Branch, Loan Status, Batch Number,
    Created At, Total Accrual Balance.
    """
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    status = request.GET.get('status') or request.POST.get('status')
    search_query = request.GET.get('search_query') or request.POST.get('search_query')

    # Start with active loans (not closed or defaulted)
    loans_qs = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).select_related('member', 'officer').prefetch_related('installments', 'repayments')

    if date_from:
        loans_qs = loans_qs.filter(disbursed_date__gte=date_from)
    if date_to:
        loans_qs = loans_qs.filter(disbursed_date__lte=date_to)
    if officer_id:
        loans_qs = loans_qs.filter(officer_id=officer_id)
    if status:
        loans_qs = loans_qs.filter(status=status)
    if search_query:
        loans_qs = loans_qs.filter(
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(member__member_number__icontains=search_query) |
            Q(loan_reference__icontains=search_query)
        )

    today = date.today()
    data = []
    total_amount = Decimal('0')
    total_principal_bal = Decimal('0')
    total_interest_bal = Decimal('0')
    total_interest_due = Decimal('0')
    total_principal_due = Decimal('0')
    total_penalty_due = Decimal('0')
    total_due = Decimal('0')
    total_accrual = Decimal('0')

    for loan in loans_qs:
        # ---- 1. Compute total balances from all installments ----
        principal_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_bal = principal_bal + interest_bal + penalty_bal

        # Skip loans with zero total balance (fully repaid, but status might not be closed)
        if total_bal == 0:
            continue

        # ---- 2. Overdue amounts ----
        overdue_inst = loan.installments.filter(paid=False, due_date__lt=today)
        principal_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_due_loan = principal_due + interest_due + penalty_due

        # ---- 3. Principal prepaid (total principal paid) ----
        principal_prepaid = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']

        # ---- 4. Classification (based on oldest overdue) ----
        if overdue_inst.exists():
            oldest_due = overdue_inst.earliest('due_date').due_date
            days_overdue = (today - oldest_due).days
            if days_overdue > 90:
                classification = 'Loss'
            elif days_overdue > 60:
                classification = 'Doubtful'
            elif days_overdue > 30:
                classification = 'Substandard'
            elif days_overdue > 0:
                classification = 'Watch'
            else:
                classification = 'Performing'
        else:
            classification = 'Performing'

        # ---- 5. Cleared At (if loan is closed, use updated_at) ----
        cleared_at = loan.updated_at.date() if loan.status == 'closed' else None

        # ---- 6. Member fields ----
        member = loan.member
        address_parts = [member.village, member.parish, member.district]
        physical_address = ', '.join([p for p in address_parts if p]) or 'N/A'

        # ---- 7. Build row ----
        row = {
            'no': member.member_number,
            'date': loan.disbursed_date or loan.start_date,
            'name': f"{member.first_name} {member.last_name}",
            'loan_no': loan.loan_reference or f"LN-{loan.id}",
            'phone': member.phone_number,
            'physical_address': physical_address,
            'town': member.district or 'N/A',
            'product': loan.get_product_type_display(),
            'amount': loan.principal_amount,
            'principal_balance': principal_bal,
            'interest_balance': interest_bal,
            'interest_due': interest_due,
            'principal_due': principal_due,
            'penalty_due': penalty_due,
            'total_due': total_due_loan,
            'principal_prepaid': principal_prepaid,
            'classification': classification,
            'cleared_at': cleared_at,
            'accrued_interest': interest_bal,      # same as interest balance
            'admin_fees_due': Decimal('0.00'),
            'admin_fees_balance': Decimal('0.00'),
            'branch': member.district or 'Main',   # use district as branch placeholder
            'loan_status': loan.get_status_display(),
            'batch_number': '',
            'created_at': loan.created_at.date(),
            'total_accrual_balance': interest_bal,
        }

        data.append(row)

        # Accumulate totals
        total_amount += loan.principal_amount
        total_principal_bal += principal_bal
        total_interest_bal += interest_bal
        total_interest_due += interest_due
        total_principal_due += principal_due
        total_penalty_due += penalty_due
        total_due += total_due_loan
        total_accrual += interest_bal

    # ---- 8. Columns definition ----
    columns = [
        {'key': 'no', 'label': 'No', 'align': 'left'},
        {'key': 'date', 'label': 'Date', 'align': 'center', 'type': 'date'},
        {'key': 'name', 'label': 'Name', 'align': 'left'},
        {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'physical_address', 'label': 'Physical Address', 'align': 'left'},
        {'key': 'town', 'label': 'Town', 'align': 'left'},
        {'key': 'product', 'label': 'Product', 'align': 'left'},
        {'key': 'amount', 'label': 'Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_prepaid', 'label': 'Principal Prepaid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'classification', 'label': 'Classification', 'align': 'center'},
        {'key': 'cleared_at', 'label': 'Cleared At', 'align': 'center', 'type': 'date'},
        {'key': 'accrued_interest', 'label': 'Accrued Interest (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'admin_fees_due', 'label': 'Admin Fees Due (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'branch', 'label': 'Branch', 'align': 'left'},
        {'key': 'loan_status', 'label': 'Loan Status', 'align': 'center', 'type': 'status'},
        {'key': 'batch_number', 'label': 'Batch Number', 'align': 'left'},
        {'key': 'created_at', 'label': 'Created At', 'align': 'center', 'type': 'date'},
        {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]

    # ---- 9. Totals for footer ----
    totals = {
        'amount': total_amount,
        'principal_balance': total_principal_bal,
        'interest_balance': total_interest_bal,
        'interest_due': total_interest_due,
        'principal_due': total_principal_due,
        'penalty_due': total_penalty_due,
        'total_due': total_due,
        'principal_prepaid': sum(row['principal_prepaid'] for row in data),
        'accrued_interest': total_interest_bal,
        'total_accrual_balance': total_accrual,
    }

    # ---- 10. KPI cards ----
    kpi_cards = [
        {'icon': 'bi-bank', 'value': f'{len(data):,}', 'label': 'Outstanding Loans', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_principal_bal + total_interest_bal + total_penalty_due:,.0f}', 'label': 'Total Outstanding', 'type': 'warning'},
        {'icon': 'bi-person', 'value': f'{len(set(loan.officer_id for loan in loans_qs if loan.officer_id))}', 'label': 'Active Officers', 'type': 'secondary'},
    ]

    # ---- 11. Summary totals ----
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_amount,
        'total_paid': 'N/A',
        'outstanding': total_principal_bal + total_interest_bal + total_penalty_due,
        'recovery_rate': 'N/A',
        'par_30': f'{(total_due / (total_principal_bal + total_interest_bal + 1) * 100):.1f}',
    }

    # ---- 12. Context ----
    context = _get_base_context(request, {
        'report_title': 'Outstanding Loans Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'selected_status': status,
        'officer_name': _get_officer_name(officer_id),
        'search_query': search_query,
    })

    # ---- 13. Export ----
    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# --------------------------------------------------------------------
# 2. Loans In Arrears Report
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# 2. Loans In Arrears Report (FULL COLUMN SET)
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# 2. Loans In Arrears Report (CORRECTED – uses actual Installment fields)
# --------------------------------------------------------------------
@login_required
def loans_in_arrears_report(request):
    """
    List of loans in arrears with all required columns.
    Computes balances using principal_portion, principal_paid, etc.
    """
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    search_query = request.GET.get('search_query') or request.POST.get('search_query')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    # Loans that have at least one overdue installment
    loans_qs = Loan.objects.filter(
        installments__paid=False,
        installments__due_date__lt=target_date,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments', 'repayments')

    if officer_id:
        loans_qs = loans_qs.filter(officer_id=officer_id)
    if search_query:
        loans_qs = loans_qs.filter(
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(member__member_number__icontains=search_query) |
            Q(loan_reference__icontains=search_query)
        )

    data = []
    total_principal_arrears = Decimal('0')
    total_interest_arrears = Decimal('0')
    total_penalty_due = Decimal('0')
    total_due = Decimal('0')
    total_outstanding = Decimal('0')

    for loan in loans_qs:
        # ---- 1. Overdue installments ----
        overdue_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        if not overdue_inst.exists():
            continue

        # ---- 2. Aggregate overdue amounts using F expressions ----
        principal_arrears = overdue_inst.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_arrears = overdue_inst.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_due_loan = principal_arrears + interest_arrears + penalty_due

        # ---- 3. Total balances across all installments ----
        principal_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_outstanding_loan = principal_bal + interest_bal + penalty_bal

        # ---- 4. Paid amounts (total) ----
        principal_paid = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']
        interest_paid = loan.installments.aggregate(
            total=Coalesce(Sum('interest_paid'), Decimal('0'))
        )['total']
        penalty_paid = loan.installments.aggregate(
            total=Coalesce(Sum('penalty_paid'), Decimal('0'))
        )['total']

        # ---- 5. Last repayment date ----
        last_repayment = loan.repayments.order_by('-date_paid').first()
        last_repayment_date = last_repayment.date_paid.date() if last_repayment else None

        # ---- 6. Arrears days ----
        oldest_due = overdue_inst.earliest('due_date').due_date
        arrears_days = (target_date - oldest_due).days

        # ---- 7. Classification ----
        if arrears_days > 90:
            classification = 'Loss'
        elif arrears_days > 60:
            classification = 'Doubtful'
        elif arrears_days > 30:
            classification = 'Substandard'
        elif arrears_days > 0:
            classification = 'Watch'
        else:
            classification = 'Performing'

        # ---- 8. Arrears rate ----
        arrears_rate = (total_due_loan / total_outstanding_loan * 100) if total_outstanding_loan > 0 else 0

        # ---- 9. Guarantors ----
        guarantors = []
        if loan.guarantor_1_name:
            guarantors.append(loan.guarantor_1_name)
        if loan.guarantor_2_name:
            guarantors.append(loan.guarantor_2_name)
        guarantor_str = ', '.join(guarantors) if guarantors else 'None'

        # ---- 10. Address ----
        member = loan.member
        address_parts = [member.village, member.parish, member.district]
        physical_address = ', '.join([p for p in address_parts if p]) or 'N/A'

        # ---- 11. Build row ----
        row = {
            'no': member.member_number,
            'name': f"{member.first_name} {member.last_name}",
            'phone': member.phone_number,
            'loan_no': loan.loan_reference or f"LN-{loan.id}",
            'principal_arrears': principal_arrears,
            'interest_arrears': interest_arrears,
            'arrears_days': arrears_days,
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'disbursed_amount': loan.principal_amount,
            'last_repayment_date': last_repayment_date,
            'principal_due': principal_arrears,
            'interest_due': interest_arrears,
            'penalty_due': penalty_due,
            'total_due': total_due_loan,
            'total_outstanding': total_outstanding_loan,
            'msacco_no': member.member_number,
            'physical_address': physical_address,
            'classification': classification,
            'batch_no': '',
            'arrears_rate': round(arrears_rate, 2),
            'admin_fees_due': Decimal('0.00'),
            'admin_fees_balance': Decimal('0.00'),
            'unpaid_arrears': total_due_loan,
            'transfer_status': '',
            'status': loan.get_status_display(),
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
            'town': member.district or 'N/A',
            'product': loan.get_product_type_display(),
            'principal_paid': principal_paid,
            'interest_paid': interest_paid,
            'penalty_paid': penalty_paid,
            'prepaid_principal': Decimal('0.00'),
            'principal_balance': principal_bal,
            'interest_balance': interest_bal,
            'penalty_balance': penalty_bal,
            'guarantors': guarantor_str,
            'total_accrual_balance': interest_bal,   # interest balance = accrued interest
        }

        data.append(row)

        total_principal_arrears += principal_arrears
        total_interest_arrears += interest_arrears
        total_penalty_due += penalty_due
        total_due += total_due_loan
        total_outstanding += total_outstanding_loan

    # ---- 12. Columns definition ----
    columns = [
        {'key': 'no', 'label': 'No', 'align': 'left'},
        {'key': 'name', 'label': 'Name', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
        {'key': 'principal_arrears', 'label': 'Principal Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_arrears', 'label': 'Interest Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'arrears_days', 'label': 'Arrears Days', 'align': 'center'},
        {'key': 'disbursement_date', 'label': 'Disbursement Date', 'align': 'center', 'type': 'date'},
        {'key': 'disbursed_amount', 'label': 'Disbursed Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'last_repayment_date', 'label': 'Last Repayment Date', 'align': 'center', 'type': 'date'},
        {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_outstanding', 'label': 'Total Outstanding (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'msacco_no', 'label': 'Msacco No', 'align': 'left'},
        {'key': 'physical_address', 'label': 'Physical Address', 'align': 'left'},
        {'key': 'classification', 'label': 'Classification', 'align': 'center'},
        {'key': 'batch_no', 'label': 'Batch No', 'align': 'left'},
        {'key': 'arrears_rate', 'label': 'Arrears rate (%)', 'align': 'right'},
        {'key': 'admin_fees_due', 'label': 'Admin Fees Due (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'unpaid_arrears', 'label': 'Unpaid Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'transfer_status', 'label': 'Transfer Status', 'align': 'left'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
        {'key': 'town', 'label': 'Town', 'align': 'left'},
        {'key': 'product', 'label': 'Product', 'align': 'left'},
        {'key': 'principal_paid', 'label': 'Principal Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_paid', 'label': 'Interest Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_paid', 'label': 'Penalty Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'prepaid_principal', 'label': 'Prepaid Principal (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_balance', 'label': 'Penalty Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'guarantors', 'label': 'Guarantors', 'align': 'left'},
        {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]

    # ---- 13. Totals for footer ----
    totals = {
        'principal_arrears': total_principal_arrears,
        'interest_arrears': total_interest_arrears,
        'penalty_due': total_penalty_due,
        'total_due': total_due,
        'total_outstanding': total_outstanding,
        'disbursed_amount': sum(row['disbursed_amount'] for row in data),
        'principal_due': total_principal_arrears,
        'interest_due': total_interest_arrears,
        'unpaid_arrears': total_due,
        'principal_paid': sum(row['principal_paid'] for row in data),
        'interest_paid': sum(row['interest_paid'] for row in data),
        'penalty_paid': sum(row['penalty_paid'] for row in data),
        'principal_balance': sum(row['principal_balance'] for row in data),
        'interest_balance': sum(row['interest_balance'] for row in data),
        'penalty_balance': sum(row['penalty_balance'] for row in data),
        'total_accrual_balance': sum(row['total_accrual_balance'] for row in data),
    }

    # ---- 14. KPI cards ----
    kpi_cards = [
        {'icon': 'bi-exclamation-triangle', 'value': f'{len(data):,}', 'label': 'Loans in Arrears', 'type': 'danger'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_due:,.0f}', 'label': 'Total Arrears', 'type': 'warning'},
        {'icon': 'bi-percent', 'value': f'{(total_due / (total_outstanding + 1) * 100):.1f}%', 'label': 'Arrears Rate', 'type': 'info'},
    ]

    # ---- 15. Summary totals ----
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_outstanding,
        'total_paid': 'N/A',
        'outstanding': total_due,
        'recovery_rate': 'N/A',
        'par_30': f'{(total_due / (total_outstanding + 1) * 100):.1f}',
    }

    # ---- 16. Context ----
    context = _get_base_context(request, {
        'report_title': 'Loans In Arrears Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
        'search_query': search_query,
    })

    # ---- 17. Export ----
    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)
# --------------------------------------------------------------------
# 3. Portfolio Status Report (already provided, but we keep it)
# --------------------------------------------------------------------
# (We are not redefining it here – you already have it from earlier examples)
# --------------------------------------------------------------------


# --------------------------------------------------------------------
# 4. Due Loans Report
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# 4. Due Loans Report
# --------------------------------------------------------------------
@login_required
def due_loans_report(request):
    """
    A list of all due loans (overdue installments).
    Columns: No, Name, Loan No, Batch No, Status, Classification,
    Transfer Status, Guarantors, Principal Arrears, Interest Arrears,
    Total arrears, Arrears Days, Arrears rate, Phone, Physical Address,
    Town, Product, Disbursed Amount, Disbursement Date, Principal Due,
    Interest Due, Penalty Due, Total Due, Principal Balance,
    Interest Balance, Penalty Balance, Total Outstanding, Accrued Interest,
    Total Accrual Balance, Admin Fees Due, Admin Fees Balance,
    Unpaid Admin Fees.
    """
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    search_query = request.GET.get('search_query') or request.POST.get('search_query')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    # Loans with overdue installments
    loans_qs = Loan.objects.filter(
        installments__paid=False,
        installments__due_date__lt=target_date,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments', 'repayments')

    if officer_id:
        loans_qs = loans_qs.filter(officer_id=officer_id)
    if search_query:
        loans_qs = loans_qs.filter(
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(member__member_number__icontains=search_query) |
            Q(loan_reference__icontains=search_query)
        )

    data = []
    totals = {
        'principal_arrears': Decimal('0'),
        'interest_arrears': Decimal('0'),
        'total_arrears': Decimal('0'),
        'principal_due': Decimal('0'),
        'interest_due': Decimal('0'),
        'penalty_due': Decimal('0'),
        'total_due': Decimal('0'),
        'principal_balance': Decimal('0'),
        'interest_balance': Decimal('0'),
        'penalty_balance': Decimal('0'),
        'total_outstanding': Decimal('0'),
        'disbursed_amount': Decimal('0'),
        'accrued_interest': Decimal('0'),
        'total_accrual_balance': Decimal('0'),
    }

    for loan in loans_qs:
        member = loan.member

        # ---- 1. Overdue installments ----
        overdue_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        if not overdue_inst.exists():
            continue

        principal_arrears = overdue_inst.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_arrears = overdue_inst.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_arrears = principal_arrears + interest_arrears + penalty_due

        # ---- 2. Total balances ----
        principal_balance = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_balance = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_balance = loan.installments.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_outstanding = principal_balance + interest_balance + penalty_balance

        # ---- 3. Arrears days & rate ----
        oldest_due = overdue_inst.earliest('due_date').due_date
        arrears_days = (target_date - oldest_due).days
        arrears_rate = (total_arrears / total_outstanding * 100) if total_outstanding > 0 else 0

        # ---- 4. Classification ----
        if arrears_days > 90:
            classification = 'Loss'
        elif arrears_days > 60:
            classification = 'Doubtful'
        elif arrears_days > 30:
            classification = 'Substandard'
        else:
            classification = 'Watch'

        # ---- 5. Guarantors ----
        guarantors = []
        if loan.guarantor_1_name:
            guarantors.append(loan.guarantor_1_name)
        if loan.guarantor_2_name:
            guarantors.append(loan.guarantor_2_name)
        guarantor_str = ', '.join(guarantors) if guarantors else 'None'

        # ---- 6. Address ----
        address_parts = [member.village, member.parish, member.district]
        physical_address = ', '.join([p for p in address_parts if p]) or 'N/A'

        # ---- 7. Build row ----
        row = {
            'no': member.member_number,
            'name': f"{member.first_name} {member.last_name}",
            'loan_no': loan.loan_reference or f"LN-{loan.id}",
            'batch_no': '',
            'status': loan.get_status_display(),
            'classification': classification,
            'transfer_status': '',
            'guarantors': guarantor_str,
            'principal_arrears': principal_arrears,
            'interest_arrears': interest_arrears,
            'total_arrears': total_arrears,
            'arrears_days': arrears_days,
            'arrears_rate': round(arrears_rate, 2),
            'phone': member.phone_number,
            'physical_address': physical_address,
            'town': member.district or 'N/A',
            'product': loan.get_product_type_display(),
            'disbursed_amount': loan.principal_amount,
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'principal_due': principal_arrears,
            'interest_due': interest_arrears,
            'penalty_due': penalty_due,
            'total_due': total_arrears,
            'principal_balance': principal_balance,
            'interest_balance': interest_balance,
            'penalty_balance': penalty_balance,
            'total_outstanding': total_outstanding,
            'accrued_interest': interest_balance,
            'total_accrual_balance': interest_balance,
            'admin_fees_due': Decimal('0.00'),
            'admin_fees_balance': Decimal('0.00'),
            'unpaid_admin_fees': Decimal('0.00'),
        }
        data.append(row)

        # Accumulate totals
        for key in totals:
            if key in row:
                totals[key] += row[key]

    # ---- 8. Columns ----
    columns = [
        {'key': 'no', 'label': 'No', 'align': 'left'},
        {'key': 'name', 'label': 'Name', 'align': 'left'},
        {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
        {'key': 'batch_no', 'label': 'Batch No', 'align': 'left'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'classification', 'label': 'Classification', 'align': 'center'},
        {'key': 'transfer_status', 'label': 'Transfer Status', 'align': 'left'},
        {'key': 'guarantors', 'label': 'Guarantors', 'align': 'left'},
        {'key': 'principal_arrears', 'label': 'Principal Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_arrears', 'label': 'Interest Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_arrears', 'label': 'Total arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'arrears_days', 'label': 'Arrears Days', 'align': 'center'},
        {'key': 'arrears_rate', 'label': 'Arrears rate (%)', 'align': 'right'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'physical_address', 'label': 'Physical Address', 'align': 'left'},
        {'key': 'town', 'label': 'Town', 'align': 'left'},
        {'key': 'product', 'label': 'Product', 'align': 'left'},
        {'key': 'disbursed_amount', 'label': 'Disbursed Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'disbursement_date', 'label': 'Disbursement Date', 'align': 'center', 'type': 'date'},
        {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_balance', 'label': 'Penalty Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_outstanding', 'label': 'Total Outstanding (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'accrued_interest', 'label': 'Accrued Interest (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'admin_fees_due', 'label': 'Admin Fees Due (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'unpaid_admin_fees', 'label': 'Unpaid Admin Fees (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
    ]

    # ---- 9. KPI & context ----
    kpi_cards = [
        {'icon': 'bi-calendar-event', 'value': f'{len(data):,}', 'label': 'Due Loans', 'type': 'warning'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["total_arrears"]:,.0f}', 'label': 'Total Arrears', 'type': 'danger'},
        {'icon': 'bi-percent', 'value': f'{(totals["total_arrears"] / (totals["total_outstanding"] + 1) * 100):.1f}%', 'label': 'Arrears Rate', 'type': 'info'},
    ]

    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['total_outstanding'],
        'total_paid': 'N/A',
        'outstanding': totals['total_arrears'],
        'recovery_rate': 'N/A',
        'par_30': f'{(totals["total_arrears"] / (totals["total_outstanding"] + 1) * 100):.1f}',
    }

    context = _get_base_context(request, {
        'report_title': 'Due Loans Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
        'search_query': search_query,
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)

# --------------------------------------------------------------------
# 5. Cleared Loans Report (CORRECTED – uses updated_at)
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# 5. Cleared Loans Report
# --------------------------------------------------------------------
@login_required
def cleared_loans_report(request):
    """List of loans that were fully cleared (closed) within a given period."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    if not date_from or not date_to:
        today = date.today()
        date_from = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')

    loans = Loan.objects.filter(status='closed', is_active=False)
    if date_from:
        loans = loans.filter(updated_at__date__gte=date_from)
    if date_to:
        loans = loans.filter(updated_at__date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    loans = loans.select_related('member', 'officer').prefetch_related('installments')

    data = []
    total_principal = Decimal('0')
    total_interest = Decimal('0')

    for loan in loans:
        interest_paid = loan.installments.aggregate(
            total=Coalesce(Sum('interest_paid'), Decimal('0'))
        )['total']
        # For closed loans, principal paid equals principal_amount (assuming fully paid)
        principal_paid = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'principal': loan.principal_amount,
            'principal_paid': principal_paid,
            'interest_paid': interest_paid,
            'closed_date': loan.updated_at.date(),
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })
        total_principal += loan.principal_amount or Decimal('0')
        total_interest += interest_paid

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'principal', 'label': 'Principal (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_paid', 'label': 'Principal Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_paid', 'label': 'Interest Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'closed_date', 'label': 'Closed Date', 'align': 'center', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'principal': total_principal, 'principal_paid': total_principal, 'interest_paid': total_interest}
    kpi_cards = [
        {'icon': 'bi-check-circle', 'value': f'{len(data):,}', 'label': 'Cleared Loans', 'type': 'success'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_principal:,.0f}', 'label': 'Total Principal Cleared', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_principal + total_interest,
        'total_paid': total_principal + total_interest,
        'outstanding': 0,
        'recovery_rate': '100',
        'par_30': '0',
    }

    context = _get_base_context(request, {
        'report_title': 'Cleared Loans Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# --------------------------------------------------------------------
# 6. Written Off Loans Report
# --------------------------------------------------------------------
@login_required
def written_off_loans_report(request):
    """List of loans written off within a given period."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    if not date_from or not date_to:
        today = date.today()
        date_from = (today - timedelta(days=365)).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')

    # Use 'defaulted' as write-off status (or add 'written_off' to STATUS_CHOICES)
    loans = Loan.objects.filter(status='defaulted', is_active=False)
    if date_from:
        loans = loans.filter(updated_at__date__gte=date_from)
    if date_to:
        loans = loans.filter(updated_at__date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    loans = loans.select_related('member', 'officer').prefetch_related('installments')

    data = []
    total_written_off = Decimal('0')

    for loan in loans:
        # Written off amount = remaining principal + interest (or just principal balance)
        principal_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        written_off_amount = principal_bal + interest_bal

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'written_off_amount': written_off_amount,
            'written_off_date': loan.updated_at.date(),
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
            'reason': loan.notes or 'N/A',
        })
        total_written_off += written_off_amount

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'written_off_amount', 'label': 'Written Off (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'written_off_date', 'label': 'Written Off Date', 'align': 'center', 'type': 'date'},
        {'key': 'reason', 'label': 'Reason', 'align': 'left'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'written_off_amount': total_written_off}
    kpi_cards = [
        {'icon': 'bi-x-circle', 'value': f'{len(data):,}', 'label': 'Written Off Loans', 'type': 'danger'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_written_off:,.0f}', 'label': 'Total Written Off', 'type': 'warning'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_written_off,
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Written Off Loans Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# --------------------------------------------------------------------
# 7. Rescheduled Loans Report (safe)
# --------------------------------------------------------------------
@login_required
def rescheduled_loans_report(request):
    """List of loans that have been rescheduled – requires a rescheduled_date field."""
    if not hasattr(Loan, 'rescheduled_date'):
        columns = [{'key': 'message', 'label': 'Message', 'align': 'left'}]
        data = [{'message': 'Rescheduled loans report is not available – please add a "rescheduled_date" field to the Loan model.'}]
        context = _get_base_context(request, {
            'report_title': 'Rescheduled Loans Report',
            'columns': columns,
            'data': data,
            'has_data': False,
        })
        return render(request, 'finance/reports/base_report.html', context)

    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    loans = Loan.objects.filter(rescheduled_date__isnull=False).select_related('member', 'officer')
    if date_from:
        loans = loans.filter(rescheduled_date__gte=date_from)
    if date_to:
        loans = loans.filter(rescheduled_date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    for loan in loans:
        original_end = loan.start_date + relativedelta(months=loan.period_months) if loan.start_date else None
        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'rescheduled_date': loan.rescheduled_date,
            'original_end_date': original_end,
            'new_end_date': getattr(loan, 'new_end_date', None),
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'rescheduled_date', 'label': 'Rescheduled Date', 'align': 'center', 'type': 'date'},
        {'key': 'original_end_date', 'label': 'Original End Date', 'align': 'center', 'type': 'date'},
        {'key': 'new_end_date', 'label': 'New End Date', 'align': 'center', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    kpi_cards = [
        {'icon': 'bi-arrow-repeat', 'value': f'{len(data):,}', 'label': 'Rescheduled Loans', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': 'N/A',
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Rescheduled Loans Report',
        'columns': columns,
        'data': data,
        'totals': {},
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# --------------------------------------------------------------------
# 8. Transferred Loans Report (safe)
# --------------------------------------------------------------------
@login_required
def transferred_loans_report(request):
    """List of loans transferred – requires a transfer_date field."""
    if not hasattr(Loan, 'transfer_date'):
        columns = [{'key': 'message', 'label': 'Message', 'align': 'left'}]
        data = [{'message': 'Transferred loans report is not available – please add a "transfer_date" field to the Loan model.'}]
        context = _get_base_context(request, {
            'report_title': 'Transferred Loans Report',
            'columns': columns,
            'data': data,
            'has_data': False,
        })
        return render(request, 'finance/reports/base_report.html', context)

    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    loans = Loan.objects.filter(transfer_date__isnull=False).select_related('member', 'officer')
    if date_from:
        loans = loans.filter(transfer_date__gte=date_from)
    if date_to:
        loans = loans.filter(transfer_date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    for loan in loans:
        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'transfer_date': loan.transfer_date,
            'from_officer': getattr(loan, 'previous_officer_name', 'N/A'),
            'to_officer': loan.officer.get_full_name() if loan.officer else 'System',
        })

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'transfer_date', 'label': 'Transfer Date', 'align': 'center', 'type': 'date'},
        {'key': 'from_officer', 'label': 'From Officer', 'align': 'left'},
        {'key': 'to_officer', 'label': 'To Officer', 'align': 'left'},
    ]
    kpi_cards = [
        {'icon': 'bi-arrow-right', 'value': f'{len(data):,}', 'label': 'Transferred Loans', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': 'N/A',
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Transferred Loans Report',
        'columns': columns,
        'data': data,
        'totals': {},
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# --------------------------------------------------------------------
# 9. Maturity Report
# --------------------------------------------------------------------
@login_required
def maturity_report(request):
    """List of loans that mature within a given period (end_date computed)."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    if not date_from or not date_to:
        today = date.today()
        date_from = today.strftime('%Y-%m-%d')
        date_to = (today + timedelta(days=90)).strftime('%Y-%m-%d')

    loans = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).select_related('member', 'officer')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    total_principal = Decimal('0')
    total_interest = Decimal('0')
    total_balance = Decimal('0')

    for loan in loans:
        end_date = loan.start_date + relativedelta(months=loan.period_months)
        if date_from <= end_date.strftime('%Y-%m-%d') <= date_to:
            p_bal = loan.installments.aggregate(
                total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
            )['total']
            i_bal = loan.installments.aggregate(
                total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
            )['total']
            total_bal = p_bal + i_bal
            data.append({
                'member': f"{loan.member.first_name} {loan.member.last_name}",
                'member_no': loan.member.member_number,
                'loan_ref': loan.loan_reference or f"LN-{loan.id}",
                'maturity_date': end_date,
                'principal_balance': p_bal,
                'interest_balance': i_bal,
                'total_balance': total_bal,
                'officer': loan.officer.get_full_name() if loan.officer else 'System',
            })
            total_principal += p_bal
            total_interest += i_bal
            total_balance += total_bal

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'maturity_date', 'label': 'Maturity Date', 'align': 'center', 'type': 'date'},
        {'key': 'principal_balance', 'label': 'Principal (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_balance', 'label': 'Total Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {
        'principal_balance': total_principal,
        'interest_balance': total_interest,
        'total_balance': total_balance,
    }
    kpi_cards = [
        {'icon': 'bi-calendar-range', 'value': f'{len(data):,}', 'label': 'Maturing Loans', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_balance:,.0f}', 'label': 'Total Portfolio Maturing', 'type': 'warning'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_balance,
        'total_paid': 'N/A',
        'outstanding': total_balance,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Maturity Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# --------------------------------------------------------------------
# 10. Forecast Report
# --------------------------------------------------------------------
@login_required
def forecast_report(request):
    """List of loans with installments due in the future."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    if not date_from or not date_to:
        today = date.today()
        date_from = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        date_to = (today + timedelta(days=60)).strftime('%Y-%m-%d')

    loans = Loan.objects.filter(
        installments__due_date__gte=date_from,
        installments__due_date__lte=date_to,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    total_forecast = Decimal('0')

    for loan in loans:
        future_inst = loan.installments.filter(due_date__gte=date_from, due_date__lte=date_to, paid=False)
        total_due = future_inst.aggregate(
            total=Coalesce(
                Sum(F('principal_portion') - F('principal_paid') + F('interest_portion') - F('interest_paid') + F('penalty_amount') - F('penalty_paid')),
                Decimal('0')
            )
        )['total']
        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'forecast_amount': total_due,
            'first_due_date': future_inst.earliest('due_date').due_date if future_inst.exists() else None,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })
        total_forecast += total_due

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'forecast_amount', 'label': 'Forecast Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'first_due_date', 'label': 'First Due Date', 'align': 'center', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'forecast_amount': total_forecast}
    kpi_cards = [
        {'icon': 'bi-binoculars', 'value': f'{len(data):,}', 'label': 'Loans with Future Dues', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_forecast:,.0f}', 'label': 'Total Forecast Amount', 'type': 'primary'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_forecast,
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Forecast Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# --------------------------------------------------------------------
# 11. Portfolio at Risk By Ageing
# --------------------------------------------------------------------
@login_required
def portfolio_at_risk_ageing_report(request):
    """Loans classified by ageing buckets."""
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    loans = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).select_related('member', 'officer').prefetch_related('installments')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    buckets = {
        '1-30_days': Decimal('0'),
        '31-60_days': Decimal('0'),
        '61-90_days': Decimal('0'),
        '91-180_days': Decimal('0'),
        '180_plus': Decimal('0'),
    }

    for loan in loans:
        unpaid_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        if unpaid_inst.exists():
            oldest_due = unpaid_inst.earliest('due_date').due_date
            days = (target_date - oldest_due).days
            # PAR amount = outstanding principal balance
            par_amount = loan.installments.aggregate(
                total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
            )['total']
            bucket_key = None
            if 1 <= days <= 30:
                bucket_key = '1-30_days'
            elif 31 <= days <= 60:
                bucket_key = '31-60_days'
            elif 61 <= days <= 90:
                bucket_key = '61-90_days'
            elif 91 <= days <= 180:
                bucket_key = '91-180_days'
            else:
                bucket_key = '180_plus'

            buckets[bucket_key] += par_amount

            data.append({
                'member': f"{loan.member.first_name} {loan.member.last_name}",
                'member_no': loan.member.member_number,
                'loan_ref': loan.loan_reference or f"LN-{loan.id}",
                'par_amount': par_amount,
                'days_overdue': days,
                'bucket': bucket_key.replace('_', ' ').title(),
                'officer': loan.officer.get_full_name() if loan.officer else 'System',
            })

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'par_amount', 'label': 'PAR Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'days_overdue', 'label': 'Days Overdue', 'align': 'center'},
        {'key': 'bucket', 'label': 'Ageing Bucket', 'align': 'center'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'par_amount': sum(item['par_amount'] for item in data)}
    kpi_cards = [
        {'icon': 'bi-clock', 'value': f'{len(data):,}', 'label': 'At Risk Loans', 'type': 'danger'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["par_amount"]:,.0f}', 'label': 'Total PAR Amount', 'type': 'warning'},
    ]
    aging_summary = [
        {'bucket': '1-30 Days', 'amount': buckets['1-30_days']},
        {'bucket': '31-60 Days', 'amount': buckets['31-60_days']},
        {'bucket': '61-90 Days', 'amount': buckets['61-90_days']},
        {'bucket': '91-180 Days', 'amount': buckets['91-180_days']},
        {'bucket': '180+ Days', 'amount': buckets['180_plus']},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['par_amount'],
        'total_paid': 'N/A',
        'outstanding': totals['par_amount'],
        'recovery_rate': 'N/A',
        'par_30': f'{(buckets["1-30_days"] / (totals["par_amount"] + 1) * 100):.1f}',
    }

    context = _get_base_context(request, {
        'report_title': 'Portfolio at Risk By Ageing',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'aging_summary': aging_summary,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# --------------------------------------------------------------------
# 12. Arrears Vs Savings Report
# --------------------------------------------------------------------
@login_required
def arrears_vs_savings_report(request):
    """Loans in arrears with the member's savings balance."""
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    loans = Loan.objects.filter(
        installments__paid=False,
        installments__due_date__lt=target_date,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    total_arrears = Decimal('0')
    total_savings = Decimal('0')

    for loan in loans:
        savings = SavingsAccount.objects.filter(member=loan.member).first()
        savings_balance = savings.balance if savings else Decimal('0')

        overdue_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        total_due = overdue_inst.aggregate(
            total=Coalesce(
                Sum(F('principal_portion') - F('principal_paid') + F('interest_portion') - F('interest_paid') + F('penalty_amount') - F('penalty_paid')),
                Decimal('0')
            )
        )['total']

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'arrears_amount': total_due,
            'savings_balance': savings_balance,
            'difference': savings_balance - total_due,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })
        total_arrears += total_due
        total_savings += savings_balance

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'arrears_amount', 'label': 'Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'savings_balance', 'label': 'Savings (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'difference', 'label': 'Difference (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'arrears_amount': total_arrears, 'savings_balance': total_savings}
    kpi_cards = [
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {total_arrears:,.0f}', 'label': 'Total Arrears', 'type': 'danger'},
        {'icon': 'bi-wallet2', 'value': f'UGX {total_savings:,.0f}', 'label': 'Total Savings', 'type': 'success'},
        {'icon': 'bi-people', 'value': f'{len(data):,}', 'label': 'Members in Arrears', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_arrears + total_savings,
        'total_paid': 'N/A',
        'outstanding': total_arrears,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Arrears vs Savings Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# --------------------------------------------------------------------
# 13. Loan Ageing Report
# --------------------------------------------------------------------
@login_required
def loan_ageing_report(request):
    """Detailed loan ageing: shows each loan and how its arrears are ageing."""
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    loans = Loan.objects.filter(
        installments__paid=False,
        installments__due_date__lt=target_date,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    total_arrears = Decimal('0')
    bucket_totals = {'1-30': Decimal('0'), '31-60': Decimal('0'), '61-90': Decimal('0'), '91-180': Decimal('0'), '180+': Decimal('0')}

    for loan in loans:
        unpaid_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        buckets = {'1-30': Decimal('0'), '31-60': Decimal('0'), '61-90': Decimal('0'), '91-180': Decimal('0'), '180+': Decimal('0')}
        for inst in unpaid_inst:
            days = (target_date - inst.due_date).days
            due_amount = inst.principal_portion - inst.principal_paid + inst.interest_portion - inst.interest_paid + inst.penalty_amount - inst.penalty_paid
            if 1 <= days <= 30:
                buckets['1-30'] += due_amount
            elif 31 <= days <= 60:
                buckets['31-60'] += due_amount
            elif 61 <= days <= 90:
                buckets['61-90'] += due_amount
            elif 91 <= days <= 180:
                buckets['91-180'] += due_amount
            else:
                buckets['180+'] += due_amount

        total_due = sum(buckets.values())
        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'bucket_1_30': buckets['1-30'],
            'bucket_31_60': buckets['31-60'],
            'bucket_61_90': buckets['61-90'],
            'bucket_91_180': buckets['91-180'],
            'bucket_180_plus': buckets['180+'],
            'total_arrears': total_due,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })
        total_arrears += total_due
        for key in bucket_totals:
            bucket_totals[key] += buckets[key]

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'bucket_1_30', 'label': '1-30 Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'bucket_31_60', 'label': '31-60 Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'bucket_61_90', 'label': '61-90 Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'bucket_91_180', 'label': '91-180 Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'bucket_180_plus', 'label': '180+ Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_arrears', 'label': 'Total Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {
        'bucket_1_30': bucket_totals['1-30'],
        'bucket_31_60': bucket_totals['31-60'],
        'bucket_61_90': bucket_totals['61-90'],
        'bucket_91_180': bucket_totals['91-180'],
        'bucket_180_plus': bucket_totals['180+'],
        'total_arrears': total_arrears,
    }
    kpi_cards = [
        {'icon': 'bi-clock-history', 'value': f'{len(data):,}', 'label': 'Loans with Arrears', 'type': 'warning'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_arrears:,.0f}', 'label': 'Total Arrears', 'type': 'danger'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_arrears,
        'total_paid': 'N/A',
        'outstanding': total_arrears,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Loan Ageing Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)
# --------------------------------------------------------------------
# Helper functions (place these at the bottom of your views.py)
# --------------------------------------------------------------------

def _get_base_context(request, extra_context):
    """Build the base context dictionary for all reports."""
    from django.contrib.auth import get_user_model
    from finance.models import Company  # adjust import as needed
    User = get_user_model()

    company = Company.objects.first()
    context = {
        'company': company or {},
        'generated_date': timezone.now().strftime('%Y-%m-%d %H:%M'),
        'generated_by': request.user.get_full_name() or request.user.username,
        'officer_list': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
        'account_list': [],  # if needed for accounting reports
        'account_type_choices': [],  # if needed
    }
    context.update(extra_context)
    return context


def _get_officer_name(officer_id):
    """Return full name of officer by ID."""
    if not officer_id:
        return None
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        officer = User.objects.get(id=officer_id)
        return officer.get_full_name() or officer.username
    except User.DoesNotExist:
        return None


def _export_requested(request):
    """Check if Excel export was requested."""
    return request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1'


def _export_excel(context):
    """Generate Excel file and return FileResponse."""
    from finance.utils import generate_excel_report  # adjust import as needed
    excel_file = generate_excel_report(
        columns=context['columns'],
        data=context['data'],
        report_title=context['report_title'],
        company_name=context['company'].get('name', 'Company'),
        totals=context.get('totals', {})
    )
    filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
    return FileResponse(excel_file, as_attachment=True, filename=filename)



# ====================================================================
# FINANCE REPORTS – COMPLETE VIEWS
# ====================================================================

import random
from decimal import Decimal
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from django.db.models import Q, Sum, F, Value, DecimalField, Count
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.utils import timezone

from finance.models import Loan, Installment, Member, SavingsAccount, Transaction
from finance.penalties import calculate_penalty          # if needed


# ====================================================================
# HELPER FUNCTIONS
# ====================================================================
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from finance.models import ChartOfAccount

User = get_user_model()

def _get_base_context(request, extra_context):
    """
    Build the base context dictionary for all reports.
    Includes officer_list, account_list, account_type_choices, company, etc.
    """
    # ---- Company info as dict ----
    company_obj = Company.objects.first()
    if company_obj:
        company = {
            'name': company_obj.name,
            'logo': company_obj.logo,
            'phone': company_obj.phone,
            'email': company_obj.email,
            'website': company_obj.website,
            'tagline': company_obj.tagline,
        }
    else:
        company = {
            'name': 'Company',
            'logo': None,
            'phone': '',
            'email': '',
            'website': '',
            'tagline': '',
        }

    # ---- Officer list (active users, ordered by name) ----
    officer_list = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    # If no users, provide an empty queryset (still safe)
    if not officer_list.exists():
        officer_list = User.objects.filter(is_active=True)  # fallback

    # ---- Account list (ChartOfAccount) ----
    account_list = ChartOfAccount.objects.filter(is_active=True).order_by('code')
    account_type_choices = ChartOfAccount.ACCOUNT_TYPES  # tuple of (code, label)

    context = {
        'company': company,
        'generated_date': timezone.now().strftime('%Y-%m-%d %H:%M'),
        'generated_by': request.user.get_full_name() or request.user.username,
        'officer_list': officer_list,
        'account_list': account_list,
        'account_type_choices': account_type_choices,
    }
    context.update(extra_context)
    return context

def _get_officer_name(officer_id):
    """Return full name of officer by ID."""
    if not officer_id:
        return None
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        officer = User.objects.get(id=officer_id)
        return officer.get_full_name() or officer.username
    except User.DoesNotExist:
        return None


def _export_requested(request):
    """Check if Excel export was requested."""
    return request.POST.get('export_excel') == '1' or request.GET.get('export_excel') == '1'


def _export_excel(context):
    """Generate Excel file and return FileResponse."""
    from finance.utils import generate_excel_report  # adjust import as needed
    excel_file = generate_excel_report(
        columns=context['columns'],
        data=context['data'],
        report_title=context['report_title'],
        company_name=context['company'].get('name', 'Company'),
        totals=context.get('totals', {})
    )
    filename = f"{context['report_title'].replace(' ', '_')}_{context['generated_date'].replace(' ', '_').replace(':', '')}.xlsx"
    return FileResponse(excel_file, as_attachment=True, filename=filename)


# ====================================================================
# 1. OUTSTANDING LOANS REPORT
# ====================================================================
@login_required
def outstanding_loans_report(request):
    """List of outstanding loans with all required columns."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    status_filter = request.GET.get('status') or request.POST.get('status')
    search_query = request.GET.get('search_query') or request.POST.get('search_query')

    loans_qs = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).select_related('member', 'officer').prefetch_related('installments', 'repayments')

    if date_from:
        loans_qs = loans_qs.filter(disbursed_date__gte=date_from)
    if date_to:
        loans_qs = loans_qs.filter(disbursed_date__lte=date_to)
    if officer_id:
        loans_qs = loans_qs.filter(officer_id=officer_id)
    if status_filter:
        loans_qs = loans_qs.filter(status=status_filter)
    if search_query:
        loans_qs = loans_qs.filter(
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(member__member_number__icontains=search_query) |
            Q(loan_reference__icontains=search_query)
        )

    today = date.today()
    data = []
    totals = {
        'amount': Decimal('0'),
        'principal_balance': Decimal('0'),
        'interest_balance': Decimal('0'),
        'interest_due': Decimal('0'),
        'principal_due': Decimal('0'),
        'penalty_due': Decimal('0'),
        'total_due': Decimal('0'),
        'principal_prepaid': Decimal('0'),
        'accrued_interest': Decimal('0'),
        'total_accrual_balance': Decimal('0'),
    }

    for loan in loans_qs:
        member = loan.member

        # ---- Balances from installments ----
        principal_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_bal = principal_bal + interest_bal + penalty_bal
        if total_bal == 0:
            continue  # skip fully paid loans

        # ---- Overdue ----
        overdue_inst = loan.installments.filter(paid=False, due_date__lt=today)
        principal_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_due = principal_due + interest_due + penalty_due

        # ---- Paid ----
        principal_paid = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']

        # ---- Classification ----
        if overdue_inst.exists():
            oldest_due = overdue_inst.earliest('due_date').due_date
            days = (today - oldest_due).days
            if days > 90:
                classification = 'Loss'
            elif days > 60:
                classification = 'Doubtful'
            elif days > 30:
                classification = 'Substandard'
            elif days > 0:
                classification = 'Watch'
            else:
                classification = 'Performing'
        else:
            classification = 'Performing'

        # ---- Address ----
        address_parts = [member.village, member.parish, member.district]
        physical_address = ', '.join([p for p in address_parts if p]) or 'N/A'

        row = {
            'no': member.member_number,
            'date': loan.disbursed_date or loan.start_date,
            'name': f"{member.first_name} {member.last_name}",
            'loan_no': loan.loan_reference or f"LN-{loan.id}",
            'phone': member.phone_number,
            'physical_address': physical_address,
            'town': member.district or 'N/A',
            'product': loan.get_product_type_display(),
            'amount': loan.principal_amount,
            'principal_balance': principal_bal,
            'interest_balance': interest_bal,
            'interest_due': interest_due,
            'principal_due': principal_due,
            'penalty_due': penalty_due,
            'total_due': total_due,
            'principal_prepaid': principal_paid,
            'classification': classification,
            'cleared_at': loan.updated_at.date() if loan.status == 'closed' else None,
            'accrued_interest': interest_bal,
            'admin_fees_due': Decimal('0.00'),
            'admin_fees_balance': Decimal('0.00'),
            'branch': member.district or 'Main',
            'loan_status': loan.get_status_display(),
            'batch_number': '',
            'created_at': loan.created_at.date(),
            'total_accrual_balance': interest_bal,
        }
        data.append(row)

        # Accumulate totals
        for key in totals:
            if key in row:
                totals[key] += row[key]

    # ---- Columns ----
    columns = [
        {'key': 'no', 'label': 'No', 'align': 'left'},
        {'key': 'date', 'label': 'Date', 'align': 'center', 'type': 'date'},
        {'key': 'name', 'label': 'Name', 'align': 'left'},
        {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'physical_address', 'label': 'Physical Address', 'align': 'left'},
        {'key': 'town', 'label': 'Town', 'align': 'left'},
        {'key': 'product', 'label': 'Product', 'align': 'left'},
        {'key': 'amount', 'label': 'Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_prepaid', 'label': 'Principal Prepaid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'classification', 'label': 'Classification', 'align': 'center'},
        {'key': 'cleared_at', 'label': 'Cleared At', 'align': 'center', 'type': 'date'},
        {'key': 'accrued_interest', 'label': 'Accrued Interest (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'admin_fees_due', 'label': 'Admin Fees Due (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'branch', 'label': 'Branch', 'align': 'left'},
        {'key': 'loan_status', 'label': 'Loan Status', 'align': 'center', 'type': 'status'},
        {'key': 'batch_number', 'label': 'Batch Number', 'align': 'left'},
        {'key': 'created_at', 'label': 'Created At', 'align': 'center', 'type': 'date'},
        {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]

    # ---- KPIs ----
    total_outstanding = totals['principal_balance'] + totals['interest_balance'] + totals['penalty_due']
    kpi_cards = [
        {'icon': 'bi-bank', 'value': f'{len(data):,}', 'label': 'Outstanding Loans', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_outstanding:,.0f}', 'label': 'Total Outstanding', 'type': 'warning'},
        {'icon': 'bi-person', 'value': f'{len(set(loan.officer_id for loan in loans_qs if loan.officer_id))}', 'label': 'Active Officers', 'type': 'secondary'},
    ]

    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['amount'],
        'total_paid': 'N/A',
        'outstanding': total_outstanding,
        'recovery_rate': 'N/A',
        'par_30': f'{(totals["total_due"] / (total_outstanding + 1) * 100):.1f}',
    }

    context = _get_base_context(request, {
        'report_title': 'Outstanding Loans Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'selected_status': status_filter,
        'officer_name': _get_officer_name(officer_id),
        'search_query': search_query,
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 2. LOANS IN ARREARS REPORT
# ====================================================================
@login_required
def loans_in_arrears_report(request):
    """List of loans in arrears with all required columns."""
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    search_query = request.GET.get('search_query') or request.POST.get('search_query')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    loans_qs = Loan.objects.filter(
        installments__paid=False,
        installments__due_date__lt=target_date,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments', 'repayments')

    if officer_id:
        loans_qs = loans_qs.filter(officer_id=officer_id)
    if search_query:
        loans_qs = loans_qs.filter(
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(member__member_number__icontains=search_query) |
            Q(loan_reference__icontains=search_query)
        )

    data = []
    totals = {
        'principal_arrears': Decimal('0'),
        'interest_arrears': Decimal('0'),
        'penalty_due': Decimal('0'),
        'total_due': Decimal('0'),
        'total_outstanding': Decimal('0'),
        'disbursed_amount': Decimal('0'),
        'principal_due': Decimal('0'),
        'interest_due': Decimal('0'),
        'unpaid_arrears': Decimal('0'),
        'principal_paid': Decimal('0'),
        'interest_paid': Decimal('0'),
        'penalty_paid': Decimal('0'),
        'principal_balance': Decimal('0'),
        'interest_balance': Decimal('0'),
        'penalty_balance': Decimal('0'),
        'total_accrual_balance': Decimal('0'),
    }

    for loan in loans_qs:
        member = loan.member

        # ---- Overdue ----
        overdue_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        if not overdue_inst.exists():
            continue

        principal_arrears = overdue_inst.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_arrears = overdue_inst.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_due = principal_arrears + interest_arrears + penalty_due

        # ---- Total balances ----
        principal_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_outstanding = principal_bal + interest_bal + penalty_bal

        # ---- Paid ----
        principal_paid = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']
        interest_paid = loan.installments.aggregate(
            total=Coalesce(Sum('interest_paid'), Decimal('0'))
        )['total']
        penalty_paid = loan.installments.aggregate(
            total=Coalesce(Sum('penalty_paid'), Decimal('0'))
        )['total']

        # ---- Arrears days ----
        oldest_due = overdue_inst.earliest('due_date').due_date
        arrears_days = (target_date - oldest_due).days

        # ---- Classification ----
        if arrears_days > 90:
            classification = 'Loss'
        elif arrears_days > 60:
            classification = 'Doubtful'
        elif arrears_days > 30:
            classification = 'Substandard'
        else:
            classification = 'Watch'

        # ---- Arrears rate ----
        arrears_rate = (total_due / total_outstanding * 100) if total_outstanding > 0 else 0

        # ---- Guarantors ----
        guarantors = []
        if loan.guarantor_1_name:
            guarantors.append(loan.guarantor_1_name)
        if loan.guarantor_2_name:
            guarantors.append(loan.guarantor_2_name)
        guarantor_str = ', '.join(guarantors) if guarantors else 'None'

        # ---- Address ----
        address_parts = [member.village, member.parish, member.district]
        physical_address = ', '.join([p for p in address_parts if p]) or 'N/A'

        # ---- Last repayment ----
        last_repayment = loan.repayments.order_by('-date_paid').first()
        last_repayment_date = last_repayment.date_paid.date() if last_repayment else None

        row = {
            'no': member.member_number,
            'name': f"{member.first_name} {member.last_name}",
            'phone': member.phone_number,
            'loan_no': loan.loan_reference or f"LN-{loan.id}",
            'principal_arrears': principal_arrears,
            'interest_arrears': interest_arrears,
            'arrears_days': arrears_days,
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'disbursed_amount': loan.principal_amount,
            'last_repayment_date': last_repayment_date,
            'principal_due': principal_arrears,
            'interest_due': interest_arrears,
            'penalty_due': penalty_due,
            'total_due': total_due,
            'total_outstanding': total_outstanding,
            'msacco_no': member.member_number,
            'physical_address': physical_address,
            'classification': classification,
            'batch_no': '',
            'arrears_rate': round(arrears_rate, 2),
            'admin_fees_due': Decimal('0.00'),
            'admin_fees_balance': Decimal('0.00'),
            'unpaid_arrears': total_due,
            'transfer_status': '',
            'status': loan.get_status_display(),
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
            'town': member.district or 'N/A',
            'product': loan.get_product_type_display(),
            'principal_paid': principal_paid,
            'interest_paid': interest_paid,
            'penalty_paid': penalty_paid,
            'prepaid_principal': principal_paid,
            'principal_balance': principal_bal,
            'interest_balance': interest_bal,
            'penalty_balance': penalty_bal,
            'guarantors': guarantor_str,
            'total_accrual_balance': interest_bal,
        }
        data.append(row)

        # Accumulate totals
        for key in totals:
            if key in row:
                totals[key] += row[key]

    # ---- Columns ----
    columns = [
        {'key': 'no', 'label': 'No', 'align': 'left'},
        {'key': 'name', 'label': 'Name', 'align': 'left'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
        {'key': 'principal_arrears', 'label': 'Principal Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_arrears', 'label': 'Interest Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'arrears_days', 'label': 'Arrears Days', 'align': 'center'},
        {'key': 'disbursement_date', 'label': 'Disbursement Date', 'align': 'center', 'type': 'date'},
        {'key': 'disbursed_amount', 'label': 'Disbursed Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'last_repayment_date', 'label': 'Last Repayment Date', 'align': 'center', 'type': 'date'},
        {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_outstanding', 'label': 'Total Outstanding (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'msacco_no', 'label': 'Msacco No', 'align': 'left'},
        {'key': 'physical_address', 'label': 'Physical Address', 'align': 'left'},
        {'key': 'classification', 'label': 'Classification', 'align': 'center'},
        {'key': 'batch_no', 'label': 'Batch No', 'align': 'left'},
        {'key': 'arrears_rate', 'label': 'Arrears rate (%)', 'align': 'right'},
        {'key': 'admin_fees_due', 'label': 'Admin Fees Due (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'unpaid_arrears', 'label': 'Unpaid Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'transfer_status', 'label': 'Transfer Status', 'align': 'left'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
        {'key': 'town', 'label': 'Town', 'align': 'left'},
        {'key': 'product', 'label': 'Product', 'align': 'left'},
        {'key': 'principal_paid', 'label': 'Principal Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_paid', 'label': 'Interest Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_paid', 'label': 'Penalty Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'prepaid_principal', 'label': 'Prepaid Principal (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_balance', 'label': 'Penalty Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'guarantors', 'label': 'Guarantors', 'align': 'left'},
        {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]

    # ---- KPIs ----
    kpi_cards = [
        {'icon': 'bi-exclamation-triangle', 'value': f'{len(data):,}', 'label': 'Loans in Arrears', 'type': 'danger'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["total_due"]:,.0f}', 'label': 'Total Overdue', 'type': 'warning'},
        {'icon': 'bi-percent', 'value': f'{(totals["total_due"] / (totals["total_outstanding"] + 1) * 100):.1f}%', 'label': 'Arrears Rate', 'type': 'info'},
    ]

    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['total_outstanding'],
        'total_paid': 'N/A',
        'outstanding': totals['total_due'],
        'recovery_rate': 'N/A',
        'par_30': f'{(totals["total_due"] / (totals["total_outstanding"] + 1) * 100):.1f}',
    }

    context = _get_base_context(request, {
        'report_title': 'Loans In Arrears Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
        'search_query': search_query,
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 3. PORTFOLIO STATUS REPORT
# ====================================================================
@login_required
def portfolio_status_report(request):
    """A Status On Outstanding Loans – comprehensive portfolio summary."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    status_filter = request.GET.get('status') or request.POST.get('status')
    search_query = request.GET.get('search_query') or request.POST.get('search_query')

    loans_qs = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).select_related('member', 'officer').prefetch_related('installments', 'repayments')

    if date_from:
        loans_qs = loans_qs.filter(disbursed_date__gte=date_from)
    if date_to:
        loans_qs = loans_qs.filter(disbursed_date__lte=date_to)
    if officer_id:
        loans_qs = loans_qs.filter(officer_id=officer_id)
    if status_filter:
        loans_qs = loans_qs.filter(status=status_filter)
    if search_query:
        loans_qs = loans_qs.filter(
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(member__member_number__icontains=search_query) |
            Q(loan_reference__icontains=search_query)
        )

    today = date.today()
    data = []
    totals = {
        'disbursed_amount': Decimal('0'),
        'principal_paid': Decimal('0'),
        'interest_paid': Decimal('0'),
        'penalty_paid': Decimal('0'),
        'principal_due': Decimal('0'),
        'interest_due': Decimal('0'),
        'penalty_due': Decimal('0'),
        'principal_balance': Decimal('0'),
        'interest_balance': Decimal('0'),
        'penalty_balance': Decimal('0'),
        'total_outstanding': Decimal('0'),
        'total_due': Decimal('0'),
        'interest_arrears': Decimal('0'),
        'principal_arrears': Decimal('0'),
        'total_accrual_balance': Decimal('0'),
    }

    for loan in loans_qs:
        member = loan.member

        # ---- Paid ----
        principal_paid = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']
        interest_paid = loan.installments.aggregate(
            total=Coalesce(Sum('interest_paid'), Decimal('0'))
        )['total']
        penalty_paid = loan.installments.aggregate(
            total=Coalesce(Sum('penalty_paid'), Decimal('0'))
        )['total']

        # ---- Balances ----
        principal_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_outstanding = principal_bal + interest_bal + penalty_bal

        # ---- Overdue ----
        overdue_inst = loan.installments.filter(paid=False, due_date__lt=today)
        principal_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_due = principal_due + interest_due + penalty_due

        # ---- Completion Rate ----
        total_payable = loan.total_payable or (loan.principal_amount + loan.principal_amount * loan.interest_rate / 100)
        completion_rate = round(((total_payable - total_outstanding) / total_payable * 100), 2) if total_payable > 0 else 0

        # ---- Classification ----
        if overdue_inst.exists():
            oldest_due = overdue_inst.earliest('due_date').due_date
            days = (today - oldest_due).days
            if days > 90:
                classification = 'Loss'
            elif days > 60:
                classification = 'Doubtful'
            elif days > 30:
                classification = 'Substandard'
            else:
                classification = 'Watch'
        else:
            classification = 'Performing'

        row = {
            'no': member.member_number,
            'name': f"{member.first_name} {member.last_name}",
            'loan_no': loan.loan_reference or f"LN-{loan.id}",
            'disbursed_amount': loan.principal_amount,
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'principal_paid': principal_paid,
            'interest_paid': interest_paid,
            'principal_due': principal_due,
            'penalty_paid': penalty_paid,
            'prepaid_principal': principal_paid,
            'interest_due': interest_due,
            'penalty_due': penalty_due,
            'total_due': total_due,
            'interest_arrears': interest_due,
            'principal_arrears': principal_due,
            'admin_fees_balance': Decimal('0.00'),
            'status': loan.get_status_display(),
            'batch_no': '',
            'classification': classification,
            'borrower_category': getattr(member, 'borrower_category', 'N/A'),
            'economic_sector': getattr(member, 'economic_sector', 'N/A'),
            'transfer_status': '',
            'product': loan.get_product_type_display(),
            'principal_balance': principal_bal,
            'interest_balance': interest_bal,
            'penalty_balance': penalty_bal,
            'total_outstanding': total_outstanding,
            'completion_rate': completion_rate,
            'total_accrual_balance': interest_bal,
        }
        data.append(row)

        # Accumulate totals
        for key in totals:
            if key in row:
                totals[key] += row[key]

    # ---- Columns ----
    columns = [
        {'key': 'no', 'label': 'No', 'align': 'left'},
        {'key': 'name', 'label': 'Name', 'align': 'left'},
        {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
        {'key': 'disbursed_amount', 'label': 'Disbursed Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'disbursement_date', 'label': 'Disbursement Date', 'align': 'center', 'type': 'date'},
        {'key': 'principal_paid', 'label': 'Principal Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_paid', 'label': 'Interest Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_paid', 'label': 'Penalty Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'prepaid_principal', 'label': 'Prepaid Principal (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_arrears', 'label': 'Interest Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_arrears', 'label': 'Principal Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'batch_no', 'label': 'Batch No', 'align': 'left'},
        {'key': 'classification', 'label': 'Classification', 'align': 'center'},
        {'key': 'borrower_category', 'label': 'Borrower category', 'align': 'left'},
        {'key': 'economic_sector', 'label': 'Economic sector', 'align': 'left'},
        {'key': 'transfer_status', 'label': 'Transfer Status', 'align': 'left'},
        {'key': 'product', 'label': 'Product', 'align': 'left'},
        {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_balance', 'label': 'Penalty Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_outstanding', 'label': 'Total Outstanding (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'completion_rate', 'label': 'Completion Rate (%)', 'align': 'right'},
        {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]

    # ---- KPIs ----
    kpi_cards = [
        {'icon': 'bi-pie-chart', 'value': f'{len(data):,}', 'label': 'Active Loans', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["total_outstanding"]:,.0f}', 'label': 'Total Outstanding', 'type': 'warning'},
        {'icon': 'bi-percent', 'value': f'{(totals["total_due"] / (totals["total_outstanding"] + 1) * 100):.1f}%', 'label': 'PAR > 30', 'type': 'danger'},
    ]

    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['disbursed_amount'],
        'total_paid': totals['principal_paid'] + totals['interest_paid'],
        'outstanding': totals['total_outstanding'],
        'recovery_rate': round(((totals['principal_paid'] + totals['interest_paid']) / (totals['disbursed_amount'] + 1) * 100), 1),
        'par_30': round((totals['total_due'] / (totals['total_outstanding'] + 1) * 100), 1),
    }

    context = _get_base_context(request, {
        'report_title': 'Portfolio Status Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'selected_status': status_filter,
        'officer_name': _get_officer_name(officer_id),
        'search_query': search_query,
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 4. DUE LOANS REPORT
# ====================================================================
@login_required
def due_loans_report(request):
    """A list of all due loans (overdue installments)."""
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')
    search_query = request.GET.get('search_query') or request.POST.get('search_query')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    loans_qs = Loan.objects.filter(
        installments__paid=False,
        installments__due_date__lt=target_date,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments', 'repayments')

    if officer_id:
        loans_qs = loans_qs.filter(officer_id=officer_id)
    if search_query:
        loans_qs = loans_qs.filter(
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query) |
            Q(member__member_number__icontains=search_query) |
            Q(loan_reference__icontains=search_query)
        )

    data = []
    totals = {
        'principal_arrears': Decimal('0'),
        'interest_arrears': Decimal('0'),
        'total_arrears': Decimal('0'),
        'principal_due': Decimal('0'),
        'interest_due': Decimal('0'),
        'penalty_due': Decimal('0'),
        'total_due': Decimal('0'),
        'principal_balance': Decimal('0'),
        'interest_balance': Decimal('0'),
        'penalty_balance': Decimal('0'),
        'total_outstanding': Decimal('0'),
        'disbursed_amount': Decimal('0'),
        'accrued_interest': Decimal('0'),
        'total_accrual_balance': Decimal('0'),
    }

    for loan in loans_qs:
        member = loan.member

        # ---- Overdue ----
        overdue_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        if not overdue_inst.exists():
            continue

        principal_arrears = overdue_inst.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_arrears = overdue_inst.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_due = overdue_inst.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_arrears = principal_arrears + interest_arrears + penalty_due

        # ---- Balances ----
        principal_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_outstanding = principal_bal + interest_bal + penalty_bal

        # ---- Arrears days ----
        oldest_due = overdue_inst.earliest('due_date').due_date
        arrears_days = (target_date - oldest_due).days
        arrears_rate = (total_arrears / total_outstanding * 100) if total_outstanding > 0 else 0

        # ---- Classification ----
        if arrears_days > 90:
            classification = 'Loss'
        elif arrears_days > 60:
            classification = 'Doubtful'
        elif arrears_days > 30:
            classification = 'Substandard'
        else:
            classification = 'Watch'

        # ---- Guarantors ----
        guarantors = []
        if loan.guarantor_1_name:
            guarantors.append(loan.guarantor_1_name)
        if loan.guarantor_2_name:
            guarantors.append(loan.guarantor_2_name)
        guarantor_str = ', '.join(guarantors) if guarantors else 'None'

        # ---- Address ----
        address_parts = [member.village, member.parish, member.district]
        physical_address = ', '.join([p for p in address_parts if p]) or 'N/A'

        row = {
            'no': member.member_number,
            'name': f"{member.first_name} {member.last_name}",
            'loan_no': loan.loan_reference or f"LN-{loan.id}",
            'batch_no': '',
            'status': loan.get_status_display(),
            'classification': classification,
            'transfer_status': '',
            'guarantors': guarantor_str,
            'principal_arrears': principal_arrears,
            'interest_arrears': interest_arrears,
            'total_arrears': total_arrears,
            'arrears_days': arrears_days,
            'arrears_rate': round(arrears_rate, 2),
            'phone': member.phone_number,
            'physical_address': physical_address,
            'town': member.district or 'N/A',
            'product': loan.get_product_type_display(),
            'disbursed_amount': loan.principal_amount,
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'principal_due': principal_arrears,
            'interest_due': interest_arrears,
            'penalty_due': penalty_due,
            'total_due': total_arrears,
            'principal_balance': principal_bal,
            'interest_balance': interest_bal,
            'penalty_balance': penalty_bal,
            'total_outstanding': total_outstanding,
            'accrued_interest': interest_bal,
            'total_accrual_balance': interest_bal,
            'admin_fees_due': Decimal('0.00'),
            'admin_fees_balance': Decimal('0.00'),
            'unpaid_admin_fees': Decimal('0.00'),
        }
        data.append(row)

        # Accumulate totals
        for key in totals:
            if key in row:
                totals[key] += row[key]

    # ---- Columns ----
    columns = [
        {'key': 'no', 'label': 'No', 'align': 'left'},
        {'key': 'name', 'label': 'Name', 'align': 'left'},
        {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
        {'key': 'batch_no', 'label': 'Batch No', 'align': 'left'},
        {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
        {'key': 'classification', 'label': 'Classification', 'align': 'center'},
        {'key': 'transfer_status', 'label': 'Transfer Status', 'align': 'left'},
        {'key': 'guarantors', 'label': 'Guarantors', 'align': 'left'},
        {'key': 'principal_arrears', 'label': 'Principal Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_arrears', 'label': 'Interest Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_arrears', 'label': 'Total arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'arrears_days', 'label': 'Arrears Days', 'align': 'center'},
        {'key': 'arrears_rate', 'label': 'Arrears rate (%)', 'align': 'right'},
        {'key': 'phone', 'label': 'Phone', 'align': 'left'},
        {'key': 'physical_address', 'label': 'Physical Address', 'align': 'left'},
        {'key': 'town', 'label': 'Town', 'align': 'left'},
        {'key': 'product', 'label': 'Product', 'align': 'left'},
        {'key': 'disbursed_amount', 'label': 'Disbursed Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'disbursement_date', 'label': 'Disbursement Date', 'align': 'center', 'type': 'date'},
        {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'penalty_balance', 'label': 'Penalty Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_outstanding', 'label': 'Total Outstanding (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'accrued_interest', 'label': 'Accrued Interest (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'admin_fees_due', 'label': 'Admin Fees Due (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'unpaid_admin_fees', 'label': 'Unpaid Admin Fees (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
    ]

    # ---- KPIs ----
    kpi_cards = [
        {'icon': 'bi-calendar-event', 'value': f'{len(data):,}', 'label': 'Due Loans', 'type': 'warning'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["total_arrears"]:,.0f}', 'label': 'Total Arrears', 'type': 'danger'},
        {'icon': 'bi-percent', 'value': f'{(totals["total_arrears"] / (totals["total_outstanding"] + 1) * 100):.1f}%', 'label': 'Arrears Rate', 'type': 'info'},
    ]

    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['total_outstanding'],
        'total_paid': 'N/A',
        'outstanding': totals['total_arrears'],
        'recovery_rate': 'N/A',
        'par_30': f'{(totals["total_arrears"] / (totals["total_outstanding"] + 1) * 100):.1f}',
    }

    context = _get_base_context(request, {
        'report_title': 'Due Loans Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
        'search_query': search_query,
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 5. CLEARED LOANS REPORT
# ====================================================================
@login_required
def cleared_loans_report(request):
    """List of loans fully cleared (closed) within a period."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    if not date_from or not date_to:
        today = date.today()
        date_from = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')

    loans = Loan.objects.filter(status='closed', is_active=False)
    if date_from:
        loans = loans.filter(updated_at__date__gte=date_from)
    if date_to:
        loans = loans.filter(updated_at__date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    loans = loans.select_related('member', 'officer').prefetch_related('installments')

    data = []
    total_principal = Decimal('0')
    total_interest = Decimal('0')

    for loan in loans:
        principal_paid = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']
        interest_paid = loan.installments.aggregate(
            total=Coalesce(Sum('interest_paid'), Decimal('0'))
        )['total']

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'principal': loan.principal_amount,
            'principal_paid': principal_paid,
            'interest_paid': interest_paid,
            'closed_date': loan.updated_at.date(),
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })
        total_principal += loan.principal_amount or Decimal('0')
        total_interest += interest_paid

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'principal', 'label': 'Principal (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'principal_paid', 'label': 'Principal Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_paid', 'label': 'Interest Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'closed_date', 'label': 'Closed Date', 'align': 'center', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'principal': total_principal, 'principal_paid': total_principal, 'interest_paid': total_interest}
    kpi_cards = [
        {'icon': 'bi-check-circle', 'value': f'{len(data):,}', 'label': 'Cleared Loans', 'type': 'success'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_principal:,.0f}', 'label': 'Total Principal Cleared', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_principal + total_interest,
        'total_paid': total_principal + total_interest,
        'outstanding': 0,
        'recovery_rate': '100',
        'par_30': '0',
    }

    context = _get_base_context(request, {
        'report_title': 'Cleared Loans Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 6. WRITTEN OFF LOANS REPORT
# ====================================================================
@login_required
def written_off_loans_report(request):
    """List of loans written off (status='defaulted' or 'written_off')."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    if not date_from or not date_to:
        today = date.today()
        date_from = (today - timedelta(days=365)).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')

    # Use 'defaulted' as write-off status – adjust if you have a dedicated status
    loans = Loan.objects.filter(status='defaulted', is_active=False)
    if date_from:
        loans = loans.filter(updated_at__date__gte=date_from)
    if date_to:
        loans = loans.filter(updated_at__date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    loans = loans.select_related('member', 'officer').prefetch_related('installments')

    data = []
    total_written_off = Decimal('0')

    for loan in loans:
        principal_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        written_off_amount = principal_bal + interest_bal

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'written_off_amount': written_off_amount,
            'written_off_date': loan.updated_at.date(),
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
            'reason': loan.notes or 'N/A',
        })
        total_written_off += written_off_amount

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'written_off_amount', 'label': 'Written Off (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'written_off_date', 'label': 'Written Off Date', 'align': 'center', 'type': 'date'},
        {'key': 'reason', 'label': 'Reason', 'align': 'left'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'written_off_amount': total_written_off}
    kpi_cards = [
        {'icon': 'bi-x-circle', 'value': f'{len(data):,}', 'label': 'Written Off Loans', 'type': 'danger'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_written_off:,.0f}', 'label': 'Total Written Off', 'type': 'warning'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_written_off,
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Written Off Loans Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 7. RESCHEDULED LOANS REPORT
# ====================================================================
@login_required
def rescheduled_loans_report(request):
    """List of rescheduled loans – requires 'rescheduled_date' field."""
    if not hasattr(Loan, 'rescheduled_date'):
        columns = [{'key': 'message', 'label': 'Message', 'align': 'left'}]
        data = [{'message': 'Rescheduled loans report is not available – please add a "rescheduled_date" field to the Loan model.'}]
        context = _get_base_context(request, {
            'report_title': 'Rescheduled Loans Report',
            'columns': columns,
            'data': data,
            'has_data': False,
        })
        return render(request, 'finance/reports/base_report.html', context)

    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    loans = Loan.objects.filter(rescheduled_date__isnull=False).select_related('member', 'officer')
    if date_from:
        loans = loans.filter(rescheduled_date__gte=date_from)
    if date_to:
        loans = loans.filter(rescheduled_date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    for loan in loans:
        original_end = loan.start_date + relativedelta(months=loan.period_months) if loan.start_date else None
        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'rescheduled_date': loan.rescheduled_date,
            'original_end_date': original_end,
            'new_end_date': getattr(loan, 'new_end_date', None),
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'rescheduled_date', 'label': 'Rescheduled Date', 'align': 'center', 'type': 'date'},
        {'key': 'original_end_date', 'label': 'Original End Date', 'align': 'center', 'type': 'date'},
        {'key': 'new_end_date', 'label': 'New End Date', 'align': 'center', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    kpi_cards = [
        {'icon': 'bi-arrow-repeat', 'value': f'{len(data):,}', 'label': 'Rescheduled Loans', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': 'N/A',
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Rescheduled Loans Report',
        'columns': columns,
        'data': data,
        'totals': {},
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 8. TRANSFERRED LOANS REPORT
# ====================================================================
@login_required
def transferred_loans_report(request):
    """List of transferred loans – requires 'transfer_date' field."""
    if not hasattr(Loan, 'transfer_date'):
        columns = [{'key': 'message', 'label': 'Message', 'align': 'left'}]
        data = [{'message': 'Transferred loans report is not available – please add a "transfer_date" field to the Loan model.'}]
        context = _get_base_context(request, {
            'report_title': 'Transferred Loans Report',
            'columns': columns,
            'data': data,
            'has_data': False,
        })
        return render(request, 'finance/reports/base_report.html', context)

    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    loans = Loan.objects.filter(transfer_date__isnull=False).select_related('member', 'officer')
    if date_from:
        loans = loans.filter(transfer_date__gte=date_from)
    if date_to:
        loans = loans.filter(transfer_date__lte=date_to)
    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    for loan in loans:
        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'transfer_date': loan.transfer_date,
            'from_officer': getattr(loan, 'previous_officer_name', 'N/A'),
            'to_officer': loan.officer.get_full_name() if loan.officer else 'System',
        })

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'transfer_date', 'label': 'Transfer Date', 'align': 'center', 'type': 'date'},
        {'key': 'from_officer', 'label': 'From Officer', 'align': 'left'},
        {'key': 'to_officer', 'label': 'To Officer', 'align': 'left'},
    ]
    kpi_cards = [
        {'icon': 'bi-arrow-right', 'value': f'{len(data):,}', 'label': 'Transferred Loans', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': 'N/A',
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Transferred Loans Report',
        'columns': columns,
        'data': data,
        'totals': {},
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 9. MATURITY REPORT
# ====================================================================
@login_required
def maturity_report(request):
    """List of loans maturing within a given period (computed end_date)."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    if not date_from or not date_to:
        today = date.today()
        date_from = today.strftime('%Y-%m-%d')
        date_to = (today + timedelta(days=90)).strftime('%Y-%m-%d')

    loans = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).select_related('member', 'officer').prefetch_related('installments')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    total_principal = Decimal('0')
    total_interest = Decimal('0')
    total_balance = Decimal('0')

    for loan in loans:
        end_date = loan.start_date + relativedelta(months=loan.period_months)
        if date_from <= end_date.strftime('%Y-%m-%d') <= date_to:
            p_bal = loan.installments.aggregate(
                total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
            )['total']
            i_bal = loan.installments.aggregate(
                total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
            )['total']
            total_bal = p_bal + i_bal
            data.append({
                'member': f"{loan.member.first_name} {loan.member.last_name}",
                'member_no': loan.member.member_number,
                'loan_ref': loan.loan_reference or f"LN-{loan.id}",
                'maturity_date': end_date,
                'principal_balance': p_bal,
                'interest_balance': i_bal,
                'total_balance': total_bal,
                'officer': loan.officer.get_full_name() if loan.officer else 'System',
            })
            total_principal += p_bal
            total_interest += i_bal
            total_balance += total_bal

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'maturity_date', 'label': 'Maturity Date', 'align': 'center', 'type': 'date'},
        {'key': 'principal_balance', 'label': 'Principal (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'interest_balance', 'label': 'Interest (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_balance', 'label': 'Total Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {
        'principal_balance': total_principal,
        'interest_balance': total_interest,
        'total_balance': total_balance,
    }
    kpi_cards = [
        {'icon': 'bi-calendar-range', 'value': f'{len(data):,}', 'label': 'Maturing Loans', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_balance:,.0f}', 'label': 'Total Portfolio Maturing', 'type': 'warning'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_balance,
        'total_paid': 'N/A',
        'outstanding': total_balance,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Maturity Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 10. FORECAST REPORT
# ====================================================================
@login_required
def forecast_report(request):
    """List of loans with future due installments."""
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    if not date_from or not date_to:
        today = date.today()
        date_from = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        date_to = (today + timedelta(days=60)).strftime('%Y-%m-%d')

    loans = Loan.objects.filter(
        installments__due_date__gte=date_from,
        installments__due_date__lte=date_to,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    total_forecast = Decimal('0')

    for loan in loans:
        future_inst = loan.installments.filter(due_date__gte=date_from, due_date__lte=date_to, paid=False)
        total_due = future_inst.aggregate(
            total=Coalesce(
                Sum(F('principal_portion') - F('principal_paid') + F('interest_portion') - F('interest_paid') + F('penalty_amount') - F('penalty_paid')),
                Decimal('0')
            )
        )['total']
        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'forecast_amount': total_due,
            'first_due_date': future_inst.earliest('due_date').due_date if future_inst.exists() else None,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })
        total_forecast += total_due

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'forecast_amount', 'label': 'Forecast Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'first_due_date', 'label': 'First Due Date', 'align': 'center', 'type': 'date'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'forecast_amount': total_forecast}
    kpi_cards = [
        {'icon': 'bi-binoculars', 'value': f'{len(data):,}', 'label': 'Loans with Future Dues', 'type': 'info'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_forecast:,.0f}', 'label': 'Total Forecast Amount', 'type': 'primary'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_forecast,
        'total_paid': 'N/A',
        'outstanding': 'N/A',
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Forecast Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 11. PORTFOLIO AT RISK BY AGEING
# ====================================================================
@login_required
def portfolio_at_risk_ageing_report(request):
    """Loans classified by ageing buckets."""
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    loans = Loan.objects.filter(
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).select_related('member', 'officer').prefetch_related('installments')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    buckets = {
        '1-30_days': Decimal('0'),
        '31-60_days': Decimal('0'),
        '61-90_days': Decimal('0'),
        '91-180_days': Decimal('0'),
        '180_plus': Decimal('0'),
    }

    for loan in loans:
        unpaid_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        if unpaid_inst.exists():
            oldest_due = unpaid_inst.earliest('due_date').due_date
            days = (target_date - oldest_due).days
            par_amount = loan.installments.aggregate(
                total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
            )['total']
            bucket_key = None
            if 1 <= days <= 30:
                bucket_key = '1-30_days'
            elif 31 <= days <= 60:
                bucket_key = '31-60_days'
            elif 61 <= days <= 90:
                bucket_key = '61-90_days'
            elif 91 <= days <= 180:
                bucket_key = '91-180_days'
            else:
                bucket_key = '180_plus'

            buckets[bucket_key] += par_amount

            data.append({
                'member': f"{loan.member.first_name} {loan.member.last_name}",
                'member_no': loan.member.member_number,
                'loan_ref': loan.loan_reference or f"LN-{loan.id}",
                'par_amount': par_amount,
                'days_overdue': days,
                'bucket': bucket_key.replace('_', ' ').title(),
                'officer': loan.officer.get_full_name() if loan.officer else 'System',
            })

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'par_amount', 'label': 'PAR Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'days_overdue', 'label': 'Days Overdue', 'align': 'center'},
        {'key': 'bucket', 'label': 'Ageing Bucket', 'align': 'center'},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'par_amount': sum(item['par_amount'] for item in data)}
    kpi_cards = [
        {'icon': 'bi-clock', 'value': f'{len(data):,}', 'label': 'At Risk Loans', 'type': 'danger'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {totals["par_amount"]:,.0f}', 'label': 'Total PAR Amount', 'type': 'warning'},
    ]
    aging_summary = [
        {'bucket': '1-30 Days', 'amount': buckets['1-30_days']},
        {'bucket': '31-60 Days', 'amount': buckets['31-60_days']},
        {'bucket': '61-90 Days', 'amount': buckets['61-90_days']},
        {'bucket': '91-180 Days', 'amount': buckets['91-180_days']},
        {'bucket': '180+ Days', 'amount': buckets['180_plus']},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': totals['par_amount'],
        'total_paid': 'N/A',
        'outstanding': totals['par_amount'],
        'recovery_rate': 'N/A',
        'par_30': f'{(buckets["1-30_days"] / (totals["par_amount"] + 1) * 100):.1f}',
    }

    context = _get_base_context(request, {
        'report_title': 'Portfolio at Risk By Ageing',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'aging_summary': aging_summary,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 12. ARREARS VS SAVINGS REPORT
# ====================================================================
@login_required
def arrears_vs_savings_report(request):
    """Loans in arrears with member's savings balance."""
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    loans = Loan.objects.filter(
        installments__paid=False,
        installments__due_date__lt=target_date,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    total_arrears = Decimal('0')
    total_savings = Decimal('0')

    for loan in loans:
        savings = SavingsAccount.objects.filter(member=loan.member).first()
        savings_balance = savings.balance if savings else Decimal('0')

        overdue_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        total_due = overdue_inst.aggregate(
            total=Coalesce(
                Sum(F('principal_portion') - F('principal_paid') + F('interest_portion') - F('interest_paid') + F('penalty_amount') - F('penalty_paid')),
                Decimal('0')
            )
        )['total']

        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'arrears_amount': total_due,
            'savings_balance': savings_balance,
            'difference': savings_balance - total_due,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })
        total_arrears += total_due
        total_savings += savings_balance

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'arrears_amount', 'label': 'Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'savings_balance', 'label': 'Savings (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'difference', 'label': 'Difference (UGX)', 'type': 'currency', 'align': 'right', 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {'arrears_amount': total_arrears, 'savings_balance': total_savings}
    kpi_cards = [
        {'icon': 'bi-exclamation-triangle', 'value': f'UGX {total_arrears:,.0f}', 'label': 'Total Arrears', 'type': 'danger'},
        {'icon': 'bi-wallet2', 'value': f'UGX {total_savings:,.0f}', 'label': 'Total Savings', 'type': 'success'},
        {'icon': 'bi-people', 'value': f'{len(data):,}', 'label': 'Members in Arrears', 'type': 'info'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_arrears + total_savings,
        'total_paid': 'N/A',
        'outstanding': total_arrears,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Arrears vs Savings Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# ====================================================================
# 13. LOAN AGEING REPORT
# ====================================================================
@login_required
def loan_ageing_report(request):
    """Detailed loan ageing: shows each loan and how its arrears are ageing."""
    date_at = request.GET.get('date_at') or request.POST.get('date_at')
    officer_id = request.GET.get('officer') or request.POST.get('officer')

    today = date.today()
    if date_at:
        try:
            target_date = datetime.strptime(date_at, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    loans = Loan.objects.filter(
        installments__paid=False,
        installments__due_date__lt=target_date,
        is_active=True,
        status__in=['approved', 'active', 'arrears']
    ).distinct().select_related('member', 'officer').prefetch_related('installments')

    if officer_id:
        loans = loans.filter(officer_id=officer_id)

    data = []
    total_arrears = Decimal('0')
    bucket_totals = {'1-30': Decimal('0'), '31-60': Decimal('0'), '61-90': Decimal('0'), '91-180': Decimal('0'), '180+': Decimal('0')}

    for loan in loans:
        unpaid_inst = loan.installments.filter(paid=False, due_date__lt=target_date)
        buckets = {'1-30': Decimal('0'), '31-60': Decimal('0'), '61-90': Decimal('0'), '91-180': Decimal('0'), '180+': Decimal('0')}
        for inst in unpaid_inst:
            days = (target_date - inst.due_date).days
            due_amount = inst.principal_portion - inst.principal_paid + inst.interest_portion - inst.interest_paid + inst.penalty_amount - inst.penalty_paid
            if 1 <= days <= 30:
                buckets['1-30'] += due_amount
            elif 31 <= days <= 60:
                buckets['31-60'] += due_amount
            elif 61 <= days <= 90:
                buckets['61-90'] += due_amount
            elif 91 <= days <= 180:
                buckets['91-180'] += due_amount
            else:
                buckets['180+'] += due_amount

        total_due = sum(buckets.values())
        data.append({
            'member': f"{loan.member.first_name} {loan.member.last_name}",
            'member_no': loan.member.member_number,
            'loan_ref': loan.loan_reference or f"LN-{loan.id}",
            'bucket_1_30': buckets['1-30'],
            'bucket_31_60': buckets['31-60'],
            'bucket_61_90': buckets['61-90'],
            'bucket_91_180': buckets['91-180'],
            'bucket_180_plus': buckets['180+'],
            'total_arrears': total_due,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
        })
        total_arrears += total_due
        for key in bucket_totals:
            bucket_totals[key] += buckets[key]

    columns = [
        {'key': 'member_no', 'label': 'Member No', 'align': 'left'},
        {'key': 'member', 'label': 'Member', 'align': 'left'},
        {'key': 'loan_ref', 'label': 'Loan Ref', 'align': 'left'},
        {'key': 'bucket_1_30', 'label': '1-30 Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'bucket_31_60', 'label': '31-60 Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'bucket_61_90', 'label': '61-90 Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'bucket_91_180', 'label': '91-180 Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'bucket_180_plus', 'label': '180+ Days (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'total_arrears', 'label': 'Total Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'officer', 'label': 'Officer', 'align': 'left'},
    ]
    totals = {
        'bucket_1_30': bucket_totals['1-30'],
        'bucket_31_60': bucket_totals['31-60'],
        'bucket_61_90': bucket_totals['61-90'],
        'bucket_91_180': bucket_totals['91-180'],
        'bucket_180_plus': bucket_totals['180+'],
        'total_arrears': total_arrears,
    }
    kpi_cards = [
        {'icon': 'bi-clock-history', 'value': f'{len(data):,}', 'label': 'Loans with Arrears', 'type': 'warning'},
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_arrears:,.0f}', 'label': 'Total Arrears', 'type': 'danger'},
    ]
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_arrears,
        'total_paid': 'N/A',
        'outstanding': total_arrears,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    context = _get_base_context(request, {
        'report_title': 'Loan Ageing Report',
        'columns': columns,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': target_date.strftime('%Y-%m-%d'),
        'date_to': target_date.strftime('%Y-%m-%d'),
        'selected_officer': officer_id,
        'officer_name': _get_officer_name(officer_id),
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)



# ====================================================================
# INCOME STATEMENT (STATEMENT OF COMPREHENSIVE INCOME)
# ====================================================================
@login_required
def income_statement_report(request):
    """
    Statement of Comprehensive Income – shows profitability over a period.
    Columns: Account, Debits In, Credits In, Amount (net balance).
    Includes only Income and Expense accounts.
    """
    # ---- 1. Get filters ----
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')

    # Default to current month if no dates provided
    today = date.today()
    if not date_from:
        date_from = today.replace(day=1).strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')

    # ---- 2. Query General Ledger for Income and Expense accounts ----
    qs = GeneralLedger.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
        account__account_type__in=['income', 'expense']
    ).values(
        'account_id',
        'account__code',
        'account__name',
        'account__account_type'
    ).annotate(
        total_debit=Coalesce(Sum('debit'), Decimal('0.00')),
        total_credit=Coalesce(Sum('credit'), Decimal('0.00'))
    ).order_by('account__code')

    # ---- 3. Build data rows ----
    data = []
    total_income = Decimal('0.00')
    total_expenses = Decimal('0.00')
    total_debits_all = Decimal('0.00')
    total_credits_all = Decimal('0.00')

    for entry in qs:
        account_type = entry['account__account_type']
        debit = entry['total_debit']
        credit = entry['total_credit']

        # Compute amount based on account type
        if account_type == 'income':
            amount = credit - debit   # positive = income
            total_income += amount
        else:  # expense
            amount = debit - credit   # positive = expense
            total_expenses += amount

        data.append({
            'account': f"{entry['account__code']} - {entry['account__name']}",
            'debits': debit,
            'credits': credit,
            'amount': amount,
            'type': account_type,
        })
        total_debits_all += debit
        total_credits_all += credit

    # ---- 4. Compute net surplus / (loss) ----
    net_surplus = total_income - total_expenses

    # ---- 5. KPI cards ----
    kpi_cards = [
        {'icon': 'bi-currency-dollar', 'value': f'UGX {total_income:,.0f}', 'label': 'Total Income', 'type': 'success'},
        {'icon': 'bi-cash', 'value': f'UGX {total_expenses:,.0f}', 'label': 'Total Expenses', 'type': 'danger'},
        {'icon': 'bi-graph-up', 'value': f'UGX {net_surplus:,.0f}', 'label': 'Net Surplus / (Loss)', 'type': 'info' if net_surplus >= 0 else 'warning'},
    ]

    # ---- 6. Summary totals ----
    summary_totals = {
        'total_records': len(data),
        'total_amount': net_surplus,
        'total_paid': total_income,
        'outstanding': total_expenses,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    # ---- 7. Totals for table footer ----
    totals = {
        'debits': total_debits_all,
        'credits': total_credits_all,
        'amount': net_surplus,
    }

    # ---- 8. Columns ----
    all_columns = [
        {'key': 'account', 'label': 'Account', 'align': 'left'},
        {'key': 'debits', 'label': 'Debits In (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'credits', 'label': 'Credits In (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'amount', 'label': 'Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]

    # ---- 9. Column selection (optional) ----
    selected_keys = get_selected_columns(request, 'income_statement', all_columns)
    columns = [col for col in all_columns if col['key'] in selected_keys]

    # ---- 10. Build context ----
    context = _get_base_context(request, {
        'report_title': 'Statement of Comprehensive Income',
        'report_type': 'income_statement',
        'columns': columns,
        'all_columns': all_columns,
        'selected_column_keys': selected_keys,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
    })

    # ---- 11. Export ----
    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)



# ====================================================================
# STATEMENT OF FINANCIAL POSITION (BALANCE SHEET)
# ====================================================================
@login_required
def statement_of_financial_position(request):
    """
    Statement of Financial Position – shows assets, liabilities, and equity.
    Columns: Account, Opening Balance, Debits In, Credits In, Closing Balance.
    """
    # ---- 1. Get filters ----
    date_from = request.GET.get('date_from') or request.POST.get('date_from')
    date_to = request.GET.get('date_to') or request.POST.get('date_to')

    today = date.today()
    if not date_from:
        date_from = today.replace(day=1).strftime('%Y-%m-%d')
    if not date_to:
        date_to = today.strftime('%Y-%m-%d')

    # ---- 2. Query General Ledger for Asset, Liability, and Equity accounts ----
    # Get distinct accounts that have ledger entries
    account_ids = GeneralLedger.objects.filter(
        date__lte=date_to,
        account__account_type__in=['asset', 'liability', 'equity']
    ).values_list('account_id', flat=True).distinct()

    accounts = ChartOfAccount.objects.filter(
        id__in=account_ids,
        account_type__in=['asset', 'liability', 'equity']
    ).order_by('code')

    data = []
    total_assets = Decimal('0.00')
    total_liabilities = Decimal('0.00')
    total_equity = Decimal('0.00')

    for account in accounts:
        # ---- Opening balance (before date_from) ----
        opening_entry = GeneralLedger.objects.filter(
            account=account,
            date__lt=date_from
        ).order_by('-date', '-id').first()
        opening_balance = opening_entry.balance if opening_entry else Decimal('0.00')

        # ---- Debits and Credits in period ----
        period_aggregate = GeneralLedger.objects.filter(
            account=account,
            date__gte=date_from,
            date__lte=date_to
        ).aggregate(
            total_debit=Coalesce(Sum('debit'), Decimal('0.00')),
            total_credit=Coalesce(Sum('credit'), Decimal('0.00'))
        )
        debits_in = period_aggregate['total_debit']
        credits_in = period_aggregate['total_credit']

        # ---- Closing balance (latest balance at or before date_to) ----
        closing_entry = GeneralLedger.objects.filter(
            account=account,
            date__lte=date_to
        ).order_by('-date', '-id').first()
        closing_balance = closing_entry.balance if closing_entry else Decimal('0.00')

        # ---- Skip accounts with zero opening, no debits/credits, and zero closing ----
        if opening_balance == 0 and debits_in == 0 and credits_in == 0 and closing_balance == 0:
            continue

        # ---- Build row ----
        row = {
            'account': f"{account.code} - {account.name}",
            'opening_balance': opening_balance,
            'debits': debits_in,
            'credits': credits_in,
            'closing_balance': closing_balance,
            'type': account.account_type,
        }
        data.append(row)

        # Accumulate totals by account type
        if account.account_type == 'asset':
            total_assets += closing_balance
        elif account.account_type == 'liability':
            total_liabilities += closing_balance
        elif account.account_type == 'equity':
            total_equity += closing_balance

    # ---- 4. KPI cards ----
    kpi_cards = [
        {'icon': 'bi-building', 'value': f'UGX {total_assets:,.0f}', 'label': 'Total Assets', 'type': 'info'},
        {'icon': 'bi-credit-card', 'value': f'UGX {total_liabilities:,.0f}', 'label': 'Total Liabilities', 'type': 'warning'},
        {'icon': 'bi-pie-chart', 'value': f'UGX {total_equity:,.0f}', 'label': 'Total Equity', 'type': 'success'},
    ]

    # ---- 5. Summary totals ----
    summary_totals = {
        'total_records': len(data),
        'total_amount': total_assets,
        'total_paid': total_liabilities,
        'outstanding': total_equity,
        'recovery_rate': 'N/A',
        'par_30': 'N/A',
    }

    # ---- 6. Totals for table footer ----
    totals = {
        'opening_balance': sum(row['opening_balance'] for row in data),
        'debits': sum(row['debits'] for row in data),
        'credits': sum(row['credits'] for row in data),
        'closing_balance': sum(row['closing_balance'] for row in data),
    }

    # ---- 7. Columns ----
    all_columns = [
        {'key': 'account', 'label': 'Account', 'align': 'left'},
        {'key': 'opening_balance', 'label': 'Opening Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'debits', 'label': 'Debits In (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'credits', 'label': 'Credits In (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
        {'key': 'closing_balance', 'label': 'Closing Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True, 'prefix': 'UGX '},
    ]

    # ---- 8. Column selection (optional) ----
    selected_keys = get_selected_columns(request, 'balance_sheet', all_columns)
    columns = [col for col in all_columns if col['key'] in selected_keys]

    # ---- 9. Context ----
    context = _get_base_context(request, {
        'report_title': 'Statement of Financial Position',
        'report_type': 'balance_sheet',
        'columns': columns,
        'all_columns': all_columns,
        'selected_column_keys': selected_keys,
        'data': data,
        'totals': totals,
        'kpi_cards': kpi_cards,
        'summary_totals': summary_totals,
        'has_data': bool(data),
        'date_from': date_from,
        'date_to': date_to,
    })

    if _export_requested(request):
        return _export_excel(context)

    return render(request, 'finance/reports/base_report.html', context)


# finance/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from .models import Company, SystemSetting, GlobalSettings, AutoRepaymentSetting, SMSConfig
from .forms import (
    CompanyForm, SystemSettingForm, GlobalSettingsForm,
    AutoRepaymentSettingForm, SMSConfigForm
)

# finance/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from .models import Company, SystemSetting, GlobalSettings, AutoRepaymentSetting, SMSConfig
from .forms import (
    CompanyForm, SystemSettingForm, GlobalSettingsForm,
    AutoRepaymentSettingForm, SMSConfigForm
)

# finance/views.py
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from .models import Company, SystemSetting, GlobalSettings, AutoRepaymentSetting, SMSConfig
from .forms import (
    CompanyForm, SystemSettingForm, GlobalSettingsForm,
    AutoRepaymentSettingForm, SMSConfigForm
)

# finance/views.py
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from .models import Company, SystemSetting, GlobalSettings, AutoRepaymentSetting, SMSConfig
from .forms import (
    CompanyForm, SystemSettingForm, GlobalSettingsForm,
    AutoRepaymentSettingForm, SMSConfigForm
)

def can_access_settings(user):
    return user.is_superuser or user.has_perm('finance.can_access_settings')

@user_passes_test(can_access_settings, login_url='dashboard')
def settings_view(request):
    # Get or create singleton instances
    company, _ = Company.objects.get_or_create(id=1)
    system_setting, _ = SystemSetting.objects.get_or_create(id=1)
    global_settings, _ = GlobalSettings.objects.get_or_create(id=1)
    auto_repay, _ = AutoRepaymentSetting.objects.get_or_create(id=1)
    sms_config, _ = SMSConfig.objects.get_or_create(id=1)

    # Determine the active tab (default to 'company')
    tab = request.GET.get('tab', 'company')

    # ==========================================================
    # Enforce SMS tab access: superuser only
    # ==========================================================
    if tab == 'sms' and not request.user.is_superuser:
        messages.warning(
            request,
            'SMS configuration is restricted to superusers only. '
            'Please contact your system administrator.'
        )
        # Redirect to the settings page with a safe default tab
        return redirect(f"{reverse('settings')}?tab=company")

    if request.method == 'POST':
        tab = request.POST.get('tab', 'company')

        # Double-check SMS tab on POST (extra security)
        if tab == 'sms' and not request.user.is_superuser:
            messages.warning(
                request,
                'You do not have permission to modify SMS settings.'
            )
            return redirect(f"{reverse('settings')}?tab=company")

        if tab == 'company':
            form = CompanyForm(request.POST, request.FILES, instance=company)
            if form.is_valid():
                form.save()
                messages.success(request, 'Company settings updated.')
                return redirect(f"{reverse('settings')}?tab=company")
        elif tab == 'system':
            form = SystemSettingForm(request.POST, instance=system_setting)
            if form.is_valid():
                form.save()
                messages.success(request, 'System settings updated.')
                return redirect(f"{reverse('settings')}?tab=system")
        elif tab == 'global':
            form = GlobalSettingsForm(request.POST, instance=global_settings)
            if form.is_valid():
                form.save()
                messages.success(request, 'Global security settings updated.')
                return redirect(f"{reverse('settings')}?tab=global")
        elif tab == 'autorepay':
            form = AutoRepaymentSettingForm(request.POST, instance=auto_repay)
            if form.is_valid():
                form.save()
                messages.success(request, 'Auto-repayment settings updated.')
                return redirect(f"{reverse('settings')}?tab=autorepay")
        elif tab == 'sms':
            form = SMSConfigForm(request.POST, instance=sms_config)
            if form.is_valid():
                form.save()
                messages.success(request, 'SMS configuration updated.')
                return redirect(f"{reverse('settings')}?tab=sms")

    # GET forms (with proper instances)
    company_form = CompanyForm(instance=company)
    system_form = SystemSettingForm(instance=system_setting)
    global_form = GlobalSettingsForm(instance=global_settings)
    auto_form = AutoRepaymentSettingForm(instance=auto_repay)
    sms_form = SMSConfigForm(instance=sms_config)

    context = {
        'company_form': company_form,
        'system_form': system_form,
        'global_form': global_form,
        'auto_form': auto_form,
        'sms_form': sms_form,
        'active_tab': tab,
    }
    return render(request, 'finance/settings.html', context)



@login_required
def deposit_status(request, tx_id):
    """Polling endpoint for mobile money deposit status."""
    transaction = get_object_or_404(Transaction, id=tx_id, created_by=request.user)
    return JsonResponse({
        'status': transaction.status,
        'transaction_id': str(transaction.id),
        'reference': transaction.reference,
    })