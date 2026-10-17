import time
from django.core import signing

TOKEN_SALT = 'flezpay-digital-download-salt'

def generate_digital_download_token(invoice, item) -> str:
    """
    Generate a tamper-proof cryptographically signed token for a purchased digital item.
    Tied strictly to the specific invoice and item.
    """
    payload = {
        'invoice_id': str(invoice.invoice_id),
        'item_id': str(item.item_id),
        'email': str(invoice.customer_email or ''),
        'created_at': int(time.time()),
    }
    return signing.dumps(payload, salt=TOKEN_SALT)

def validate_digital_download_token(token: str, max_age_days: int = 30, safe: bool = False) -> dict:
    """
    Validate and decode a digital download token.
    Raises signing.BadSignature or signing.SignatureExpired if invalid.
    If safe=True, returns None instead of raising exceptions.
    """
    max_age = max_age_days * 24 * 60 * 60
    if safe:
        try:
            return signing.loads(token, salt=TOKEN_SALT, max_age=max_age)
        except Exception:
            return None
    return signing.loads(token, salt=TOKEN_SALT, max_age=max_age)
