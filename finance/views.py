from enum import member

from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import (
    Installment, Loan, Member, Repayment, SavingsAccount, Transaction, 
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


@transaction.atomic
def deposit_savings(request, member_id):
    member = get_object_or_404(Member, id=member_id)
    
    if request.method == "POST":
        amount_raw = request.POST.get('amount')
        
        if not amount_raw or Decimal(amount_raw) <= 0:
            messages.error(request, "Invalid deposit amount.")
            return redirect('deposit_savings', member_id=member.id)
            
        amount = Decimal(amount_raw)
        
        # 1. Update Savings
        # Using select_for_update() to prevent race conditions during the balance update
        savings, created = SavingsAccount.objects.select_for_update().get_or_create(member=member)
        savings.balance = Decimal(str(savings.balance)) + amount
        savings.save()
        
        # 2. Generate Unique Reference and Log Transaction
        # We use the 'DEP' prefix for all savings deposits
        ref = generate_transaction_ref("DEP")
        Transaction.objects.create(
            member=member,
            amount=amount,
            type='deposit',
            reference=ref
        )
        
        # 3. Loan Link Logic
        # Check if the member has an active loan that needs recovery
        active_loan = Loan.objects.filter(member=member, is_active=True).first()
        if active_loan:
            # Check for overdue installments up to today
            has_overdue = active_loan.installments.filter(
                paid=False, 
                due_date__lte=timezone.now().date()
            ).exists()
            
            if has_overdue:
                # The process_repayment function should also be updated 
                # to use generate_transaction_ref("AUTO")
                process_repayment(active_loan.id)
                messages.info(request, f"Deposit {ref} received. Auto-repayment processed for overdue balance.")
            else:
                messages.success(request, f"Deposit {ref} of UGX {amount:,.0f} processed successfully.")
        else:
            messages.success(request, f"Deposit {ref} of UGX {amount:,.0f} processed successfully.")
        
        return redirect('member_profile', member_id=member.id)
    
    return render(request, 'finance/deposit.html', {'member': member})


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

    # Use select_for_update to lock the loan row during the payment process
    loan = get_object_or_404(Loan.objects.select_for_update(), id=loan_id)

    if loan.status != 'approved' or not getattr(loan, 'is_active', True):
        messages.error(request, "Repayments are only accepted for active and approved loans.")
        return redirect('loan_detail', pk=loan_id)

    # Get current balance safely using both principal and interest balances
    try:
        current_balance = Decimal(str(loan.principal_balance + loan.interest_balance))
    except (TypeError, InvalidOperation):
        current_balance = Decimal('0')

    if current_balance <= 0:
        messages.warning(request, "This loan has already been fully paid.")
        return redirect('loan_detail', pk=loan_id)

    # Get form data
    principal_raw = request.POST.get('principal', '0')
    interest_raw = request.POST.get('interest', '0')
    penalty_raw = request.POST.get('penalty', '0')
    notes = request.POST.get('notes', '').strip()

    try:
        principal = Decimal(str(principal_raw).strip() or '0')
        interest = Decimal(str(interest_raw).strip() or '0')
        penalty = Decimal(str(penalty_raw).strip() or '0')

        total_payment = principal + interest + penalty

        if total_payment <= 0:
            messages.error(request, "Total payment amount must be greater than zero.")
            return redirect('loan_detail', pk=loan_id)

        if total_payment > current_balance:
            messages.error(request, 
                f"Total payment (UGX {total_payment:,.0f}) cannot exceed the current balance (UGX {current_balance:,.0f}).")
            return redirect('loan_detail', pk=loan_id)

        # 1. Generate a Unique Payment Reference
        # This replaces the need for random integers in the model save() method
        ref = generate_transaction_ref("PAY")

        # 2. Create the repayment record
        # The Repayment.save() method will handle the 'waterfall' logic to installments
        Repayment.objects.create(
            loan=loan,
            amount_paid=total_payment,
            receipt_number=ref,
            notes=notes if notes else None,
        )

        # 3. Create a Transaction log for the audit trail
        Transaction.objects.create(
            member=loan.member,
            amount=total_payment,
            type='repayment',
            reference=ref
        )

        messages.success(request, 
            f"Payment {ref} of UGX {total_payment:,.0f} successfully recorded for {loan.loan_reference}.")

    except (ValueError, InvalidOperation):
        messages.error(request, "Please enter valid numbers for the payment amounts.")
    except Exception as e:
        messages.error(request, f"System Error: {str(e)}")

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

@transaction.atomic
def withdraw_savings(request, member_id):
    """
    Handles internal withdrawals from a member's savings account with unique referencing.
    """
    member = get_object_or_404(Member, id=member_id)
    # Ensure the member has a savings account
    savings, created = SavingsAccount.objects.select_for_update().get_or_create(member=member)

    if request.method == 'POST':
        amount_str = request.POST.get('amount')
        
        try:
            amount = Decimal(amount_str)
            
            if amount <= 0:
                messages.error(request, "Withdrawal amount must be greater than zero.")
            elif savings.balance < amount:
                messages.error(request, f"Insufficient funds. Current balance is UGX {savings.balance:,.0f}")
            else:
                # 1. Generate a unique reference for this specific withdrawal
                # We use the 'WTH' prefix for withdrawals
                ref = generate_transaction_ref("WTH")

                # 2. Deduct from Savings
                savings.balance -= amount
                savings.save()

                # 3. Create Audit Transaction with the unique reference
                Transaction.objects.create(
                    member=member,
                    amount=amount,
                    type='withdrawal',
                    reference=ref
                )

                messages.success(request, f"Successfully processed {ref}. UGX {amount:,.0f} withdrawn from {member.first_name}'s account.")
                return redirect('member_profile', member_id=member.id)

        except (ValueError, TypeError, Decimal.InvalidOperation):
            messages.error(request, "Invalid amount entered. Please enter a valid number.")

    return render(request, 'finance/withdraw_form.html', {
        'member': member,
        'savings': savings
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
from .models import Loan, Installment, User # Ensure User is imported if using for officers

from decimal import Decimal
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import Coalesce

def portfolio_status_report(request):
    """
    Comprehensive Portfolio Status Report - ZIROBWE SACCO Format
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