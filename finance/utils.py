import requests
import logging
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.contrib import messages

from decouple import config
from .models import Installment, SMSConfig, SMSTransaction

logger = logging.getLogger(__name__)

# Load from .env
SPEEDA_API_ID = config('SPEEDA_API_ID')
SPEEDA_API_PASSWORD = config('SPEEDA_API_PASSWORD')
SPEEDA_SENDER_ID = config('SPEEDA_SENDER_ID', default='MACFinTech')
SMS_COST_PER_MESSAGE = Decimal(config('SMS_COST_PER_MESSAGE', default=100))


def send_arrears_reminder_sms(request, loan):
    """
    Send arrears reminder SMS to a member using SpeedaMobile API.
    Costs SMS_COST_PER_MESSAGE per SMS.
    """
    member = loan.member
    school = getattr(request.user, 'school', None)

    if not school:
        return {"status": "F", "remarks": "School configuration missing."}

    # Get SMS Wallet
    try:
        sms_conf = SMSConfig.objects.get(school=school)
    except SMSConfig.DoesNotExist:
        return {"status": "F", "remarks": "SMS service not configured for this school."}

    if sms_conf.balance < SMS_COST_PER_MESSAGE:
        return {"status": "F", "remarks": "Insufficient SMS credits. Please top up."}

    # Format phone number (SpeedaMobile expects 256xxxxxxxxx)
    raw_phone = str(member.phone_number).strip().replace(" ", "").replace("+", "")
    if raw_phone.startswith('0'):
        formatted_phone = '256' + raw_phone[1:]
    else:
        formatted_phone = raw_phone

    # Professional SMS Message
    message = (
        f"Dear {member.first_name}, your loan repayment of UGX {loan.balance:,.0f} "
        f"is overdue. Please make payment to avoid penalties. "
        f"Thank you, MAC FinTech SACCO."
    )

    # Call SpeedaMobile API
    url = "http://apidocs.speedamobile.com/api/SendSMS"

    payload = {
        "api_id": SPEEDA_API_ID,
        "api_password": SPEEDA_API_PASSWORD,
        "sms_type": "P",
        "encoding": "T",
        "sender_id": SPEEDA_SENDER_ID,
        "phonenumber": formatted_phone,
        "textmessage": message[:160],
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("status") == "S":
            with transaction.atomic():
                # Lock the row to prevent race conditions
                wallet = SMSConfig.objects.select_for_update().get(id=sms_conf.id)
                wallet.balance -= SMS_COST_PER_MESSAGE
                wallet.save()

                SMSTransaction.objects.create(
                    school=school,
                    amount=SMS_COST_PER_MESSAGE,
                    transaction_type='REMINDER',
                    description=f"Arrears reminder sent to {member.first_name} {member.last_name}",
                    performed_by=request.user
                )

            logger.info(f"SMS sent successfully to {formatted_phone}")
            return {"status": "S", "remarks": "Reminder sent successfully."}

        else:
            return {"status": "F", "remarks": result.get('remarks', 'Unknown API error')}

    except requests.RequestException as e:
        logger.error(f"SMS API error for {formatted_phone}: {str(e)}")
        return {"status": "F", "remarks": "Failed to connect to SMS gateway."}
    except Exception as e:
        logger.error(f"Unexpected error sending SMS: {str(e)}")
        return {"status": "F", "remarks": "Internal error occurred."}


def send_bulk_arrears_reminders(request):
    """
    Send arrears reminders to all members with outstanding loans.
    """
    from .models import Loan   # Adjust import as needed

    sent = 0
    failed = 0

    loans_with_arrears = Loan.objects.filter(
        status='approved',
        balance__gt=0
    ).select_related('member')

    for loan in loans_with_arrears:
        result = send_arrears_reminder_sms(request, loan)
        if result['status'] == 'S':
            sent += 1
        else:
            failed += 1
            # Stop early if out of credits
            if "Insufficient SMS credits" in result['remarks']:
                break

    return sent, failed




def generate_schedule(loan):
    """Generates installments with explicit Principal and Interest portions"""
    # Flat Rate: Fixed principal and fixed interest every month
    monthly_principal = loan.principal_amount / loan.period_months
    monthly_interest = loan.interest_balance / loan.period_months
    
    with transaction.atomic():
        for i in range(loan.period_months):
            Installment.objects.create(
                loan=loan,
                principal_portion=monthly_principal,
                interest_portion=monthly_interest,
                due_date=loan.start_date + relativedelta(months=i + 1)
            )

def generate_loan_ref(length=10):
    """Generates a unique uppercase alphanumeric loan reference."""
    chars = string.ascii_uppercase + string.digits
    return f"LN-{''.join(random.choices(chars, k=length))}"

import string
import random

def generate_transaction_ref(prefix, length=8):
    """
    Generates a reference like: DEP-A1B2C3D4
    """
    chars = string.ascii_uppercase + string.digits
    code = ''.join(random.choices(chars, k=length))
    return f"{prefix}-{code}"


