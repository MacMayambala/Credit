from django.shortcuts import render, redirect, get_object_or_404

from finance.models import SavingsAccount, Transaction
from .models import Member

def register_member(request):
    if request.method == "POST":
        # Professional practice: Capture all fields from POST and FILES
        Member.objects.create(
            member_number=request.POST.get('member_number'),
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name'),
            phone_number=request.POST.get('phone_number'),
            email=request.POST.get('email'),
            photo=request.FILES.get('photo'),
            id_front=request.FILES.get('id_front'),
            signature=request.FILES.get('signature'),
        )
        return redirect('dashboard')
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
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages

class CustomLoginView(LoginView):
    template_name = 'account/login.html'

    def form_valid(self, form):
        messages.success(self.request, "Welcome back! Login successful.")
        return super().form_valid(form)

    def form_invalid(self, form):
        # This triggers if the username/password is wrong OR if the form is missing a field
        messages.error(self.request, "Invalid username or password.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Adding 'title' so it shows up in your <title> tag if your template uses it
        context['title'] = "Sign In | MAC Tech"
        return context

def custom_logout(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')