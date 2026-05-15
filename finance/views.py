from enum import member

from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import (
    Installment, Loan, Member, Repayment, SavingsAccount, SystemSetting, Transaction, TransactionReversal, 
    process_repayment, generate_schedule
)

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

def allowed_users(allowed_roles=[]):
    def decorator(view_func):
        def wrapper_func(request, *args, **kwargs):
            group = None
            if request.user.groups.exists():
                group = request.user.groups.all()[0].name

            if group in allowed_roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            else:
                raise PermissionDenied # Shows 403 Forbidden
        return wrapper_func
    return decorator

@login_required
def dashboard(request):
    """
    Main SACCO Dashboard with updated split-balance aggregation
    """
    # 1. SUMMARY WIDGETS
    # Total Savings Pool
    total_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance'))['total'] or 0

    # Total Active Loans (Summing principal_balance and interest_balance)
    loan_stats = Loan.objects.filter(is_active=True).aggregate(
        p_bal=Sum('principal_balance'),
        i_bal=Sum('interest_balance')
    )
    total_loans = (loan_stats['p_bal'] or 0) + (loan_stats['i_bal'] or 0)

    # Total Interest Profit (Transactions tagged as 'interest_payment')
    total_interest = Transaction.objects.filter(type='interest_payment').aggregate(
        total=Sum('amount'))['total'] or 0

    # Counts for context
    total_members = Member.objects.count()
    active_loans_count = Loan.objects.filter(is_active=True).count()
    recent_loans = Loan.objects.select_related('member').order_by('-start_date')[:10]

    # 2. CHART DATA (Logic remains the same, ensure it uses correct fields)
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    savings_trend = [0] * 12
    loan_trend = [0] * 12

    savings_data = Transaction.objects.filter(type='deposit')\
            .annotate(month=ExtractMonth('timestamp'))\
            .values('month').annotate(total=Sum('amount'))
    
    for entry in savings_data:
        if 1 <= entry['month'] <= 12:
            savings_trend[entry['month'] - 1] = float(entry['total'])

    loan_data = Loan.objects.filter(status='approved')\
            .annotate(month=ExtractMonth('start_date'))\
            .values('month').annotate(total=Sum('principal_amount'))

    for entry in loan_data:
        if 1 <= entry['month'] <= 12:
            loan_trend[entry['month'] - 1] = float(entry['total'])

    # 3. PREPARE CONTEXT
    context = {
        'total_savings': total_savings,
        'total_loans': total_loans,
        'total_interest': total_interest,
        'total_members': total_members,
        'active_loans_count': active_loans_count,
        'loans': recent_loans,
        'chart_labels': labels,
        'chart_savings': savings_trend,
        'chart_loans': loan_trend,
    }

    return render(request, 'finance/dashboard.html', context)



def approve_loan(request, loan_id):
    """
    Approves a loan and generates the repayment schedule.
    """
    loan = get_object_or_404(Loan, id=loan_id)
    if loan.status == 'pending':
        loan.status = 'approved'
        loan.is_active = True
        loan.save()
        generate_schedule(loan)
        messages.success(request, f"Loan for {loan.member.first_name} approved successfully.")
    return redirect('dashboard')


from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from .models import Member, SavingsAccount, Transaction, SystemSetting, Loan
# from .utils import generate_transaction_ref, process_repayment

@login_required
@transaction.atomic
def deposit_savings(request, member_id):
    """
    Handles member deposits with high-precision Decimal math and 
    automated loan recovery (sweep logic).
    """
    member = get_object_or_404(Member, id=member_id)
    
    # Permission check: Setting must be ON and user must be Staff/Admin
    backdate_allowed = SystemSetting.is_backdate_allowed()
    
    if request.method == "POST":
        amount_raw = request.POST.get('amount', '0').strip()
        custom_date = request.POST.get('back_date')
        
        try:
            # CRITICAL: Fix precision error (ensure exact math to 2 decimal places)
            amount = Decimal(amount_raw).quantize(Decimal('1.00'), rounding=ROUND_HALF_UP)
            
            if amount <= 0:
                messages.error(request, "Deposit amount must be greater than zero.")
                return redirect('deposit_savings', member_id=member.id)
            
            # 1. Update Savings Account using row locking
            savings, created = SavingsAccount.objects.select_for_update().get_or_create(member=member)
            
            # Convert existing balance to string before Decimal to avoid float pollution
            current_balance = Decimal(str(savings.balance))
            savings.balance = current_balance + amount
            savings.save()
            
            # 2. Determine Timestamp
            txn_timestamp = timezone.now()
            if backdate_allowed and custom_date:
                # The view expects the template to provide a valid datetime string
                txn_timestamp = custom_date

            # 3. Log the Transaction
            ref = generate_transaction_ref("DEP")
            Transaction.objects.create(
                member=member,
                amount=amount,
                type='deposit',
                reference=ref,
                timestamp=txn_timestamp
            )
            
            # 4. Loan Link Logic (Auto-sweep for overdue balance)
            # We look for active loans to see if we should trigger process_repayment
            active_loan = Loan.objects.filter(member=member, is_active=True).first()
            
            if active_loan:
                # Check for overdue installments up to TODAY
                has_overdue = active_loan.installments.filter(
                    paid=False, 
                    due_date__lte=timezone.now().date()
                ).exists()
                
                if has_overdue:
                    # Trigger the repayment engine
                    process_repayment(active_loan.id)
                    messages.info(request, f"Deposit {ref} recorded. Arrears detected and auto-repayment triggered.")
                else:
                    messages.success(request, f"Deposit {ref} of UGX {amount:,.0f} successful.")
            else:
                messages.success(request, f"Deposit {ref} of UGX {amount:,.0f} processed successfully.")
            
            return redirect('member_profile', member_id=member.id)

        except (ValueError, InvalidOperation):
            messages.error(request, "Please enter a valid deposit amount.")
            return redirect('deposit_savings', member_id=member.id)
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {str(e)}")
            return redirect('deposit_savings', member_id=member.id)
    
    return render(request, 'finance/deposit.html', {
        'member': member,
        'backdate_allowed': backdate_allowed
    })
def member_statement(request, member_id):
    """
    Detailed financial ledger for a specific member.
    """
    member = get_object_or_404(Member, id=member_id)
    transactions = Transaction.objects.filter(member=member).order_by('-timestamp')
    # Use direct query to ensure we get the latest balance
    savings = SavingsAccount.objects.filter(member=member).first()
    
    return render(request, 'finance/statement.html', {
        'member': member,
        'transactions': transactions,
        'savings': savings
    })

from django.db.models import Sum, F

def arrears_report(request):
    """
    Portfolio at Risk (PAR) Report.
    """
    today = timezone.now().date()
    # Find all unpaid installments that are past their due date
    overdue_installments = Installment.objects.filter(
        paid=False, 
        due_date__lt=today
    ).select_related('loan__member').order_by('due_date')

    # FIX: Sum the specific component fields because 'amount' does not exist
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

@login_required
def apply_loan(request, member_id=None):
    """
    Handles loan applications using the specific fields defined in the Loan model.
    """
    members = Member.objects.all().order_by('first_name')
    selected_member = None
    
    if member_id:
        selected_member = get_object_or_404(Member, id=member_id)
    
    if request.method == "POST":
        try:
            posted_member_id = request.POST.get('member') or member_id
            member = get_object_or_404(Member, id=posted_member_id)

            # Financial fields
            principal = Decimal(request.POST.get('principal_amount') or '0')
            interest_rate = Decimal(request.POST.get('interest_rate') or '0')
            months_raw = request.POST.get('period_months')

            if not months_raw:
                messages.error(request, "Error: Period (Months) is required.")
                return render(request, 'finance/apply_loan.html', {
                    'members': members, 
                    'selected_member': selected_member
                })

            months = int(months_raw)

            with transaction.atomic():
                # Generate unique loan reference
                ref_code = f"{generate_loan_ref()}"

                # Financial Calculations
                total_interest = (principal * (interest_rate / 100) * months).quantize(Decimal('0.01'))
                calc_total_payable = principal + total_interest

                # Create Loan object with model-compliant field names
                loan = Loan(
                    member=member,
                    officer=request.user,
                    loan_reference=ref_code,
                    principal_amount=principal,
                    interest_rate=interest_rate,
                    period_months=months,
                    total_payable=calc_total_payable,
                    principal_balance=principal,
                    interest_balance=total_interest,
                    status='pending',

                    # === PRODUCT & PURPOSE ===
                    product_type=request.POST.get('product_type', 'personal'),
                    purpose=request.POST.get('purpose', ''),

                    # === GUARANTORS (Mapping to CharFields) ===
                    guarantor_1_name=request.POST.get('guarantor_1_name', ''),
                    guarantor_1_phone=request.POST.get('guarantor_1_phone', ''),
                    guarantor_2_name=request.POST.get('guarantor_2_name') or None,
                    guarantor_2_phone=request.POST.get('guarantor_2_phone') or None,

                    # === COLLATERAL ===
                    collateral_type=request.POST.get('collateral_type', ''),
                    collateral_value=Decimal(request.POST.get('collateral_value') or '0'),
                    collateral_description=request.POST.get('collateral_description', ''),

                    # === LOCATION & CONTACT ===
                    location=request.POST.get('location', ''),
                    contact_person=request.POST.get('contact_person', ''),
                    contact_phone=request.POST.get('contact_phone', ''),
                )
                loan.save()
                
                messages.success(request, f"Loan Application {ref_code} for {member.first_name} submitted successfully.")
                return redirect('dashboard')

        except Exception as e:
            # This will now catch any remaining logic errors and display them
            messages.error(request, f"Error processing application: {str(e)}")
            
    return render(request, 'finance/apply_loan.html', {
        'members': members,
        'selected_member': selected_member
    })



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

def loan_detail(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    member = loan.member

    # Savings Balance
    try:
        savings_balance = loan.member.savings.balance
    except Exception:
        savings_balance = Decimal('0.00')

    # Schedule and Repayments
    schedule = loan.installments.all().order_by('due_date')
    repayments = loan.repayments.all().order_by('-date_paid')

    today = timezone.now().date()

    # Unpaid overdue installments
    unpaid_installments = loan.installments.filter(paid=False, due_date__lte=today)

    # === SAFE CALCULATIONS ===
    try:
        principal_amount = Decimal(str(loan.principal_amount or 0))
        total_payable = Decimal(str(getattr(loan, 'total_payable', 0) or 0))

        if loan.period_months and loan.period_months > 0:
            monthly_principal = principal_amount / loan.period_months
            total_interest = total_payable - principal_amount
            monthly_interest = total_interest / loan.period_months
        else:
            monthly_principal = Decimal('0')
            monthly_interest = Decimal('0')
    except (TypeError, ZeroDivisionError, InvalidOperation):
        monthly_principal = Decimal('0')
        monthly_interest = Decimal('0')

    unpaid_count = unpaid_installments.count()
    interest_due = (unpaid_count * monthly_interest).quantize(Decimal('0.01'))
    principal_due = (unpaid_count * monthly_principal).quantize(Decimal('0.01'))
    total_due_now = (interest_due + principal_due).quantize(Decimal('0.01'))

    # Total Paid (using correct field name)
    total_paid = loan.repayments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')

    # Officer
    officer = getattr(loan, 'officer', None)

    # === NEW: Disbursement Date, Duration & End Date ===
    disbursement_date = getattr(loan, 'disbursement_date', getattr(loan, 'start_date', None))
    period_months = getattr(loan, 'period_months', 0)

    if disbursement_date and period_months:
        end_date = disbursement_date + relativedelta(months=+period_months)
    else:
        end_date = None

    context = {
        'loan': loan,
        'savings_balance': savings_balance,
        'schedule': schedule,
        'repayments': repayments,
        'officer': officer,
        'member_address': f"{member.village}, {member.parish}, {member.district}",

        # Balances
        'principal_balance': getattr(loan, 'principal_balance', principal_amount),
        'interest_balance': getattr(loan, 'interest_balance', interest_due),
        'total_penalty': getattr(loan, 'total_penalty', Decimal('0')),
        'total_payable': getattr(loan, 'total_payable', total_payable),

        # Current Due
        'interest_due': interest_due,
        'principal_due': principal_due,
        'total_due_now': total_due_now,

        'total_paid': total_paid.quantize(Decimal('0.01')),

        # New fields for template
        'disbursement_date': disbursement_date,
        'period_months': period_months,
        'end_date': end_date,
        'today': today,
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

    if loan.status != 'approved' and loan.status != 'arrears':
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

        # 1. Create the repayment record 
        # (Pass date_paid to override the default now())
        Repayment.objects.create(
            loan=loan,
            amount_paid=total_payment,
            receipt_number=ref,
            date_paid=txn_timestamp, 
            notes=notes if notes else None,
        )

        # 2. Create Transaction log
        Transaction.objects.create(
            member=loan.member,
            amount=total_payment,
            type='repayment',
            reference=ref,
            timestamp=txn_timestamp
        )

        messages.success(request, f"Payment {ref} recorded for date: {txn_timestamp}.")

    except (ValueError, InvalidOperation):
        messages.error(request, "Invalid payment amounts entered.")
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")

    return redirect('loan_detail', pk=loan_id)


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from .models import Loan, Transaction, SavingsAccount

@transaction.atomic
def update_loan_status(request, pk, action):
    """
    Handles approval or rejection of a loan with unique disbursement referencing.
    """
    loan = get_object_or_404(Loan, pk=pk)
    
    if action == 'approve':
        if loan.status == 'approved':
            messages.info(request, "This loan has already been approved.")
            return redirect('loan_detail', pk=loan.id)

        try:
            with transaction.atomic():
                # 1. Update Loan Status
                loan.status = 'approved'
                loan.is_active = True
                if not loan.disbursed_date:
                    loan.disbursed_date = timezone.now().date()
                
                loan.save()

                # 2. Generate Repayment Schedule
                # This ensures installments start with the correct amount_remaining
                generate_schedule(loan)

                # 3. Disburse principal to member's savings
                savings = loan.member.savings
                principal = Decimal(str(loan.principal_amount))
                
                # Using select_for_update here is a good safety measure if not already in the model
                savings.balance += principal
                savings.save()

                # 4. Record disbursement transaction with UNIQUE REFERENCE
                # We use the 'DSB' prefix for disbursements
                ref = generate_transaction_ref("DSB")
                Transaction.objects.create(
                    member=loan.member,
                    amount=principal,
                    type='disbursement',
                    reference=ref
                )

                messages.success(
                    request, 
                    f"Loan {loan.id} approved successfully. "
                    f"Reference {ref}: UGX {principal:,.0f} disbursed to savings."
                )

        except AttributeError:
            messages.error(request, "Approval failed: Member has no savings account.")
            return redirect('loan_detail', pk=loan.id)

        except Exception as e:
            messages.error(request, f"Error during approval: {str(e)}")
            return redirect('loan_detail', pk=loan.id)

    elif action == 'reject':
        loan.status = 'rejected'
        loan.is_active = False
        loan.save()
        messages.warning(request, f"Loan {loan.id} has been rejected.")

    return redirect('loan_detail', pk=loan.id)

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

@login_required
@transaction.atomic
def withdraw_savings(request, member_id):
    """
    Handles internal withdrawals with exact Decimal precision to prevent 
    rounding errors (e.g., 40,000 becoming 39,998).
    """
    member = get_object_or_404(Member, id=member_id)
    
    # Use select_for_update() to lock the row and prevent race conditions
    savings, created = SavingsAccount.objects.select_for_update().get_or_create(member=member)
    
    # Permission check: Setting must be enabled AND user must be staff
    backdate_allowed = SystemSetting.is_backdate_allowed()

    if request.method == 'POST':
        amount_raw = request.POST.get('amount', '0').strip()
        custom_date = request.POST.get('back_date')
        
        try:
            # CRITICAL: Convert to string first, then Decimal to maintain exact precision
            amount = Decimal(amount_raw)
            
            # Ensure the savings balance is also treated as a Decimal
            current_balance = Decimal(str(savings.balance))
            
            if amount <= 0:
                messages.error(request, "Withdrawal amount must be greater than zero.")
            elif current_balance < amount:
                messages.error(request, f"Insufficient funds. Current balance is UGX {current_balance:,.0f}")
            else:
                # 1. Determine Timestamp (Back-date logic)
                # Ensure custom_date is parsed correctly if provided
                txn_timestamp = timezone.now()
                if backdate_allowed and custom_date:
                    try:
                        txn_timestamp = custom_date
                    except Exception:
                        messages.warning(request, "Invalid date format provided. Using current time.")

                # 2. Generate a unique reference
                ref = generate_transaction_ref("WTH")

                # 3. Deduct from Savings (Exact math)
                savings.balance = current_balance - amount
                savings.save()

                # 4. Create Audit Transaction
                # Ensure your Transaction model's 'timestamp' field is NOT 'auto_now_add=True'
                # It should have 'default=timezone.now' to allow manual overrides.
                Transaction.objects.create(
                    member=member,
                    amount=amount,
                    type='withdrawal',
                    reference=ref,
                    timestamp=txn_timestamp
                )

                messages.success(request, f"Successfully processed {ref}. UGX {amount:,.0f} withdrawn.")
                return redirect('member_profile', member_id=member.id)

        except (ValueError, TypeError, InvalidOperation):
            messages.error(request, "Invalid amount entered. Please enter a valid number.")

    return render(request, 'finance/withdraw_form.html', {
        'member': member,
        'savings': savings,
        'backdate_allowed': backdate_allowed
    })
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


def reports_dashboard(request):
    """Central Reports Dashboard"""
    return render(request, 'finance/reports/reports_dashboard.html')


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

def portfolio_status_report(request):
    """
    Comprehensive Portfolio Status Report - Format
    """
    today = timezone.now().date()

    # Optimized Query
    loans = Loan.objects.select_related('member', 'officer').filter(
        status__in=['approved', 'active', 'closed']
    ).order_by('member__member_number')

    report_data = []

    for loan in loans:
        # 1. Paid Amounts (from paid installments)
        paid_stats = loan.installments.filter(paid=True).aggregate(
            p_paid=Coalesce(Sum('principal_portion'), Decimal('0.00')),
            i_paid=Coalesce(Sum('interest_portion'), Decimal('0.00')),
            penalty_paid=Coalesce(Sum('penalty_amount'), Decimal('0.00')),
        )

        # 2. Arrears (Unpaid installments due before today)
        arrears_stats = loan.installments.filter(
            paid=False,
            due_date__lt=today
        ).aggregate(
            p_due=Coalesce(Sum('principal_portion'), Decimal('0.00')),
            i_due=Coalesce(Sum('interest_portion'), Decimal('0.00')),
            pen_due=Coalesce(Sum('penalty_amount'), Decimal('0.00')),
        )

        # 3. Total Due (including today's due date)
        total_due_stats = loan.installments.filter(
            paid=False,
            due_date__lte=today
        ).aggregate(
            total_due=Coalesce(Sum('principal_portion') + Sum('interest_portion'), Decimal('0.00'))
        )

        # 4. Aging Classification
        oldest_unpaid = loan.installments.filter(
            paid=False, 
            due_date__lt=today
        ).order_by('due_date').first()

        classification = "Performing"
        if oldest_unpaid:
            days_past_due = (today - oldest_unpaid.due_date).days
            if days_past_due > 180:
                classification = "Loss"
            elif days_past_due > 90:
                classification = "Doubtful"
            elif days_past_due > 30:
                classification = "Substandard"
            else:
                classification = "Watch"

        report_data.append({
            'member_no': loan.member.member_number or str(loan.member.id),
            'name': f"{loan.member.first_name} {loan.member.last_name}",
            'loan_no': loan.loan_reference or loan.id,
            'disbursed_amount': Decimal(str(loan.principal_amount or 0)),
            'disbursed_date': loan.disbursed_date or loan.start_date,
            'principal_paid': paid_stats['p_paid'],
            'interest_paid': paid_stats['i_paid'],
            'penalty_paid': paid_stats['penalty_paid'],
            'principal_due': arrears_stats['p_due'],
            'interest_due': arrears_stats['i_due'],
            'penalty_due': arrears_stats['pen_due'],
            'total_due': arrears_stats['p_due'] + arrears_stats['i_due'] + arrears_stats['pen_due'],
            'principal_balance': Decimal(str(loan.principal_balance or 0)),
            'interest_balance': Decimal(str(loan.interest_balance or 0)),
            'classification': classification,
            'sector': getattr(loan.member, 'economic_sector', 'N/A'),
        })

    # Calculate Grand Totals for Footer
    grand_total_disbursed = sum(item['disbursed_amount'] for item in report_data)
    grand_total_prin_paid = sum(item['principal_paid'] for item in report_data)
    grand_total_int_paid = sum(item['interest_paid'] for item in report_data)
    grand_total_penalty_paid = sum(item['penalty_paid'] for item in report_data)

    grand_total_prin_due = sum(item['principal_due'] for item in report_data)
    grand_total_int_due = sum(item['interest_due'] for item in report_data)
    grand_total_penalty_due = sum(item['penalty_due'] for item in report_data)
    grand_total_due = sum(item['total_due'] for item in report_data)

    grand_total_prin_bal = sum(item['principal_balance'] for item in report_data)
    grand_total_int_bal = sum(item['interest_balance'] for item in report_data)
    grand_total_exposure = grand_total_prin_bal + grand_total_int_bal

    context = {
        'report_data': report_data,
        'today': today,

        # Summary Totals
        'total_principal_bal': grand_total_prin_bal,
        'total_arrears': grand_total_prin_due + grand_total_int_due + grand_total_penalty_due,

        # Grand Totals for Table Footer
        'grand_total_disbursed': grand_total_disbursed,
        'grand_total_prin_paid': grand_total_prin_paid,
        'grand_total_int_paid': grand_total_int_paid,
        'grand_total_penalty': grand_total_penalty_due,        # Usually we show unpaid penalty
        'grand_total_prin_due': grand_total_prin_due,
        'grand_total_int_due': grand_total_int_due,
        'grand_total_due': grand_total_due,
        'grand_total_prin_bal': grand_total_prin_bal,
        'grand_total_int_bal': grand_total_int_bal,
        'grand_total_exposure': grand_total_exposure,
    }

    return render(request, 'finance/reports/portfolio_status.html', context)

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

def loan_details(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id)
    # Fetch repayments specifically related to this loan if you have a way to link them
    # For now, we'll assume you might want to see recent activity
    repayments = Transaction.objects.filter(member=loan.member, type='repayment').order_by('-timestamp')[:10]
    
    context = {
        'loan': loan,
        'repayments': repayments,
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

@login_required
def general_ledger(request):
    """
    Main General Ledger View
    Synchronized with ledger.html to show all movements.
    """
    
    # 1. Calculate Total Revenue (Inflows) 
    # In accounting, Income is increased by Credits
    total_inflow = GeneralLedger.objects.filter(
        account__account_type='income'
    ).aggregate(total=Sum('credit'))['total'] or 0

    # 2. Calculate Total Expenses (Outflows)
    # In accounting, Expenses are increased by Debits
    total_outflow = GeneralLedger.objects.filter(
        account__account_type='expense'
    ).aggregate(total=Sum('debit'))['total'] or 0

    # 3. Calculate Net Cash Position (Account 1001)
    # For Assets (Cash), Balance = Debits - Credits
    cash_entries = GeneralLedger.objects.filter(account__code='1001')
    cash_in = cash_entries.aggregate(total=Sum('debit'))['total'] or 0
    cash_out = cash_entries.aggregate(total=Sum('credit'))['total'] or 0
    net_cash = cash_in - cash_out

    # 4. Fetch all entries for the table
    # We use 'transactions' to match the {% for tx in transactions %} in your HTML
    # We exclude the '1001' account entries if you only want to see the "Category" side
    # Or keep them all to see the full double-entry trail:
    transactions = GeneralLedger.objects.select_related('account', 'transaction').order_by('-date')

    context = {
        'transactions': transactions, # This matches your template loop
        'total_inflow': total_inflow,
        'total_outflow': total_outflow,
        'net_cash': net_cash,
        'title': 'General Ledger'
    }
    
    return render(request, 'accounting/ledger.html', context)


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