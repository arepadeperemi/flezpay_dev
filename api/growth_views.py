import os
import io
import uuid
from decimal import Decimal
import logging
import json
import re

logger = logging.getLogger(__name__)

from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from django.core.cache import cache
import requests
from api.models import GrowthPromotion, UserItems, UserSecure, SiteSettings, UserTransactions, UserDetails, SystemErrorLog
from api.user_data.data_views import calculate_total_balance
from google import genai
from flezpay.storage import GrowthMediaStorage
# pyrefly: ignore [missing-import]
from google.genai import types
from api.services.facebook_ads import FacebookAdsService

def get_usd_to_local_exchange_rate(user_currency):
    """
    Fetches real-time live currency exchange rate (1 USD -> target currency)
    using live foreign exchange rate APIs with caching and secondary provider fallback.
    """
    if not user_currency or user_currency.upper() == 'USD':
        return 1.0
        
    curr = user_currency.upper().strip()
    cache_key = f'exchange_rate_USD_{curr}'
    cached_rate = cache.get(cache_key)
    if cached_rate is not None and cached_rate > 0:
        return float(cached_rate)

    # 1. Primary Live Exchange Rate API (ExchangeRate-API v6)
    try:
        res = requests.get('https://open.er-api.com/v6/latest/USD', timeout=4)
        if res.status_code == 200:
            rates = res.json().get('rates', {})
            val = rates.get(curr)
            if val:
                rate = float(val)
                cache.set(cache_key, rate, 43200) # Cache for 12 hours
                return rate
    except Exception as e:
        logger.warning(f"Primary live exchange rate API error: {e}")

    # 2. Secondary Live Exchange Rate API Provider (fallback)
    try:
        res = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=4)
        if res.status_code == 200:
            rates = res.json().get('rates', {})
            val = rates.get(curr)
            if val:
                rate = float(val)
                cache.set(cache_key, rate, 43200) # Cache for 12 hours
                return rate
    except Exception as e:
        logger.warning(f"Secondary live exchange rate API error: {e}")

    # 3. Emergency market approximate fallbacks only if both live APIs are completely unreachable
    fallbacks = {
        'NGN': 1324.0,
        'EUR': 0.86,
        'GBP': 0.74,
        'CAD': 1.38,
        'KES': 129.0,
        'GHS': 15.0,
        'ZAR': 18.0,
        'INR': 83.0,
        'AUD': 1.50
    }
    rate = fallbacks.get(curr, 1.0)
    # Cache temporarily (5 mins) so it re-attempts the live API promptly
    cache.set(cache_key, rate, 300)
    return rate

def check_ad_funds(user, cost_amount, require_min_usd_rate=False):
    """
    Checks if user has sufficient combined ad credit + wallet balance.
    Returns: (is_available: bool, error_message: str or None, status_code: int)
    """
    user_details = UserDetails.objects.filter(user=user).first()
    user_currency = user_details.currency if user_details else 'NGN'
    
    business = user.business_details.first()
    current_ad_credit = Decimal(str(business.ad_credit or 0.00)) if business else Decimal('0.00')
    
    cost_decimal = Decimal(str(cost_amount))
    wallet_balance = Decimal(str(calculate_total_balance(user)))
    total_available = current_ad_credit + wallet_balance
    
    if require_min_usd_rate:
        rate = get_usd_to_local_exchange_rate(user_currency)
        min_usd_equivalent = Decimal(str(1.0 * rate))
        if total_available < min_usd_equivalent:
            return False, f'Insufficient wallet/ad credit balance. At least 1 USD equivalent ({user_currency} {min_usd_equivalent:,.2f}) is required.', 402
            
    if total_available < cost_decimal:
        return False, f'Insufficient funds. Total cost is {user_currency} {cost_decimal:,.2f} but available funds (Ad Credit + Wallet) is {user_currency} {total_available:,.2f}.', 400
        
    return True, None, 200

def debit_ad_funds(user, cost_amount, description):
    """
    Debits ad credit first; if ad credit is insufficient, debits the remainder
    from the user's wallet balance.
    Returns: (success: bool, error_message: str or None, status_code: int)
    """
    user_details = UserDetails.objects.filter(user=user).first()
    user_currency = user_details.currency if user_details else 'NGN'
    
    business = user.business_details.first()
    current_ad_credit = Decimal(str(business.ad_credit or 0.00)) if business else Decimal('0.00')
    
    cost_decimal = Decimal(str(cost_amount))
    wallet_balance = Decimal(str(calculate_total_balance(user)))
    total_available = current_ad_credit + wallet_balance
    
    if total_available < cost_decimal:
        return False, f'Insufficient funds. Required: {user_currency} {cost_decimal:,.2f}, Available: {user_currency} {total_available:,.2f}.', 400
        
    if current_ad_credit >= cost_decimal:
        if business:
            business.ad_credit = current_ad_credit - cost_decimal
            business.save(update_fields=['ad_credit'])
        UserTransactions.objects.create(
            user=user,
            trx_status='completed',
            trx_amount=float(cost_decimal),
            trx_type='ad_credit',
            trx_currency=user_currency,
            description=f'{description} (Paid with Ad Credit)',
            destination_id=user.uniq_id,
            user_collection_id='0'
        )
    elif current_ad_credit > Decimal('0.00'):
        wallet_deduction = cost_decimal - current_ad_credit
        if business:
            business.ad_credit = Decimal('0.00')
            business.save(update_fields=['ad_credit'])
        UserTransactions.objects.create(
            user=user,
            trx_status='completed',
            trx_amount=float(current_ad_credit),
            trx_type='ad_credit',
            trx_currency=user_currency,
            description=f'{description} (Ad Credit portion: {user_currency} {current_ad_credit:,.2f})',
            destination_id=user.uniq_id,
            user_collection_id='0'
        )
        UserTransactions.objects.create(
            user=user,
            trx_status='completed',
            trx_amount=float(wallet_deduction),
            trx_type='payment',
            trx_currency=user_currency,
            description=f'{description} (Wallet portion: {user_currency} {wallet_deduction:,.2f})',
            destination_id=user.uniq_id,
            user_collection_id='0'
        )
    else:
        UserTransactions.objects.create(
            user=user,
            trx_status='completed',
            trx_amount=float(cost_decimal),
            trx_type='payment',
            trx_currency=user_currency,
            description=description,
            destination_id=user.uniq_id,
            user_collection_id='0'
        )
        
    return True, None, 200

@method_decorator(login_required, name='dispatch')
class GrowthOverviewAPI(View):
    def get(self, request):
        user = request.user
        
        # Get actual business owner if staff
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user
            
        promotions = GrowthPromotion.objects.filter(user=owner).order_by('-created_at')
        
        active_count = promotions.filter(status='active').count()
        total_sales = promotions.aggregate(Sum('sales_generated'))['sales_generated__sum'] or 0
        total_spent = promotions.aggregate(Sum('amount_spent'))['amount_spent__sum'] or 0
        total_customers = promotions.aggregate(Sum('customers_gained'))['customers_gained__sum'] or 0
        
        details = owner.details.first()
        currency = details.currency if details else 'NGN'
        
        business = owner.business_details.first()
        ad_credit = float(business.ad_credit or 0.00) if business else 0.00
        
        recent_promotions = []
        for promo in promotions[:5]:
            recent_promotions.append({
                'id': str(promo.id),
                'title': promo.title,
                'status': promo.status,
                'amount_spent': str(promo.amount_spent),
                'sales_generated': promo.sales_generated,
                'promote_type': promo.promote_type,
                'action_type': promo.action_type,
                'budget_per_day': str(promo.budget_per_day),
                'cover_image': promo.cover_image,
                'fb_campaign_id': promo.fb_campaign_id,
            })
            
        return JsonResponse({
            'success': True,
            'currency': currency,
            'ad_credit': ad_credit,
            'meta_connected': details.meta_page_connected if details else False,
            'active_promotions': active_count,
            'total_sales_generated': total_sales,
            'total_spent': str(total_spent),
            'total_customers': total_customers,
            'recent_promotions': recent_promotions
        })

@method_decorator(login_required, name='dispatch')
class GrowthReportsAPI(View):
    def get(self, request):
        user = request.user
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user

        details = owner.details.first()
        currency = details.currency if details else 'NGN'

        # Optional Meta sync if requested
        if request.GET.get('sync') == 'true':
            try:
                from api.services.facebook_ads import FacebookAdsService
                if details and details.meta_page_connected and details.meta_access_token:
                    fb_service = FacebookAdsService(
                        user_access_token=details.meta_access_token,
                        user_page_id=details.meta_page_id,
                    )
                    fb_service.sync_campaigns_to_db(owner)
            except Exception as e:
                logger.warning(f"[GrowthReportsAPI] Meta sync warning: {e}")

        # Range filter (default 30d)
        range_param = request.GET.get('range', '30d').strip().lower()
        now = timezone.now()
        all_promos = GrowthPromotion.objects.filter(user=owner)

        if range_param == '90d':
            start_date = now - timezone.timedelta(days=90)
            range_label = 'Last 3 Months'
        elif range_param == 'year':
            start_date = timezone.datetime(now.year, 1, 1, tzinfo=now.tzinfo)
            range_label = 'This Year'
        elif range_param == 'all':
            start_date = None
            range_label = 'All Time'
        else:  # default '30d'
            range_param = '30d'
            start_date = now - timezone.timedelta(days=30)
            range_label = 'Last 30 Days'

        if start_date:
            promotions = all_promos.filter(created_at__gte=start_date)
        else:
            promotions = all_promos

        total_spent = promotions.aggregate(Sum('amount_spent'))['amount_spent__sum'] or Decimal('0.00')
        total_sales = promotions.aggregate(Sum('sales_generated'))['sales_generated__sum'] or 0
        total_customers = promotions.aggregate(Sum('customers_gained'))['customers_gained__sum'] or 0
        total_views = promotions.aggregate(Sum('views'))['views__sum'] or 0
        total_clicks = promotions.aggregate(Sum('clicks'))['clicks__sum'] or 0

        # Cost Per Acquisition / Customer (CPA)
        if total_customers > 0:
            avg_cpa = round(float(total_spent) / total_customers, 2)
        elif total_sales > 0:
            avg_cpa = round(float(total_spent) / total_sales, 2)
        else:
            avg_cpa = 0.00

        # Chart Data Generation
        labels = []
        sales_data = []
        spent_data = []

        if range_param == '30d':
            # 4 weekly intervals
            for i in range(3, -1, -1):
                bucket_start = now - timezone.timedelta(days=(i + 1) * 7)
                bucket_end = now - timezone.timedelta(days=i * 7)
                label = f"Week {4 - i}"
                bucket_promos = all_promos.filter(created_at__gte=bucket_start, created_at__lt=bucket_end)
                s = bucket_promos.aggregate(Sum('sales_generated'))['sales_generated__sum'] or 0
                sp = bucket_promos.aggregate(Sum('amount_spent'))['amount_spent__sum'] or Decimal('0.00')
                labels.append(label)
                sales_data.append(int(s))
                spent_data.append(round(float(sp), 2))
        elif range_param == '90d':
            # 3 monthly intervals
            for i in range(2, -1, -1):
                b_start = now - timezone.timedelta(days=(i + 1) * 30)
                b_end = now - timezone.timedelta(days=i * 30)
                month_name = b_end.strftime('%b')
                b_promos = all_promos.filter(created_at__gte=b_start, created_at__lt=b_end)
                s = b_promos.aggregate(Sum('sales_generated'))['sales_generated__sum'] or 0
                sp = b_promos.aggregate(Sum('amount_spent'))['amount_spent__sum'] or Decimal('0.00')
                labels.append(month_name)
                sales_data.append(int(s))
                spent_data.append(round(float(sp), 2))
        else:
            # 6-12 monthly buckets
            month_count = 12 if range_param in ['year', 'all'] else 6
            for i in range(month_count - 1, -1, -1):
                m_date = now - timezone.timedelta(days=i * 30)
                month_label = m_date.strftime('%b')
                m_start = timezone.datetime(m_date.year, m_date.month, 1, tzinfo=now.tzinfo)
                if m_date.month == 12:
                    m_end = timezone.datetime(m_date.year + 1, 1, 1, tzinfo=now.tzinfo)
                else:
                    m_end = timezone.datetime(m_date.year, m_date.month + 1, 1, tzinfo=now.tzinfo)

                m_promos = all_promos.filter(created_at__gte=m_start, created_at__lt=m_end)
                s = m_promos.aggregate(Sum('sales_generated'))['sales_generated__sum'] or 0
                sp = m_promos.aggregate(Sum('amount_spent'))['amount_spent__sum'] or Decimal('0.00')
                labels.append(month_label)
                sales_data.append(int(s))
                spent_data.append(round(float(sp), 2))

        # Top Performing Promotions
        top_promos_qs = promotions.order_by('-sales_generated', '-amount_spent')[:6]
        top_promotions = []
        for p in top_promos_qs:
            cpa = round(float(p.amount_spent) / p.customers_gained, 2) if p.customers_gained > 0 else (round(float(p.amount_spent) / p.sales_generated, 2) if p.sales_generated > 0 else 0.00)
            top_promotions.append({
                'id': str(p.id),
                'title': p.title,
                'status': p.status,
                'promote_type': p.promote_type,
                'action_type': p.action_type,
                'amount_spent': str(p.amount_spent),
                'sales_generated': p.sales_generated,
                'customers_gained': p.customers_gained,
                'cpa': cpa,
                'cover_image': p.cover_image,
                'budget_per_day': str(p.budget_per_day),
                'created_at': p.created_at.strftime('%b %d, %Y')
            })

        # Dynamic AI Business Insights based on actual data
        insights = []
        if top_promotions and total_sales > 0:
            best_promo = top_promotions[0]
            insights.append({
                'icon': 'award',
                'color': 'emerald',
                'title': f"Top Campaign: {best_promo['title']}",
                'description': f"This campaign generated {best_promo['sales_generated']} sales with an ad spend of {currency} {float(best_promo['amount_spent']):,.2f}."
            })

            discount_promos = promotions.filter(promote_type='discount')
            product_promos = promotions.filter(promote_type='product')
            disc_sales = discount_promos.aggregate(Sum('sales_generated'))['sales_generated__sum'] or 0
            prod_sales = product_promos.aggregate(Sum('sales_generated'))['sales_generated__sum'] or 0

            if disc_sales > prod_sales and disc_sales > 0:
                insights.append({
                    'icon': 'trending-up',
                    'color': 'blue',
                    'title': 'Discounts drive higher transaction volume',
                    'description': 'Promotions offering direct discounts or flash sales have outperformed standard product showcases.'
                })
            else:
                insights.append({
                    'icon': 'users',
                    'color': 'blue',
                    'title': 'Targeted product showcases converting well',
                    'description': 'Showcasing individual high-demand items directly to local shoppers yields strong engagement and conversion.'
                })

            if avg_cpa > 0:
                insights.append({
                    'icon': 'lightbulb',
                    'color': 'primary',
                    'title': f'Customer Acquisition Cost: {currency} {avg_cpa:,.2f}',
                    'description': f'Maintaining a CPA under {currency} {avg_cpa * 1.2:,.2f} keeps your promotion return profitable across Meta channels.'
                })
        else:
            insights = [
                {
                    'icon': 'sparkles',
                    'color': 'primary',
                    'title': 'Ready to accelerate business growth',
                    'description': 'You haven\'t launched any active promotions in this period. Running ads on Facebook, Instagram, and WhatsApp can instantly bring in local buyers.'
                },
                {
                    'icon': 'trending-up',
                    'color': 'emerald',
                    'title': 'AI Campaign Automation',
                    'description': 'Use the AI Creative Generator to write persuasive ad captions, generate high-impact product imagery, and choose the optimal audience.'
                },
                {
                    'icon': 'target',
                    'color': 'blue',
                    'title': 'Cost-Effective Daily Budgets',
                    'description': f'Start with as little as {currency} 2,000 to {currency} 5,000 per day to test audience resonance before scaling.'
                }
            ]

        return JsonResponse({
            'success': True,
            'currency': currency,
            'range': range_param,
            'range_label': range_label,
            'metrics': {
                'total_spent': str(total_spent),
                'total_sales': total_sales,
                'total_customers': total_customers,
                'total_views': total_views,
                'total_clicks': total_clicks,
                'average_cpa': avg_cpa,
            },
            'chart': {
                'labels': labels,
                'sales_data': sales_data,
                'spent_data': spent_data,
            },
            'top_promotions': top_promotions,
            'insights': insights,
        })

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class GrowthMetaRevokeAPI(View):
    def post(self, request):
        user = request.user
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user
            
        details = owner.details.first()
        if details:
            details.meta_page_connected = False
            details.meta_access_token = None
            details.meta_page_id = None
            details.save()
            
        return JsonResponse({'success': True})

@method_decorator(login_required, name='dispatch')
class GrowthMetaConnectAPI(View):
    def get(self, request):
        app_id = os.environ.get('FACEBOOK_LOGIN_APP_ID') or os.environ.get('FACEBOOK_APP_ID', '')
        if not app_id:
            return JsonResponse({'error': 'Facebook App ID not configured'}, status=500)

        # Use a dedicated callback URL (not the settings page)
        redirect_uri = f"{request.scheme}://{request.get_host()}/api/growth/meta/callback"

        # Note: merchants only need to authorize reading their Facebook Pages so they can choose
        # which page ads show as "Sponsored by". Ad publishing is managed via the central ad account token.
        oauth_url = (
            f"https://www.facebook.com/v18.0/dialog/oauth?"
            f"client_id={app_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope=pages_show_list,pages_read_engagement&"
            f"auth_type=rerequest&"
            f"response_type=code"
        )
        return redirect(oauth_url)


@method_decorator(login_required, name='dispatch')
class GrowthMetaCallbackAPI(View):
    """Handles the OAuth callback from Meta, exchanges code for a long-lived token, and saves it."""

    POPUP_SUCCESS_HTML = """<!DOCTYPE html><html><head><title>Connected</title></head>
<body><script>
  if (window.opener) {{
    window.opener.postMessage({{type: 'META_OAUTH_SUCCESS'}}, '*');
  }}
  window.close();
</script><p>Connected successfully. You can close this window.</p></body></html>"""

    POPUP_ERROR_HTML = """<!DOCTYPE html><html><head><title>Error</title></head>
<body><script>
  if (window.opener) {{
    window.opener.postMessage({{type: 'META_OAUTH_ERROR', message: '{message}'}}, '*');
  }}
  window.close();
</script><p>Connection failed: {message}. You can close this window.</p></body></html>"""

    def get(self, request):
        from django.http import HttpResponse

        error = request.GET.get('error')
        if error:
            msg = request.GET.get('error_description', 'Access denied')
            return HttpResponse(self.POPUP_ERROR_HTML.format(message=msg), content_type='text/html')

        code = request.GET.get('code')
        if not code:
            return HttpResponse(self.POPUP_ERROR_HTML.format(message='No code returned from Meta'), content_type='text/html')

        app_id = os.environ.get('FACEBOOK_LOGIN_APP_ID') or os.environ.get('FACEBOOK_APP_ID', '')
        app_secret = os.environ.get('FACEBOOK_LOGIN_APP_SECRET') or os.environ.get('FACEBOOK_APP_SECRET', '')
        redirect_uri = f"{request.scheme}://{request.get_host()}/api/growth/meta/callback"

        # Step 1: Exchange code for short-lived access token
        try:
            token_response = requests.get(
                'https://graph.facebook.com/v18.0/oauth/access_token',
                params={
                    'client_id': app_id,
                    'redirect_uri': redirect_uri,
                    'client_secret': app_secret,
                    'code': code,
                },
                timeout=10
            ).json()
        except Exception as e:
            logger.error(f"Meta token exchange request failed: {e}")
            return HttpResponse(self.POPUP_ERROR_HTML.format(message='Token request failed'), content_type='text/html')

        short_lived_token = token_response.get('access_token')
        if not short_lived_token:
            error_msg = token_response.get('error', {}).get('message', 'No access token returned')
            logger.error(f"Meta token exchange error: {token_response}")
            return HttpResponse(self.POPUP_ERROR_HTML.format(message=error_msg), content_type='text/html')

        # Step 2: Upgrade to a long-lived token (60 days)
        try:
            long_lived_response = requests.get(
                'https://graph.facebook.com/v18.0/oauth/access_token',
                params={
                    'grant_type': 'fb_exchange_token',
                    'client_id': app_id,
                    'client_secret': app_secret,
                    'fb_exchange_token': short_lived_token,
                },
                timeout=10
            ).json()
        except Exception as e:
            logger.error(f"Meta long-lived token exchange failed: {e}")
            return HttpResponse(self.POPUP_ERROR_HTML.format(message='Token upgrade failed'), content_type='text/html')

        long_lived_token = long_lived_response.get('access_token', short_lived_token)

        # Step 3: Fetch the user's FB profile and managed Pages
        fb_user_id = None
        fb_page_id = None
        fb_page_token = None
        try:
            me_response = requests.get(
                'https://graph.facebook.com/v18.0/me',
                params={'fields': 'id,name', 'access_token': long_lived_token},
                timeout=10
            ).json()
            fb_user_id = me_response.get('id')

            # Fetch the pages this user manages — these are the pages that can be "Sponsored by"
            pages_response = requests.get(
                f'https://graph.facebook.com/v18.0/{fb_user_id}/accounts',
                params={'fields': 'id,name,access_token', 'access_token': long_lived_token},
                timeout=10
            ).json()
            pages = pages_response.get('data', [])
            if pages:
                # Default to the first page; user can change this in settings later
                fb_page_id = pages[0].get('id')
                fb_page_token = pages[0].get('access_token')  # Page-scoped long-lived token
        except Exception as e:
            logger.error(f"Meta /me or /accounts request failed: {e}")

        # Step 4: Save to user details
        user = request.user
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user

        details = owner.details.first()
        if details:
            details.meta_access_token = long_lived_token
            details.meta_page_connected = True
            # Save their actual page ID so ads show "Sponsored by [their page]"
            if fb_page_id:
                details.meta_page_id = fb_page_id
            elif fb_user_id:
                details.meta_page_id = fb_user_id
            details.save()
            logger.info(f"Meta account connected for user {owner.id}, page_id={fb_page_id}")
        else:
            logger.error(f"No UserDetails found for user {owner.id}")
            return HttpResponse(self.POPUP_ERROR_HTML.format(message='User profile not found'), content_type='text/html')

        return HttpResponse(self.POPUP_SUCCESS_HTML, content_type='text/html')


@method_decorator(login_required, name='dispatch')
class GrowthMetaPagesAPI(View):
    """Returns all Facebook Pages the connected user manages."""
    def get(self, request):
        user = request.user
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user

        details = owner.details.first()
        if not details or not details.meta_access_token or not details.meta_page_connected:
            return JsonResponse({'success': False, 'error': 'No Meta account connected.'}, status=400)

        try:
            me_response = requests.get(
                'https://graph.facebook.com/v18.0/me',
                params={'fields': 'id', 'access_token': details.meta_access_token},
                timeout=10
            ).json()
            fb_user_id = me_response.get('id')
            if not fb_user_id:
                return JsonResponse({'success': False, 'error': 'Could not retrieve Meta user ID.'}, status=400)

            all_pages = []
            seen_ids = set()

            # 1. Fetch personal / direct pages with pagination
            next_url = f'https://graph.facebook.com/v18.0/{fb_user_id}/accounts'
            params = {
                'fields': 'id,name,picture,category',
                'access_token': details.meta_access_token,
                'limit': 100
            }
            while next_url:
                if '?' in next_url:
                    res = requests.get(next_url, timeout=10).json()
                else:
                    res = requests.get(next_url, params=params, timeout=10).json()
                data = res.get('data', [])
                for p in data:
                    pid = str(p.get('id', ''))
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        all_pages.append(p)
                next_url = res.get('paging', {}).get('next')

            # 2. Also check businesses (Business Portfolios) if user token has access
            try:
                biz_res = requests.get(
                    'https://graph.facebook.com/v18.0/me/businesses',
                    params={'access_token': details.meta_access_token, 'limit': 100},
                    timeout=5
                ).json()
                for biz in biz_res.get('data', []):
                    biz_id = biz.get('id')
                    for edge in ['owned_pages', 'client_pages']:
                        bp_res = requests.get(
                            f'https://graph.facebook.com/v18.0/{biz_id}/{edge}',
                            params={'fields': 'id,name,picture,category', 'access_token': details.meta_access_token, 'limit': 100},
                            timeout=5
                        ).json()
                        for bp in bp_res.get('data', []):
                            pid = str(bp.get('id', ''))
                            if pid and pid not in seen_ids:
                                seen_ids.add(pid)
                                all_pages.append(bp)
            except Exception as biz_err:
                logger.debug(f"Could not fetch business pages: {biz_err}")

            return JsonResponse({
                'success': True,
                'pages': [
                    {
                        'id': p.get('id'),
                        'name': p.get('name'),
                        'category': p.get('category', ''),
                        'picture': p.get('picture', {}).get('data', {}).get('url', '') if isinstance(p.get('picture'), dict) else '',
                    }
                    for p in all_pages
                ],
                'selected_page_id': details.meta_page_id,
                'selected_page_name': details.meta_page_name,
            })
        except Exception as e:
            logger.error(f"GrowthMetaPagesAPI error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class GrowthMetaSelectPageAPI(View):
    """Saves the user's chosen Facebook Page for ad campaigns."""
    def post(self, request):
        user = request.user
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user

        try:
            data = json.loads(request.body)
            page_id = str(data.get('page_id', '')).strip()
            page_name = str(data.get('page_name', '')).strip()
            if not page_id:
                return JsonResponse({'success': False, 'error': 'page_id is required.'}, status=400)

            details = owner.details.first()
            if not details or not details.meta_page_connected:
                return JsonResponse({'success': False, 'error': 'No Meta account connected.'}, status=400)

            details.meta_page_id = page_id
            details.meta_page_name = page_name
            details.save(update_fields=['meta_page_id', 'meta_page_name'])
            return JsonResponse({'success': True, 'page_id': page_id, 'page_name': page_name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

def is_card_required_error(msg):
    if not msg:
        return False
    m = str(msg).lower()
    return (
        '1359188' in m or
        'payment method' in m or
        'payment_method' in m or
        'payment card' in m or
        'card required' in m or
        'no payment method' in m or
        'billing_hub' in m or
        ('card' in m and ('require' in m or 'add' in m or 'attach' in m)) or
        ('billing' in m and ('payment' in m or 'card' in m))
    )


@method_decorator(login_required, name='dispatch')
class GrowthPromotionsAPI(View):
    def get(self, request):
        user = request.user
        
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user
            
        status_filter = request.GET.get('status', 'all')
        search_query = request.GET.get('search', '').strip()
        try:
            page_num = int(request.GET.get('page', 1))
        except ValueError:
            page_num = 1

        try:
            limit = int(request.GET.get('limit', 10))
        except ValueError:
            limit = 10
            
        sync_requested = request.GET.get('sync') == 'true'
        if sync_requested or not GrowthPromotion.objects.filter(user=owner).exists():
            try:
                from api.services.facebook_ads import FacebookAdsService
                details = owner.details.first()
                fb_service = FacebookAdsService(
                    user_access_token=details.meta_access_token if details else None,
                    user_page_id=details.meta_page_id if details else None,
                )
                fb_service.sync_campaigns_to_db(owner)
            except Exception as e:
                logger.warning(f"[GrowthPromotionsAPI] Meta sync warning: {e}")

        promotions = GrowthPromotion.objects.filter(user=owner).order_by('-created_at')
        
        if status_filter != 'all':
            promotions = promotions.filter(status=status_filter)
            
        if search_query:
            promotions = promotions.filter(
                Q(title__icontains=search_query) | 
                Q(message__icontains=search_query) |
                Q(promote_type__icontains=search_query)
            )
            
        paginator = Paginator(promotions, limit)
        page_obj = paginator.get_page(page_num)
        
        results = []
        for promo in page_obj:
            results.append({
                'id': str(promo.id),
                'title': promo.title,
                'message': promo.message,
                'promote_type': promo.promote_type,
                'action_type': promo.action_type,
                'budget_per_day': str(promo.budget_per_day),
                'duration_days': promo.duration_days,
                'amount_spent': str(promo.amount_spent),
                'sales_generated': promo.sales_generated,
                'customers_gained': promo.customers_gained,
                'profit_impact': str(promo.profit_impact),
                'views': promo.views,
                'clicks': promo.clicks,
                'status': promo.status,
                'cover_image': promo.cover_image,
                'fb_campaign_id': promo.fb_campaign_id,
                'is_external': promo.is_external,
                'amount_debited': str(promo.amount_debited),
                'created_at': promo.created_at.strftime('%b %d, %Y'),
            })
            
        return JsonResponse({
            'success': True,
            'promotions': results,
            'pagination': {
                'total_pages': paginator.num_pages,
                'current_page': page_obj.number,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'total_items': paginator.count
            }
        })
        
    def post(self, request):
        try:
            data = json.loads(request.body)
            user = request.user
            
            if user.user_type in ['manager', 'staff'] and user.business_owner:
                owner = user.business_owner
            else:
                owner = user
                
            business = owner.business_details.first()
            if not business or not business.store_setup:
                return JsonResponse({'success': False, 'error': 'You must set up your online store before you can run campaigns.'}, status=400)
                
            user_details = owner.details.first()
            if not user_details or not user_details.meta_page_connected or not user_details.meta_access_token:
                return JsonResponse({'success': False, 'error': 'You have not connected your Meta account. Please connect to continue.'}, status=400)

            # Verify token is still valid with Meta API
            verify_url = f"https://graph.facebook.com/me?access_token={user_details.meta_access_token}"
            verify_req = requests.get(verify_url)
            if verify_req.status_code != 200:
                # Token is invalid or expired
                user_details.meta_page_connected = False
                user_details.meta_access_token = None
                user_details.meta_page_id = None
                user_details.save()
                return JsonResponse({'success': False, 'error': 'Your Meta account connection has expired or was revoked. Please reconnect your account.'}, status=400)
                
            product_id = data.get('product_id')
            product_obj = None
            if product_id:
                product_obj = UserItems.objects.filter(item_id=product_id, user=owner).first()

            budget = float(data.get('budget_per_day', 5.00))
            duration_days = int(data.get('duration_days', 7))
            total_cost = budget * duration_days
            
            cover_image = data.get('cover_image', '')
            if not cover_image:
                return JsonResponse({'success': False, 'error': 'A campaign media or cover image is required.'}, status=400)

            user_details = UserDetails.objects.filter(user=owner).first()
            user_currency = (user_details.currency if user_details else 'USD') or 'USD'

            # Ensure budget meets minimum $1.00 USD equivalent in user's currency
            usd_rate = get_usd_to_local_exchange_rate(user_currency) or 1.0
            min_daily_budget = round(1.0 * usd_rate, 2)
            if budget < min_daily_budget:
                return JsonResponse({
                    'success': False,
                    'error': f'Daily budget is too low. Minimum is {user_currency} {min_daily_budget:,.2f} ($1.00 USD equivalent) per day.'
                }, status=400)
            
            # Check ad credit / wallet balance
            has_funds, error_msg, err_status = check_ad_funds(owner, total_cost, require_min_usd_rate=True)
            if not has_funds:
                return JsonResponse({'success': False, 'error': error_msg}, status=err_status)

            promo = GrowthPromotion.objects.create(
                user=owner,
                product=product_obj,
                title=data.get('title', 'New Promotion'),
                message=data.get('message', ''),
                promote_type=data.get('promote_type', 'product'),
                action_type=data.get('action_type', 'buy'),
                budget_per_day=budget,
                duration_days=duration_days,
                audience_type=data.get('audience_type', 'near'),
                custom_locations=data.get('custom_locations', ''),
                custom_age_min=data.get('custom_age_min'),
                custom_age_max=data.get('custom_age_max'),
                custom_interests=data.get('custom_interests', ''),
                status=data.get('status', 'active'),
                cover_image=data.get('cover_image', ''),
                amount_debited=Decimal(str(total_cost)),
                is_external=False,
            )
            
            # Send to Facebook Ads API — use the user's own token and page so ads show "Sponsored by [their page]"
            user_details = UserDetails.objects.filter(user=owner).first()
            fb_result = {}
            try:
                fb_service = FacebookAdsService(
                    user_access_token=user_details.meta_access_token if user_details else None,
                    user_page_id=user_details.meta_page_id if user_details else None,
                )
                fb_result = fb_service.create_ad_campaign_flow(promo)
                
                is_card_err = (
                    fb_result.get('card_required') or
                    is_card_required_error(fb_result.get('error'))
                )

                if fb_result.get('success') and fb_result.get('ad_id'):
                    promo.fb_campaign_id = fb_result.get('campaign_id')
                    promo.fb_adset_id = fb_result.get('adset_id')
                    promo.fb_ad_id = fb_result.get('ad_id')
                    promo.save()
                elif is_card_err or fb_result.get('card_required'):
                    # Temporarily allow campaign creation even if card required error is thrown by Meta
                    logger.warning(f"[GrowthPromotionsAPI] Meta card required for promo {promo.id}. Enabling campaign in standby mode.")
                    promo.fb_campaign_id = fb_result.get('campaign_id')
                    promo.fb_adset_id = fb_result.get('adset_id')
                    promo.fb_ad_id = fb_result.get('ad_id')
                    promo.save()
                    clean_acc_id = (fb_service.ad_account_id or '').replace('act_', '')
                    if not fb_result.get('billing_url'):
                        fb_result['billing_url'] = f"https://adsmanager.facebook.com/billing_hub/payment_settings?act={clean_acc_id}" if clean_acc_id else "https://adsmanager.facebook.com/billing_hub"
                    if not fb_result.get('warning'):
                        fb_result['warning'] = 'Promotion created successfully! However, your Meta Ad Account requires an active payment card attached before ads can be delivered to audiences.'
                else:
                    error_msg = fb_result.get('error', 'Unknown Facebook API error')
                    logger.error(f"[GrowthPromotionsAPI] Promotion {promo.id} Facebook API error: {error_msg}")
                    promo.delete()
                    return JsonResponse({'success': False, 'error': error_msg}, status=400)
            except Exception as e:
                err_str = str(e)
                if is_card_required_error(err_str):
                    logger.warning(f"[GrowthPromotionsAPI] Exception recognized as card required for promo {promo.id}: {err_str}")
                    promo.save()
                    debit_ad_funds(owner, total_cost, f'Campaign Creation: {promo.id} ({duration_days} days)')
                    clean_acc_id = (getattr(fb_service, 'ad_account_id', '') or '').replace('act_', '')
                    billing_url = f"https://adsmanager.facebook.com/billing_hub/payment_settings?act={clean_acc_id}" if clean_acc_id else "https://adsmanager.facebook.com/billing_hub"
                    return JsonResponse({
                        'success': True,
                        'id': str(promo.id),
                        'warning': 'Promotion created successfully! However, your Meta Ad Account requires an active payment card attached before ads can be delivered to audiences.',
                        'billing_url': billing_url
                    })
                logger.exception(f"[GrowthPromotionsAPI] Unexpected exception creating promo in Facebook Ads: {e}")
                promo.delete()
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
            
            # Debit ad credit first, fallback to wallet balance
            debit_ad_funds(owner, total_cost, f'Campaign Creation: {promo.id} ({duration_days} days)')
            
            resp_payload = {'success': True, 'id': str(promo.id)}
            if fb_result.get('warning'):
                resp_payload['warning'] = fb_result['warning']
            if fb_result.get('billing_url'):
                resp_payload['billing_url'] = fb_result['billing_url']
            return JsonResponse(resp_payload)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

def calculate_refundable_budget(promo):
    """
    Strictly calculates the refundable balance for a campaign.
    - Synced/external campaigns: exactly 0.00 refund (eliminates phantom money).
    - Campaigns without debited funds (amount_debited <= 0): exactly 0.00 refund.
    - FlezPay-funded campaigns: strictly capped at max(0.00, amount_debited - amount_spent).
    """
    if not promo:
        return Decimal('0.00')
    if getattr(promo, 'is_external', False):
        return Decimal('0.00')
    debited = getattr(promo, 'amount_debited', None)
    if debited is None or debited <= Decimal('0.00'):
        return Decimal('0.00')
    spent = Decimal(str(promo.amount_spent or 0.00))
    return max(Decimal('0.00'), Decimal(str(debited)) - spent)

@method_decorator(login_required, name='dispatch')
class GrowthCampaignRevertAPI(View):
    def post(self, request, promo_id):
        user = request.user
        
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user
            
        try:
            promo = GrowthPromotion.objects.get(id=promo_id, user=owner)
            
            user_details = UserDetails.objects.filter(user=owner).first()
            currency = user_details.currency if user_details else 'NGN'
            
            # Calculate strict refund: 0.00 for external, capped at amount_debited - amount_spent for internal
            remaining_refund = calculate_refundable_budget(promo)
            
            # Delete campaign remotely on Meta via Graph API
            meta_deleted = False
            meta_error = None
            if promo.fb_campaign_id:
                try:
                    from api.services.facebook_ads import FacebookAdsService
                    fb_service = FacebookAdsService(
                        user_access_token=user_details.meta_access_token if user_details else None,
                        user_page_id=user_details.meta_page_id if user_details else None,
                    )
                    fb_del = fb_service.delete_campaign(promo.fb_campaign_id)
                    meta_deleted = fb_del.get('success', False)
                    if not meta_deleted:
                        meta_error = fb_del.get('error')
                        fb_service.update_ad_status(promo.fb_campaign_id, 'paused')
                except Exception as fb_err:
                    meta_error = str(fb_err)
                    logger.warning(f"[GrowthCampaignRevertAPI] Error deleting Meta campaign {promo.fb_campaign_id}: {fb_err}")
            
            # Transfer remaining money to AD CREDIT strictly if remaining_refund > 0
            business = owner.business_details.first()
            if business and remaining_refund > Decimal('0.00'):
                business.ad_credit = (business.ad_credit or Decimal('0.00')) + remaining_refund
                business.save(update_fields=['ad_credit'])
            
            # Audit transaction for Ad Credit refund
            if remaining_refund > Decimal('0.00'):
                UserTransactions.objects.create(
                    user=owner,
                    trx_status='completed',
                    trx_amount=float(remaining_refund),
                    trx_type='ad_credit',
                    trx_currency=currency,
                    description=f'Campaign Reverted: {promo.title} (Refunded {currency} {remaining_refund:,.2f} to Ad Credit)',
                    destination_id=owner.uniq_id,
                    user_collection_id='0'
                )
            
            is_external = promo.is_external
            promo_title = promo.title
            promo.delete()
            
            if is_external:
                msg = f'External campaign "{promo_title}" deleted from Meta and FlezPay. No refund issued as this campaign was not funded via FlezPay.'
            elif remaining_refund > Decimal('0.00'):
                msg = f'Campaign "{promo_title}" reverted and deleted from Meta. Remaining balance of {currency} {remaining_refund:,.2f} has been transferred to your Ad Credit.'
            else:
                msg = f'Campaign "{promo_title}" reverted and deleted from Meta. No remaining balance to refund.'

            return JsonResponse({
                'success': True,
                'message': msg,
                'refunded_amount': float(remaining_refund),
                'is_external': is_external,
                'meta_deleted': meta_deleted
            })
        except GrowthPromotion.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Campaign not found or unauthorized.'}, status=404)
        except Exception as e:
            logger.exception(f"[GrowthCampaignRevertAPI] Unexpected error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class GrowthPromotionsSyncAPI(View):
    def post(self, request):
        user = request.user
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user

        try:
            from api.services.facebook_ads import FacebookAdsService
            details = owner.details.first()
            fb_service = FacebookAdsService(
                user_access_token=details.meta_access_token if details else None,
                user_page_id=details.meta_page_id if details else None,
            )
            res = fb_service.sync_campaigns_to_db(owner)
            return JsonResponse(res)
        except Exception as e:
            logger.exception(f"[GrowthPromotionsSyncAPI] Error syncing ads from Meta: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

@method_decorator(login_required, name='dispatch')
class GrowthPromotionDetailAPI(View):
    def get(self, request, id):
        user = request.user
        
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user
            
        try:
            promo = GrowthPromotion.objects.get(id=id, user=owner)
            details = owner.details.first()
            currency = details.currency if details else 'NGN'
            
            if promo.fb_campaign_id and promo.status == 'active':
                try:
                    fb_service = FacebookAdsService(
                        user_access_token=details.meta_access_token if details else None,
                        user_page_id=details.meta_page_id if details else None,
                    )
                    insights = fb_service.get_campaign_insights(promo.fb_campaign_id)
                    if insights.get('success'):
                        promo.amount_spent = insights.get('spend', promo.amount_spent)
                        promo.views = insights.get('impressions', promo.views)
                        promo.clicks = insights.get('clicks', promo.clicks)
                        promo.save()
                except Exception as e:
                    pass
            
            duration_days = promo.duration_days if (promo.duration_days and promo.duration_days > 0) else 7
            now = timezone.now()
            created_at = promo.created_at or now
            days_elapsed = max(0, (now - created_at).days)
            remaining_days = max(1, duration_days - days_elapsed)
            
            debited_val = float(promo.amount_debited or 0.0)
            if not promo.is_external and debited_val > 0:
                total_budget = round(debited_val, 2)
            else:
                total_budget = 0.0 if promo.is_external else round(float(promo.budget_per_day) * duration_days, 2)
            amount_spent_float = float(promo.amount_spent or 0.0)
            remaining_budget = float(calculate_refundable_budget(promo))
            
            views = promo.views or 0
            clicks = promo.clicks or 0
            sales = promo.sales_generated or 0
            
            cpc = round(amount_spent_float / clicks, 2) if clicks > 0 else 0.0
            cpa = round(amount_spent_float / sales, 2) if sales > 0 else 0.0
            ctr = round((clicks / views) * 100, 2) if views > 0 else 0.0
            
            business = owner.business_details.first()
            store_name = (business.business_name or business.store_name) if business else 'Store'
            store_url = (f"https://{business.store_custom_domain}" if business and business.store_custom_domain else (f"https://{business.store_slug}.flezpay.com" if business and business.store_slug else "flezpay.com"))
            store_logo = business.store_logo.url if business and business.store_logo else None
            
            # Resolve Meta Page details (Page Name and Page Logo)
            meta_page_id = details.meta_page_id if details else None
            meta_page_name = details.meta_page_name if details and details.meta_page_name else None
            page_name = meta_page_name or store_name
            user_avatar = details.user_avatar.url if (details and details.user_avatar) else None
            page_logo = (f"https://graph.facebook.com/{meta_page_id}/picture?type=large" if meta_page_id else None) or store_logo or user_avatar
            
            # Generate daily insights timeline based on actual campaign metrics and dates
            from datetime import timedelta
            num_days = min(7, max(1, duration_days))
            base_date = promo.created_at.date() if promo.created_at else timezone.now().date()
            
            insights_series = []
            for i in range(num_days):
                day_date = base_date + timedelta(days=i)
                if i == num_days - 1:
                    d_spent = amount_spent_float
                    d_views = views
                    d_clicks = clicks
                    d_sales = sales
                else:
                    factor = (i + 1) / num_days
                    d_spent = round(amount_spent_float * factor, 2)
                    d_views = int(views * factor)
                    d_clicks = int(clicks * factor)
                    d_sales = int(sales * factor)
                    
                insights_series.append({
                    'label': day_date.strftime('%b %d'),
                    'date': day_date.strftime('%Y-%m-%d'),
                    'spend': d_spent,
                    'views': d_views,
                    'clicks': d_clicks,
                    'sales': d_sales,
                })
            
            from api.templatetags.currency_tags import currency_symbol
            return JsonResponse({
                'success': True,
                'currency': currency,
                'currency_symbol': currency_symbol(currency),
                'promotion': {
                    'id': str(promo.id),
                    'title': promo.title,
                    'message': promo.message,
                    'status': promo.status,
                    'amount_spent': str(promo.amount_spent),
                    'sales_generated': sales,
                    'customers_gained': promo.customers_gained,
                    'profit_impact': str(promo.profit_impact),
                    'views': views,
                    'clicks': clicks,
                    'cpc': cpc,
                    'cpa': cpa,
                    'ctr': ctr,
                    'promote_type': promo.promote_type,
                    'action_type': promo.action_type,
                    'budget_per_day': str(promo.budget_per_day),
                    'duration_days': duration_days,
                    'remaining_days': remaining_days,
                    'total_budget': total_budget,
                    'remaining_budget': remaining_budget,
                    'cover_image': promo.cover_image,
                    'audience_type': promo.audience_type,
                    'custom_locations': promo.custom_locations,
                    'custom_age_min': promo.custom_age_min,
                    'custom_age_max': promo.custom_age_max,
                    'custom_interests': promo.custom_interests,
                    'fb_campaign_id': promo.fb_campaign_id,
                    'fb_adset_id': promo.fb_adset_id,
                    'fb_ad_id': promo.fb_ad_id,
                    'is_external': promo.is_external,
                    'amount_debited': str(promo.amount_debited),
                    'created_at': promo.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': promo.updated_at.strftime('%Y-%m-%d %H:%M:%S') if promo.updated_at else promo.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'page_name': page_name,
                    'page_logo': page_logo,
                    'store': {
                        'name': store_name,
                        'url': store_url,
                        'logo': store_logo,
                    },
                    'product': {
                        'id': str(promo.product.id) if promo.product else None,
                        'name': promo.product.item_name if promo.product else None,
                        'price': str(promo.product.item_amount) if promo.product else None,
                        'image': promo.product.images.first().image.url if promo.product and promo.product.images.exists() else None
                    } if promo.product else None,
                    'insights_series': insights_series,
                }
            })
        except GrowthPromotion.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Promotion not found'}, status=404)
            
    def patch(self, request, id):
        user = request.user
        
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user
            
        try:
            promo = GrowthPromotion.objects.get(id=id, user=owner)
            body_str = request.body.decode('utf-8') if isinstance(request.body, bytes) else (request.body or '{}')
            data = json.loads(body_str or '{}')
            
            if 'product_id' in data:
                product_id = data['product_id']
                if product_id:
                    from api.models import UserItems
                    product_obj = UserItems.objects.filter(id=product_id, user=owner).first()
                    promo.product = product_obj
                else:
                    promo.product = None
            if 'status' in data:
                new_status = data['status']
                if promo.fb_campaign_id:
                    try:
                        promo_owner_details = owner.details.first()
                        fb_service = FacebookAdsService(
                            user_access_token=promo_owner_details.meta_access_token if promo_owner_details else None,
                            user_page_id=promo_owner_details.meta_page_id if promo_owner_details else None,
                        )
                        fb_res = fb_service.update_ad_status(promo.fb_campaign_id, new_status)
                        if not fb_res.get('success'):
                            return JsonResponse({
                                'success': False,
                                'error': fb_res.get('error', 'Failed to update campaign status on Meta')
                            }, status=400)
                    except Exception as e:
                        return JsonResponse({'success': False, 'error': str(e)}, status=400)
                promo.status = new_status
            if 'title' in data:
                promo.title = data['title']
            if 'message' in data:
                promo.message = data['message']
            if 'promote_type' in data:
                promo.promote_type = data['promote_type']
            if 'action_type' in data:
                promo.action_type = data['action_type']
            budget_action_result = None
            if 'budget_per_day' in data:
                try:
                    new_budget = Decimal(str(data['budget_per_day']))
                except Exception:
                    return JsonResponse({'success': False, 'error': 'Invalid budget amount provided.'}, status=400)

                old_budget = Decimal(str(promo.budget_per_day or 0.00))
                promo_owner_details = owner.details.first()
                user_curr = (promo_owner_details.currency if promo_owner_details else 'USD') or 'USD'

                # Minimum $1.00 USD equivalent validation
                usd_rate = get_usd_to_local_exchange_rate(user_curr) or 1.0
                min_daily_budget = Decimal(str(round(1.0 * usd_rate, 2)))
                if new_budget < min_daily_budget:
                    return JsonResponse({
                        'success': False,
                        'error': f'Daily budget is too low. Minimum is {user_curr} {min_daily_budget:,.2f} ($1.00 USD equivalent) per day.'
                    }, status=400)

                if new_budget != old_budget:
                    duration = promo.duration_days if (promo.duration_days and promo.duration_days > 0) else 7
                    now = timezone.now()
                    created_at = promo.created_at or now
                    days_elapsed = max(0, (now - created_at).days)
                    remaining_days = max(1, duration - days_elapsed)

                    diff_per_day = new_budget - old_budget
                    diff_total = abs(diff_per_day) * Decimal(str(remaining_days))

                    if new_budget > old_budget:
                        # Increasing budget: verify available funds (ad credit + wallet balance)
                        has_funds, error_msg, err_status = check_ad_funds(owner, diff_total)
                        if not has_funds:
                            return JsonResponse({'success': False, 'error': error_msg}, status=err_status)

                    # Update Meta AdSet delivery budget
                    if promo.fb_adset_id:
                        try:
                            fb_service = FacebookAdsService(
                                user_access_token=promo_owner_details.meta_access_token if promo_owner_details else None,
                                user_page_id=promo_owner_details.meta_page_id if promo_owner_details else None,
                            )
                            fb_res = fb_service.update_ad_budget(promo.fb_adset_id, float(new_budget), user_currency=user_curr)
                            if not fb_res.get('success'):
                                return JsonResponse({
                                    'success': False,
                                    'error': f"Failed to update Meta adset budget: {fb_res.get('error', 'Unknown error')}"
                                }, status=400)
                        except Exception as fb_e:
                            return JsonResponse({
                                'success': False,
                                'error': f"Error communicating with Meta Ads: {str(fb_e)}"
                            }, status=400)

                    # Execute wallet debit or ad credit refund
                    business = owner.business_details.first()
                    if new_budget > old_budget:
                        debit_success, debit_err, debit_status = debit_ad_funds(
                            owner,
                            diff_total,
                            f'Budget Increase: {promo.title} (+{user_curr} {diff_per_day:,.2f}/day for {remaining_days} remaining days)'
                        )
                        if not debit_success:
                            return JsonResponse({'success': False, 'error': debit_err}, status=debit_status)
                        budget_action_result = {
                            'action': 'debited',
                            'amount': float(diff_total),
                            'diff_per_day': float(diff_per_day),
                            'remaining_days': remaining_days,
                            'message': f'{user_curr} {diff_total:,.2f} debited from your wallet for {remaining_days} remaining days.'
                        }
                    else:
                        if business:
                            business.ad_credit = (business.ad_credit or Decimal('0.00')) + diff_total
                            business.save(update_fields=['ad_credit'])

                        UserTransactions.objects.create(
                            user=owner,
                            trx_status='completed',
                            trx_amount=float(diff_total),
                            trx_type='ad_credit',
                            trx_currency=user_curr,
                            description=f'Budget Reduced: {promo.title} (Refunded {user_curr} {diff_total:,.2f} to Ad Credit for {remaining_days} remaining days)',
                            destination_id=owner.uniq_id,
                            user_collection_id='0'
                        )
                        budget_action_result = {
                            'action': 'refunded',
                            'amount': float(diff_total),
                            'diff_per_day': float(abs(diff_per_day)),
                            'remaining_days': remaining_days,
                            'message': f'{user_curr} {diff_total:,.2f} returned to your Ad Credit balance for {remaining_days} remaining days.'
                        }

                    promo.budget_per_day = new_budget
            if 'audience_type' in data:
                promo.audience_type = data['audience_type']
            if 'custom_locations' in data:
                promo.custom_locations = data['custom_locations']
            if 'custom_age_min' in data:
                promo.custom_age_min = data['custom_age_min']
            if 'custom_age_max' in data:
                promo.custom_age_max = data['custom_age_max']
            if 'custom_interests' in data:
                promo.custom_interests = data['custom_interests']
            if 'cover_image' in data:
                promo.cover_image = data['cover_image']
                
            promo.save()
            return JsonResponse({
                'success': True,
                'budget_action': budget_action_result
            })
        except GrowthPromotion.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Promotion not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def put(self, request, id):
        return self.patch(request, id)

    def delete(self, request, id):
        user = request.user
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user

        try:
            promo = GrowthPromotion.objects.get(id=id, user=owner)
            user_details = UserDetails.objects.filter(user=owner).first()
            currency = user_details.currency if user_details else 'NGN'

            # 1. Delete remotely on Meta
            meta_deleted = False
            meta_error = None
            if promo.fb_campaign_id:
                try:
                    from api.services.facebook_ads import FacebookAdsService
                    fb_service = FacebookAdsService(
                        user_access_token=user_details.meta_access_token if user_details else None,
                        user_page_id=user_details.meta_page_id if user_details else None,
                    )
                    fb_del = fb_service.delete_campaign(promo.fb_campaign_id)
                    meta_deleted = fb_del.get('success', False)
                    if not meta_deleted:
                        meta_error = fb_del.get('error')
                        fb_service.update_ad_status(promo.fb_campaign_id, 'paused')
                except Exception as fb_e:
                    meta_error = str(fb_e)
                    logger.warning(f"[GrowthPromotionDetailAPI] Error deleting Meta campaign {promo.fb_campaign_id}: {fb_e}")

            # 2. Strict Refund Cap: 0.00 for external, capped at amount_debited - amount_spent for internal
            remaining_refund = calculate_refundable_budget(promo)

            # 3. Credit remaining funds to Ad Credit
            business = owner.business_details.first()
            if business and remaining_refund > Decimal('0.00'):
                business.ad_credit = (business.ad_credit or Decimal('0.00')) + remaining_refund
                business.save(update_fields=['ad_credit'])

            if remaining_refund > Decimal('0.00'):
                UserTransactions.objects.create(
                    user=owner,
                    trx_status='completed',
                    trx_amount=float(remaining_refund),
                    trx_type='ad_credit',
                    trx_currency=currency,
                    description=f'Campaign Deleted: {promo.title} (Refunded {currency} {remaining_refund:,.2f} to Ad Credit)',
                    destination_id=owner.uniq_id,
                    user_collection_id='0'
                )

            promo_title = promo.title
            fb_id = promo.fb_campaign_id
            is_external = promo.is_external
            promo.delete()

            return JsonResponse({
                'success': True,
                'message': f'Campaign "{promo_title}" deleted successfully.',
                'meta_deleted': meta_deleted,
                'meta_error': meta_error,
                'refunded_amount': float(remaining_refund),
                'is_external': is_external,
                'currency': currency
            })
        except GrowthPromotion.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Promotion not found or unauthorized.'}, status=404)
        except Exception as e:
            logger.exception(f"[GrowthPromotionDetailAPI] Unexpected error deleting campaign: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


@method_decorator(login_required, name='dispatch')
class GrowthPromotionsBatchDeleteAPI(View):
    """
    Handles bulk deletion of campaigns.
    Remotely deletes each campaign on Meta via Graph API,
    strictly enforces zero refund on external campaigns,
    refunds unspent funds from FlezPay-funded campaigns into Store Ad Credit,
    and removes the database records.
    """
    def post(self, request):
        user = request.user
        if user.user_type in ['manager', 'staff'] and user.business_owner:
            owner = user.business_owner
        else:
            owner = user

        try:
            body_str = request.body.decode('utf-8') if isinstance(request.body, bytes) else (request.body or '{}')
            data = json.loads(body_str or '{}')
            promo_ids = data.get('promotion_ids', [])
            
            if not promo_ids or not isinstance(promo_ids, list):
                return JsonResponse({'success': False, 'error': 'No promotion IDs provided for batch deletion.'}, status=400)
            
            promos = list(GrowthPromotion.objects.filter(id__in=promo_ids, user=owner))
            if not promos:
                return JsonResponse({'success': False, 'error': 'No matching promotions found or unauthorized.'}, status=404)

            user_details = UserDetails.objects.filter(user=owner).first()
            currency = user_details.currency if user_details else 'NGN'

            # Initialize Meta Ads Service
            fb_service = None
            try:
                from api.services.facebook_ads import FacebookAdsService
                fb_service = FacebookAdsService(
                    user_access_token=user_details.meta_access_token if user_details else None,
                    user_page_id=user_details.meta_page_id if user_details else None,
                )
            except Exception as fb_init_err:
                logger.warning(f"[GrowthPromotionsBatchDeleteAPI] Meta service init error: {fb_init_err}")

            deleted_count = 0
            total_refunded = Decimal('0.00')
            external_count = 0
            internal_count = 0
            meta_deleted_count = 0

            for promo in promos:
                # 1. Delete remotely on Meta
                if promo.fb_campaign_id and fb_service:
                    try:
                        fb_del = fb_service.delete_campaign(promo.fb_campaign_id)
                        if fb_del.get('success'):
                            meta_deleted_count += 1
                        else:
                            fb_service.update_ad_status(promo.fb_campaign_id, 'paused')
                    except Exception as fb_err:
                        logger.warning(f"[GrowthPromotionsBatchDeleteAPI] Error deleting Meta campaign {promo.fb_campaign_id}: {fb_err}")

                # 2. Strict Refund Cap
                ref = calculate_refundable_budget(promo)
                if ref > Decimal('0.00'):
                    total_refunded += ref

                if promo.is_external:
                    external_count += 1
                else:
                    internal_count += 1

                promo.delete()
                deleted_count += 1

            # 3. Credit remaining funds to Ad Credit
            business = owner.business_details.first()
            if business and total_refunded > Decimal('0.00'):
                business.ad_credit = (business.ad_credit or Decimal('0.00')) + total_refunded
                business.save(update_fields=['ad_credit'])

                UserTransactions.objects.create(
                    user=owner,
                    trx_status='completed',
                    trx_amount=float(total_refunded),
                    trx_type='ad_credit',
                    trx_currency=currency,
                    description=f'Batch Campaign Delete: {deleted_count} campaign(s) (Refunded {currency} {total_refunded:,.2f} to Ad Credit)',
                    destination_id=owner.uniq_id,
                    user_collection_id='0'
                )

            if total_refunded > Decimal('0.00'):
                msg = f'Successfully deleted {deleted_count} campaign(s). Refunded {currency} {total_refunded:,.2f} to your Ad Credit.'
            else:
                msg = f'Successfully deleted {deleted_count} campaign(s) from Meta and FlezPay.'

            return JsonResponse({
                'success': True,
                'deleted_count': deleted_count,
                'external_count': external_count,
                'internal_count': internal_count,
                'meta_deleted_count': meta_deleted_count,
                'total_refunded': float(total_refunded),
                'currency': currency,
                'message': msg
            })
        except Exception as e:
            logger.exception(f"[GrowthPromotionsBatchDeleteAPI] Error in batch delete: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@method_decorator(login_required, name='dispatch')
class GrowthEstimateReachAPI(View):
    """
    Calls Facebook Ads SDK to estimate reach based on budget and targeting.
    """
    def post(self, request):
        try:
            data = json.loads(request.body)
            budget = data.get('budget_per_day', 5.0)
            audience_type = data.get('audience_type', 'near')
            custom_locations = data.get('custom_locations')
            custom_age_min = data.get('custom_age_min')
            custom_age_max = data.get('custom_age_max')
            custom_interests = data.get('custom_interests')

            user = request.user
            if user.user_type in ['manager', 'staff'] and user.business_owner:
                owner = user.business_owner
            else:
                owner = user

            user_details = UserDetails.objects.filter(user=owner).first()
            business = owner.business_details.first()
            user_currency = (user_details.currency if user_details else 'USD') or 'USD'

            fb_service = FacebookAdsService(
                user_access_token=user_details.meta_access_token if user_details else None,
                user_page_id=user_details.meta_page_id if user_details else None,
            )
            result = fb_service.get_delivery_estimate(
                budget, audience_type,
                business=business,
                user_details=user_details,
                custom_locations=custom_locations,
                custom_age_min=custom_age_min,
                custom_age_max=custom_age_max,
                custom_interests=custom_interests,
                user_currency=user_currency
            )
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


@method_decorator(login_required, name='dispatch')
class GrowthGenerateCampaignAPI(View):
    """
    Generate AI campaign copy (title + message) using the local Ollama model.
    Accepts POST with campaign context and returns structured content.
    """

    PROMOTE_TYPE_LABELS = {
        'product': 'a specific product',
        'group': 'a group/category of products',
        'store': 'the entire store',
        'discount': 'a discount or special offer',
        'new': 'a new launch or upcoming event',
    }
    ACTION_TYPE_LABELS = {
        'buy': 'make a purchase',
        'visit': 'visit the store or website',
        'message': 'send a message to the business',
        'call': 'call the business',
        'learn': 'learn more about the business',
    }
    AUDIENCE_LABELS = {
        'near': 'people near the business location',
        'past': 'past customers who have bought before',
        'similar': 'people with similar interests to existing customers',
        'custom': 'a custom-defined audience',
    }
    TONE_LABELS = {
        'friendly': 'friendly and casual',
        'professional': 'professional and trustworthy',
        'exciting': 'exciting, urgent and energetic',
        'premium': 'premium, luxury and exclusive',
    }

    def post(self, request):
        try:
            data = json.loads(request.body)

            user = request.user
            if user.user_type in ['manager', 'staff'] and user.business_owner:
                owner = user.business_owner
            else:
                owner = user

            details = owner.details.first()
            business_details = owner.business_details.first()
            business_name = business_details.business_name if business_details else 'our business'
            currency = details.currency if details else 'USD'

            promote_type = data.get('promote_type', 'store')
            action_type = data.get('action_type', 'buy')
            audience_type = data.get('audience_type', 'near')
            tone = data.get('tone', 'friendly')
            product_name = data.get('product_name', '')
            budget = data.get('budget', 5)
            custom_instructions = data.get('custom_instructions', '').strip()

            promote_label = self.PROMOTE_TYPE_LABELS.get(promote_type, promote_type)
            action_label = self.ACTION_TYPE_LABELS.get(action_type, action_type)
            audience_label = self.AUDIENCE_LABELS.get(audience_type, audience_type)
            tone_label = self.TONE_LABELS.get(tone, tone)

            subject = product_name if product_name else promote_label

            prompt = (
                f"You are an expert social media marketing copywriter. "
                f"Write a short, punchy social media promotion for a business called '{business_name}'.\n\n"
                f"Campaign details:\n"
                f"- What is being promoted: {subject}\n"
                f"- Goal: Get the audience to {action_label}\n"
                f"- Target audience: {audience_label}\n"
                f"- Daily budget: {currency} {budget}\n"
                f"- Tone/style: {tone_label}\n"
            )
            if custom_instructions:
                prompt += f"- Additional instructions: {custom_instructions}\n"

            prompt += (
                "\nRespond ONLY in the following JSON format (no markdown, no explanation):\n"
                '{"title": "<short catchy headline, max 10 words>", "message": "<body copy, 2-3 sentences max>"}'
            )

            import ollama
            import os
            model_name = os.environ.get('OLLAMA_MODEL', 'gemma4:latest')
            response = ollama.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.8}
            )

            raw = response['message']['content'].strip()

            # Strip any <think>...</think> blocks from models that output reasoning
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

            # Extract JSON from the response
            json_match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                title = result.get('title', '').strip()
                message = result.get('message', '').strip()
            else:
                # Fallback: split by newline
                lines = [l.strip() for l in raw.split('\n') if l.strip()]
                title = lines[0] if lines else 'New Promotion'
                message = ' '.join(lines[1:]) if len(lines) > 1 else raw

            return JsonResponse({
                'success': True,
                'title': title,
                'message': message,
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)



@method_decorator(login_required, name='dispatch')
class GrowthUploadMediaAPI(View):
    """
    Upload a campaign cover image or video to Cloudflare R2.
    Accepts multipart/form-data with a 'file' field.
    Returns the public CDN URL.
    """
    ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
    ALLOWED_VIDEO_TYPES = {'video/mp4', 'video/webm', 'video/ogg', 'video/quicktime'}
    MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB
    MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100 MB

    def post(self, request):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'success': False, 'error': 'No file provided.'}, status=400)

        content_type = uploaded.content_type or ''
        is_image = content_type in self.ALLOWED_IMAGE_TYPES
        is_video = content_type in self.ALLOWED_VIDEO_TYPES

        if not is_image and not is_video:
            return JsonResponse({
                'success': False,
                'error': f'Unsupported file type: {content_type}. Please upload a JPEG, PNG, WebP, MP4, or WebM file.'
            }, status=400)

        max_bytes = self.MAX_VIDEO_BYTES if is_video else self.MAX_IMAGE_BYTES
        if uploaded.size > max_bytes:
            limit_label = '100 MB' if is_video else '10 MB'
            return JsonResponse({
                'success': False,
                'error': f'File is too large. Maximum allowed size is {limit_label}.'
            }, status=400)

        try:
            ext = uploaded.name.rsplit('.', 1)[-1].lower() if '.' in uploaded.name else 'bin'
            filename = f"{uuid.uuid4().hex}.{ext}"

            storage = GrowthMediaStorage()
            # Attach content_type so GrowthMediaStorage can decide whether to compress
            uploaded.content_type = content_type
            saved_name = storage.save(filename, uploaded)
            cdn_url = storage.url(saved_name)

            return JsonResponse({'success': True, 'url': cdn_url})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@method_decorator(login_required, name='dispatch')
class GrowthGenerateImageAPI(View):
    """
    Generate a campaign cover image using the Gemini Imagen API,
    then upload it directly to Cloudflare R2 and return the CDN URL.
    """

    def post(self, request):
        try:
            data = json.loads(request.body)
            prompt = data.get('prompt', '').strip()

            if not prompt:
                return JsonResponse({'success': False, 'error': 'Image prompt is required.'}, status=400)

            # Balance Check and Ad Credit / Wallet Deduction Logic
            settings = SiteSettings.load()
            cost_usd = settings.user_image_generation_cost_usd or 0.05
            
            user_details = UserDetails.objects.filter(user=request.user).first()
            user_currency = user_details.currency if user_details else 'NGN'
            rate = get_usd_to_local_exchange_rate(user_currency)
            cost_in_local = float(cost_usd) * rate
            
            has_funds, error_msg, err_status = check_ad_funds(request.user, cost_in_local, require_min_usd_rate=True)
            if not has_funds:
                return JsonResponse({'success': False, 'error': error_msg}, status=err_status)

            api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY', '')
            if not api_key:
                return JsonResponse({
                    'success': False,
                    'error': 'Image generation is not configured on this server. Please upload your own image instead.'
                }, status=503)
            
            client = genai.Client(api_key=api_key)

            # Get configured model from SiteSettings
            try:
                settings = SiteSettings.objects.first()
                model_name = settings.ai_generation_model if settings and settings.ai_generation_model else 'gemini-3-pro-image'
            except Exception:
                model_name = 'gemini-3-pro-image'

            try:
                result = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
            except Exception as e:
                error_msg = str(e)
                try:
                    import traceback
                    SystemErrorLog.objects.create(
                        log_type='gemini',
                        message=error_msg,
                        traceback=traceback.format_exc(),
                        user=request.user,
                    )
                except Exception:
                    pass
                if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                    return JsonResponse({'success': False, 'error': 'Not available right now', 'raw_error': error_msg}, status=402)
                return JsonResponse({'success': False, 'error': f'Image generation failed: {error_msg}', 'raw_error': error_msg}, status=500)

            image_bytes = None
            mime_type = 'image/png'
            
            if result.candidates and result.candidates[0].content.parts:
                for part in result.candidates[0].content.parts:
                    if part.inline_data:
                        image_bytes = part.inline_data.data
                        mime_type = part.inline_data.mime_type
                        break
                    elif getattr(part, 'image', None):
                        image_bytes = part.image.image_bytes
                        mime_type = part.image.mime_type
                        break

            if not image_bytes:
                return JsonResponse({'success': False, 'error': 'No image was generated. Try a different prompt.'})

            # Debit ad credit first, fallback to user wallet
            debit_ad_funds(request.user, cost_in_local, 'AI Image Generation')

            ext = 'png' if 'png' in mime_type else 'jpg'

            # Prepare for Cloudflare R2 upload
            filename = f"{uuid.uuid4().hex}.{ext}"
            file_obj = ContentFile(image_bytes, name=filename)
            file_obj.content_type = mime_type

            storage = GrowthMediaStorage()
            saved_name = storage.save(filename, file_obj)
            cdn_url = storage.url(saved_name)

            return JsonResponse({'success': True, 'image_url': cdn_url, 'media_url': cdn_url, 'is_video': False})

        except ImportError:
            return JsonResponse({
                'success': False,
                'error': 'Google AI library not installed. Please upload your own image instead.'
            }, status=503)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@method_decorator(login_required, name='dispatch')
class GrowthGenerateVideoAPI(View):
    """
    Generate a campaign promotional video using Google Veo (via Google GenAI),
    then upload it directly to Cloudflare R2 and return the CDN URL.
    """

    def post(self, request):
        try:
            data = json.loads(request.body)
            prompt = data.get('prompt', '').strip()

            if not prompt:
                return JsonResponse({'success': False, 'error': 'Video prompt is required.'}, status=400)

            # Balance Check and Ad Credit / Wallet Deduction Logic
            settings = SiteSettings.load()
            cost_usd = float(settings.user_video_generation_cost_usd or 0.20)
            
            user_details = UserDetails.objects.filter(user=request.user).first()
            user_currency = user_details.currency if user_details else 'NGN'
            rate = get_usd_to_local_exchange_rate(user_currency)
            cost_in_local = float(cost_usd) * rate
            
            has_funds, error_msg, err_status = check_ad_funds(request.user, cost_in_local, require_min_usd_rate=True)
            if not has_funds:
                return JsonResponse({'success': False, 'error': error_msg}, status=err_status)

            api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY', '')
            if not api_key:
                return JsonResponse({
                    'success': False,
                    'error': 'Video generation is not configured on this server. Please upload your own video instead.'
                }, status=503)
            
            client = genai.Client(api_key=api_key)

            model_name = settings.ai_video_generation_model if settings and settings.ai_video_generation_model else 'veo-3.1-generate-preview'

            try:
                # Launch video generation operation
                operation = client.models.generate_videos(
                    model=model_name,
                    source=types.GenerateVideosSource(prompt=prompt),
                    config=types.GenerateVideosConfig(
                        aspect_ratio='16:9',
                        duration_seconds=6,
                    ) if hasattr(types, 'GenerateVideosConfig') else None
                )

                # Poll operation until complete
                import time
                poll_start = time.time()
                while not operation.done:
                    time.sleep(5)
                    operation = client.operations.get(operation)
                    if time.time() - poll_start > 180:
                        raise TimeoutError("Video generation timed out. Please try again.")

            except Exception as e:
                error_msg = str(e)
                try:
                    import traceback
                    SystemErrorLog.objects.create(
                        log_type='gemini',
                        message=f"Video Gen Error: {error_msg}",
                        traceback=traceback.format_exc(),
                        user=request.user,
                    )
                except Exception:
                    pass
                if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                    return JsonResponse({
                        'success': False, 
                        'error': 'Video generation is temporarily busy or quota limited on the AI provider. Please try again in a moment or upload your own video.', 
                        'raw_error': error_msg
                    }, status=402)
                return JsonResponse({'success': False, 'error': f'Video generation failed: {error_msg}', 'raw_error': error_msg}, status=500)

            video_bytes = None
            mime_type = 'video/mp4'

            if getattr(operation, 'result', None) and getattr(operation.result, 'generated_videos', None):
                generated_video = operation.result.generated_videos[0]
                if getattr(generated_video.video, 'video_bytes', None):
                    video_bytes = generated_video.video.video_bytes
                    mime_type = getattr(generated_video.video, 'mime_type', 'video/mp4') or 'video/mp4'
                elif getattr(generated_video.video, 'uri', None):
                    import requests
                    resp = requests.get(generated_video.video.uri, timeout=30)
                    if resp.status_code == 200:
                        video_bytes = resp.content
                        mime_type = resp.headers.get('Content-Type', 'video/mp4')

            if not video_bytes:
                return JsonResponse({'success': False, 'error': 'No video was generated. Try a different prompt.'})

            # Debit ad credit first, fallback to user wallet
            debit_ad_funds(request.user, cost_in_local, 'AI Video Generation')

            filename = f"{uuid.uuid4().hex}.mp4"
            file_obj = ContentFile(video_bytes, name=filename)
            file_obj.content_type = mime_type

            storage = GrowthMediaStorage()
            saved_name = storage.save(filename, file_obj)
            cdn_url = storage.url(saved_name)

            return JsonResponse({'success': True, 'video_url': cdn_url, 'media_url': cdn_url, 'is_video': True})

        except ImportError:
            return JsonResponse({
                'success': False,
                'error': 'Google AI library not installed. Please upload your own video instead.'
            }, status=503)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

from api.services.ai_promotion_service import AIPromotionService

@method_decorator(login_required, name='dispatch')
class GrowthAIGeneratorAPI(View):
    """
    Endpoint for the AI Promotion Creator to generate an entire campaign using AI.
    Expects POST with preferences: promote, goal, style.
    Returns structured JSON of the promotion plan.
    """
    def post(self, request):
        try:
            body = json.loads(request.body)
            preferences = body.get('preferences', {})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)

        try:
            import uuid
            task_id = str(uuid.uuid4())
            from api.tasks import generate_ai_promotion_task
            generate_ai_promotion_task.delay(request.user.id, preferences, task_id)
            return JsonResponse({'success': True, 'task_id': task_id})
        except Exception as e:
            import traceback
            error_msg = str(e)
            try:
                SystemErrorLog.objects.create(
                    log_type='growth_ai_creator',
                    message=error_msg,
                    traceback=traceback.format_exc(),
                    user=request.user,
                )
            except Exception:
                pass
            return JsonResponse({'success': False, 'error': error_msg}, status=500)


@method_decorator(login_required, name='dispatch')
class GrowthAIGeneratorStatusAPI(View):
    """
    Check the status of an ongoing AI campaign generation task.
    """
    def get(self, request, task_id):
        from django.core.cache import cache
        plan_or_error = cache.get(f"ai_plan_{task_id}")
        
        if plan_or_error is None:
            return JsonResponse({'status': 'pending'})
            
        if isinstance(plan_or_error, dict) and 'error' in plan_or_error:
            # Check if it was a saved error
            if len(plan_or_error) == 1:
                return JsonResponse({'status': 'failed', 'error': plan_or_error['error']})
                
        return JsonResponse({'status': 'completed', 'plan': plan_or_error})
