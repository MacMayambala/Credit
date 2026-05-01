from django.core.management.base import BaseCommand
from django.utils import timezone
from finance.models import Loan

class Command(BaseCommand):
    help = 'Updates loans to arrears if they have missed payments'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        
        # 1. Get all active/approved loans
        active_loans = Loan.objects.filter(status__in=['approved', 'arrears'])
        
        count = 0
        for loan in active_loans:
            # Check if there's any repayment installment due before today that isn't fully paid
            # Note: This assumes you have a Repayment model linked to Loan
            overdue_installments = loan.repayments.filter(
                due_date__lt=today, 
                is_paid=False
            ).exists()

            if overdue_installments:
                if loan.status != 'arrears':
                    loan.status = 'arrears'
                    loan.save()
                    count += 1
            else:
                # If they were in arrears but have now paid up, move back to approved
                if loan.status == 'arrears':
                    loan.status = 'approved'
                    loan.save()

        self.stdout.write(self.style.SUCCESS(f'Updated {count} loans to arrears status.'))