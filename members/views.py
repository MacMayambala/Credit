from django.shortcuts import render, redirect, get_object_or_404

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Member
from finance.models import Transaction
# Note: Since you're building a SACCO system, you might eventually 
# want to auto-create a SavingsAccount here too.

from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction  # Import for data integrity
from .models import Member
from finance.models import SavingsAccount

def register_member(request):
    if request.method == "POST":
        try:
            # Use atomic transaction to ensure both Member and Account are created together
            with transaction.atomic():
                # 1. Create the Member
                new_member = Member.objects.create(
                    first_name=request.POST.get('first_name'),
                    last_name=request.POST.get('last_name'),
                    gender=request.POST.get('gender', 'Male'),
                    phone_number=request.POST.get('phone_number'),
                    alternative_phone=request.POST.get('alternative_phone'),
                    email=request.POST.get('email'),
                    dob=request.POST.get('dob') or None,
                    nin=request.POST.get('nin'),
                    card_number=request.POST.get('card_number'),
                    
                    # Location
                    physical_address=request.POST.get('physical_address'),
                    village=request.POST.get('village'),
                    parish=request.POST.get('parish'),
                    district=request.POST.get('district'),
                    
                    # KYC Media
                    photo=request.FILES.get('photo'),
                    id_front=request.FILES.get('id_front'),
                    signature=request.FILES.get('signature'),
                )

                # 2. Create the Savings Account automatically
                # We use the generated member_number to create a unique account number
                SavingsAccount.objects.create(
                    member=new_member,
                    balance=0.00,
                    account_number=f"ACC-{new_member.member_number}"
                )

            # 3. Success Feedback
            messages.success(
                request, 
                f"Registration Successful! Member ID: {new_member.member_number} | Account: ACC-{new_member.member_number}"
            )
            return redirect('dashboard')

        except Exception as e:
            # If anything fails inside the 'with transaction.atomic()', 
            # nothing is saved to the database.
            messages.error(request, f"Onboarding failed: {str(e)}")
            
    return render(request, 'members/register.html')
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Member


@login_required
def edit_member(request, member_id):
    member = get_object_or_404(Member, id=member_id)

    if request.method == "POST":
        try:
            # Update basic information
            member.member_number = request.POST.get('member_number', member.member_number)
            member.first_name = request.POST.get('first_name', member.first_name)
            member.last_name = request.POST.get('last_name', member.last_name)
            member.phone_number = request.POST.get('phone_number', member.phone_number)
            member.alternative_phone = request.POST.get('alternative_phone', member.alternative_phone)
            member.email = request.POST.get('email', member.email)
            member.dob = request.POST.get('dob') or member.dob

            # New fields
            member.nin = request.POST.get('nin', member.nin)
            member.card_number = request.POST.get('card_number', member.card_number)
            member.physical_address = request.POST.get('physical_address', member.physical_address)
            member.village = request.POST.get('village', member.village)
            member.parish = request.POST.get('parish', member.parish)
            member.district = request.POST.get('district', member.district)

            # Handle file uploads
            if 'photo' in request.FILES:
                member.photo = request.FILES['photo']
            if 'id_front' in request.FILES:
                member.id_front = request.FILES['id_front']
            if 'signature' in request.FILES:
                member.signature = request.FILES['signature']

            member.save()
            messages.success(request, f"Member {member.get_full_name()} updated successfully.")
            return redirect('member_profile', member_id=member.id)

        except Exception as e:
            messages.error(request, f"Error updating member: {str(e)}")

    context = {
        'member': member,
    }
    return render(request, 'members/edit_member.html', context)

from django.shortcuts import render, get_object_or_404
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from .models import Member

def member_profile(request, member_id):
    member = get_object_or_404(Member, id=member_id)
    
    # 1. Fetch transactions (Savings History)
    transactions = Transaction.objects.filter(member=member).order_by('-timestamp')
    
    # 2. Fetch savings account
    savings = SavingsAccount.objects.filter(member=member).first()
    
    # 3. Fetch loans
    try:
        raw_loans = member.loans.all().order_by('-start_date')
    except AttributeError:
        raw_loans = member.loan_set.all().order_by('-start_date')

    total_loan_balance = 0
    for loan in raw_loans:
        # Calculate the actual total balance from your new split fields
        current_total = (loan.principal_balance or 0) + (loan.interest_balance or 0)
        
        # Update UI display fields to match the new schema
        loan.display_total_balance = current_total
        loan.display_principal_balance = loan.principal_balance
        loan.display_interest_balance = loan.interest_balance
        
        # Update the aggregate total for the profile header
        total_loan_balance += current_total

    return render(request, 'members/profile.html', {
        'member': member,
        'savings': savings,
        'loans': raw_loans,
        'transactions': transactions, 
        'total_loan_balance': total_loan_balance,
        
    })

from django.shortcuts import render, redirect, get_object_or_404
from .forms import MemberKYCForm

def update_kyc(request, member_id):
    member = get_object_or_404(Member, id=member_id)
    
    if request.method == 'POST':
        # request.FILES is crucial for image uploads
        form = MemberKYCForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            form.save()
            return redirect('member_profile', member_id=member.id)
    else:
        form = MemberKYCForm(instance=member)
    
    return render(request, 'members/update_kyc.html', {'form': form, 'member': member})
from datetime import date
from django.shortcuts import render
from .models import Member

from datetime import date

from django.shortcuts import render
from django.db.models import Count
from datetime import date
from .models import Member

from django.shortcuts import render
from datetime import date
from .models import Member

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import date

def customer_list(request):
    """
    Registry view for MAC FinTech Member Directory with Pagination
    """
    # Fetch all members
    all_members = Member.objects.all().order_by('last_name')
    today = date.today()

    # 1. Safe Gender Distribution
    has_gender_field = 'gender' in [f.name for f in Member._meta.get_fields()]
    if has_gender_field:
        male_count = all_members.filter(gender='Male').count()
        female_count = all_members.filter(gender='Female').count()
    else:
        male_count = 0
        female_count = 0

    # 2. Pagination Logic
    items_per_page = 5
    paginator = Paginator(all_members, items_per_page)
    page_number = request.GET.get('page')
    
    try:
        members_page = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        members_page = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results.
        members_page = paginator.page(paginator.num_pages)

    # 3. Enrich Member objects on the current page with Age
    for member in members_page:
        if hasattr(member, 'dob') and member.dob:
            member.age = today.year - member.dob.year - (
                (today.month, today.day) < (member.dob.month, member.dob.day)
            )
        else:
            member.age = "N/A"

    # 4. Context dictionary
    context = {
        'members': members_page, # This is now a Page object
        'male_count': male_count,
        'female_count': female_count,
        'total_count': all_members.count(),
    }

    return render(request, 'members/customer_list.html', context)



# accounts/views.py

# accounts/views.py
import logging
import random
import pyotp

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
)
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.contrib.auth import views as auth_views
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from .models import UserProfile


logger = logging.getLogger(__name__)


# =========================================================
# LOGIN WITH 2FA
# =========================================================

# =========================================================
# LOGIN WITH 2FA
# =========================================================

# accounts/views.py

import random
import pyotp

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
)
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from .models import UserProfile


@require_http_methods(["GET", "POST"])
def user_login(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user:

            # LOGIN USER FIRST
            login(request, user)

            # Mark 2FA as NOT verified yet
            request.session["2fa_verified"] = False

            messages.success(
                request,
                "Credentials verified successfully."
            )

            return redirect("select_2fa_method")

        else:

            messages.error(
                request,
                "Invalid username or password."
            )

    return render(
        request,
        "account/login.html"
    )

# =========================================================
# SELECT 2FA METHOD
# =========================================================

# accounts/views.py

import random
import pyotp

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
)
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from .models import UserProfile


@require_http_methods(["GET", "POST"])
def user_login(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user:

            # LOGIN USER FIRST
            login(request, user)

            # Mark 2FA as NOT verified yet
            request.session["2fa_verified"] = False

            messages.success(
                request,
                "Credentials verified successfully."
            )

            return redirect("select_2fa_method")

        else:

            messages.error(
                request,
                "Invalid username or password."
            )

    return render(
        request,
        "account/login.html"
    )
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator



import random
import pyotp
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import UserProfile  # Adjust import as needed

import random
from datetime import timedelta

from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from .models import UserProfile  # Adjust the import path if needed


class Select2FAMethodView(View):
    """Step 1: User selects 2FA method (Email or Authenticator App)"""
    
    template_name = 'account/select_2fa.html'

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        context = {
            'has_authenticator': bool(profile.otp_base32 and profile.is_2fa_enabled),
            'user_email': request.user.email,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        method = request.POST.get('method')

        if method not in ['email', 'app']:
            messages.error(request, 'Invalid verification method selected.')
            return redirect('select_2fa_method')

        # Store selection in session
        request.session['selected_2fa_method'] = method
        request.session['2fa_attempt_time'] = timezone.now().isoformat()

        if method == 'email':
            # Generate secure OTP
            code = str(random.randint(100000, 999999))
            
            request.session['email_otp'] = code
            request.session['email_otp_expires'] = (timezone.now() + timedelta(minutes=10)).isoformat()

            try:
                # Render beautiful HTML email
                html_message = render_to_string('account/email_2fa_code.html', {
                    'user': request.user,
                    'otp_code': code,
                })

                plain_message = f'Verification code is: {code}\n\nThis code expires in 10 minutes.'

                send_mail(
                    subject='Verification Code',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[request.user.email],
                    html_message=html_message,   # This enables the nice HTML template
                    fail_silently=False,
                )

                messages.success(request, f'A verification code has been sent to {request.user.email}')

            except Exception as e:
                messages.error(request, 'Failed to send email. Please try again later.')
                return redirect('select_2fa_method')

            return redirect('verify_2fa')

        elif method == 'app':
            profile = getattr(request.user, 'profile', None)
            if not profile or not profile.otp_base32:
                messages.error(request, 'Authenticator app is not configured. Please set it up first.')
                return redirect('select_2fa_method')

            messages.info(request, 'Enter the 6-digit code from your authenticator app.')
            return redirect('verify_2fa')

        messages.error(request, 'Something went wrong. Please try again.')
        return redirect('select_2fa_method')
    
class Verify2FAView(View):
    """Step 2: Verify the 2FA code"""
    
    template_name = 'account/verify_2fa.html'

    def get(self, request):
        method = request.session.get('selected_2fa_method')
        if not method:
            messages.error(request, 'Session expired. Please select a method again.')
            return redirect('select_2fa_method')

        context = {
            'method': method,
            'user_email': request.user.email if method == 'email' else None,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        # Collect 6 digits
        entered_code = ''.join(
            request.POST.get(f'digit{i}', '').strip() for i in range(1, 7)
        )

        if len(entered_code) != 6 or not entered_code.isdigit():
            messages.error(request, 'Please enter a valid 6-digit code.')
            return redirect('verify_2fa')

        method = request.session.get('selected_2fa_method')
        if not method:
            messages.error(request, 'Session expired. Please start again.')
            return redirect('select_2fa_method')

        is_valid = False

        # ==================== EMAIL OTP ====================
        if method == 'email':
            saved_code = request.session.get('email_otp')
            expires_str = request.session.get('email_otp_expires')

            if not saved_code or not expires_str:
                messages.error(request, 'Code has expired. Please request a new one.')
                return redirect('select_2fa_method')

            expiry_time = timezone.datetime.fromisoformat(expires_str)
            if timezone.now() > expiry_time:
                messages.error(request, 'Code has expired. Please request a new one.')
                self._cleanup_session(request)
                return redirect('select_2fa_method')

            if entered_code == saved_code:
                is_valid = True

        # ==================== AUTHENTICATOR APP ====================
        elif method == 'app':
            try:
                profile = request.user.profile
                if profile.otp_base32:
                    totp = pyotp.TOTP(profile.otp_base32)
                    if totp.verify(entered_code, valid_window=1):  # Allow 30s window
                        is_valid = True
            except Exception:
                pass  # Fail silently, is_valid remains False

        # ==================== SUCCESS ====================
        if is_valid:
            request.session['2fa_verified'] = True
            request.session['2fa_verified_at'] = timezone.now().isoformat()

            # Cleanup
            self._cleanup_session(request)

            messages.success(request, f'Login successful! Welcome back, {request.user.get_full_name() or request.user.username}.')
            return redirect('dashboard')

        # ==================== FAILURE ====================
        messages.error(request, 'Invalid or expired verification code. Please try again.')
        return redirect('verify_2fa')

    def _cleanup_session(self, request):
        """Helper to clean up 2FA session data"""
        keys = ['email_otp', 'email_otp_expires', 'selected_2fa_method', '2fa_attempt_time']
        for key in keys:
            request.session.pop(key, None)



def custom_logout(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')


import logging
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.contrib.auth.models import User
from django.contrib import messages

logger = logging.getLogger(__name__)

class MyPasswordResetView(auth_views.PasswordResetView):
    template_name = 'account/password_reset.html'

    email_template_name = 'account/password_reset_email.html' 
    html_email_template_name = 'account/password_reset_email.html' 
    subject_template_name = 'account/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        email = form.cleaned_data.get('email')
        # Check for active user with case-insensitive email
        user_exists = User.objects.filter(email__iexact=email, is_active=True).exists()
        
        if not user_exists:
            form.add_error('email', "This email address is not registered in our system.")
            logger.warning(f"Password reset failed: {email} not found or inactive.")
            return self.form_invalid(form)
        
        logger.info(f"Password reset link sent to: {email}")
        return super().form_valid(form)

class MyPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'account/password_reset_done.html'

class MyPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'account/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

class MyPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'account/password_reset_complete.html'


# views.py
from django.contrib.auth.models import User, Group
from django.shortcuts import get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages

import logging
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.decorators import user_passes_test

logger = logging.getLogger(__name__)

# Security Helper: Only allow Staff/Superusers
class AdminOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

# 1. Staff List View
class UserListView(LoginRequiredMixin, AdminOnlyMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    ordering = ['-date_joined']

# 2. Create User View
class UserCreateView(LoginRequiredMixin, AdminOnlyMixin, CreateView):
    model = User
    template_name = 'users/user_form.html'
    fields = ['username', 'first_name', 'last_name', 'email', 'groups']
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        # Create user without a password (they will set it via email reset)
        user = form.save(commit=False)
        user.is_active = True  # Or False if you want to force email activation
        user.save()
        form.save_m2m() # Important for groups!
        
        messages.success(self.request, f"Staff account for {user.username} created successfully.")
        logger.info(f"New user created by {self.request.user}: {user.username}")
        return super().form_valid(form)

# 3. Update User View
class UserUpdateView(LoginRequiredMixin, AdminOnlyMixin, UpdateView):
    model = User
    template_name = 'users/user_form.html'
    fields = ['username', 'first_name', 'last_name', 'email', 'groups', 'is_staff']
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        messages.success(self.request, "User details updated successfully.")
        return super().form_valid(form)

# 4. Toggle Status (Block/Unblock)
@user_passes_test(lambda u: u.is_staff)
def toggle_user_status(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, "Security Alert: You cannot block your own account.")
    else:
        target_user.is_active = not target_user.is_active
        target_user.save()
        action = "activated" if target_user.is_active else "blocked"
        messages.warning(request, f"User {target_user.username} has been {action}.")
    return redirect('user_list')



import pyotp
import qrcode
import base64
from io import BytesIO
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def setup_authenticator(request):
    user_profile = request.user.profile  # Assuming UserProfile model exists
    
    # 1. Generate a secret key if the user doesn't have one yet
    if not user_profile.otp_base32:
        user_profile.otp_base32 = pyotp.random_base32()
        user_profile.save()

    # 2. Create the TOTP URI for the QR Code
    otp_uri = pyotp.totp.TOTP(user_profile.otp_base32).provisioning_uri(
        name=request.user.email, 
        issuer_name="MAC Technologies"
    )

    # 3. Generate QR Code Image
    qr = qrcode.make(otp_uri)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    if request.method == "POST":
        otp_token = request.POST.get("otp_token").replace(" ", "")
        totp = pyotp.totp.TOTP(user_profile.otp_base32)
        
        if totp.verify(otp_token):
            user_profile.two_factor_enabled = True
            user_profile.save()
            messages.success(request, "Authenticator app linked successfully!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid code. Please try again.")

    context = {
        "qr_code": qr_base64,
        "secret_key": user_profile.otp_base32,
    }
    return render(request, 'account/setup_authenticator.html', context)