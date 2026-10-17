from .templatetags.currency_tags import currency_symbol
from .models import SiteSettings, Backer
from api.functions.misc import get_owner_from_user

def site_settings(request):
    """
    Context processor to inject SiteSettings and Backers globally.
    """
    return {
        'site': SiteSettings.load(),
        'backers': Backer.objects.filter(is_active=True).order_by('-created_at')
    }

def user_currency(request):
    """
    Context processor to inject the authenticated user's currency and symbol
    into all templates globally.
    """
    context = {
        'user_currency': 'NGN',
        'user_currency_symbol': '₦'
    }
    
    if request.user.is_authenticated:
        # Get details
        owner = get_owner_from_user(request.user)
        details = owner.details.first()
        if details and details.currency:
            context['user_currency'] = details.currency.upper()
            context['user_currency_symbol'] = currency_symbol(context['user_currency'])
            
        from api.growth_views import get_usd_to_local_exchange_rate
        context['usd_exchange_rate'] = get_usd_to_local_exchange_rate(context['user_currency'])
            
    return context


def user_growth_context(request):
    """
    Context processor to inject the user's online store and contact status
    into all templates globally.
    
    Variables injected:
    - user_has_online_store: True if the user has an active online store (store_setup=True).
    - user_has_phone: True if the user has a phone number set up.
    - user_has_contact: True if the user has a phone or WhatsApp contact set up.
    """
    context = {
        'user_has_online_store': False,
        'user_has_phone': False,
        'user_has_contact': False,
    }

    if request.user.is_authenticated:
        try:
            owner = get_owner_from_user(request.user)
            # Phone number lives on the UserSecure model (we check the original user or owner? Typically we check owner)
            has_phone = bool(getattr(owner, 'user_phone', None)) or bool(getattr(request.user, 'user_phone', None))

            # Online store and contact details live on BusinessDetails of the owner
            biz = owner.business_details.first()
            if biz:
                context['user_has_online_store'] = bool(biz.store_setup)
                has_whatsapp = bool(getattr(biz, 'store_whatsapp_number', None))
                has_pickup_phone = bool(getattr(biz, 'store_pickup_phone', None))
                
                # If they have any kind of phone on the store or user level
                any_phone = has_phone or has_whatsapp or has_pickup_phone
                
                context['user_has_phone'] = any_phone
                context['user_has_contact'] = any_phone or has_whatsapp
            else:
                context['user_has_phone'] = has_phone
                context['user_has_contact'] = has_phone
        except Exception:
            pass

    return context
