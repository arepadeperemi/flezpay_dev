import os
import tempfile
import requests
import logging
import json
import re
import base64
from decimal import Decimal

logger = logging.getLogger(__name__)
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.adcreative import AdCreative
from facebook_business.adobjects.adimage import AdImage
from facebook_business.adobjects.ad import Ad
from facebook_business.exceptions import FacebookRequestError

COUNTRY_NAME_TO_CODE = {
    'nigeria': 'NG', 'united states': 'US', 'usa': 'US', 'united kingdom': 'GB', 'uk': 'GB',
    'ghana': 'GH', 'kenya': 'KE', 'south africa': 'ZA', 'canada': 'CA', 'australia': 'AU',
    'germany': 'DE', 'france': 'FR', 'italy': 'IT', 'spain': 'ES', 'india': 'IN',
    'united arab emirates': 'AE', 'uae': 'AE', 'rwanda': 'RW', 'uganda': 'UG',
    'tanzania': 'TZ', 'egypt': 'EG', 'morocco': 'MA', 'brazil': 'BR', 'mexico': 'MX',
}
CURRENCY_TO_COUNTRY = {
    'NGN': 'NG', 'USD': 'US', 'GBP': 'GB', 'GHS': 'GH', 'KES': 'KE',
    'ZAR': 'ZA', 'CAD': 'CA', 'AUD': 'AU', 'EUR': 'DE', 'RWF': 'RW', 'UGX': 'UG'
}

def clean_meta_name(text, max_length=100):
    """
    Cleans and formats names for Meta objects (Campaign, AdSet, Creative, Ad).
    Strips brackets, internal tags, and emojis that can cause corrupted unicode replacement
    characters or cluttered names in the Facebook Ads Manager dashboard.
    """
    if not text:
        return ""
    # Strip emojis and symbol ranges
    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010ffff"
        "\u200d"
        "\u2600-\u26ff"
        "\u2700-\u27bf"
        "\ufe00-\ufe0f"
        "]+",
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub('', str(text))
    # Remove bracketed prefixes/tags like [Store Name] or [promo:...]
    cleaned = re.sub(r'\[.*?\]', '', cleaned)
    # Remove any stray brackets or braces
    cleaned = cleaned.replace('[', '').replace(']', '').replace('{', '').replace('}', '')
    # Collapse multiple spaces or dashes
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'^[ \-_•]+|[ \-_•]+$', '', cleaned)
    return cleaned[:max_length].strip()

class FacebookAdsService:
    def __init__(self, user_access_token=None, user_page_id=None):
        self.app_id = os.environ.get('FACEBOOK_APP_ID')
        self.app_secret = os.environ.get('FACEBOOK_APP_SECRET')
        # Ad account operations (Campaign, AdSet, Creative, Ad) require the system token
        # which owns and has ads_management rights on the central platform ad account.
        self.access_token = os.environ.get('FACEBOOK_TOKEN')
        self.user_access_token = user_access_token
        self.ad_account_id = os.environ.get('FACEBOOK_AD_ACCOUNT_ID', 'act_1035234889122971')
        # Use the user's connected page if provided, otherwise fall back to system page
        self.page_id = user_page_id or os.environ.get('FACEBOOK_PAGE_ID', '103116665016386')

        if self.app_id and self.app_secret and self.access_token:
            FacebookAdsApi.init(self.app_id, self.app_secret, self.access_token)

        self.account = AdAccount(self.ad_account_id)

    def get_ad_account_currency(self):
        """Returns the currency of the target Facebook ad account (cached)."""
        cache_key = f'fb_ad_acc_curr_{self.ad_account_id}'
        curr = cache.get(cache_key)
        if not curr:
            try:
                acc = AdAccount(self.ad_account_id)
                data = acc.api_get(fields=['currency'])
                curr = data.get('currency') or 'NGN'
                cache.set(cache_key, curr, 86400)
            except Exception:
                curr = os.environ.get('FACEBOOK_AD_ACCOUNT_CURRENCY', 'NGN')
        return curr or 'NGN'

    def _resolve_business_countries(self, business=None, user_details=None):
        """Resolves the 2-letter ISO country codes for a business."""
        countries = []
        if business and getattr(business, 'store_countries', None):
            sc = business.store_countries
            if isinstance(sc, str):
                try:
                    sc = json.loads(sc)
                except Exception:
                    sc = [c.strip() for c in sc.split(',') if c.strip()]
            if isinstance(sc, list):
                for item in sc:
                    code = str(item).strip()
                    if len(code) == 2 and code.isalpha():
                        countries.append(code.upper())
                    else:
                        mapped = COUNTRY_NAME_TO_CODE.get(code.lower())
                        if mapped:
                            countries.append(mapped)

        if not countries and user_details and getattr(user_details, 'user_country', None):
            uc = str(user_details.user_country).strip()
            if len(uc) == 2 and uc.isalpha():
                countries.append(uc.upper())
            else:
                mapped = COUNTRY_NAME_TO_CODE.get(uc.lower())
                if mapped:
                    countries.append(mapped)

        if not countries and user_details and getattr(user_details, 'currency', None):
            curr = str(user_details.currency).strip().upper()
            mapped = CURRENCY_TO_COUNTRY.get(curr)
            if mapped:
                countries.append(mapped)

        if not countries:
            countries = ['NG']

        seen = set()
        deduped = []
        for c in countries:
            if c not in seen:
                seen.add(c)
                deduped.append(c)
        return deduped

    def _resolve_business_coordinates(self, business=None, default_country='NG'):
        """Attempts to resolve lat/lon coordinates for a business location."""
        if not business:
            return None
        address = getattr(business, 'store_pickup_address', None)
        if not address and getattr(business, 'store_pickup_locations', None):
            locs = business.store_pickup_locations
            if isinstance(locs, dict):
                for k, v in locs.items():
                    if isinstance(v, dict) and v.get('address'):
                        address = v.get('address')
                        break
        if not address:
            return None

        cache_key = f'biz_coords_{business.id}_{hash(address)}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            query = f"{address}, {default_country}"
            resp = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={'q': query, 'format': 'json', 'limit': 1},
                headers={'User-Agent': 'FlezPay-Ads/1.0'},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    coords = {
                        'latitude': float(data[0]['lat']),
                        'longitude': float(data[0]['lon']),
                        'radius': 15,
                        'distance_unit': 'kilometer'
                    }
                    cache.set(cache_key, coords, 86400 * 7)
                    return coords
        except Exception as e:
            logger.warning(f"[FacebookAdsService] Geocoding address '{address}' failed: {e}")
        return None

    def _get_targeting_spec(self, audience_type, business=None, user_details=None, custom_locations=None, custom_age_min=None, custom_age_max=None, custom_interests=None):
        """Construct targeting spec based on audience preferences and business location."""
        target_countries = self._resolve_business_countries(business, user_details)
        geo_locations = {'countries': target_countries}

        if audience_type == 'custom' and custom_locations:
            try:
                coords = []
                for pair in custom_locations.split('|'):
                    if ',' in pair:
                        lat_str, lng_str = pair.split(',', 1)
                        coords.append({
                            'latitude': float(lat_str.strip()),
                            'longitude': float(lng_str.strip()),
                            'radius': 15,
                            'distance_unit': 'kilometer'
                        })
                if coords:
                    geo_locations = {'custom_locations': coords}
            except Exception as e:
                logger.warning(f"[FacebookAdsService] Error parsing custom_locations '{custom_locations}': {e}")
        elif audience_type == 'near':
            biz_coords = self._resolve_business_coordinates(business, target_countries[0] if target_countries else 'NG')
            if biz_coords:
                geo_locations = {'custom_locations': [biz_coords]}
            else:
                geo_locations = {'countries': target_countries}
        else:
            # 'past', 'similar', or standard: target the business's country
            geo_locations = {'countries': target_countries}

        targeting = {
            'geo_locations': geo_locations,
            'age_min': custom_age_min or 18,
            'age_max': custom_age_max or 65,
            'targeting_automation': {'advantage_audience': 0},
        }

        return targeting

    def get_delivery_estimate(self, budget_per_day, audience_type, business=None, user_details=None, custom_locations=None, custom_age_min=None, custom_age_max=None, custom_interests=None, user_currency='USD'):
        """
        Calls Facebook's delivery estimate endpoint.
        budget_per_day is in user_currency units (e.g. 5.00)
        """
        from api.growth_views import get_usd_to_local_exchange_rate
        user_rate = get_usd_to_local_exchange_rate(user_currency) or 1.0
        acc_currency = self.get_ad_account_currency()
        acc_rate = get_usd_to_local_exchange_rate(acc_currency) or 1.0

        try:
            targeting = self._get_targeting_spec(
                audience_type,
                business=business,
                user_details=user_details,
                custom_locations=custom_locations,
                custom_age_min=custom_age_min,
                custom_age_max=custom_age_max,
                custom_interests=custom_interests
            )
            
            # Convert user budget to USD then to Ad Account currency
            budget_usd = float(budget_per_day) / user_rate
            budget_in_acc = budget_usd * acc_rate
            budget_cents = int(round(budget_in_acc * 100))
            
            # Minimum check: at least 1.00 USD equivalent in ad account currency
            min_budget_cents = int(round(1.0 * acc_rate * 100))
            if budget_cents < min_budget_cents:
                budget_cents = min_budget_cents
            
            params = {
                'optimization_goal': 'REACH',
                'targeting_spec': targeting,
                'daily_budget': budget_cents,
            }
            
            estimates = self.account.get_delivery_estimate(params=params)
            if estimates and len(estimates) > 0:
                est = estimates[0]
                daily_outcomes = est.get('daily_outcomes_curve', [])
                
                reach_min = 0
                reach_max = 0
                if daily_outcomes:
                    closest_point = min(daily_outcomes, key=lambda p: abs(p.get('spend', 0) - budget_cents))
                    reach_estimate = closest_point.get('reach', 0)
                    reach_min = int(reach_estimate * 0.8)
                    reach_max = int(reach_estimate * 1.2)
                else:
                    base_reach = int(budget_usd * 300)
                    reach_min = int(base_reach * 0.8)
                    reach_max = int(base_reach * 1.2)
                    
                    mau_upper = est.get('estimate_mau_upper_bound', 0)
                    if mau_upper > 0:
                        reach_max = min(reach_max, mau_upper)
                        reach_min = min(reach_min, reach_max)
                
                return {
                    'success': True,
                    'reach_min': reach_min,
                    'reach_max': reach_max,
                    'clicks_min': int(reach_min * 0.01),
                    'clicks_max': int(reach_max * 0.02)
                }
            
            return {'success': False, 'error': 'No estimate returned'}
        except Exception as e:
            budget_usd = float(budget_per_day) / user_rate
            base_reach = int(budget_usd * 300)
            return {
                'success': True,
                'reach_min': int(base_reach * 0.8),
                'reach_max': int(base_reach * 1.2),
                'clicks_min': int(base_reach * 0.008),
                'clicks_max': int(base_reach * 0.024)
            }

    def upload_image(self, image_source):
        """Downloads/decodes an image from URL or base64 and uploads it to Facebook Ads."""
        if not image_source:
            return None
        tmp_name = None
        local_path = None
        try:
            image_source_str = str(image_source).strip()
            if image_source_str.startswith('data:image'):
                # Base64 data URI
                header, encoded = image_source_str.split(',', 1)
                data = base64.b64decode(encoded)
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    tmp.write(data)
                    tmp_name = tmp.name
            elif image_source_str.startswith('http://') or image_source_str.startswith('https://'):
                res = requests.get(image_source_str, timeout=15)
                res.raise_for_status()
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    tmp.write(res.content)
                    tmp_name = tmp.name
            elif image_source_str.startswith('/'):
                # Local filesystem path
                local_path = os.path.join(settings.BASE_DIR, image_source_str.lstrip('/'))
                if not os.path.exists(local_path):
                    local_path = os.path.join(settings.MEDIA_ROOT, image_source_str.replace('/media/', ''))
                if os.path.exists(local_path):
                    tmp_name = local_path
                else:
                    logger.error(f"[FacebookAdsService] Local image not found: {image_source_str}")
                    return None
            else:
                logger.error(f"[FacebookAdsService] Unsupported image source format: {image_source_str[:30]}")
                return None

            image = AdImage(parent_id=self.ad_account_id)
            image[AdImage.Field.filename] = tmp_name
            image.remote_create()

            if tmp_name and tmp_name != local_path:
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass
            img_hash = image[AdImage.Field.hash]
            logger.info(f"[FacebookAdsService] Successfully uploaded image to Meta, hash={img_hash}")
            return img_hash
        except Exception as e:
            logger.error(f"[FacebookAdsService] Failed to upload image to Meta: {e}", exc_info=True)
            if tmp_name and tmp_name != local_path and os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass
            return None

    def create_ad_campaign_flow(self, promotion):
        """Creates the full Campaign -> AdSet -> Ad flow, scoped to the promotion's user/store."""
        created_campaign = None
        try:
            owner = promotion.user
            user_details = owner.details.first()
            user_currency = (user_details.currency if user_details else 'USD') or 'USD'

            # Dynamically calculate the minimum daily budget as 1.00 USD equivalent in the user's currency
            from api.growth_views import get_usd_to_local_exchange_rate
            rate_to_user_curr = get_usd_to_local_exchange_rate(user_currency) or 1.0
            min_user_budget = round(1.0 * rate_to_user_curr, 2)

            user_budget = float(promotion.budget_per_day)
            if user_budget < min_user_budget:
                return {
                    'success': False,
                    'error': f'Budget too low. Minimum is {user_currency} {min_user_budget:,.2f} ($1.00 USD equivalent) per day (got {user_currency} {user_budget:,.2f}).'
                }

            # Convert user budget to the target ad account's currency and lowest denomination (e.g. kobo/cents)
            ad_account_currency = self.get_ad_account_currency()
            rate_to_ad_acc = get_usd_to_local_exchange_rate(ad_account_currency) or 1.0

            budget_usd = user_budget / rate_to_user_curr
            budget_in_ad_acc = budget_usd * rate_to_ad_acc
            budget_lowest_unit = int(round(budget_in_ad_acc * 100))

            min_ad_acc_unit = int(round(1.0 * rate_to_ad_acc * 100))
            if budget_lowest_unit < min_ad_acc_unit:
                budget_lowest_unit = min_ad_acc_unit

            # Identify the store/user for naming and labelling
            business = owner.business_details.first()
            store_name = (business.business_name or business.store_name or owner.username) if business else str(owner.uniq_id)

            # Clean and format names to avoid bracket clutter, hash tags, and corrupted emojis in Meta Ads Manager
            clean_title = clean_meta_name(promotion.title) or "Special Promotion"
            clean_store = clean_meta_name(store_name)
            campaign_name = f"{clean_store} • {clean_title}" if clean_store and clean_store.lower() not in clean_title.lower() else clean_title
            campaign_name = campaign_name[:100]
            adset_name = f"{clean_title} - Ad Set"[:100]
            creative_name = f"{clean_title} - Creative"[:100]
            ad_name = f"{clean_title} - Ad"[:100]

            # 1. Create Campaign
            campaign = Campaign(parent_id=self.ad_account_id)
            campaign.update({
                Campaign.Field.name: campaign_name,
                Campaign.Field.objective: 'OUTCOME_AWARENESS',
                Campaign.Field.status: Campaign.Status.paused if promotion.status == 'draft' else Campaign.Status.active,
                Campaign.Field.special_ad_categories: [],
                'is_adset_budget_sharing_enabled': False,
            })
            campaign.remote_create()
            created_campaign = campaign
            fb_campaign_id = campaign[Campaign.Field.id]

            # 2. Create Ad Set with location targeting scoped to business
            targeting = self._get_targeting_spec(
                promotion.audience_type,
                business=business,
                user_details=user_details,
                custom_locations=promotion.custom_locations,
                custom_age_min=promotion.custom_age_min,
                custom_age_max=promotion.custom_age_max,
                custom_interests=promotion.custom_interests
            )

            end_time = (timezone.now() + timezone.timedelta(days=promotion.duration_days)).isoformat()
            
            adset = AdSet(parent_id=self.ad_account_id)
            adset.update({
                AdSet.Field.name: adset_name,
                AdSet.Field.campaign_id: fb_campaign_id,
                AdSet.Field.daily_budget: budget_lowest_unit,
                AdSet.Field.billing_event: AdSet.BillingEvent.impressions,
                AdSet.Field.optimization_goal: AdSet.OptimizationGoal.reach,
                AdSet.Field.bid_strategy: 'LOWEST_COST_WITHOUT_CAP',
                AdSet.Field.targeting: targeting,
                AdSet.Field.status: AdSet.Status.active if promotion.status == 'active' else AdSet.Status.paused,
                AdSet.Field.end_time: end_time,
            })
            system_page_id = os.environ.get('FACEBOOK_PAGE_ID', '103116665016386')
            active_page_id = self.page_id or system_page_id
            adset[AdSet.Field.promoted_object] = {'page_id': active_page_id}

            try:
                adset.remote_create()
            except FacebookRequestError as e:
                err_msg = str(e.api_error_message() or '')
                subcode = e.api_error_subcode()
                if (subcode in (1487202, 1341012) or "Page permission" in err_msg or "promoted_object[page_id]" in err_msg) and active_page_id != system_page_id:
                    logger.warning(f"Ad account lacks permission for page {active_page_id}. Falling back to system page {system_page_id}")
                    active_page_id = system_page_id
                    adset[AdSet.Field.promoted_object] = {'page_id': active_page_id}
                    adset.remote_create()
                else:
                    raise
            fb_adset_id = adset[AdSet.Field.id]

            # 3. Handle Creative Media
            image_hash = None
            if promotion.cover_image:
                image_hash = self.upload_image(promotion.cover_image)
            elif promotion.product and promotion.product.images.exists():
                image_url = promotion.product.images.first().image.url
                image_hash = self.upload_image(image_url)

            link = 'https://flezpay.com'
            if business and business.store_setup:
                if business.store_custom_domain:
                    link = f"https://{business.store_custom_domain}"
                elif business.store_slug:
                    link = f"https://{business.store_slug}.flezpay.com"

            # 4. Create Ad Creative with full metadata (headline, description, call to action)
            cta_map = {
                'buy': 'SHOP_NOW',
                'visit': 'LEARN_MORE',
                'message': 'CONTACT_US',
                'call': 'CALL_NOW',
                'learn': 'LEARN_MORE',
            }
            cta_type = cta_map.get(promotion.action_type, 'LEARN_MORE')

            link_data = {
                'link': link,
                'message': promotion.message or promotion.title,
                'name': clean_title,
                'description': promotion.message or promotion.title,
                'call_to_action': {
                    'type': cta_type,
                    'value': {'link': link}
                }
            }
            if image_hash:
                link_data['image_hash'] = image_hash

            creative = AdCreative(parent_id=self.ad_account_id)
            creative.update({
                AdCreative.Field.name: creative_name,
                AdCreative.Field.object_story_spec: {
                    'page_id': active_page_id,
                    'link_data': link_data
                }
            })
            try:
                creative.remote_create()
            except FacebookRequestError as e:
                subcode = e.api_error_subcode()
                err_msg = str(e.api_error_message() or '')
                body_str = str(getattr(e, 'body', lambda: '')())
                if (subcode in (1341012, 1487202) or "required_permission" in body_str or "No permission to access this profile" in err_msg) and active_page_id != system_page_id:
                    logger.warning(f"Ad account lacks permission for creative on page {active_page_id}. Falling back to system page {system_page_id}")
                    active_page_id = system_page_id
                    creative[AdCreative.Field.object_story_spec]['page_id'] = active_page_id
                    creative.remote_create()
                else:
                    raise
            creative_id = creative[AdCreative.Field.id]

            # 5. Create Ad
            ad = Ad(parent_id=self.ad_account_id)
            ad.update({
                Ad.Field.name: ad_name,
                Ad.Field.adset_id: fb_adset_id,
                Ad.Field.creative: {'creative_id': creative_id},
                Ad.Field.status: Ad.Status.active if promotion.status == 'active' else Ad.Status.paused,
            })

            try:
                ad.remote_create()
                fb_ad_id = ad[Ad.Field.id]
            except FacebookRequestError as ad_err:
                subcode = ad_err.api_error_subcode()
                body = getattr(ad_err, 'body', lambda: {})()
                error_data = body.get('error', {}) if isinstance(body, dict) else {}
                user_title = error_data.get('error_user_title', '')
                clean_acc_id = str(self.ad_account_id or '').replace('act_', '')
                is_card_issue = (
                    subcode == 1359188 or 
                    "No payment method" in str(user_title or '') or
                    "payment method" in str(ad_err.api_error_message() or '').lower() or
                    "card" in str(ad_err.api_error_message() or '').lower()
                )

                if is_card_issue:
                    logger.warning(f"[FacebookAdsService] Card required on Meta. Enabling campaign creation in standby mode.")
                    billing_url = f"https://adsmanager.facebook.com/billing_hub/payment_settings?act={clean_acc_id}"
                    return {
                        'success': True,
                        'card_required': True,
                        'campaign_id': fb_campaign_id,
                        'adset_id': fb_adset_id,
                        'ad_id': None,
                        'warning': 'Promotion created successfully! However, your Meta Ad Account requires an active payment card attached before ads can be delivered to audiences.',
                        'billing_url': billing_url,
                    }

                # If Ad creation failed for other reasons, rollback the Campaign and AdSet
                logger.error(f"[FacebookAdsService] Failed to create Ad: {ad_err.api_error_message()} (subcode: {subcode})")
                if created_campaign:
                    try:
                        created_campaign.remote_delete()
                        logger.info(f"[FacebookAdsService] Cleaned up orphaned campaign {fb_campaign_id}")
                    except Exception as del_err:
                        logger.warning(f"[FacebookAdsService] Could not delete orphaned campaign {fb_campaign_id}: {del_err}")

                raise

            return {
                'success': True,
                'campaign_id': fb_campaign_id,
                'adset_id': fb_adset_id,
                'ad_id': fb_ad_id,
            }
        except FacebookRequestError as e:
            if created_campaign:
                try:
                    created_campaign.remote_delete()
                except Exception:
                    pass

            body = e.body() if hasattr(e, 'body') else {}
            error_data = body.get('error', {}) if isinstance(body, dict) else {}
            user_msg = error_data.get('error_user_msg')
            user_title = error_data.get('error_user_title')
            subcode = e.api_error_subcode()
            
            if user_msg:
                error_text = f"{user_title}: {user_msg}" if user_title else user_msg
            else:
                error_text = e.api_error_message()
                
            # Intercept specific common Facebook errors
            if "promoted_object[page_id]" in error_text or "valid page ID" in error_text:
                error_text = 'Invalid Facebook Page selected. Please <a href="/growth/settings" class="underline text-blue-600 font-bold hover:text-blue-800">click here to go to connection settings</a> and select a valid page.'
            elif subcode == 1885183 or "app that is in development mode" in error_text:
                error_text = 'Meta App is currently in Development Mode. Ads cannot be created until the app is switched to Live mode in Meta for Developers (developers.facebook.com) or Live credentials are used in .env.'
            elif subcode == 1359188 or "No payment method" in str(user_title or '') or "payment method" in str(error_text or '').lower() or "card" in str(error_text or '').lower():
                clean_acc_id = self.ad_account_id.replace('act_', '')
                billing_url = f"https://adsmanager.facebook.com/billing_hub/payment_settings?act={clean_acc_id}"
                logger.warning(f"[FacebookAdsService] Card required on Meta ad account. Allowing promotion creation in standby mode.")
                return {
                    'success': True,
                    'card_required': True,
                    'campaign_id': created_campaign[Campaign.Field.id] if created_campaign and hasattr(created_campaign, '__getitem__') and Campaign.Field.id in created_campaign else None,
                    'adset_id': None,
                    'ad_id': None,
                    'warning': 'Promotion created successfully! However, your Meta Ad Account requires an active payment card attached before ads can be delivered to audiences.',
                    'billing_url': billing_url,
                }
                
            logger.error(f"[FacebookAdsService] create_ad_campaign_flow failed: {error_text}")
            return {'success': False, 'error': error_text}
        except Exception as e:
            if created_campaign:
                try:
                    created_campaign.remote_delete()
                except Exception:
                    pass
            logger.exception(f"[FacebookAdsService] Unexpected error creating ad campaign: {e}")
            return {'success': False, 'error': str(e)}

    def update_ad_status(self, fb_campaign_id, status):
        """Updates the status of a campaign."""
        try:
            campaign = Campaign(fb_campaign_id)
            new_status = Campaign.Status.active if status == 'active' else Campaign.Status.paused
            campaign.api_update(params={'status': new_status})
            return {'success': True}
        except FacebookRequestError as e:
            subcode = e.api_error_subcode()
            body = getattr(e, 'body', lambda: {})()
            error_data = body.get('error', {}) if isinstance(body, dict) else {}
            user_title = error_data.get('error_user_title', '')
            if subcode == 1359188 or "No payment method" in str(user_title or ''):
                clean_acc_id = self.ad_account_id.replace('act_', '')
                return {
                    'success': False,
                    'error': f'Cannot activate campaign on Meta: No valid payment method attached to the Ad Account. Please add a payment card in <a href="https://adsmanager.facebook.com/billing_hub/payment_settings?act={clean_acc_id}" target="_blank" class="underline font-bold text-blue-600 hover:text-blue-800">Meta Ads Manager Billing</a> first.'
                }
            return {'success': False, 'error': str(e.api_error_message())}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def delete_campaign(self, fb_campaign_id):
        """Deletes a campaign remotely on Meta."""
        try:
            campaign = Campaign(fb_campaign_id)
            campaign.remote_delete()
            return {'success': True}
        except Exception as e:
            logger.warning(f"[FacebookAdsService] Failed to delete campaign {fb_campaign_id} on Meta: {e}")
            return {'success': False, 'error': str(e)}

    def update_ad_budget(self, fb_adset_id, user_budget, user_currency='USD'):
        """Updates the daily budget of an active AdSet on Meta."""
        try:
            from api.growth_views import get_usd_to_local_exchange_rate
            rate_to_user_curr = get_usd_to_local_exchange_rate(user_currency) or 1.0
            ad_account_currency = self.get_ad_account_currency()
            rate_to_ad_acc = get_usd_to_local_exchange_rate(ad_account_currency) or 1.0

            budget_usd = float(user_budget) / rate_to_user_curr
            budget_in_ad_acc = budget_usd * rate_to_ad_acc
            budget_lowest_unit = int(round(budget_in_ad_acc * 100))

            min_ad_acc_unit = int(round(1.0 * rate_to_ad_acc * 100))
            if budget_lowest_unit < min_ad_acc_unit:
                budget_lowest_unit = min_ad_acc_unit

            adset = AdSet(fb_adset_id)
            adset.api_update(params={AdSet.Field.daily_budget: budget_lowest_unit})
            return {'success': True}
        except Exception as e:
            logger.warning(f"[FacebookAdsService] Could not update budget on Meta adset {fb_adset_id}: {e}")
            return {'success': False, 'error': str(e)}

    def get_campaign_insights(self, fb_campaign_id):
        """Fetches spend, reach, impressions, and clicks for a campaign."""
        try:
            campaign = Campaign(fb_campaign_id)
            params = {
                'date_preset': 'maximum',
            }
            fields = ['spend', 'reach', 'impressions', 'clicks']
            insights = campaign.get_insights(fields=fields, params=params)
            
            if insights and len(insights) > 0:
                data = insights[0]
                return {
                    'success': True,
                    'spend': float(data.get('spend', 0.00)),
                    'reach': int(data.get('reach', 0)),
                    'impressions': int(data.get('impressions', 0)),
                    'clicks': int(data.get('clicks', 0)),
                }
            return {'success': True, 'spend': 0.0, 'reach': 0, 'impressions': 0, 'clicks': 0}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def fetch_all_ads_and_campaigns(self):
        """Fetches all campaigns, ad sets, and creatives directly from Meta Ad Account."""
        try:
            campaigns = list(self.account.get_campaigns(fields=[
                Campaign.Field.id,
                Campaign.Field.name,
                Campaign.Field.status,
                Campaign.Field.effective_status,
                Campaign.Field.objective,
                Campaign.Field.created_time,
                Campaign.Field.start_time,
                Campaign.Field.stop_time,
                Campaign.Field.daily_budget,
                Campaign.Field.lifetime_budget,
            ]))

            adsets = list(self.account.get_ad_sets(fields=[
                AdSet.Field.id,
                AdSet.Field.name,
                AdSet.Field.campaign_id,
                AdSet.Field.status,
                AdSet.Field.daily_budget,
                AdSet.Field.lifetime_budget,
            ]))
            adset_by_camp = {s.get('campaign_id'): s for s in adsets if s.get('campaign_id')}

            creatives = list(self.account.get_ad_creatives(fields=[
                AdCreative.Field.id,
                AdCreative.Field.name,
                AdCreative.Field.title,
                AdCreative.Field.body,
                AdCreative.Field.image_url,
                AdCreative.Field.object_story_spec,
            ]))

            import re
            results = []
            for c in campaigns:
                c_id = c.get('id')
                c_name = c.get('name') or ''
                c_status = (c.get('status') or 'PAUSED').lower()

                # Extract promo short code from campaign name if present
                m = re.search(r'\[promo:([a-f0-9]{8})\]', c_name)
                promo_code = m.group(1) if m else None

                # Clean title for display
                clean_title = re.sub(r'\[.*?\]\s*', '', c_name).strip()
                if not clean_title:
                    clean_title = c_name

                s = adset_by_camp.get(c_id)
                adset_id = s.get('id') if s else None
                budget_cents = int(s.get('daily_budget', 0)) if s and s.get('daily_budget') else 0
                budget_acc_units = (budget_cents / 100.0) if budget_cents > 0 else 0.0

                # Match creative
                matched_cr = None
                if promo_code:
                    for cr in creatives:
                        if promo_code in (cr.get('name') or ''):
                            matched_cr = cr
                            break
                if not matched_cr:
                    words = [w.lower() for w in re.findall(r'\b\w{4,}\b', clean_title) if w.lower() not in ['your', 'with', 'look', 'from', 'this', 'that', 'shop', 'grab', 'alert']]
                    for cr in creatives:
                        cr_name = (cr.get('name') or '').lower()
                        if any(w in cr_name for w in words):
                            matched_cr = cr
                            break

                image_url = matched_cr.get('image_url') if matched_cr else ''
                body_text = (matched_cr.get('body') or '') if matched_cr else ''

                results.append({
                    'campaign_id': c_id,
                    'name': c_name,
                    'title': clean_title,
                    'status': c_status,
                    'effective_status': c.get('effective_status'),
                    'objective': c.get('objective'),
                    'adset_id': adset_id,
                    'daily_budget_acc': budget_acc_units,
                    'promo_code': promo_code,
                    'cover_image': image_url,
                    'body': body_text,
                    'created_time': c.get('created_time'),
                })

            return {'success': True, 'campaigns': results}
        except Exception as e:
            logger.exception(f"[FacebookAdsService] Failed to fetch all ads and campaigns: {e}")
            return {'success': False, 'error': str(e), 'campaigns': []}

    def sync_campaigns_to_db(self, owner):
        """Fetches all campaigns from Meta and creates or updates GrowthPromotion records for the owner."""
        res = self.fetch_all_ads_and_campaigns()
        if not res.get('success'):
            return res

        from api.models import GrowthPromotion, UserItems
        from api.growth_views import get_usd_to_local_exchange_rate

        details = owner.details.first() if hasattr(owner, 'details') else None
        user_currency = details.currency if details and details.currency else 'USD'
        acc_currency = self.get_ad_account_currency()

        user_rate = get_usd_to_local_exchange_rate(user_currency) or 1.0
        acc_rate = get_usd_to_local_exchange_rate(acc_currency) or 1.0

        user_items = list(UserItems.objects.filter(user=owner))
        synced_count = 0
        created_count = 0

        for c in res.get('campaigns', []):
            c_id = c['campaign_id']
            clean_title = c['title']
            c_status = c['status']
            budget_acc_units = c['daily_budget_acc']
            image_url = c['cover_image']
            body_text = c['body']
            adset_id = c['adset_id']

            # Convert budget from ad account currency to owner user currency
            if budget_acc_units > 0:
                budget_usd = budget_acc_units / acc_rate
                budget_user_currency = round(budget_usd * user_rate, 2)
            else:
                budget_user_currency = round(1.0 * user_rate, 2)

            matched_item = None
            for it in user_items:
                it_name = it.item_name.lower()
                if it_name in clean_title.lower() or it_name in c['name'].lower():
                    matched_item = it
                    break

            promo = GrowthPromotion.objects.filter(fb_campaign_id=c_id).first()
            if not promo:
                promo = GrowthPromotion(
                    user=owner,
                    fb_campaign_id=c_id,
                    title=clean_title,
                    status=c_status,
                    budget_per_day=budget_user_currency,
                    cover_image=image_url,
                    message=body_text,
                    fb_adset_id=adset_id,
                    product=matched_item,
                    promote_type='product' if matched_item else 'store',
                    action_type='buy' if matched_item else 'learn',
                    amount_debited=Decimal('0.00'),
                    is_external=True,
                )
                promo.save()
                created_count += 1
            else:
                promo.status = c_status
                if budget_user_currency > 0:
                    promo.budget_per_day = budget_user_currency
                if not promo.cover_image and image_url:
                    promo.cover_image = image_url
                if not promo.message and body_text:
                    promo.message = body_text
                if not promo.fb_adset_id and adset_id:
                    promo.fb_adset_id = adset_id
                if not promo.product and matched_item:
                    promo.product = matched_item
                promo.save()

            synced_count += 1

        return {
            'success': True,
            'synced_count': synced_count,
            'created_count': created_count,
            'total_campaigns': len(res.get('campaigns', []))
        }

