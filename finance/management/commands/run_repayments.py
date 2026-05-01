from django.core.management.base import BaseCommand
from django.utils import timezone
from finance.models import Loan
# Ensure process_repayment is imported from your utility or logic file
from finance.utils import process_repayment 

class Command(BaseCommand):
    help = 'Sweeps savings for loan repayments (Handles Approved and Arrears loans)'

    def handle(self, *args, **options):
        self.stdout.write("Starting automated repayment sweep...")
        
        # Include 'arrears' so that people who missed payments are still swept 
        # when they eventually deposit money into their savings.
        active_loans = Loan.objects.filter(
            status__in=['approved', 'arrears'], 
            is_active=True
        )
        
        success_count = 0
        skipped_count = 0
        
        for loan in active_loans:
            # Check for any unpaid installments due today or in the past
            has_due = loan.installments.filter(
                paid=False, 
                due_date__lte=timezone.now().date()
            ).exists()

            if has_due:
                # process_repayment handles the atomic transaction and balance logic
                success = process_repayment(loan.id)
                
                if success:
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Collected payment for Loan {loan.loan_reference}"))
                else:
                    skipped_count += 1
                    # Usually means insufficient savings balance
                    self.stdout.write(self.style.WARNING(f"Skipped Loan {loan.loan_reference}: No funds."))

        self.stdout.write(self.style.MIGRATE_SUCCESS(
            f"Sweep complete. Processed: {success_count}, Skipped: {skipped_count}"
        ))