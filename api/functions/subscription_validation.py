from datetime import datetime
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ObjectDoesNotExist
from api.models import SubscriptionPlans, BusinessDetails, UserSecure
from api.external.encryption import Encryption



class SubscriptionLimitError(Exception):
    """Raised when a user exceeds their subscription plan limit"""
    pass


class SubscriptionManager:
    def __init__(self, user: UserSecure):
        self.user = user
        self.business = BusinessDetails.objects.filter(user=user, store_setup=True).first() or BusinessDetails.objects.filter(user=user).first()
        if not self.business:
            from api.models import UserDetails, AllowedCountries
            user_country_code = UserDetails.objects.filter(user=user).values_list('user_country', flat=True).first() or 'NG'
            allowed_country = AllowedCountries.objects.filter(code=user_country_code).first()
            country_vat = allowed_country.vat_percentage if (allowed_country and allowed_country.vat_percentage is not None) else 0.0
            self.business = BusinessDetails.objects.create(
                user=user,
                plan_code=0,
                vat_percentage=country_vat,
                enable_ai_calls=False,
                enable_loyalty=False,
                loyalty_point_equivalent=0,
            )

    def assign_plan(self, plan_id: int, duration: str = "one_amount"):
        """Assign subscription plan to user with encrypted expiry"""
        try:
            plan = SubscriptionPlans.objects.get(uniq_id=plan_id)
        except SubscriptionPlans.DoesNotExist:
            raise ValueError("Invalid plan selected")

        # Save plan_code
        self.business.plan_code = plan.uniq_id

        if duration == "prorated_upgrade":
            self.business.save()
            return True

        # Expiry map
        duration_map = {
            "one_amount": 30,
            "three_months": 90,
            "six_months": 180,
            "twelve_months": 365,
            "one_hundred_years": 36500,
        }
        days = duration_map.get(duration)
        if not days:
            raise ValueError("Invalid subscription duration")

        expiry = timezone.now() + timedelta(days=days)

        self.business.subscription_expiry = expiry
        self.business.save()
        return True

    def renew_subscription(self, duration: str = "one_amount"):
        """Renew current subscription plan"""
        if self.business.plan_code == 0:
            # If no plan, assign the first available plan (or Free plan)
            try:
                first_plan = SubscriptionPlans.objects.all().first()
                if first_plan:
                    return self.assign_plan(first_plan.uniq_id, duration)
            except:
                return False

        # Expiry map
        duration_map = {
            "one_amount": 30,
            "three_months": 90,
            "six_months": 180,
            "twelve_months": 365,
            "one_hundred_years": 36500,
        }
        days = duration_map.get(duration, 30)
        
        # Get current expiry
        now_dt = timezone.now()
        current_expiry_str = self.business.subscription_expiry
        
        if current_expiry_str:
            try:
                current_expiry = datetime.fromisoformat(current_expiry_str)
                if timezone.is_naive(current_expiry):
                    current_expiry = timezone.make_aware(current_expiry, timezone=timezone.utc)
                
                # If still active, add to existing expiry. If expired, start from now.
                base_date = max(now_dt, current_expiry)
                new_expiry = base_date + timedelta(days=days)
            except:
                new_expiry = now_dt + timedelta(days=days)
        else:
            new_expiry = now_dt + timedelta(days=days)

        self.business.subscription_expiry = new_expiry
        self.business.save()
        return True

    def get_plan(self):
        """Return user’s subscription plan object"""
        try:
            return SubscriptionPlans.objects.get(uniq_id=self.business.plan_code)
        except SubscriptionPlans.DoesNotExist:
            return None

    def is_active(self):
        """Check if subscription is still valid"""
        expiry_str = self.business.subscription_expiry

        if not expiry_str:
            return False

        try:
            expiry = datetime.fromisoformat(expiry_str)
            if timezone.is_naive(expiry):
                expiry = timezone.make_aware(expiry, timezone=timezone.utc)

            return timezone.now() <= expiry
        except Exception as e:
            pass
            return False

    def _check_subscription(self):
        """Raise if no valid subscription"""
        if not self.is_active() or not self.get_plan():
            raise SubscriptionLimitError("No active subscription")

    # ---------- VALIDATIONS ----------
    def check_collection_accounts(self, current_accounts: int):
        self._check_subscription()
        plan = self.get_plan()
        try:
            limit_val = int(plan.collection_accounts)
            unit = "collection account" if limit_val == 1 else "collection accounts"
            if current_accounts >= limit_val:
                raise SubscriptionLimitError(
                    f"You can only add {limit_val} {unit} on this plan, upgrade or contact support."
                )
        except (ValueError, TypeError):
            if current_accounts >= 1:
                raise SubscriptionLimitError(
                    "You cannot add more collection accounts on this plan, upgrade or contact support."
                )
        return True

    def check_managers(self, current_managers: int):
        self._check_subscription()
        plan = self.get_plan()
        managers_limit = getattr(plan, 'managers', 1)
        try:
            limit_val = int(managers_limit)
        except (ValueError, TypeError):
            limit_val = 1
        unit = "manager" if limit_val == 1 else "managers"
        if current_managers >= limit_val:
            raise SubscriptionLimitError(
                f"You can only add {limit_val} {unit} on this plan, upgrade or contact support."
            )
        return True

    def check_cashiers(self, current_cashiers: int):
        self._check_subscription()
        plan = self.get_plan()
        cashiers_limit = getattr(plan, 'cashiers', 1)
        try:
            limit_val = int(cashiers_limit)
        except (ValueError, TypeError):
            limit_val = 1
        unit = "staff / cashier" if limit_val == 1 else "staff / cashiers"
        if current_cashiers >= limit_val:
            raise SubscriptionLimitError(
                f"You can only add {limit_val} {unit} on this plan, upgrade or contact support."
            )
        return True

    def check_payroll(self, current_payrolls: int):
        self._check_subscription()
        plan = self.get_plan()
        try:
            limit_val = int(plan.payroll)
            unit = "payroll" if limit_val == 1 else "payrolls"
            if current_payrolls >= limit_val:
                raise SubscriptionLimitError(
                    f"You can only add {limit_val} {unit} on this plan, upgrade or contact support."
                )
        except (ValueError, TypeError):
            pass
        return True

    def require_payroll(self):
        self._check_subscription()
        plan = self.get_plan()
        try:
            if int(plan.payroll) <= 0:
                raise SubscriptionLimitError("Payroll feature not included in this plan")
        except (ValueError, TypeError):
            if not plan.payroll:
                raise SubscriptionLimitError("Payroll feature not included in this plan")
        return True

    def require_ai_manager(self):
        self._check_subscription()
        plan = self.get_plan()
        if not plan.ai_manager:
            raise SubscriptionLimitError("AI Business Manager not included in this plan")
        return True

    def require_inventory(self):
        self._check_subscription()
        plan = self.get_plan()
        if not plan.inventory:
            raise SubscriptionLimitError("Inventory management not included in this plan")
        return True

    def require_online_store(self):
        self._check_subscription()
        plan = self.get_plan()
        if not plan.online_store:
            raise SubscriptionLimitError("Online Store feature not included in this plan")
        return True

    def require_business_reporting(self):
        self._check_subscription()
        plan = self.get_plan()
        if not plan.business_reporting:
            raise SubscriptionLimitError("Business Reporting not included in this plan")
        return True

    def require_installment_payment(self):
        self._check_subscription()
        plan = self.get_plan()
        if not plan.installment_payment:
            raise SubscriptionLimitError("Installment Payment not included in this plan")
        return True

    def check_max_products(self, current_count: int, adding_count: int = 1):
        self._check_subscription()
        plan = self.get_plan()
        if current_count + adding_count > plan.max_products:
            raise SubscriptionLimitError(f"Limit reached. Your subscription plan allows up to {plan.max_products} products.")
        return True

import requests
from django.core.cache import cache
from api.models import UserDetails

def get_currency_symbol(currency_code):
    symbols = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'NGN': '₦', 'CAD': '$',
        'AUD': '$', 'ZAR': 'R', 'KES': 'KSh', 'GHS': 'GH₵', 'INR': '₹',
        'AED': 'د.إ', 'SAR': '﷼', 'CHF': 'CHF'
    }
    return symbols.get(currency_code, currency_code + ' ')

def format_currency_amount(val, user_currency):
    fmt = f"{val:,.0f}" if val > 0 else "0.00"
    if val > 0 and val < 100 and user_currency in ['USD', 'EUR', 'GBP']:
         fmt = f"{val:,.2f}"
    elif val > 0 and val >= 1000 and user_currency == 'NGN':
         fmt = f"{val/1000:g}k"
    return fmt

def get_processed_subscription_context(user):
    from api.models import SiteSettings, SubscriptionInvoices
    user_details = UserDetails.objects.filter(user=user).first()
    user_currency = user_details.currency if user_details else 'NGN'
    
    exchange_rate = 1.0
    if user_currency != 'NGN':
        cache_key = f'exchange_rate_NGN_{user_currency}'
        rate = cache.get(cache_key)
        if rate is None:
            try:
                res = requests.get('https://open.er-api.com/v6/latest/NGN', timeout=3)
                if res.status_code == 200:
                    rates = res.json().get('rates', {})
                    rate = float(rates.get(user_currency, 1.0))
                    cache.set(cache_key, rate, 86400)
            except Exception:
                rate = 1.0
                cache.set(cache_key, 1.0, 3600)
        exchange_rate = rate or 1.0
        
    plans = list(SubscriptionPlans.objects.all())
    def safe_float(val):
        try: return float(val)
        except (ValueError, TypeError): return 0.0
        
    plans.sort(key=lambda p: safe_float(p.one_amount))
    
    site = SiteSettings.objects.first()
    promo_plan_id_config = site.promo_plan.uniq_id if site and site.promo_plan else None
    promo_duration_config = site.promo_duration if site else 'one_amount'
    
    promo_plan_uniq_id = None
    promo_amount_display = "0.00"
    fallback_plan_id = None
    fallback_amount_display = "0.00"

    processed_plans = []
    for p in plans:
        amount_val = safe_float(p.one_amount) * exchange_rate
        three_months_val = safe_float(p.three_months) * exchange_rate
        six_months_val = safe_float(p.six_months) * exchange_rate
        year_val = safe_float(p.twelve_months) * exchange_rate
        
        # Track the first non-free plan as a fallback
        if fallback_plan_id is None and safe_float(p.one_amount) > 0:
            fallback_plan_id = p.uniq_id
            if promo_duration_config == 'three_months':
                fallback_amount_display = format_currency_amount(three_months_val, user_currency)
            elif promo_duration_config == 'six_months':
                fallback_amount_display = format_currency_amount(six_months_val, user_currency)
            elif promo_duration_config == 'twelve_months':
                fallback_amount_display = format_currency_amount(year_val, user_currency)
            else:
                fallback_amount_display = format_currency_amount(amount_val, user_currency)

        # Match configured promo plan
        if promo_plan_id_config and p.uniq_id == promo_plan_id_config:
            promo_plan_uniq_id = p.uniq_id
            if promo_duration_config == 'three_months':
                promo_amount_display = format_currency_amount(three_months_val, user_currency)
            elif promo_duration_config == 'six_months':
                promo_amount_display = format_currency_amount(six_months_val, user_currency)
            elif promo_duration_config == 'twelve_months':
                promo_amount_display = format_currency_amount(year_val, user_currency)
            else:
                promo_amount_display = format_currency_amount(amount_val, user_currency)
            
        processed_plans.append({
            'uniq_id': p.uniq_id,
            'plan_name': p.plan_name,
            'description': p.description,
            'one_amount_display': format_currency_amount(amount_val, user_currency),
            'three_months_display': format_currency_amount(three_months_val, user_currency),
            'six_months_display': format_currency_amount(six_months_val, user_currency),
            'twelve_months_display': format_currency_amount(year_val, user_currency),
            'one_amount_converted': amount_val,
            'three_months_converted': three_months_val,
            'six_months_converted': six_months_val,
            'twelve_months_converted': year_val,
            'one_amount': safe_float(p.one_amount), 
            'three_months': safe_float(p.three_months),
            'six_months': safe_float(p.six_months),
            'twelve_months': safe_float(p.twelve_months), 
            'is_popular': p.is_popular,
            'inventory': p.inventory,
            'ai_manager': p.ai_manager,
            'managers': getattr(p, 'managers', 1),
            'business_reporting': p.business_reporting,
            'installment_payment': p.installment_payment,
            'online_store': p.online_store,
            'cashiers': p.cashiers,
            'max_products': p.max_products,
            'payroll': p.payroll,
            'support': p.support,
            'collection_accounts': p.collection_accounts
        })
        
    # Check if user has claimed the configured promo offer from UserDetails model
    has_claimed_promo = False
    if user_details:
        has_claimed_promo = user_details.has_claimed_promo
        
    # Check if current subscription is expired or free plan
    sub_manager = SubscriptionManager(user)
    current_plan = sub_manager.get_plan()
    
    is_expired = not sub_manager.is_active()
    is_free_plan = False
    if current_plan:
        try:
            is_free_plan = safe_float(current_plan.one_amount) == 0
        except Exception:
            is_free_plan = True
    else:
        is_free_plan = True
        
    is_expired_or_free = is_expired or is_free_plan
    
    # Disable banner if the user HAS already claimed the promo,
    # OR if they have an active paid plan (which is neither expired nor free)
    disable_banner = has_claimed_promo or not is_expired_or_free
        
    return {
        'plans': processed_plans,
        'user_currency': user_currency,
        'currency_symbol': get_currency_symbol(user_currency),
        'exchange_rate': exchange_rate,
        'disable_banner': disable_banner,
        'promo_plan_uniq_id': promo_plan_uniq_id or fallback_plan_id,
        'promo_amount_display': promo_amount_display if promo_plan_uniq_id else fallback_amount_display,
        'promo_duration': promo_duration_config
    }
