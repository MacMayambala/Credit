from django.db import models

from django.db import models

class Member(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]
    
    gender = models.CharField(
        max_length=10, 
        choices=GENDER_CHOICES, 
        default='Male'
    )
    
    member_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    
    # Date of Birth
    dob = models.DateField(blank=True, null=True, verbose_name="Date of Birth")
    
    # === NEW FIELDS ADDED ===
    nin = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        unique=True,
        verbose_name="National ID Number (NIN)"
    )
    
    card_number = models.CharField(
        max_length=30, 
        blank=True, 
        null=True,
        verbose_name="Membership Card Number"
    )
    
    # Additional Contact & Location
    alternative_phone = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        verbose_name="Alternative Phone Number"
    )
    
    physical_address = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Physical Address / Residence"
    )
    
    village = models.CharField(max_length=100, blank=True, null=True)
    parish = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)

    # KYC Fields
    photo = models.ImageField(upload_to='members/photos/', blank=True, null=True)
    id_front = models.ImageField(upload_to='members/ids/', blank=True, null=True)
    signature = models.ImageField(upload_to='members/signatures/', blank=True, null=True)
    
    date_joined = models.DateField(auto_now_add=True)
    # inside class Member in members/models.py
    def get_address(self):
        parts = [self.village, self.parish, self.district]
        return ", ".join([p for p in parts if p]) # Only joins fields that aren't empty

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.member_number} - {self.get_full_name()}"

    class Meta:
        ordering = ['member_number']