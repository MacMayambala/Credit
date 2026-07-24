from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Notification

# Import models from your other apps (adjust paths as needed)
from members.models import Member
from finance.models import Loan, SavingsAccount

# ---------- NEW MEMBER ----------
@receiver(post_save, sender=Member)
def notify_new_member(sender, instance, created, **kwargs):
    if created:
        # Notify all staff users
        staff_users = User.objects.filter(is_staff=True)
        for user in staff_users:
            Notification.objects.create(
                user=user,
                message=f"New member registered: {instance.get_full_name()} (#{instance.member_number})",
                icon="bi-person-plus",
                link=f"/members/{instance.id}/"
            )

# ---------- LOAN APPROVED ----------
@receiver(post_save, sender=Loan)
def notify_loan_approved(sender, instance, **kwargs):
    # Check if status changed to 'approved' or 'active'
    if instance.status in ['approved', 'active']:
        # Notify the loan officer
        if instance.officer:
            Notification.objects.create(
                user=instance.officer,
                message=f"Loan #{instance.loan_reference} approved for {instance.member.get_full_name()}",
                icon="bi-check-circle",
                link=f"/loans/{instance.id}/"
            )
        # Also notify the member (if they have a user account)
        if instance.member.user:
            Notification.objects.create(
                user=instance.member.user,
                message=f"Your loan #{instance.loan_reference} has been approved!",
                icon="bi-check-circle",
                link=f"/loans/{instance.id}/"
            )

# ---------- LOW BALANCE ALERT ----------
@receiver(post_save, sender=SavingsAccount)
def check_low_balance(sender, instance, **kwargs):
    # Trigger when balance drops below a threshold (e.g., 10,000)
    threshold = 10000
    if instance.balance < threshold and instance.balance >= 0:
        if instance.member.user:
            Notification.objects.create(
                user=instance.member.user,
                message=f"Low balance alert: Your savings balance is UGX {instance.balance:,.0f}",
                icon="bi-exclamation-triangle",
                link="/savings/"
            )