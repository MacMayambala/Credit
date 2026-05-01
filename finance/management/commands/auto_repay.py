from django.core.management.base import BaseCommand
from django.utils import timezone
from finance.models import Loan
# Make sure this import matches where you put the process_repayment function
from finance.views import process_repayment 

class Command(BaseCommand):  # <--- MUST be named 'Command' with a capital C
    help = 'Sweeps savings for loan repayments (Partial collection enabled)'

    def handle(self, *args, **options):
        self.stdout.write("Starting automated repayment sweep...")
        
        active_loans = Loan.objects.filter(status='approved', is_active=True)
        
        for loan in active_loans:
            # Check for due or overdue installments
            has_due = loan.installments.filter(
                paid=False, 
                due_date__lte=timezone.now().date()
            ).exists()

            if has_due:
                success = process_repayment(loan.id)
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f"Collected payment for Loan #{loan.id}"))
                else:
                    self.stdout.write(f"Skipped Loan #{loan.id}: No funds available.")