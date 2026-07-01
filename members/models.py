from django.db import models
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver



class Member(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    member_number = models.CharField(max_length=20, unique=True, editable=False)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male')
    dob = models.DateField(blank=True, null=True)

    nin = models.CharField(max_length=20, blank=True, null=True, unique=True)
    card_number = models.CharField(max_length=30, blank=True, null=True)

    phone_number = models.CharField(max_length=15)
    alternative_phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    physical_address = models.TextField(blank=True, null=True)
    village = models.CharField(max_length=100, blank=True, null=True)
    parish = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)

    photo = models.ImageField(upload_to='members/photos/', blank=True, null=True)
    id_front = models.ImageField(upload_to='members/ids/', blank=True, null=True)
    signature = models.ImageField(upload_to='members/signatures/', blank=True, null=True)

    date_joined = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-date_joined', 'member_number']

    def save(self, *args, **kwargs):
        if not self.member_number:

            # ✅ safe import (still ok here)
            from finance.models import SystemSetting

            setting = SystemSetting.objects.first()
            prefix = setting.member_prefix if setting else "KAL"

            last_member = Member.objects.filter(
                member_number__startswith=prefix
            ).order_by('id').last()

            if not last_member:
                new_number = 1
            else:
                try:
                    last_number_str = last_member.member_number.replace(prefix, '')
                    new_number = int(last_number_str) + 1
                except:
                    new_number = Member.objects.filter(
                        member_number__startswith=prefix
                    ).count() + 1

            self.member_number = f"{prefix}{str(new_number).zfill(5)}"

        super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_address(self):
        return ", ".join(filter(None, [self.village, self.parish, self.district]))

    def __str__(self):
        return f"{self.member_number} - {self.get_full_name()}"


    
    
from django.db import models
from django.contrib.auth.models import User

class Module(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # Optional: help_text to describe what the module does
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    otp_base32 = models.CharField(max_length=32, blank=True, null=True) # For Google Authenticator
    is_2fa_enabled = models.BooleanField(default=False)
    allowed_modules = models.ManyToManyField(Module, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

# These signals ensure a profile is automatically created whenever a User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        UserProfile.objects.get_or_create(user=instance)



