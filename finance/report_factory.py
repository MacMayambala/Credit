# finance/report_factory.py
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db.models import Q, Sum, F, Count, Value, DecimalField
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Loan, Installment, Member, SavingsAccount

User = get_user_model()

class ReportFactory:
    """Build report context for any loan report type."""

    @staticmethod
    def get_report_type_config(report_type):
        """Return configuration for a given report type."""
        configs = {
            'outstanding': {
                'title': 'Outstanding Loans Report',
                'columns': [
                    {'key': 'no', 'label': 'No', 'align': 'left'},
                    {'key': 'date', 'label': 'Date', 'align': 'center', 'type': 'date'},
                    {'key': 'name', 'label': 'Name', 'align': 'left'},
                    {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
                    {'key': 'phone', 'label': 'Phone', 'align': 'left'},
                    {'key': 'physical_address', 'label': 'Physical Address', 'align': 'left'},
                    {'key': 'town', 'label': 'Town', 'align': 'left'},
                    {'key': 'product', 'label': 'Product', 'align': 'left'},
                    {'key': 'amount', 'label': 'Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'principal_prepaid', 'label': 'Principal Prepaid (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'classification', 'label': 'Classification', 'align': 'center'},
                    {'key': 'cleared_at', 'label': 'Cleared At', 'align': 'center', 'type': 'date'},
                    {'key': 'accrued_interest', 'label': 'Accrued Interest (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'admin_fees_due', 'label': 'Admin Fees Due (UGX)', 'type': 'currency', 'align': 'right'},
                    {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right'},
                    {'key': 'branch', 'label': 'Branch', 'align': 'left'},
                    {'key': 'loan_status', 'label': 'Loan Status', 'align': 'center', 'type': 'status'},
                    {'key': 'batch_number', 'label': 'Batch Number', 'align': 'left'},
                    {'key': 'created_at', 'label': 'Created At', 'align': 'center', 'type': 'date'},
                    {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                ],
                'kpi_fields': ['total_principal_balance', 'total_interest_balance', 'total_due'],
                'summary_fields': {
                    'total_records': 'count',
                    'total_amount': 'total_principal_balance',
                    'outstanding': 'total_principal_balance + total_interest_balance',
                }
            },
            'arrears': {
                'title': 'Loans In Arrears Report',
                'columns': [
                    {'key': 'no', 'label': 'No', 'align': 'left'},
                    {'key': 'name', 'label': 'Name', 'align': 'left'},
                    {'key': 'phone', 'label': 'Phone', 'align': 'left'},
                    {'key': 'loan_no', 'label': 'Loan No', 'align': 'left'},
                    {'key': 'principal_arrears', 'label': 'Principal Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'interest_arrears', 'label': 'Interest Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'arrears_days', 'label': 'Arrears Days', 'align': 'center'},
                    {'key': 'disbursement_date', 'label': 'Disbursement Date', 'align': 'center', 'type': 'date'},
                    {'key': 'disbursed_amount', 'label': 'Disbursed Amount (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'last_repayment_date', 'label': 'Last Repayment Date', 'align': 'center', 'type': 'date'},
                    {'key': 'principal_due', 'label': 'Principal Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'interest_due', 'label': 'Interest Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'penalty_due', 'label': 'Penalty Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'total_due', 'label': 'Total Due (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'total_outstanding', 'label': 'Total Outstanding (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'msacco_no', 'label': 'Msacco No', 'align': 'left'},
                    {'key': 'physical_address', 'label': 'Physical Address', 'align': 'left'},
                    {'key': 'classification', 'label': 'Classification', 'align': 'center'},
                    {'key': 'batch_no', 'label': 'Batch No', 'align': 'left'},
                    {'key': 'arrears_rate', 'label': 'Arrears rate (%)', 'align': 'right'},
                    {'key': 'admin_fees_due', 'label': 'Admin Fees Due (UGX)', 'type': 'currency', 'align': 'right'},
                    {'key': 'admin_fees_balance', 'label': 'Admin Fees Balance (UGX)', 'type': 'currency', 'align': 'right'},
                    {'key': 'unpaid_arrears', 'label': 'Unpaid Arrears (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'transfer_status', 'label': 'Transfer Status', 'align': 'left'},
                    {'key': 'status', 'label': 'Status', 'align': 'center', 'type': 'status'},
                    {'key': 'officer', 'label': 'Officer', 'align': 'left'},
                    {'key': 'town', 'label': 'Town', 'align': 'left'},
                    {'key': 'product', 'label': 'Product', 'align': 'left'},
                    {'key': 'principal_paid', 'label': 'Principal Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'interest_paid', 'label': 'Interest Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'penalty_paid', 'label': 'Penalty Paid (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'prepaid_principal', 'label': 'Prepaid Principal (UGX)', 'type': 'currency', 'align': 'right'},
                    {'key': 'principal_balance', 'label': 'Principal Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'interest_balance', 'label': 'Interest Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'penalty_balance', 'label': 'Penalty Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                    {'key': 'guarantors', 'label': 'Guarantors', 'align': 'left'},
                    {'key': 'total_accrual_balance', 'label': 'Total Accrual Balance (UGX)', 'type': 'currency', 'align': 'right', 'total': True},
                ],
                'kpi_fields': ['total_arrears', 'total_due', 'arrears_rate'],
                'summary_fields': {
                    'total_records': 'count',
                    'total_amount': 'total_outstanding',
                    'outstanding': 'total_due',
                }
            },
            # Add other report types (portfolio_status, due_loans, etc.) here
            # Each with its own columns and KPIs
        }
        return configs.get(report_type)

    @staticmethod
    def build_context(request, report_type):
        """Build the full context for a given report type."""
        config = ReportFactory.get_report_type_config(report_type)
        if not config:
            raise ValueError(f"Unknown report type: {report_type}")

        # ---- 1. Extract filters ----
        date_from = request.POST.get('date_from') or request.GET.get('date_from')
        date_to = request.POST.get('date_to') or request.GET.get('date_to')
        officer_id = request.POST.get('officer') or request.GET.get('officer')
        status_filter = request.POST.get('status') or request.GET.get('status')
        search_query = request.POST.get('search_query') or request.GET.get('search_query')

        # ---- 2. Build base queryset (only active loans) ----
        qs = Loan.objects.filter(
            is_active=True,
            status__in=['approved', 'active', 'arrears']
        ).select_related('member', 'officer').prefetch_related('installments', 'repayments')

        # Apply filters
        if date_from:
            qs = qs.filter(disbursed_date__gte=date_from)
        if date_to:
            qs = qs.filter(disbursed_date__lte=date_to)
        if officer_id:
            qs = qs.filter(officer_id=officer_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search_query:
            qs = qs.filter(
                Q(member__first_name__icontains=search_query) |
                Q(member__last_name__icontains=search_query) |
                Q(member__member_number__icontains=search_query) |
                Q(loan_reference__icontains=search_query)
            )

        # ---- 3. Build data rows ----
        data = []
        totals = {}
        today = date.today()

        for loan in qs:
            row = ReportFactory._build_row(loan, report_type, today)
            data.append(row)

            # Accumulate totals for columns that have 'total': True
            for col in config['columns']:
                if col.get('total'):
                    key = col['key']
                    totals[key] = totals.get(key, Decimal('0')) + row.get(key, Decimal('0'))

        # ---- 4. Compute KPIs ----
        kpi_cards = []
        # Example KPIs – you can customise per report type
        kpi_cards.append({
            'label': 'Total Loans',
            'value': len(data),
            'icon': 'bi-file-earmark-text',
            'type': 'info'
        })
        if 'total_principal_balance' in totals:
            kpi_cards.append({
                'label': 'Total Principal',
                'value': f"UGX {totals['total_principal_balance']:,.0f}",
                'icon': 'bi-cash',
                'type': 'success'
            })
        if 'total_interest_balance' in totals:
            kpi_cards.append({
                'label': 'Total Interest',
                'value': f"UGX {totals['total_interest_balance']:,.0f}",
                'icon': 'bi-percent',
                'type': 'warning'
            })
        if 'total_due' in totals:
            kpi_cards.append({
                'label': 'Total Due',
                'value': f"UGX {totals['total_due']:,.0f}",
                'icon': 'bi-exclamation-triangle',
                'type': 'danger'
            })

        # ---- 5. Summary totals ----
        summary_totals = {
            'total_records': len(data),
            'total_amount': totals.get('total_balance', totals.get('total_outstanding', 0)),
            'total_paid': 'N/A',
            'outstanding': totals.get('total_due', totals.get('total_balance', 0)),
            'recovery_rate': 'N/A',
            'par_30': 'N/A',
        }

        # ---- 6. Aging summary (if needed) ----
        aging_summary = []  # You can compute if report_type requires it

        # ---- 7. Officer list ----
        officer_list = User.objects.filter(is_active=True).order_by('first_name', 'last_name')

        # ---- 8. Company info ----
        from core.models import Company  # adjust import
        company = Company.objects.first() or {'name': 'Your Company'}

        # ---- 9. Final context ----
        context = {
            'report_title': config['title'],
            'columns': config['columns'],
            'data': data,
            'totals': totals,
            'kpi_cards': kpi_cards,
            'summary_totals': summary_totals,
            'aging_summary': aging_summary,
            'has_data': bool(data),
            'company': company,
            'date_from': date_from,
            'date_to': date_to,
            'selected_officer': officer_id,
            'selected_status': status_filter,
            'officer_list': officer_list,
            'officer_name': dict(officer_list.values_list('id', 'username')).get(int(officer_id) if officer_id else None),
            'generated_date': timezone.now().strftime('%d %b %Y %H:%M'),
            'generated_by': request.user.get_full_name() if request.user.is_authenticated else 'System',
        }
        return context

    @staticmethod
    def _build_row(loan, report_type, today):
        """Build a single data row for the given loan and report type."""
        # This is where you put the specific logic for each report type
        # You can move the existing row-building code from your views here.
        # For brevity, I'll show a simplified example.
        # In practice, you'd have a large if/elif chain or a dict lookup.

        member = loan.member
        row = {
            'no': member.member_number,
            'name': f"{member.first_name} {member.last_name}",
            'loan_no': loan.loan_reference or f"LN-{loan.id}",
            'phone': member.phone_number,
            'physical_address': ', '.join(filter(None, [member.village, member.parish, member.district])) or 'N/A',
            'town': member.district or 'N/A',
            'product': loan.get_product_type_display(),
            'amount': loan.principal_amount,
            'disbursed_amount': loan.principal_amount,
            'disbursement_date': loan.disbursed_date or loan.start_date,
            'officer': loan.officer.get_full_name() if loan.officer else 'System',
            'status': loan.get_status_display(),
            'loan_status': loan.get_status_display(),
            'created_at': loan.created_at.date(),
            'classification': 'Performing',  # will be computed below
        }

        # ---- Compute installment aggregates ----
        # Total balances
        principal_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('principal_portion') - F('principal_paid')), Decimal('0'))
        )['total']
        interest_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('interest_portion') - F('interest_paid')), Decimal('0'))
        )['total']
        penalty_bal = loan.installments.aggregate(
            total=Coalesce(Sum(F('penalty_amount') - F('penalty_paid')), Decimal('0'))
        )['total']
        total_balance = principal_bal + interest_bal + penalty_bal

        row['principal_balance'] = principal_bal
        row['interest_balance'] = interest_bal
        row['penalty_balance'] = penalty_bal
        row['total_balance'] = total_balance

        # Overdue amounts
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

        row['principal_due'] = principal_due
        row['interest_due'] = interest_due
        row['penalty_due'] = penalty_due
        row['total_due'] = total_due

        # Paid amounts
        principal_paid = loan.installments.aggregate(
            total=Coalesce(Sum('principal_paid'), Decimal('0'))
        )['total']
        interest_paid = loan.installments.aggregate(
            total=Coalesce(Sum('interest_paid'), Decimal('0'))
        )['total']
        penalty_paid = loan.installments.aggregate(
            total=Coalesce(Sum('penalty_paid'), Decimal('0'))
        )['total']

        row['principal_paid'] = principal_paid
        row['interest_paid'] = interest_paid
        row['penalty_paid'] = penalty_paid
        row['principal_prepaid'] = principal_paid

        # Arrears-specific fields (for arrears report)
        row['principal_arrears'] = principal_due
        row['interest_arrears'] = interest_due
        row['penalty_due'] = penalty_due
        row['total_arrears'] = total_due
        row['unpaid_arrears'] = total_due
        row['total_outstanding'] = total_balance
        row['accrued_interest'] = interest_bal
        row['total_accrual_balance'] = interest_bal
        row['admin_fees_due'] = Decimal('0')
        row['admin_fees_balance'] = Decimal('0')
        row['batch_no'] = ''
        row['transfer_status'] = ''
        row['guarantors'] = ', '.join(filter(None, [loan.guarantor_1_name, loan.guarantor_2_name])) or 'None'

        # Classification
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
            row['arrears_days'] = days
        else:
            classification = 'Performing'
            row['arrears_days'] = 0

        row['classification'] = classification
        row['arrears_rate'] = (total_due / total_balance * 100) if total_balance > 0 else 0

        # Last repayment
        last_repayment = loan.repayments.order_by('-date_paid').first()
        row['last_repayment_date'] = last_repayment.date_paid.date() if last_repayment else None
        row['cleared_at'] = loan.updated_at.date() if loan.status == 'closed' else None

        # Branch (using district as proxy)
        row['branch'] = member.district or 'Main'

        return row