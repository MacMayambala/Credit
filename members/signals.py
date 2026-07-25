from django.db.models.signals import post_save
from django.dispatch import receiver
from members.models import Member
from finance.models import SavingsAccount

@receiver(post_save, sender=Member)
def create_member_savings(sender, instance, created, **kwargs):
    if created:
        SavingsAccount.objects.get_or_create(member=instance)