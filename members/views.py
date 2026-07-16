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

from django.shortcuts import render, redirect
from django.db import transaction
from django.contrib import messages
from .models import Member  # Adjust import based on your app structure
from finance.models import SavingsAccount  # Adjust import based on your app structure

def register_member(request):
    if request.method == "POST":
        try:
            # Use atomic transaction to ensure both Member and Account are created together
            with transaction.atomic():
                # 1. Create the Member (Generates KALxxxxx via its save() method)
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
                # No account_number needed here anymore because it maps directly to member_number
                SavingsAccount.objects.create(
                    member=new_member,
                    balance=0.00
                )

            # 3. Success Feedback
            messages.success(
                request, 
                f"Registration Successful! Member ID / Account No: {new_member.member_number}"
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

    # ============================================
    # RECEIPT DATA FROM SESSION
    # ============================================
    receipt_data = None
    show_receipt = False
    
    # Check if receipt data exists in session
    if 'deposit_receipt' in request.session:
        receipt_data = request.session['deposit_receipt'].get('data')
        show_receipt = request.session['deposit_receipt'].get('show', False)
        
        # Clear the receipt from session after displaying
        if show_receipt:
            request.session['deposit_receipt']['show'] = False
            request.session.modified = True
        
        # If receipt data is still in session but show is False, clean it up
        if not show_receipt and receipt_data:
            del request.session['deposit_receipt']
            request.session.modified = True

    # ============================================
    # CONTEXT
    # ============================================
    context = {
        'member': member,
        'savings': savings,
        'loans': raw_loans,
        'transactions': transactions,
        'total_loan_balance': total_loan_balance,
        'receipt_data': receipt_data,
        'show_receipt': show_receipt,
    }
    
    return render(request, 'members/profile.html', context)

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

from django.db.models import Q
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from datetime import date
from django.shortcuts import render

from django.db.models import Q
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.shortcuts import render
from datetime import date
from .models import Member

import json
from datetime import date

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from .models import Member

from datetime import date

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.template import Context, Template

from .models import Member

from datetime import date

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from .models import Member

from django.template.loader import render_to_string
from django.http import JsonResponse
from django.shortcuts import render, reverse
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from datetime import date
from .models import Member

from datetime import date

def _annotate_age(members_page):
    today = date.today()
    for member in members_page:
        if getattr(member, 'dob', None):
            # Calculate age correctly
            member.age = (
                today.year - member.dob.year
                - ((today.month, today.day) < (member.dob.month, member.dob.day))
            )
        else:
            member.age = 'N/A'

from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse

import json
from django.views.decorators.csrf import csrf_exempt # Optional: only if you handle CSRF via headers

from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from .models import Member

def _annotate_age(members_page):
    today = timezone.now().date()
    for member in members_page:
        if member.dob:
            member.age = today.year - member.dob.year - ((today.month, today.day) < (member.dob.month, member.dob.day))
        else:
            member.age = None

def customer_list(request):
    search_query = request.GET.get('q', request.POST.get('q', '')).strip()
    page_number = request.GET.get('page', request.POST.get('page', 1))

    qs = Member.objects.all().order_by('last_name')

    if search_query:
        qs = qs.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(member_number__icontains=search_query)
        )

    # Annotate each member with the count of active loans (to determine status)
    qs = qs.annotate(active_loan_count=Count('loans', filter=Q(loans__is_active=True)))

    paginator = Paginator(qs, 5)
    members_page = paginator.get_page(page_number)
    _annotate_age(members_page)

    # Set profile_url and status for each member
    for m in members_page:
        m.profile_url = reverse('member_profile', args=[m.id])
        m.status = 'active' if m.active_loan_count > 0 else 'inactive'

    # Count total active members (those with at least one active loan)
    active_count = Member.objects.filter(loans__is_active=True).distinct().count()
    new_this_month = Member.objects.filter(date_joined__month=timezone.now().month).count()

    context = {
        'members': members_page,
        'search_query': search_query,
        'total_count': paginator.count,
        'active_count': active_count,
        'new_this_month': new_this_month,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'rows_html': render_to_string('members/partials/member_rows.html', context),
            'pagination_html': render_to_string('members/partials/pagination.html', context),
            'entry_count_html': render_to_string('members/partials/entry_count.html', context),
            'total_count': paginator.count,
        })

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


from finance.models import GlobalSettings

@require_http_methods(["GET", "POST"])
def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            
            # Fetch the setting from the database
            config = GlobalSettings.objects.first()
            # Default to True if for some reason the config doesn't exist yet
            is_2fa_required = config.enable_global_2fa if config else True

            if is_2fa_required:
                request.session["2fa_verified"] = False
                messages.success(request, "Credentials verified. Complete 2FA.")
                return redirect("select_2fa_method")
            else:
                # SKIP 2FA
                request.session["2fa_verified"] = True
                messages.success(request, f"Welcome, {user.username}!")
                return redirect("dashboard")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "account/login.html")
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
def get_masked_email(email):
    try:
        user_part, domain_part = email.split('@')
        return f"{user_part[:4]}****@***{domain_part[-8:]}"
    except:
        return email

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

                masked = get_masked_email(request.user.email)
                messages.success(request, f'A verification code has been sent to {masked}')

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

from .forms import StaffForm # Import your new form

# 2. Create User View
class UserCreateView(LoginRequiredMixin, AdminOnlyMixin, CreateView):
    model = User
    form_class = StaffForm  # <--- Changed from fields to form_class
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        # The form.save() now handles user creation AND profile module assignment
        user = form.save()
        messages.success(self.request, f"Staff account for {user.username} created successfully.")
        return super().form_valid(form)

# 3. Update User View
class UserUpdateView(LoginRequiredMixin, AdminOnlyMixin, UpdateView):
    model = User
    form_class = StaffForm  # <--- Changed from fields to form_class
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        form.save() # This ensures modules are updated on the profile
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


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import transaction

User = get_user_model()

@staff_member_required
def manage_user_rights(request):
    """Dashboard to view users and update their assigned security groups/roles."""
    if request.method == "POST":
        user_id = request.POST.get('user_id')
        # Get the list of group IDs selected for this user (defaults to empty list if none checked)
        selected_group_ids = request.POST.getlist('groups')
        
        user_to_update = get_object_or_404(User, id=user_id)
        
        try:
            with transaction.atomic():
                # Clear existing groups and set the new ones
                user_to_update.groups.set(selected_group_ids)
                messages.success(request, f"Permissions updated successfully for {user_to_update.get_full_name() or user_to_update.username}.")
        except Exception as e:
            messages.error(request, f"Failed to update permissions: {str(e)}")
            
        return redirect('manage_user_rights')

    # GET request: Fetch all active users and all available system groups
    users = User.objects.filter(is_active=True).prefetch_related('groups').order_by('username')
    groups = Group.objects.all().order_by('name')
    
    context = {
        'users': users,
        'groups': groups,
    }
    return render(request, 'users/manage_rights.html', context)



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import transaction

@staff_member_required
def manage_group_permissions(request, group_id=None):
    """Dashboard to assign specific model permissions/rights to Groups."""
    
    # Fetch all groups so the user can switch between them
    groups = Group.objects.all().order_by('name')
    selected_group = None
    
    if group_id:
        selected_group = get_object_or_404(Group, id=group_id)

    if request.method == "POST":
        target_group_id = request.POST.get('group_id')
        selected_group = get_object_or_404(Group, id=target_group_id)
        
        # Get list of permission IDs checked in the form
        permission_ids = request.POST.getlist('permissions')
        
        try:
            with transaction.atomic():
                # Sync the group's permissions directly
                selected_group.permissions.set(permission_ids)
                messages.success(request, f"Successfully updated rights for the '{selected_group.name}' group!")
        except Exception as e:
            messages.error(request, f"Error updating group rights: {str(e)}")
            
        return redirect('manage_group_permissions_detail', group_id=selected_group.id)

    # Fetch permissions only for your custom functional apps to keep the UI clean
    target_apps = ['finance', 'members']
    available_permissions = Permission.objects.filter(
        content_type__app_label__in=target_apps
    ).select_related('content_type').order_by('content_type__app_label', 'content_type__model', 'codename')

    # Structure permissions by app/model dynamically for beautiful template grouping
    grouped_permissions = {}
    for perm in available_permissions:
        app_label = perm.content_type.app_label.upper()
        model_name = perm.content_type.model.title()
        group_key = f"{app_label} — {model_name}"
        
        if group_key not in grouped_permissions:
            grouped_permissions[group_key] = []
        grouped_permissions[group_key].append(perm)

    context = {
        'groups': groups,
        'selected_group': selected_group,
        'grouped_permissions': grouped_permissions,
        'current_group_permissions': selected_group.permissions.all() if selected_group else []
    }
    return render(request, 'users/manage_group_permissions.html', context)



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse
from .utils import generate_migration_template_http
from .services import DataMigrationService

class TemplateDownloadView(APIView):
    """API Endpoint to retrieve the formatted Excel template."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs) -> HttpResponse:
        return generate_migration_template_http()


class MigrationPreviewView(APIView):
    """
    Parses the upload data structures for a frontend validation preview
    without committing data to the database.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs) -> Response:
        file_obj = request.data.get('file')
        if not file_obj:
            return Response({"error": "No file submitted under payload key 'file'."}, status=status.HTTP_400_BAD_REQUEST)
        
        preview_data = DataMigrationService.preview_file(file_obj)
        if preview_data["errors"]:
            return Response(preview_data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            
        return Response(preview_data, status=status.HTTP_200_OK)


class MigrationImportExecutionView(APIView):
    """Executes the row-by-row production import process."""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs) -> Response:
        file_obj = request.data.get('file')
        if not file_obj:
            return Response({"error": "No file submitted under payload key 'file'."}, status=status.HTTP_400_BAD_REQUEST)

        # Run row-by-row transactional data migration
        import_report = DataMigrationService.execute_import(file_obj, request.user)
        
        if not import_report["success"]:
            return Response(import_report, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(import_report, status=status.HTTP_201_CREATED)



from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

class MigrationDashboardView(LoginRequiredMixin, TemplateView):
    """Renders the HTML workspace interface for data migration operations."""
    template_name = "members/migration_dashboard.html"