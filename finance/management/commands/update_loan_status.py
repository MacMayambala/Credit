from django.core.management.base import BaseCommand
from django.utils import timezone
from finance.models import Loan, Installment

class Command(BaseCommand):
    help = 'Automatically marks loans as "In Arrears" if they have missed installments'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        
        # 1. Find all active/approved loans that are NOT already in arrears
        loans_to_check = Loan.objects.filter(status='approved', is_active=True)
        
        arrears_count = 0
        
        for loan in loans_to_check:
            # 2. Check if there are any installments that are unpaid and overdue
            has_overdue = loan.installments.filter(
                due_date__lt=today, 
                paid=False
            ).exists()

            if has_overdue:
                loan.status = 'arrears'
                loan.save()
                arrears_count += 1
                self.stdout.write(f"Loan {loan.loan_reference} marked as ARREARS.")

        # 3. Optional: Move loans back to 'approved' if they cleared their arrears
        # but the loan is still active
        cleared_loans = Loan.objects.filter(status='arrears', is_active=True)
        for loan in cleared_loans:
            still_overdue = loan.installments.filter(due_date__lt=today, paid=False).exists()
            if not still_overdue:
                loan.status = 'approved'
                loan.save()

        self.stdout.write(self.style.SUCCESS(f'Update complete. {arrears_count} loans moved to arrears.'))