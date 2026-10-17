import logging
from django.utils import timezone
from django.db import models
from api.functions import send_mail
from api.models import UserDetails, AllowedCountries

logger = logging.getLogger(__name__)

def send_tier_verification_email(user, tier_type, new_status, reason=None):
    """
    Sends individual status emails for Tier 1 (KYC) and Tier 2 (KYB).
    - new_status: '1' for Approved/Verified, '2' for Declined/Rejected
    - tier_type: 'KYC' or 'KYB'
    """
    if not user or not user.user_email:
        return False

    v_type = (tier_type or 'KYC').upper().strip()
    status_str = str(new_status).strip()

    user_details = UserDetails.objects.filter(user=user).first()
    user_name = user_details.first_name if (user_details and user_details.first_name) else (user.user_email.split('@')[0] if user.user_email else "Merchant")
    user_currency = user_details.currency if (user_details and user_details.currency) else "NGN"
    timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")

    # Determine dynamic Tier 1 daily limit and currency based on user's country
    tier1_limit = 50000.00
    limit_currency = user_currency
    user_country = user_details.user_country if (user_details and user_details.user_country) else None

    country_config = None
    if user_country:
        country_config = AllowedCountries.objects.filter(
            models.Q(code__iexact=user_country) | models.Q(name__iexact=user_country)
        ).first()
    if not country_config and user_currency:
        country_config = AllowedCountries.objects.filter(currency__iexact=user_currency).first()

    if country_config:
        if country_config.tier1_daily_limit is not None:
            tier1_limit = float(country_config.tier1_daily_limit)
        if country_config.currency:
            limit_currency = country_config.currency

    symbols = {"NGN": "₦", "USD": "$", "GBP": "£", "EUR": "€", "KES": "KSh ", "GHS": "GH₵ "}
    symbol = symbols.get(limit_currency.upper(), f"{limit_currency} ")
    daily_limit_formatted = f"Up to {symbol}{tier1_limit:,.2f} / day"

    context = {
        "user_name": user_name,
        "verification_date": timestamp,
        "reason": reason or "",
        "currency": limit_currency,
        "daily_limit_formatted": daily_limit_formatted
    }

    try:
        if v_type == 'KYC':
            if status_str == '1':
                # Tier 1 Approved
                send_mail.mailSenderAsync(
                    'tier1_verified.html',
                    'Tier 1 Identity Verification Approved - Flezpay',
                    [user.user_email],
                    context=context
                )
                logger.info(f"Sent Tier 1 Approved email to {user.user_email}")
                return True
            elif status_str == '2':
                # Tier 1 Declined
                send_mail.mailSenderAsync(
                    'tier1_declined.html',
                    'Tier 1 Identity Verification Update - Action Required - Flezpay',
                    [user.user_email],
                    context=context
                )
                logger.info(f"Sent Tier 1 Declined email to {user.user_email}")
                return True
        elif v_type == 'KYB':
            if status_str == '1':
                # Tier 2 Approved
                send_mail.mailSenderAsync(
                    'tier2_verified.html',
                    'Tier 2 Business Verification Approved - Flezpay',
                    [user.user_email],
                    context=context
                )
                logger.info(f"Sent Tier 2 Approved email to {user.user_email}")
                return True
            elif status_str == '2':
                # Tier 2 Declined
                send_mail.mailSenderAsync(
                    'tier2_declined.html',
                    'Tier 2 Business Verification Update - Action Required - Flezpay',
                    [user.user_email],
                    context=context
                )
                logger.info(f"Sent Tier 2 Declined email to {user.user_email}")
                return True
    except Exception as e:
        logger.error(f"Error sending tier verification email to {user.user_email}: {e}")
        return False

    return False
