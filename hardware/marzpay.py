# hardware/marzpay.py
import logging
import uuid
import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)

def _get_api_base():
    return getattr(settings, 'MARZPAY_API_BASE', None) or getattr(settings, 'MARZ_API_URL', None)

def _get_api_key():
    return getattr(settings, 'MARZPAY_API_KEY', None) or getattr(settings, 'MARZ_API_USERNAME', None)

def _get_api_secret():
    return getattr(settings, 'MARZPAY_API_SECRET', None) or getattr(settings, 'MARZ_API_PASSWORD', None)

def _get_callback_url():
    return getattr(settings, 'MARZPAY_CALLBACK_URL', None) or getattr(settings, 'MARZ_CALLBACK_URL', None)

def _prepare_metadata(metadata):
    """
    Convert metadata dict or list to MarzPay format (list of objects with a single key-value each).
    """
    if not metadata:
        return []
    if isinstance(metadata, list):
        for item in metadata:
            if not isinstance(item, dict) or len(item) != 1:
                raise ValueError("Metadata list items must be single-key dicts")
        return metadata
    if isinstance(metadata, dict):
        return [{k: v} for k, v in metadata.items()]
    raise ValueError("Metadata must be dict or list")

def initiate_collection(phone_number, amount, reference, description, metadata=None):
    """
    Initiate a collection via MarzPay using HTTP Basic Auth.
    """
    api_base = _get_api_base()
    if not api_base:
        raise ValueError("Marz API base URL not configured (MARZPAY_API_BASE or MARZ_API_URL).")

    url = f"{api_base}/collect-money"

    # Ensure amount is an integer (UGX has no decimals)
    if isinstance(amount, Decimal):
        amount = int(amount)
    elif isinstance(amount, float):
        amount = int(amount)
    elif isinstance(amount, str):
        amount = int(float(amount))

    formatted_metadata = _prepare_metadata(metadata)

    payload = {
        "amount": amount,
        "phone_number": phone_number,
        "country": "UG",
        "reference": str(reference),
        "description": description[:255],
        "callback_url": _get_callback_url() or "",
        "metadata": formatted_metadata,
    }

    api_key = _get_api_key()
    api_secret = _get_api_secret()

    if not api_key or not api_secret:
        raise ValueError(
            "MarzPay credentials not configured. "
            "Set MARZPAY_API_KEY and MARZPAY_API_SECRET (or MARZ_API_USERNAME/PASSWORD)."
        )

    auth = HTTPBasicAuth(api_key, api_secret)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    }

    logger.info(f"MarzPay collection request: reference={reference}, phone={phone_number}, amount={amount}")

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=auth,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"MarzPay collection initiated successfully: {reference}")
        return data
    except requests.exceptions.HTTPError as e:
        logger.error(f"MarzPay HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"MarzPay request error: {e}")
        raise