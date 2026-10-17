from django.core.mail import EmailMessage
from django.conf import settings
from celery import shared_task
from celery.schedules import crontab
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta
import requests
import os
import logging

from .functions.fcm_service import send_fcm_to_user
from .models import CryptoLedger, UserTransactions, UserSecure, UserPayroll
from .crypto.circle_usdc import CircleUSDC
from .crypto.stellar import StellarWallet
from .crypto.bitcoin import BitcoinWallet, get_btc_to_ngn_rate, get_crypto_sweep_fee_btc
import uuid
from api.external.paystack_api import PaystackAPI
from api.user_data.data_views import calculate_total_balance
from api.models import BusinessDetails

from api import models
from api.openprovider import OpenproviderAPI
from django.core.mail import send_mail
from django.template.loader import render_to_string

import json
from pathlib import Path
from api.external.psb_api import PSB

logger = logging.getLogger(__name__)

@shared_task
def add(x, y):
    return x + y


@shared_task
def mul(x, y):
    return x * y

@shared_task
def provision_ssl_task(domain_name, extension):
    from .functions.ssl import provision_ssl
    return provision_ssl(domain_name, extension)


def check_user_dual_verification(user):
    """
    Checks if a user has both KYC and KYB verified.
    If both are verified and user is not yet marked is_verified:
      - Sets user.is_verified = True
      - Sends account_verified.html email to user
    """
    from api.models import UserVerificationDetails, UserDetails
    from api.functions import send_mail as api_send_mail
    from django.utils import timezone
    import logging

    task_logger = logging.getLogger(__name__)

    # Check if KYC is approved
    has_kyc_approved = UserVerificationDetails.objects.filter(
        user=user,
        verification_type='KYC',
        verification_status='1'
    ).exists()

    # Check if KYB is approved
    has_kyb_approved = UserVerificationDetails.objects.filter(
        user=user,
        verification_type='KYB',
        verification_status='1'
    ).exists()

    update_fields = []
    if user.kyc_verified != has_kyc_approved:
        user.kyc_verified = has_kyc_approved
        update_fields.append('kyc_verified')

    if user.kyb_verified != has_kyb_approved:
        user.kyb_verified = has_kyb_approved
        update_fields.append('kyb_verified')

    both_verified = has_kyc_approved and has_kyb_approved

    if both_verified and not user.is_verified:
        user.is_verified = True
        update_fields.append('is_verified')
        user.save(update_fields=update_fields)

        # Send Account Verified Email
        try:
            user_details = UserDetails.objects.filter(user=user).first()
            user_name = user_details.first_name if (user_details and user_details.first_name) else (user.user_email.split('@')[0] if user.user_email else "Merchant")
            timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")
            if user.user_email:
                api_send_mail.mailSenderAsync(
                    'account_verified.html',
                    'Account Successfully Verified - Flezpay',
                    [user.user_email],
                    {
                        "user_name": user_name,
                        "verification_date": timestamp
                    }
                )
                task_logger.info(f"Sent account verification email to {user.user_email}")
        except Exception as e:
            task_logger.error(f"Error sending verification email to {user.user_email}: {e}")
        return True
    elif not both_verified and user.is_verified:
        user.is_verified = False
        update_fields.append('is_verified')
        user.save(update_fields=update_fields)
        return False
    elif update_fields:
        user.save(update_fields=update_fields)

    return both_verified


@shared_task(name='api.tasks.check_dual_verification_status')
def check_dual_verification_status(user_id=None):
    from api.models import UserSecure
    if user_id:
        users = UserSecure.objects.filter(user_id=user_id)
    else:
        users = UserSecure.objects.filter(is_superuser=False)

    verified_count = 0
    for user in users:
        if check_user_dual_verification(user):
            verified_count += 1
    return f"Completed dual verification check: {verified_count} accounts fully verified."


@shared_task(name='api.tasks.poll_pending_myaza_verifications')
def poll_pending_myaza_verifications():
    """
    Polls Myaza Trust API for any KYC submissions in '0' (Pending) status
    that have a provider_reference.
    """
    from api.models import UserVerificationDetails
    from api.external.myaza_api import MyazaTrustAPI
    import logging

    task_logger = logging.getLogger(__name__)
    pending_records = UserVerificationDetails.objects.filter(
        verification_type='KYC',
        verification_status='0'
    ).exclude(provider_reference__isnull=True).exclude(provider_reference='')

    updated_count = 0
    client = MyazaTrustAPI()

    for record in pending_records:
        try:
            res = client.get_status(record.provider_reference)
            if not res.get('status'):
                continue

            myaza_status = str(res.get('myaza_status') or '').lower()
            check_status = str(res.get('check_status') or '').lower()

            if myaza_status in ['approved'] or check_status in ['verified']:
                record.verification_status = '1'
                record.reason = ''
                record.save(update_fields=['verification_status', 'reason'])

                user = record.user
                user.kyc_verified = True
                user.save(update_fields=['kyc_verified'])

                try:
                    from api.functions.verification_sync import sync_verified_identity_from_provider
                    sync_verified_identity_from_provider(record, payload_data=res, client=client)
                except Exception as sync_err:
                    task_logger.error(f"Error syncing verified identity in polling task: {sync_err}")

                check_user_dual_verification(user)
                try:
                    from api.functions.verification_emails import send_tier_verification_email
                    send_tier_verification_email(user=user, tier_type=record.verification_type or 'KYC', new_status='1')
                except Exception:
                    pass
                updated_count += 1
                task_logger.info(f"Myaza KYC approved for user {user.user_email} via background poll")

            elif myaza_status in ['failed', 'declined', 'not_found'] or check_status in ['failed', 'not_found']:
                record.verification_status = '2'
                data = res.get('data') or {}
                reason = data.get('reason') or data.get('reasonCode') or 'Verification declined by identity authority'
                record.reason = f"Provider: {reason}"
                record.save(update_fields=['verification_status', 'reason'])

                user = record.user
                user.kyc_verified = False
                user.save(update_fields=['kyc_verified'])
                check_user_dual_verification(user)
                try:
                    from api.functions.verification_emails import send_tier_verification_email
                    send_tier_verification_email(user=user, tier_type=record.verification_type or 'KYC', new_status='2', reason=reason)
                except Exception:
                    pass
                updated_count += 1
                task_logger.info(f"Myaza KYC declined for user {user.user_email} via background poll: {reason}")
        except Exception as e:
            task_logger.error(f"Error polling Myaza verification {record.provider_reference}: {e}")

    return f"Completed Myaza poll: {updated_count} records updated."


@shared_task(name='api.tasks.check_store_subscription_status')
def check_store_subscription_status():
    # TEMPORARILY COMMENTED OUT: store online status disable after subscription expires
    # from api.models import BusinessDetails
    # from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
    # import logging
    # 
    # logger = logging.getLogger(__name__)
    # 
    # businesses = BusinessDetails.objects.filter(is_published=True, store_setup=True)
    # count = 0
    # for business in businesses:
    #     try:
    #         sub_manager = SubscriptionManager(business.user)
    #         sub_manager.require_online_store()
    #     except SubscriptionLimitError:
    #         # Plan expired or downgraded and no longer supports online store
    #         business.is_published = False
    #         business.save(update_fields=['is_published'])
    #         count += 1
    #         logger.info(f"Automatically took offline store for user {business.user.uniq_id} due to subscription limits")
    #     except Exception as e:
    #         logger.error(f"Error checking subscription for business {business.id}: {str(e)}")
    #         
    # return f"Checked online stores. Offline count: {count}"
    return "Checked online stores (auto-disable temporarily paused)."


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def update_cloudflare_dns_task(self, user_id, subdomain):
    """
    Asynchronously create or update a Cloudflare DNS A record for a store subdomain.

    If wildcard DNS is active, subdomains are already routed via *.flezpay.com,
    so we record the audit entry and notify the user immediately without consuming DNS slots.
    """
    from .external.cloudflare_dns import CloudflareDNS, CloudflareDNSError
    from .models import UserSecure, CloudflareDNSRecord, Notifications
    from django.conf import settings

    try:
        user = UserSecure.objects.get(user_id=user_id)
    except UserSecure.DoesNotExist:
        logger.error('update_cloudflare_dns_task: User %s not found', user_id)
        return

    # Check if wildcard DNS routing is enabled
    use_wildcard = getattr(settings, 'CLOUDFLARE_USE_WILDCARD', True)
    target_domain = getattr(settings, 'CLOUDFLARE_TARGET_DOMAIN', getattr(settings, 'STORE_BASE_DOMAIN', 'flezpay.com'))
    full_domain = f"{subdomain}.{target_domain}" if target_domain else subdomain

    if use_wildcard:
        # With wildcard DNS, *.flezpay.com handles routing instantly
        CloudflareDNSRecord.objects.update_or_create(
            subdomain=subdomain,
            defaults={
                'user': user,
                'full_domain': full_domain,
                'record_type': 'A',
                'record_id': 'wildcard',
                'zone_id': 'wildcard',
                'target_value': 'wildcard',
                'is_active': True,
            }
        )

        Notifications.objects.create(
            user=user,
            title='Store Domain Connected',
            description=f'Your store domain {full_domain} has been configured successfully.',
            notification_type='tranc_success'
        )

        logger.info('Wildcard DNS active for user %s: %s', user_id, full_domain)
        return

    try:
        cf = CloudflareDNS()
        result = cf.upsert_subdomain_record(subdomain)

        # Save or update the audit record
        CloudflareDNSRecord.objects.update_or_create(
            subdomain=subdomain,
            defaults={
                'user': user,
                'full_domain': result['full_domain'],
                'record_type': result['record_type'],
                'record_id': result['record_id'],
                'zone_id': result['zone_id'],
                'target_value': result['target_value'],
                'is_active': True,
            }
        )

        Notifications.objects.create(
            user=user,
            title='Store Domain Connected',
            description=f'Your store domain {result["full_domain"]} has been configured successfully.',
            notification_type='tranc_success'
        )

        logger.info('Cloudflare DNS updated for user %s: %s', user_id, result['full_domain'])

    except CloudflareDNSError as e:
        logger.error('Cloudflare DNS update failed for user %s, subdomain %s: %s', user_id, subdomain, str(e))
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            Notifications.objects.create(
                user=user,
                title='Store Domain Setup Failed',
                description=f'We could not configure the DNS for your store domain. Please try again or contact support.',
                notification_type='tranc_error'
            )

    except Exception as e:
        logger.error('Unexpected error in update_cloudflare_dns_task for user %s: %s', user_id, str(e))
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            Notifications.objects.create(
                user=user,
                title='Store Domain Setup Failed',
                description=f'We could not configure the DNS for your store domain. Please try again or contact support.',
                notification_type='tranc_error'
            )


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def remove_cloudflare_dns_task(self, user_id, subdomain):
    """
    Asynchronously remove a Cloudflare DNS record when a store domain is cleared or changed.
    """
    from .external.cloudflare_dns import CloudflareDNS, CloudflareDNSError
    from .models import UserSecure, CloudflareDNSRecord, Notifications
    from django.conf import settings

    use_wildcard = getattr(settings, 'CLOUDFLARE_USE_WILDCARD', True)
    if use_wildcard:
        CloudflareDNSRecord.objects.filter(subdomain=subdomain).update(is_active=False)
        logger.info('Wildcard DNS: deactivated record for subdomain %s', subdomain)
        return

    try:
        user = UserSecure.objects.get(user_id=user_id)
    except UserSecure.DoesNotExist:
        logger.error('remove_cloudflare_dns_task: User %s not found', user_id)
        return

    try:
        cf = CloudflareDNS()
        deleted = cf.remove_subdomain_record(subdomain)

        # Mark the audit record as inactive
        CloudflareDNSRecord.objects.filter(subdomain=subdomain).update(is_active=False)

        if deleted:
            logger.info('Cloudflare DNS record removed for user %s: %s', user_id, subdomain)
        else:
            logger.info('No Cloudflare DNS record found to remove for subdomain: %s', subdomain)

    except CloudflareDNSError as e:
        logger.error('Cloudflare DNS removal failed for user %s, subdomain %s: %s', user_id, subdomain, str(e))
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            Notifications.objects.create(
                user=user,
                title='Domain Cleanup Notice',
                description=f'We could not remove the old DNS record for subdomain "{subdomain}".',
                notification_type='basic'
            )

    except Exception as e:
        logger.error('Unexpected error in remove_cloudflare_dns_task for user %s: %s', user_id, str(e))
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            pass


@shared_task
def sendmail():
    email = 'arepadedaniel@gmail.com'
    send_mail.mailSender('welcome.html', 'Celery', [email])


def get_usdc_to_ngn_rate():
    """
    Get USDC to NGN exchange rate
    USDC is pegged to USD, so we get USD to NGN rate
    """
    try:
        # Using exchangerate-api.com free tier
        response = requests.get(
            'https://api.exchangerate-api.com/v4/latest/USD',
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            ngn_rate = data.get('rates', {}).get('NGN', 1500)  # Default fallback
            return Decimal(str(ngn_rate))
        else:
            return Decimal('1500')  # Default fallback rate
    except Exception as e:
        return Decimal('1500')  # Default fallback rate


def get_xlm_to_ngn_rate():
    """
    Get XLM to NGN exchange rate
    First get XLM to USD, then USD to NGN
    """
    try:
        # Get XLM to USD rate from CoinGecko
        xlm_response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=stellar&vs_currencies=usd',
            timeout=10
        )
        if xlm_response.status_code == 200:
            xlm_data = xlm_response.json()
            xlm_to_usd = Decimal(str(xlm_data.get('stellar', {}).get('usd', 0.1)))
        else:
            xlm_to_usd = Decimal('0.1')  # Default fallback
        
        # Get USD to NGN rate
        usd_response = requests.get(
            'https://api.exchangerate-api.com/v4/latest/USD',
            timeout=10
        )
        if usd_response.status_code == 200:
            usd_data = usd_response.json()
            usd_to_ngn = Decimal(str(usd_data.get('rates', {}).get('NGN', 1500)))
        else:
            usd_to_ngn = Decimal('1500')  # Default fallback
        
        # Calculate XLM to NGN
        xlm_to_ngn = xlm_to_usd * usd_to_ngn
        return xlm_to_ngn
        
    except Exception as e:
        return Decimal('150')  # Default fallback rate (0.1 USD * 1500 NGN)


def get_crypto_sweep_fee_usd():
    """
    Get the crypto sweep fee in USD from admin settings.
    
    IMPORTANT: This function ALWAYS uses the admin-configured value from the database.
    The hardcoded 1.0 USD is ONLY used as a fallback if:
    - Admin settings are not configured
    - Admin settings don't contain crypto_sweep_fee_usd
    - An error occurs reading the settings
    
    Returns the configured fee (can be 0 if admin sets it to 0) or defaults to 1.0 USD if not set.
    """
    try:
        # Get any admin user's settings (they should all have the same global settings)
        admin = UserSecure.objects.filter(is_superuser=True).first()
        if admin and admin.admin_settings:
            fee = admin.admin_settings.get('crypto_sweep_fee_usd')
            if fee is not None:
                try:
                    fee_decimal = Decimal(str(fee))
                    if fee_decimal >= 0:  # Allow 0 fee if admin sets it
                        return fee_decimal
                    else:
                        pass
                except (ValueError, TypeError) as e:
                    pass
        
        # Default to 1.0 USD ONLY if admin setting is not configured
        # This fallback should rarely be used in production
        return Decimal('1.0')
    except Exception as e:
        # Fallback only used if there's an error reading settings
        return Decimal('1.0')



def fetch_fiat_rates():
    try:
        response = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=10)
        if response.status_code == 200:
            return response.json().get('rates', {})
    except Exception:
        pass
    return {'NGN': 1500}

def get_xlm_to_usd():
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=stellar&vs_currencies=usd', timeout=10)
        if response.status_code == 200:
            return Decimal(str(response.json().get('stellar', {}).get('usd', 0.1)))
    except Exception:
        pass
    return Decimal('0.1')

def get_btc_to_usd():
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd', timeout=10)
        if response.status_code == 200:
            return Decimal(str(response.json().get('bitcoin', {}).get('usd', 50000)))
    except Exception:
        pass
    return Decimal('50000')

@shared_task
def monitor_wallet_balances():
    """
    Periodic task to monitor Circle USDC, Stellar XLM, and Bitcoin BTC wallet balances.
    Fetches external balances concurrently using asyncio to massively improve performance.
    When current balance > saved balance, creates a deposit transaction in Naira.
    """
    import asyncio
    try:
        # Get admin-configured sweep fee once for the entire task run
        sweep_fee_usd = get_crypto_sweep_fee_usd()
        sweep_fee_btc = get_crypto_sweep_fee_btc()
        
        circle_usdc = CircleUSDC()
        stellar_wallet = StellarWallet()
        bitcoin_wallet = BitcoinWallet()
        fiat_rates = fetch_fiat_rates()
        xlm_to_usd = get_xlm_to_usd()
        btc_to_usd = get_btc_to_usd()
        
        total_processed = 0
        total_deposits = 0
        total_errors = 0
        
        usdc_wallets = list(CryptoLedger.objects.filter(asset='USDC'))
        xlm_wallets = list(CryptoLedger.objects.filter(asset='XLM'))
        btc_wallets = list(CryptoLedger.objects.filter(asset='BTC'))
        
        # --- PHASE 1: Fetch balances concurrently from blockchains ---
        async def fetch_all_balances():
            tasks = []
            
            # Map wallets to their async fetch operations
            for wallet in usdc_wallets:
                try:
                    wallet_id = CircleUSDC._decrypt_key(wallet.public_key)
                    tasks.append(asyncio.to_thread(circle_usdc.get_balance, wallet_id, 'USDC'))
                except Exception:
                    tasks.append(asyncio.to_thread(lambda: Exception("Decryption Error")))
                    
            for wallet in xlm_wallets:
                try:
                    public_key = StellarWallet._decrypt_key(wallet.public_key)
                    tasks.append(asyncio.to_thread(stellar_wallet.get_balance, public_key, 'XLM'))
                except Exception:
                    tasks.append(asyncio.to_thread(lambda: Exception("Decryption Error")))
                    
            for wallet in btc_wallets:
                try:
                    address = BitcoinWallet._decrypt_key(wallet.public_key)
                    tasks.append(asyncio.to_thread(bitcoin_wallet.get_balance, address, 'BTC'))
                except Exception:
                    tasks.append(asyncio.to_thread(lambda: Exception("Decryption Error")))

            return await asyncio.gather(*tasks, return_exceptions=True)
            
        # Run async event loop to fetch everything at once
        results = asyncio.run(fetch_all_balances())
        
        # Unpack results
        usdc_results = results[0:len(usdc_wallets)]
        xlm_results = results[len(usdc_wallets):len(usdc_wallets)+len(xlm_wallets)]
        btc_results = results[len(usdc_wallets)+len(xlm_wallets):]
        
        # --- PHASE 2: Process USDC ---
        for i, wallet in enumerate(usdc_wallets):
            current_balance = usdc_results[i]
            if isinstance(current_balance, Exception):
                total_errors += 1
                continue
                
            try:
                # Optimistic check before locking
                if Decimal(str(current_balance)) <= Decimal(str(wallet.balance)):
                    total_processed += 1
                    continue
                    
                with transaction.atomic():
                    locked_wallet = CryptoLedger.objects.select_for_update().get(pk=wallet.pk)
                    saved_balance = Decimal(str(locked_wallet.balance))
                    balance_delta = Decimal(str(current_balance)) - saved_balance
                    threshold = Decimal('0.0000001')
                    
                    if balance_delta <= threshold:
                        total_processed += 1
                        continue
                        
                    deposit_amount_usdc = balance_delta
                    sweep_fee_usdc = sweep_fee_usd
                    
                    if deposit_amount_usdc <= sweep_fee_usdc:
                        locked_wallet.balance = current_balance
                        locked_wallet.last_checked = timezone.now()
                        locked_wallet.save(update_fields=['balance', 'last_checked'])
                        total_processed += 1
                        continue
                        
                    net_deposit_usdc = deposit_amount_usdc - sweep_fee_usdc
                    user = locked_wallet.user
                    details = user.details.first() if hasattr(user, 'details') else None
                    user_currency = details.currency if details and hasattr(details, 'currency') else 'NGN'
                    usd_to_fiat = Decimal(str(fiat_rates.get(user_currency, 1500)))
                    deposit_amount_fiat = net_deposit_usdc * usd_to_fiat
                    
                    wallet_identifier = f"{locked_wallet.asset_chain}-{locked_wallet.uniq_id}"
                    description_pattern = f'USDC {locked_wallet.asset_chain} wallet deposit: {net_deposit_usdc:.7f}'
                    
                    recent_duplicate = UserTransactions.objects.filter(
                        user=user,
                        trx_source='crypto_wallet_monitor',
                        trx_type='credit',
                        trx_status='completed',
                        timestamp__gte=timezone.now() - timedelta(minutes=10),
                        description__contains=description_pattern
                    ).exists()
                    
                    if recent_duplicate:
                        locked_wallet.balance = current_balance
                        locked_wallet.last_checked = timezone.now()
                        locked_wallet.save(update_fields=['balance', 'last_checked'])
                        total_processed += 1
                        continue
                        
                    deposit_transaction = UserTransactions.objects.create(
                        user=user,
                        trx_amount=float(deposit_amount_fiat),
                        trx_currency=user_currency,
                        trx_type='credit',
                        trx_status='completed',
                        description=f'USDC {locked_wallet.asset_chain} wallet deposit: {net_deposit_usdc:.7f} USDC (fee: {sweep_fee_usdc:.7f} USDC) @ {usd_to_fiat} {user_currency}/USD',
                        trx_source='crypto_wallet_monitor',
                        user_collection_id='0',
                        destination_id=str(user.uniq_id)
                    )
                    
                    locked_wallet.balance = current_balance
                    locked_wallet.last_checked = timezone.now()
                    locked_wallet.save(update_fields=['balance', 'last_checked'])
                    
                    if user.user_email:
                        try:
                            send_mail.mailSender(
                                'crypto_deposit.html',
                                'Crypto Deposit Received',
                                [user.user_email],
                                {
                                    'user_name': user.user_email.split('@')[0],
                                    'asset': 'USDC',
                                    'amount_crypto': f"{net_deposit_usdc:.7f}",
                                    'amount_ngn': f"{deposit_amount_fiat:,.2f} {user_currency}",
                                    'fee': f"{sweep_fee_usdc:.7f} USDC",
                                    'transaction_id': str(deposit_transaction.trx_id),
                                    'date': datetime.now().strftime('%B %d, %Y at %I:%M %p'),
                                    'current_year': datetime.now().year
                                }
                            )
                        except Exception:
                            pass

                    try:
                        send_fcm_to_user(
                            user_id=str(user.user_id),
                            title="Crypto Deposit Received",
                            body=f"{net_deposit_usdc:.7f} USDC ({user_currency} {deposit_amount_fiat:,.2f}) credited to your wallet",
                            data={
                                "type": "crypto_deposit", "asset": "USDC",
                                "amount_crypto": str(net_deposit_usdc),
                                "amount_fiat": str(deposit_amount_fiat),
                                "currency": user_currency,
                                "fee": str(sweep_fee_usdc),
                                "transaction_id": str(deposit_transaction.trx_id)
                            }
                        )
                    except Exception:
                        pass
                    
                    total_deposits += 1
                    total_processed += 1
                    
            except Exception as e:
                total_errors += 1
                continue
                
        # --- PHASE 3: Process XLM ---
        for i, wallet in enumerate(xlm_wallets):
            current_balance = xlm_results[i]
            if isinstance(current_balance, Exception):
                total_errors += 1
                continue
                
            try:
                if Decimal(str(current_balance)) <= Decimal(str(wallet.balance)):
                    total_processed += 1
                    continue
                    
                with transaction.atomic():
                    locked_wallet = CryptoLedger.objects.select_for_update().get(pk=wallet.pk)
                    saved_balance = Decimal(str(locked_wallet.balance))
                    balance_delta = Decimal(str(current_balance)) - saved_balance
                    threshold = Decimal('0.0000001')
                    
                    if balance_delta <= threshold:
                        total_processed += 1
                        continue
                        
                    deposit_amount_xlm = balance_delta
                    sweep_fee_xlm = sweep_fee_usd / xlm_to_usd if xlm_to_usd > 0 else Decimal('0')
                    
                    if deposit_amount_xlm <= sweep_fee_xlm:
                        locked_wallet.balance = current_balance
                        locked_wallet.last_checked = timezone.now()
                        locked_wallet.save(update_fields=['balance', 'last_checked'])
                        total_processed += 1
                        continue
                        
                    net_deposit_xlm = deposit_amount_xlm - sweep_fee_xlm
                    user = locked_wallet.user
                    details = user.details.first() if hasattr(user, 'details') else None
                    user_currency = details.currency if details and hasattr(details, 'currency') else 'NGN'
                    usd_to_fiat = Decimal(str(fiat_rates.get(user_currency, 1500)))
                    deposit_amount_fiat = net_deposit_xlm * xlm_to_usd * usd_to_fiat
                    
                    description_pattern = f'XLM {locked_wallet.asset_chain} wallet deposit: {net_deposit_xlm:.7f}'
                    recent_duplicate = UserTransactions.objects.filter(
                        user=user, trx_source='crypto_wallet_monitor', trx_type='credit',
                        trx_status='completed', timestamp__gte=timezone.now() - timedelta(minutes=10),
                        description__contains=description_pattern
                    ).exists()
                    
                    if recent_duplicate:
                        locked_wallet.balance = current_balance
                        locked_wallet.last_checked = timezone.now()
                        locked_wallet.save(update_fields=['balance', 'last_checked'])
                        total_processed += 1
                        continue
                        
                    deposit_transaction = UserTransactions.objects.create(
                        user=user, trx_amount=float(deposit_amount_fiat), trx_currency=user_currency,
                        trx_type='credit', trx_status='completed',
                        description=f'XLM {locked_wallet.asset_chain} wallet deposit: {net_deposit_xlm:.7f} XLM (fee: {sweep_fee_xlm:.7f} XLM) @ {usd_to_fiat} {user_currency}/USD',
                        trx_source='crypto_wallet_monitor', user_collection_id='0', destination_id=str(user.uniq_id)
                    )
                    
                    locked_wallet.balance = current_balance
                    locked_wallet.last_checked = timezone.now()
                    locked_wallet.save(update_fields=['balance', 'last_checked'])
                    
                    if user.user_email:
                        try:
                            send_mail.mailSender(
                                'crypto_deposit.html', 'Crypto Deposit Received', [user.user_email],
                                {'user_name': user.user_email.split('@')[0], 'asset': 'XLM',
                                 'amount_crypto': f"{net_deposit_xlm:.7f}", 'amount_ngn': f"{deposit_amount_fiat:,.2f} {user_currency}",
                                 'fee': f"{sweep_fee_xlm:.7f} XLM", 'transaction_id': str(deposit_transaction.trx_id),
                                 'date': datetime.now().strftime('%B %d, %Y at %I:%M %p'), 'current_year': datetime.now().year}
                            )
                        except Exception: pass

                    try:
                        send_fcm_to_user(
                            user_id=str(user.user_id), title="Crypto Deposit Received",
                            body=f"{net_deposit_xlm:.7f} XLM ({user_currency} {deposit_amount_fiat:,.2f}) credited to your wallet",
                            data={"type": "crypto_deposit", "asset": "XLM", "amount_crypto": str(net_deposit_xlm),
                                  "amount_fiat": str(deposit_amount_fiat), "currency": user_currency, "fee": str(sweep_fee_xlm), "transaction_id": str(deposit_transaction.trx_id)}
                        )
                    except Exception: pass
                    
                    total_deposits += 1
                    total_processed += 1
                    
            except Exception as e:
                total_errors += 1
                continue
                
        # --- PHASE 4: Process BTC ---
        for i, wallet in enumerate(btc_wallets):
            current_balance = btc_results[i]
            if isinstance(current_balance, Exception):
                total_errors += 1
                continue
                
            try:
                if Decimal(str(current_balance)) <= Decimal(str(wallet.balance)):
                    total_processed += 1
                    continue
                    
                with transaction.atomic():
                    locked_wallet = CryptoLedger.objects.select_for_update().get(pk=wallet.pk)
                    saved_balance = Decimal(str(locked_wallet.balance))
                    balance_delta = Decimal(str(current_balance)) - saved_balance
                    threshold = Decimal('0.00000001')
                    
                    if balance_delta <= threshold:
                        total_processed += 1
                        continue
                        
                    deposit_amount_btc = balance_delta
                    sweep_fee_current_btc = sweep_fee_btc
                    
                    if deposit_amount_btc <= sweep_fee_current_btc:
                        locked_wallet.balance = current_balance
                        locked_wallet.last_checked = timezone.now()
                        locked_wallet.save(update_fields=['balance', 'last_checked'])
                        total_processed += 1
                        continue
                        
                    net_deposit_btc = deposit_amount_btc - sweep_fee_current_btc
                    user = locked_wallet.user
                    details = user.details.first() if hasattr(user, 'details') else None
                    user_currency = details.currency if details and hasattr(details, 'currency') else 'NGN'
                    usd_to_fiat = Decimal(str(fiat_rates.get(user_currency, 1500)))
                    deposit_amount_fiat = net_deposit_btc * btc_to_usd * usd_to_fiat
                    
                    description_pattern = f'BTC {locked_wallet.asset_chain} wallet deposit: {net_deposit_btc:.8f}'
                    recent_duplicate = UserTransactions.objects.filter(
                        user=user, trx_source='crypto_wallet_monitor', trx_type='credit',
                        trx_status='completed', timestamp__gte=timezone.now() - timedelta(minutes=10),
                        description__contains=description_pattern
                    ).exists()
                    
                    if recent_duplicate:
                        locked_wallet.balance = current_balance
                        locked_wallet.last_checked = timezone.now()
                        locked_wallet.save(update_fields=['balance', 'last_checked'])
                        total_processed += 1
                        continue
                        
                    deposit_transaction = UserTransactions.objects.create(
                        user=user, trx_amount=float(deposit_amount_fiat), trx_currency=user_currency,
                        trx_type='credit', trx_status='completed',
                        description=f'BTC {locked_wallet.asset_chain} wallet deposit: {net_deposit_btc:.8f} BTC (fee: {sweep_fee_current_btc:.8f} BTC) @ {usd_to_fiat} {user_currency}/USD',
                        trx_source='crypto_wallet_monitor', user_collection_id='0', destination_id=str(user.uniq_id)
                    )
                    
                    locked_wallet.balance = current_balance
                    locked_wallet.last_checked = timezone.now()
                    locked_wallet.save(update_fields=['balance', 'last_checked'])
                    
                    if user.user_email:
                        try:
                            send_mail.mailSender(
                                'crypto_deposit.html', 'Crypto Deposit Received', [user.user_email],
                                {'user_name': user.user_email.split('@')[0], 'asset': 'BTC',
                                 'amount_crypto': f"{net_deposit_btc:.8f}", 'amount_fiat': f"{deposit_amount_fiat:,.2f} {user_currency}",
                                 'fee': f"{sweep_fee_current_btc:.8f} BTC", 'transaction_id': str(deposit_transaction.trx_id),
                                 'date': datetime.now().strftime('%B %d, %Y at %I:%M %p'), 'current_year': datetime.now().year}
                            )
                        except Exception: pass

                    try:
                        send_fcm_to_user(
                            user_id=str(user.user_id), title="Crypto Deposit Received",
                            body=f"{net_deposit_btc:.8f} BTC ({user_currency} {deposit_amount_fiat:,.2f}) credited to your wallet",
                            data={"type": "crypto_deposit", "asset": "BTC", "amount_crypto": str(net_deposit_btc),
                                  "amount_fiat": str(deposit_amount_fiat), "currency": user_currency, "fee": str(sweep_fee_current_btc), "transaction_id": str(deposit_transaction.trx_id)}
                        )
                    except Exception: pass
                    
                    total_deposits += 1
                    total_processed += 1
                    
            except Exception as e:
                total_errors += 1
                continue
                
        return {
            'processed': total_processed,
            'deposits': total_deposits,
            'errors': total_errors
        }
    except Exception as e:
        return {'processed': 0, 'deposits': 0, 'errors': 1, 'message': str(e)}


@shared_task
def process_automatic_payroll():
    """
    Periodic task to run automated payroll processing.
    Checks for employees whose payout day matches the current day,
    and creates a transaction if they haven't been paid this month.
    """
    now = timezone.now()
    current_day = now.day

    # Get all active payrolls for businesses that have auto payroll enabled, are in NG, Tier 2 verified, and do NOT have withdrawals disabled
    active_payrolls = UserPayroll.objects.filter(
        pay_status='active',
        user_id__business_details__enable_auto_payroll=True,
        user_id__details__user_country='NG',
        user_id__kyb_verified=True
    ).exclude(user_id__withdrawals_disabled=True).distinct()

    transfers_payload = []
    valid_payrolls_data = []
    user_cumulative_deductions = {}
    users_notified_insufficient_funds = set()

    for payroll in active_payrolls:
        try:
            if getattr(payroll.user_id, 'withdrawals_disabled', False):
                logger.warning(f"Skipping automatic payroll for {payroll.account_name}: Withdrawals disabled for account {payroll.user_id.user_email}.")
                continue

            pay_date_str = payroll.get_pay_date()
            if not pay_date_str:
                continue

            # Parse date string (e.g. '2024-05-26')
            # Fallback to multiple formats in case it varies
            try:
                pay_date_obj = datetime.strptime(pay_date_str, "%Y-%m-%d")
            except ValueError:
                # If format is different, skip for safety or handle accordingly
                continue

            # Determine if payroll is due today based on frequency
            freq = payroll.get_pay_frequency() or 'monthly'
            is_due = False
            
            if freq == 'daily':
                is_due = True
            elif freq == 'weekly':
                is_due = pay_date_obj.weekday() == now.weekday()
            elif freq == 'quarterly':
                months_diff = (now.year - pay_date_obj.year) * 12 + now.month - pay_date_obj.month
                is_due = (pay_date_obj.day == current_day) and (months_diff >= 0 and months_diff % 3 == 0)
            elif freq == 'annually':
                is_due = (pay_date_obj.day == current_day) and (pay_date_obj.month == now.month)
            else: # monthly (default)
                is_due = pay_date_obj.day == current_day
                
            if is_due:
                # Ensure no duplicate payments for this cycle
                from datetime import timedelta
                
                query_kwargs = {
                    'user': payroll.user_id,
                    'trx_source': 'Payroll',
                    'user_collection_id': payroll.account_number,
                    'trx_status__in': ['completed', 'pending']
                }
                
                if freq == 'daily':
                    query_kwargs['timestamp__date'] = now.date()
                elif freq == 'weekly':
                    query_kwargs['timestamp__gte'] = now - timedelta(days=6)
                elif freq == 'quarterly':
                    quarter = (now.month - 1) // 3 + 1
                    query_kwargs['timestamp__year'] = now.year
                    query_kwargs['timestamp__month__gte'] = (quarter - 1) * 3 + 1
                    query_kwargs['timestamp__month__lte'] = quarter * 3
                elif freq == 'annually':
                    query_kwargs['timestamp__year'] = now.year
                else: # monthly
                    query_kwargs['timestamp__month'] = now.month
                    query_kwargs['timestamp__year'] = now.year
                    
                already_paid = UserTransactions.objects.filter(**query_kwargs).exists()

                if not already_paid:
                    amount = payroll.get_pay_amount() + payroll.get_allowances() - payroll.get_deductions()
                    if amount <= 0:
                        continue
                        
                    if not payroll.paystack_recipient_code:
                        rcp_resp = paystack.create_transfer_recipient(
                            name=payroll.account_name,
                            account_number=payroll.account_number,
                            bank_code=payroll.account_id
                        )
                        if rcp_resp.get("status"):
                            payroll.paystack_recipient_code = rcp_resp.get("data", {}).get("recipient_code")
                            payroll.save(update_fields=['paystack_recipient_code'])
                            
                    if not payroll.paystack_recipient_code:
                        logger.error(f"Cannot process automatic payroll for {payroll.account_name}: No valid Paystack recipient code.")
                        continue
                    
                    # Calculate available balance + overdraft
                    try:
                        
                        available_balance = calculate_total_balance(payroll.user_id)
                        
                        business_details = BusinessDetails.objects.filter(user=payroll.user_id).first()
                        overdraft_limit = float(business_details.payroll_overdraft or 0.0) if business_details else 0.0
                            
                        # Add cumulative deductions for this user
                        current_deductions = user_cumulative_deductions.get(payroll.user_id.id, 0.0)
                        total_required = float(amount) + current_deductions
                            
                        if total_required > (available_balance + overdraft_limit):
                            logger.error(f"Cannot process automatic payroll for {payroll.account_name}: Insufficient funds (Balance: {available_balance}, Overdraft: {overdraft_limit}, Required: {amount}, Cumulative: {current_deductions})")
                            
                            if payroll.user_id.user_email not in users_notified_insufficient_funds:
                                try:
                                    send_mail(
                                        subject="Insufficient Funds for Automated Payroll",
                                        message=f"Hello,\n\nYour automated payroll for {payroll.account_name} and potentially others could not be processed due to insufficient funds in your wallet.\n\nPlease top up your wallet to ensure your employees are paid.\n\nThank you,\nThe Flezpay Team",
                                        from_email="no-reply@flezpay.com",
                                        recipient_list=[payroll.user_id.user_email],
                                    )
                                    users_notified_insufficient_funds.add(payroll.user_id.user_email)
                                except Exception as e:
                                    logger.error(f"Failed to send insufficient funds email to {payroll.user_id.user_email}: {e}")
                            
                            continue
                            
                        # Funds are sufficient, update cumulative deductions
                        user_cumulative_deductions[payroll.user_id.id] = total_required
                            
                    except Exception as e:
                        logger.error(f"Error checking balance for automatic payroll {payroll.account_name}: {e}")
                        continue
                        
                    reference = f"PR-{uuid.uuid4().hex[:12].upper()}"
                    
                    transfers_payload.append({
                        "amount": int(amount * 100),
                        "recipient": payroll.paystack_recipient_code,
                        "reference": reference,
                        "reason": f"Automated Payroll Disbursement: {payroll.account_name}"
                    })
                    
                    valid_payrolls_data.append({
                        "payroll": payroll,
                        "amount": amount,
                        "reference": reference
                    })
        except Exception as e:
            logger.error(f"Error processing automatic payroll for {payroll.account_name}: {e}")
            continue

    # Process bulk transfers in chunks of 100
    if transfers_payload:
        paystack = PaystackAPI()
        chunk_size = 100
        
        for i in range(0, len(transfers_payload), chunk_size):
            payload_chunk = transfers_payload[i:i + chunk_size]
            data_chunk = valid_payrolls_data[i:i + chunk_size]
            try:
                bulk_resp = paystack.bulk_transfer(payload_chunk)
                
                if not bulk_resp.get("status") and bulk_resp.get("meta", {}).get("invalidRecipients"):
                    invalid_recipients = bulk_resp.get("meta").get("invalidRecipients")
                    for item in data_chunk:
                        p = item["payroll"]
                        if p.paystack_recipient_code in invalid_recipients:
                            rcp_resp = paystack.create_transfer_recipient(
                                name=p.account_name,
                                account_number=p.account_number,
                                bank_code=p.account_id
                            )
                            if rcp_resp.get("status"):
                                new_rcp = rcp_resp.get("data", {}).get("recipient_code")
                                p.paystack_recipient_code = new_rcp
                                p.save(update_fields=['paystack_recipient_code'])
                                for p_item in payload_chunk:
                                    if p_item["reference"] == item["reference"]:
                                        p_item["recipient"] = new_rcp
                    
                    bulk_resp = paystack.bulk_transfer(payload_chunk)
                
                if bulk_resp.get("status") is True:
                    # Create pending UserTransactions for all successful transfers in this chunk
                    transactions_to_create = []
                    for item in data_chunk:
                        p = item["payroll"]
                        transactions_to_create.append(
                            UserTransactions(
                                user=p.user_id,
                                trx_amount=Decimal(str(item["amount"])),
                                trx_currency='NGN',
                                trx_type='payment',
                                trx_status='pending',
                                description=item["reference"],
                                user_collection_id=p.account_number,
                                destination_id=p.bank_name or '0',
                                trx_source='Payroll'
                            )
                        )
                    UserTransactions.objects.bulk_create(transactions_to_create)
                else:
                    err_msg = bulk_resp.get('message', 'Unknown error')
                    meta = bulk_resp.get('meta', {})
                    if meta:
                        invalid_recipients = meta.get('invalidRecipients', [])
                        if invalid_recipients:
                            failed_names = []
                            for item in data_chunk:
                                if item['payroll'].paystack_recipient_code in invalid_recipients:
                                    failed_names.append(item['payroll'].account_name)
                            if failed_names:
                                err_msg += f". Invalid employees: {', '.join(failed_names)}"
                    
                    logger.error(f"Paystack bulk transfer failed for chunk {i//chunk_size + 1}: {err_msg}")
                    try:
                        settings_obj = models.SiteSettings.objects.first()
                        admin_email = settings_obj.email if settings_obj else 'help@flezpay.com'
                        send_mail(
                            subject="Paystack Bulk Transfer Error",
                            message=f"An error occurred during automatic payroll bulk transfer.\n\nAPI Response:\n{err_msg}",
                            from_email="no-reply@flezpay.com",
                            recipient_list=[admin_email],
                            fail_silently=True,
                        )
                    except Exception:
                        pass
                    
            except Exception as e:
                logger.error(f"Exception during bulk transfer for chunk {i//chunk_size + 1}: {e}")
                try:
                    settings_obj = models.SiteSettings.objects.first()
                    admin_email = settings_obj.email if settings_obj else 'help@flezpay.com'
                    send_mail(
                        subject="Paystack Bulk Transfer Exception",
                        message=f"An exception occurred during automatic payroll bulk transfer.\n\nException:\n{str(e)}",
                        from_email="no-reply@flezpay.com",
                        recipient_list=[admin_email],
                        fail_silently=True,
                    )
                except Exception:
                    pass


@shared_task
def process_domain_purchase_task(user_id, domain_name, extension, transaction_id, server_ip):
    
    try:
        user = models.UserSecure.objects.get(user_id=user_id)
        trx = models.UserTransactions.objects.get(trx_id=transaction_id)
        
        op = OpenproviderAPI()
        reg_result = op.register_domain(domain_name, extension)
        
        if reg_result.get('status') != 'success':
            # Handle failure: Refund user
            trx.trx_status = 'failed'
            trx.save()
            
            # Create refund
            models.UserTransactions.objects.create(
                user=user,
                trx_status='completed',
                trx_amount=trx.trx_amount,
                trx_type='credit',
                trx_source='Domain Purchase Refund',
                trx_currency=trx.trx_currency,
                description=f"Refund for failed domain purchase: {domain_name}.{extension}",
                user_collection_id='DOMAIN-REFUND',
                destination_id='System'
            )
            
            # Send error email to admin
            try:
                settings_obj = models.SiteSettings.objects.first()
                admin_email = settings_obj.email if settings_obj else 'help@flezpay.com'
                
                html_content = render_to_string('emails/domain_api_error.html', {
                    'action': 'Domain Registration',
                    'domain_name': domain_name,
                    'extension': extension,
                    'api_message': reg_result.get('message')
                })
                
                send_mail(
                    subject=f'Domain Registration Error: {domain_name}.{extension}',
                    message=f"Error registering domain {domain_name}.{extension}:\n\nAPI Response:\n{reg_result.get('message')}",
                    from_email='no-reply@flezpay.com',
                    recipient_list=[admin_email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception:
                pass
                
            return False
            
        # Success
        trx.trx_status = 'completed'
        trx.save()
        
        # Setup DNS Zone automatically
        op.create_dns_zone(domain_name, extension, server_ip)
        
        # Schedule SSL provisioning
        provision_ssl_task.apply_async(args=[domain_name, extension], countdown=300)
        
        # Update store custom domain
        business = models.BusinessDetails.objects.filter(user=user, store_setup=True).first() or models.BusinessDetails.objects.filter(user=user).first()
        if business:
            business.store_custom_domain = f"{domain_name}.{extension}"
            business.save(update_fields=['store_custom_domain'])
            
        # Send a notification
        models.Notifications.objects.create(
            user=user,
            title='Domain Purchased',
            description=f'You have successfully purchased and connected {domain_name}.{extension} to your store.',
            notification_type='tranc_success'
        )
        
        return True
    except Exception as e:
        return False

@shared_task
def process_domain_transfer_task(user_id, domain_name, extension, auth_code, transaction_id, server_ip=None):
    
    try:
        user = models.UserSecure.objects.get(user_id=user_id)
        trx = models.UserTransactions.objects.get(trx_id=transaction_id)
        
        op = OpenproviderAPI()
        trans_result = op.transfer_domain(domain_name, extension, auth_code)
        
        if trans_result.get('status') != 'success':
            # Handle failure: Refund user
            trx.trx_status = 'failed'
            trx.save()
            
            # Create refund
            models.UserTransactions.objects.create(
                user=user,
                trx_status='completed',
                trx_amount=trx.trx_amount,
                trx_type='credit',
                trx_source='Domain Transfer Refund',
                trx_currency=trx.trx_currency,
                description=f"Refund for failed domain transfer: {domain_name}.{extension} - {trans_result.get('message', 'Unknown Error')}",
                user_collection_id='DOMAIN-REFUND',
                destination_id='System'
            )
            
            # Send error email to admin
            try:
                settings_obj = models.SiteSettings.objects.first()
                admin_email = settings_obj.email if settings_obj else 'help@flezpay.com'
                
                html_content = render_to_string('emails/domain_api_error.html', {
                    'action': 'Domain Transfer',
                    'domain_name': domain_name,
                    'extension': extension,
                    'api_message': trans_result.get('message')
                })
                
                send_mail(
                    subject=f'Domain Transfer Error: {domain_name}.{extension}',
                    message=f"Error transferring domain {domain_name}.{extension}:\n\nAPI Response:\n{trans_result.get('message')}",
                    from_email='no-reply@flezpay.com',
                    recipient_list=[admin_email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception:
                pass
                
            return False
            
        # Success
        trx.trx_status = 'completed'
        trx.save()
        
        # Note: OpenProvider transfer doesn't immediately setup DNS usually, but we could try.
        # For now, just mark success and notify.
        
        business = models.BusinessDetails.objects.filter(user=user, store_setup=True).first() or models.BusinessDetails.objects.filter(user=user).first()
        if business:
            business.store_custom_domain = f"{domain_name}.{extension}"
            business.save(update_fields=['store_custom_domain'])
            
        models.Notifications.objects.create(
            user=user,
            title='Domain Transfer Initiated',
            description=f'Transfer process started for {domain_name}.{extension}. This usually takes a few days.',
            notification_type='tranc_success'
        )
        
        return True
    except Exception as e:
        return False



@shared_task
def forward_webhook_to_logistics_task(raw_body_str, signature, event_type):

    logger = logging.getLogger(__name__)

    forwardable_events = [
        'charge.success',
        'charge.failed',
        'transfer.success',
        'transfer.failed',
        'transfer.reversed'
    ]
    
    if event_type not in forwardable_events:
        return
    
    logistics_webhook_url = os.getenv('LOGISTICS_WEBHOOK_URL')
    if not logistics_webhook_url:
        return
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'X-Paystack-Signature': signature,
            'X-Forwarded-From': 'flezpay-backend',
        }
        # Encode back to bytes
        raw_body_bytes = raw_body_str.encode('utf-8')
        
        response = requests.post(
            logistics_webhook_url,
            data=raw_body_bytes,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully forwarded {event_type} webhook to logistics backend")
        else:
            logger.warning(f"Logistics backend returned {response.status_code} for {event_type}")
            
    except Exception as e:
        logger.error(f"Error forwarding {event_type} webhook to logistics backend: {e}")



@shared_task
def process_psb_webhook_task(data, account_number):
    
    logger = logging.getLogger(__name__)

    try:
        psb_api = PSB()
        response = psb_api.webhook_response(data, account_number)
        
        # Original code used to save this to a json file in the webhook directory.
        # We can still do it, but maybe in a better place. For now, matching legacy:
        try:
            current_path = Path(__file__).resolve().parent.parent / 'api' / 'webhook'
            if current_path.exists():
                with open(f'{current_path}/{datetime.now().strftime("%Y%m%d_%H%M%S")}_webhook_response.json', 'w') as file:
                    file.write(json.dumps(data))
        except Exception as file_e:
            logger.error(f"Failed to write webhook json: {file_e}")

        if 'code' in response and response['code'] != '00':
            logger.warning(f"PSB webhook response returned code {response['code']}: {response}")
            return False
            
        logger.info(f"PSB webhook processed successfully for account {account_number}")
        return True
    except Exception as e:
        logger.error(f"Error processing PSB webhook: {e}")
        return False


@shared_task
def send_pending_livechat_notifications():
    from api.models import LiveChat
    from django.utils import timezone
    from django.core.mail import send_mail
    from django.conf import settings
    from datetime import timedelta
    
    # We want chats that:
    # 1. Are open
    # 2. Have not had a notification sent yet
    # 3. Have at least one message
    chats = LiveChat.objects.filter(status='open', notification_sent=False).prefetch_related('messages', 'store__user')
    
    for chat in chats:
        last_msg = chat.messages.last()
        if last_msg and last_msg.sender_type == 'visitor' and not last_msg.is_read:
            # Check if last message is older than 1 minute
            if last_msg.created_at <= timezone.now() - timedelta(minutes=1):
                try:
                    owner_email = chat.store.user.user_email
                    store_name = chat.store.store_name
                    
                    user_details = chat.store.user.details.first()
                    owner_name = user_details.first_name if user_details and user_details.first_name else "Store Owner"
                    
                    from django.template.loader import render_to_string
                    import zoneinfo
                    user_tz = zoneinfo.ZoneInfo(user_details.user_timezone) if user_details and user_details.user_timezone else timezone.get_default_timezone()
                    
                    context = {
                        'owner_name': owner_name,
                        'store_name': store_name,
                        'message_text': last_msg.message_text,
                        'timestamp': timezone.localtime(last_msg.created_at, user_tz).strftime("%B %d, %Y at %I:%M %p"),
                        'dashboard_link': getattr(settings, 'FRONTEND_URL', 'https://flezpay.com') + "/livechat"
                    }
                    html_content = render_to_string('emails/unread_chat.html', context)
                    
                    send_mail(
                        subject=f"New pending chat message on {store_name}",
                        message=f"You have a new unread message from a visitor on your store {store_name}.\n\nMessage: {last_msg.message_text}\n\nPlease login to your dashboard to reply.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[owner_email],
                        fail_silently=True,
                        html_message=html_content
                    )
                    
                    # Mark as sent
                    chat.notification_sent = True
                    chat.save(update_fields=['notification_sent'])
                except Exception as e:
                    logger.error(f"Failed to send pending chat notification to merchant: {e}")

@shared_task
def send_pending_visitor_livechat_notifications():
    from api.models import LiveChat
    from django.utils import timezone
    from django.core.mail import send_mail
    from django.conf import settings
    from datetime import timedelta
    
    chats = LiveChat.objects.filter(status='open', notification_sent=False).prefetch_related('messages', 'store__user', 'visitor')
    logger.info(f"[VisitorChatNotify] Found {chats.count()} open chats with notification_sent=False")
    
    for chat in chats:
        last_msg = chat.messages.last()
        if not last_msg:
            logger.info(f"[VisitorChatNotify] Chat {chat.id} has no messages, skipping")
            continue
            
        logger.info(f"[VisitorChatNotify] Chat {chat.id} last message sender_type={last_msg.sender_type}, is_read={last_msg.is_read}, created_at={last_msg.created_at}")
        
        # Check if last message is older than 1 minute
        time_diff = timezone.now() - last_msg.created_at
        logger.info(f"[VisitorChatNotify] Chat {chat.id} message age: {time_diff.total_seconds()} seconds")
        
        if last_msg.created_at <= timezone.now() - timedelta(minutes=1):
            if last_msg.sender_type == 'agent' and not last_msg.is_read:
                # Notification to Visitor (Customer)
                visitor = chat.visitor
                logger.info(f"[VisitorChatNotify] Chat {chat.id} visitor email: {visitor.visitor_email}")
                if visitor.visitor_email:
                    try:
                        store_name = chat.store.store_name
                        visitor_name = visitor.visitor_name or "there"
                        
                        from django.template.loader import render_to_string
                        
                        STORE_BASE_DOMAIN = getattr(settings, 'STORE_BASE_DOMAIN', 'localhost:8000')
                        STORE_PROTOCOL = getattr(settings, 'STORE_PROTOCOL', 'http' if settings.DEBUG else 'https')
                        store_link = f"{STORE_PROTOCOL}://{chat.store.store_slug}.{STORE_BASE_DOMAIN}/"
                        
                        context = {
                            'visitor_name': visitor.visitor_name,
                            'store_name': store_name,
                            'message_text': last_msg.message_text,
                            'timestamp': last_msg.created_at.strftime("%B %d, %Y at %I:%M %p"),
                            'store_link': store_link
                        }
                        html_content = render_to_string('emails/unread_chat_visitor.html', context)
                        
                        send_mail(
                            subject=f"New message from {store_name}",
                            message=f"Hello {visitor_name},\n\nThe support agent at {store_name} has replied to your message:\n\n\"{last_msg.message_text}\"\n\nPlease visit {store_link} to view and reply.",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[visitor.visitor_email],
                            fail_silently=True,
                            html_message=html_content
                        )
                        
                        # Mark as sent so we don't spam them
                        chat.notification_sent = True
                        chat.save(update_fields=['notification_sent'])
                        logger.info(f"Sent unread chat notification to visitor {visitor.visitor_email}")
                    except Exception as e:
                        logger.error(f"Failed to send pending chat notification to visitor: {e}")
                else:
                    logger.info(f"[VisitorChatNotify] Chat {chat.id} has no registered visitor email. Marking notification_sent=True to skip.")
                    # Mark as sent even if they don't have email, to avoid reprocessing
                    chat.notification_sent = True
                    chat.save(update_fields=['notification_sent'])

@shared_task
def send_business_reports():
    """
    Sends weekly business reports to users whose subscription plan has business_reporting=True.
    Includes revenue chart and critically low stock items.
    """
    from api.models import BusinessDetails, SubscriptionPlans, UserTransactions, UserItems, UserSecure
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils import timezone
    from datetime import timedelta
    import os
    import urllib.parse
    import json
    
    # Get all active plans that have business reporting enabled
    reporting_plans = SubscriptionPlans.objects.filter(business_reporting=True).values_list('uniq_id', flat=True)
    if not reporting_plans:
        return
        
    businesses = BusinessDetails.objects.filter(plan_code__in=reporting_plans)
    
    end_date = timezone.now()
    start_date = end_date - timedelta(days=7)
    
    for business in businesses:
        user_secure = business.user
        
        # Check if user has Email Reports enabled in Notification Preferences
        privacy_settings = user_secure.privacy_settings or {}
        # Default to True, but if explicitly set to False, skip
        if not privacy_settings.get('notifications_email', True):
            continue
            
        # Calculate revenue for the last 7 days
        # Group by day
        daily_revenue = {}
        for i in range(7):
            d = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            daily_revenue[d] = 0.0
            
        transactions = UserTransactions.objects.filter(
            user=user_secure,
            trx_type='credit',
            trx_status='completed',
            timestamp__gte=start_date,
            timestamp__lte=end_date
        )
        
        total_revenue = 0.0
        for t in transactions:
            try:
                amt = float(t.trx_amount)
                day_str = t.timestamp.strftime('%Y-%m-%d')
                if day_str in daily_revenue:
                    daily_revenue[day_str] += amt
                total_revenue += amt
            except (ValueError, TypeError):
                pass
                
        # Generate QuickChart URL
        labels = list(daily_revenue.keys())
        # Shorten labels to 'Mon', 'Tue', etc.
        short_labels = [(start_date + timedelta(days=i)).strftime('%a') for i in range(7)]
        data = list(daily_revenue.values())
        
        chart_config = {
            "type": "bar",
            "data": {
                "labels": short_labels,
                "datasets": [{
                    "label": "Revenue",
                    "data": data,
                    "backgroundColor": "rgba(79, 70, 229, 0.8)",
                    "borderColor": "rgb(79, 70, 229)",
                    "borderWidth": 1
                }]
            },
            "options": {
                "title": {"display": True, "text": "7-Day Revenue"},
                "scales": {
                    "yAxes": [{"ticks": {"beginAtZero": True}}]
                }
            }
        }
        
        chart_url = f"https://quickchart.io/chart?c={urllib.parse.quote(json.dumps(chart_config))}&w=600&h=300"
        
        # Get currency symbol
        user_details = getattr(user_secure, 'details', None)
        currency = '₦'
        if user_details and user_details.exists():
            curr = user_details.first().currency
            if curr == 'USD': currency = '$'
            elif curr == 'EUR': currency = '€'
            elif curr == 'GBP': currency = '£'
        
        # Render and send email
        context = {
            'store_name': business.store_name or 'Your Store',
            'total_revenue': f"{total_revenue:,.2f}",
            'currency': currency,
            'chart_url': chart_url
        }
        
        email_body = render_to_string('emails/business_report.html', context)
        
        try:
            send_mail(
                subject="Your Weekly Business Report",
                message="Your weekly business report is ready. Please view this email in an HTML-compatible client.",
                from_email=os.getenv("EMAIL_HOST_USER"),
                recipient_list=[user_secure.user_email],
                html_message=email_body
            )
            logger.info(f"Sent business report to {user_secure.user_email}")
        except Exception as e:
            logger.error(f"Failed to send business report to {user_secure.user_email}: {e}")

@shared_task
def send_pos_order_status_email(order_id, target_currency, final_amount, dashboard_url=None):
    from api.models import POSKitOrder, UserDetails
    try:
        order = POSKitOrder.objects.get(id=order_id)
        details = UserDetails.objects.get(user=order.user)
        
        if not dashboard_url:
            dashboard_url = f"{getattr(settings, 'FRONTEND_URL', 'https://flezpay.com')}/pos"
            
        context = {
            'first_name': details.first_name,
            'currency': target_currency,
            'amount': f"{final_amount:,.2f}" if final_amount else "0.00",
            'units': order.units,
            'delivery_address': order.address,
            'state': order.state,
            'country': order.country,
            'phone_number': order.phone,
            'email': order.email,
            'status': order.status,
            'dashboard_url': dashboard_url
        }
        
        if order.status == 'pending':
            subject = "Your FlezPay POS Kit Order is being processed"
            template = 'emails/pos_kit_purchase.html'
        else:
            subject = "Your FlezPay POS Kit Order has been processed"
            template = 'emails/pos_kit_processed.html'
            
        html_body = render_to_string(template, context)
        
        email = EmailMessage(
            subject=subject,
            body=html_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.email, order.user.user_email]
        )
        email.content_subtype = "html"
        email.send(fail_silently=True)
    except POSKitOrder.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Failed to send POS order email for order {order_id}: {e}")


@shared_task
def send_promo_claim_congratulations(user_id, plan_name):
    from api.models import UserSecure
    try:
        user = UserSecure.objects.get(user_id=user_id)
        details = user.details.first()
        if not user.user_email:
            return
            
        dashboard_url = f"{getattr(settings, 'FRONTEND_URL', 'https://flezpay.com')}/dashboard"
        
        context = {
            'first_name': details.first_name if details else user.user_email.split('@')[0],
            'plan_name': plan_name,
            'dashboard_url': dashboard_url,
        }
        
        html_body = render_to_string('emails/promo_claimed.html', context)
        
        email = EmailMessage(
            subject="Congratulations! You've successfully claimed your promo",
            body=html_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.user_email]
        )
        email.content_subtype = "html"
        email.send(fail_silently=True)
    except Exception as e:
        logger.error(f"Failed to send promo claim congratulatory email to user {user_id}: {e}")

@shared_task
def notify_subscription_expiry():
    from api.models import BusinessDetails
    try:
        businesses = BusinessDetails.objects.all()
        now = timezone.now()
        
        for business in businesses:
            expiry_str = business.subscription_expiry
            if not expiry_str:
                continue
                
            try:
                expiry_date = datetime.fromisoformat(expiry_str)
            except ValueError:
                continue
                
            if timezone.is_naive(expiry_date):
                expiry_date = timezone.make_aware(expiry_date)
                
            days_left = (expiry_date.date() - now.date()).days
            
            # Notify on exactly 5 days and 3 days left
            if days_left in [3, 5]:
                user_secure = business.user
                if not user_secure or not user_secure.user_email:
                    continue
                    
                context = {
                    'store_name': business.store_name or 'Your Store',
                    'days_left': days_left,
                    'expiry_date': expiry_date.strftime('%B %d, %Y')
                }
                
                email_body = render_to_string('emails/subscription_expiry.html', context)
                
                try:
                    send_mail(
                        subject=f"Action Required: Your FlezPay subscription expires in {days_left} days",
                        message=f"Your subscription is expiring in {days_left} days. Please renew.",
                        from_email=os.getenv("EMAIL_HOST_USER"),
                        recipient_list=[user_secure.user_email],
                        html_message=email_body,
                        fail_silently=True
                    )
                    logger.info(f"Sent {days_left}-day subscription expiry notice to {user_secure.user_email}")
                except Exception as inner_e:
                    logger.error(f"Failed to send subscription expiry to {user_secure.user_email}: {inner_e}")
                    
    except Exception as e:
        logger.error(f"Failed to process subscription expiry notifications: {e}")

@shared_task
def send_low_stock_alerts():
    from api.models import BusinessDetails, UserItems
    try:
        businesses = BusinessDetails.objects.all()
        
        for business in businesses:
            user_secure = business.user
            if not user_secure or not user_secure.user_email:
                continue
                
            privacy_settings = user_secure.privacy_settings or {}
            if not privacy_settings.get('notifications_stock', False):
                continue
                
            low_stock_qs = UserItems.objects.filter(user=user_secure, item_quantity__lte=2).order_by('item_quantity')
            if not low_stock_qs.exists():
                continue
                
            low_stock_items = []
            for item in low_stock_qs:
                first_img = item.images.first()
                image_url = None
                if first_img and first_img.image:
                    image_url = first_img.image.url
                    if image_url.startswith('/'):
                        from django.conf import settings
                        STORE_BASE_DOMAIN = getattr(settings, 'STORE_BASE_DOMAIN', 'localhost:8000')
                        STORE_PROTOCOL = getattr(settings, 'STORE_PROTOCOL', 'http' if settings.DEBUG else 'https')
                        image_url = f"{STORE_PROTOCOL}://{STORE_BASE_DOMAIN}{image_url}"
                
                low_stock_items.append({
                    "name": item.item_name,
                    "quantity": item.item_quantity,
                    "image_url": image_url
                })
            
            context = {
                'store_name': business.store_name or 'Your Store',
                'low_stock_items': low_stock_items
            }
            
            email_body = render_to_string('emails/low_stock_alert.html', context)
            
            try:
                send_mail(
                    subject="Low Stock Alert - Flezpay",
                    message="Some of your items are running critically low on stock. Please restock them soon.",
                    from_email=os.getenv("EMAIL_HOST_USER"),
                    recipient_list=[user_secure.user_email],
                    html_message=email_body,
                    fail_silently=True
                )
                logger.info(f"Sent low stock alert to {user_secure.user_email}")
            except Exception as inner_e:
                logger.error(f"Failed to send low stock alert to {user_secure.user_email}: {inner_e}")
                
    except Exception as e:
        logger.error(f"Failed to process low stock alerts: {e}")

@shared_task
def generate_ai_promotion_task(user_id, preferences, task_id):
    from api.models import UserSecure
    from api.services.ai_promotion_service import AIPromotionService
    from django.core.cache import cache
    from django.core.mail import send_mail
    from django.conf import settings
    import traceback
    
    try:
        user_secure = UserSecure.objects.get(pk=user_id)
        service = AIPromotionService(user_secure)
        plan = service.generate_promotion_plan(preferences)
        
        # Save plan to cache for 24 hours
        cache.set(f"ai_plan_{task_id}", plan, timeout=86400)
        
        # Send email
        from api.functions import send_mail
        context = {
            "business_name": "Flezpay",
            "message": "Your AI Campaign plan has been generated successfully! Please return to the AI Creator in your browser to view it and continue."
        }
        send_mail.mailSender(
            'staff_message.html',
            "Your AI Campaign is Ready - Flezpay",
            [user_secure.user_email],
            context=context
        )
        logger.info(f"Generated AI Plan for task {task_id}")
        
    except Exception as e:
        # Save error to cache
        cache.set(f"ai_plan_{task_id}", {"error": str(e)}, timeout=86400)
        logger.error(f"Failed to generate AI plan for task {task_id}: {e}")
        try:
            from api.models import SystemErrorLog
            SystemErrorLog.objects.create(
                log_type='growth_ai_creator_task',
                message=str(e),
                traceback=traceback.format_exc(),
            )
        except:
            pass

@shared_task
def generate_ai_insights_task(user_id, task_id):
    """
    Background Celery task to generate Smart AI Insights for a merchant.
    Gathers business performance data, calls Ollama (with intelligent fallback),
    and caches the structured payload for UI polling and immediate tab view.
    """
    from django.core.cache import cache
    from django.utils.timezone import now
    import traceback
    from api.models import UserSecure, SystemErrorLog
    from api.functions.ai_business_tools import build_ai_performance_data, get_business_summary
    from api.functions.ai_chat import AIChatHandler

    try:
        user_secure = UserSecure.objects.get(pk=user_id)
        from api.ai_insights_views import (
            _get_business_owner,
            _cache_key,
            _build_insights_prompt,
            _call_ollama_structured,
            _build_metrics_snapshot,
            _generate_fallback_insights,
            AI_INSIGHTS_CACHE_TTL,
        )

        business_user = _get_business_owner(user_secure)

        try:
            performance_data = build_ai_performance_data(business_user)
            summary = get_business_summary(business_user)
            currency = summary.get('currency', '₦')
        except Exception as e:
            logger.error(f"generate_ai_insights_task: failed to build context for user {user_id}: {e}")
            cache.set(f"ai_insights_task_{task_id}", {"error": "Could not load business analytics data."}, timeout=86400)
            return

        has_data = (
            summary.get('sales_this_month', 0) > 0 or
            summary.get('total_products', 0) > 0 or
            summary.get('completed_count', 0) > 0
        )

        if not has_data:
            payload = {
                'status': 'no_data',
                'generated_at': now().isoformat(),
                'from_cache': False,
                'summary': (
                    "There isn't enough transaction data yet to generate meaningful AI insights. "
                    "Complete a few sales and check back — insights improve as your data grows."
                ),
                'opportunities': [],
                'recommendations': [
                    {
                        'title': 'Add your products',
                        'description': 'Start by adding products to your inventory so FlezPay can track your sales performance.',
                        'cta_label': 'View Inventory',
                        'cta_type': 'view_inventory'
                    }
                ],
                'data_quality': 'insufficient',
                'metrics_snapshot': _build_metrics_snapshot(summary, performance_data)
            }
        else:
            handler = AIChatHandler(performance_data=performance_data, user=business_user, currency=currency)
            data_summary = handler._build_data_summary()
            prompt = _build_insights_prompt(data_summary, currency)

            try:
                insights = _call_ollama_structured(prompt)
            except Exception as e:
                logger.warning(f"generate_ai_insights_task: Ollama call failed ({e}). Using heuristic insight generator.")
                insights = _generate_fallback_insights(summary, performance_data, currency)

            payload = {
                'status': 'ok',
                'generated_at': now().isoformat(),
                'from_cache': False,
                'summary': insights.get('summary', ''),
                'opportunities': insights.get('opportunities', []),
                'recommendations': insights.get('recommendations', []),
                'data_quality': insights.get('data_quality', 'sufficient'),
                'metrics_snapshot': _build_metrics_snapshot(summary, performance_data)
            }

        # Cache task status for polling
        cache.set(f"ai_insights_task_{task_id}", payload, timeout=86400)
        # Cache standard key for fast GETs
        cache.set(_cache_key(business_user), payload, timeout=AI_INSIGHTS_CACHE_TTL)
        logger.info(f"generate_ai_insights_task: Successfully generated insights for user {user_id}, task {task_id}")

    except Exception as e:
        logger.error(f"generate_ai_insights_task failed for task {task_id}: {e}")
        cache.set(f"ai_insights_task_{task_id}", {"error": str(e)}, timeout=86400)
        try:
            SystemErrorLog.objects.create(
                log_type='ai_insights_task',
                message=str(e),
                traceback=traceback.format_exc(),
            )
        except Exception:
            pass

@shared_task
def cleanup_pending_invoices():
    """
    Delete all invoices that are not installment, have pending payment,
    and are older than 1 hour.
    """
    from .models import UserInvoices
    
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    invoices_to_delete = UserInvoices.objects.filter(
        invoice_status='pending',
        delivery_status='pending',
        timestamp__lt=one_hour_ago
    ).exclude(
        invoice_type='installment'
    )
    
    count, _ = invoices_to_delete.delete()
    if count > 0:
        logger.info(f"Deleted {count} pending invoices older than 1 hour.")


@shared_task
def send_store_created_instant_email_task(user_id):
    from api.models import UserSecure, BusinessDetails
    from api.functions import send_mail
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        user = UserSecure.objects.get(user_id=user_id)
        business_details = BusinessDetails.objects.filter(user=user).first()
        
        if not business_details or not business_details.store_setup:
            return
            
        whatsapp_link = "https://chat.whatsapp.com/G3ryIgjSXc07o9dJXQX6fo?s=cl&p=a&ilr=1"
        youtube_link = "https://youtu.be/gRn2iueCOPw"
        
        details = user.details.first() if hasattr(user, 'details') else None
        user_name = details.first_name if details and details.first_name else user.user_email.split('@')[0]
        
        if business_details.store_custom_domain:
            store_link = f"https://{business_details.store_custom_domain}"
        elif business_details.store_domain:
            store_link = f"https://{business_details.store_domain}"
        else:
            store_link = "https://flezpay.com"
        
        context = {
            'user_name': user_name,
            'whatsapp_link': whatsapp_link,
            'youtube_link': youtube_link,
            'store_link': store_link,
        }
        
        try:
            send_mail.mailSender(
                'store_created_instant.html',
                'Congratulations! Your Store Is Live - Flezpay',
                [user.user_email],
                context
            )
        except Exception as e:
            logger.error(f"Failed to send instant store setup email to {user.user_email}: {e}")
            
    except Exception as e:
        logger.error(f"Error in send_store_created_instant_email_task for user {user_id}: {e}")


@shared_task
def check_store_setup_followup_task(user_id):
    from api.models import UserSecure, UserItems, BusinessDetails
    from api.functions import send_mail
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        user = UserSecure.objects.get(user_id=user_id)
        business_details = BusinessDetails.objects.filter(user=user).first()
        
        if not business_details or not business_details.store_setup or business_details.has_received_setup_email:
            return
            
        featured_items_count = UserItems.objects.filter(user=user, is_featured=True).count()
        if featured_items_count <= 0:
            whatsapp_link = "https://chat.whatsapp.com/G3ryIgjSXc07o9dJXQX6fo?s=cl&p=a&ilr=1"
            youtube_link = "https://youtu.be/gRn2iueCOPw"
            
            details = user.details.first() if hasattr(user, 'details') else None
            user_name = details.first_name if details and details.first_name else user.user_email.split('@')[0]
            
            if business_details.store_custom_domain:
                store_link = f"https://{business_details.store_custom_domain}"
            elif business_details.store_domain:
                store_link = f"https://{business_details.store_domain}"
            else:
                store_link = "https://flezpay.com"
            
            context = {
                'user_name': user_name,
                'whatsapp_link': whatsapp_link,
                'youtube_link': youtube_link,
                'store_link': store_link,
            }
            
            try:
                send_mail.mailSender(
                    'store_setup_followup.html',
                    'Complete Your Website Setup! - Need help?',
                    [user.user_email],
                    context
                )
                business_details.has_received_setup_email = True
                business_details.save(update_fields=['has_received_setup_email'])
            except Exception as e:
                logger.error(f"Failed to send store setup email to {user.user_email}: {e}")
                
    except Exception as e:
        logger.error(f"Error in check_store_setup_followup_task for user {user_id}: {e}")

@shared_task
def sweep_store_setup_followups_task():
    from api.models import BusinessDetails, UserItems
    businesses = BusinessDetails.objects.filter(store_setup=True, has_received_setup_email=False).select_related('user')
    triggered_count = 0
    for biz in businesses:
        user = biz.user
        if not user:
            continue
        featured_count = UserItems.objects.filter(user=user, is_featured=True).count()
        if featured_count <= 0:
            check_store_setup_followup_task.apply_async(args=[user.user_id])
            triggered_count += 1
    return f"Triggered {triggered_count} followups"

@shared_task
def send_manual_plan_assignment_email(user_id, plan_name, duration_months, expiry_date_str):
    try:
        from api.models import UserSecure
        from api.functions import send_mail
        from django.conf import settings
        
        user = UserSecure.objects.get(user_id=user_id)
        
        context = {
            'user_name': user.user_email.split('@')[0],
            'plan_name': plan_name,
            'duration_months': duration_months,
            'expiry_date': expiry_date_str,
            'dashboard_link': f"{settings.FRONTEND_URL}/dashboard" if hasattr(settings, 'FRONTEND_URL') else 'https://flezpay.com/dashboard',
        }
        
        send_mail.mailSender(
            'plan_assigned.html',
            'Congratulations! Your Subscription Plan Was Upgraded',
            [user.user_email],
            context
        )
        return f"Successfully sent plan assignment email to {user.user_email}"
    except Exception as e:
        logger.error(f"Failed to send plan assignment email to user {user_id}: {e}")
        return str(e)


@shared_task
def send_ad_credit_awarded_email(user_id, amount, currency_code='NGN', total_balance=None, business_name=''):
    try:
        from api.models import UserSecure, UserDetails
        from api.functions import send_mail
        from django.conf import settings
        from api.templatetags.currency_tags import currency_symbol
        
        user = UserSecure.objects.get(user_id=user_id)
        if not user.user_email:
            return f"User {user_id} has no email address"
            
        user_details = UserDetails.objects.filter(user=user).first()
        first_name = user_details.first_name if (user_details and user_details.first_name) else user.user_email.split('@')[0]
        
        curr_code = str(currency_code).upper() if currency_code else 'NGN'
        curr_sym = currency_symbol(curr_code)
        amount_dec = Decimal(str(amount))
        
        if curr_sym and curr_sym != curr_code:
            formatted_amount = f"{curr_sym}{amount_dec:,.2f}"
        else:
            formatted_amount = f"{curr_code} {amount_dec:,.2f}"
            
        formatted_total = None
        if total_balance is not None:
            tot_dec = Decimal(str(total_balance))
            if curr_sym and curr_sym != curr_code:
                formatted_total = f"{curr_sym}{tot_dec:,.2f}"
            else:
                formatted_total = f"{curr_code} {tot_dec:,.2f}"
                
        frontend_url = getattr(settings, 'FRONTEND_URL', 'https://flezpay.com').rstrip('/')
        growth_link = f"{frontend_url}/growth"
        
        context = {
            'first_name': first_name,
            'business_name': business_name,
            'amount': amount_dec,
            'currency_code': curr_code,
            'currency_symbol': curr_sym,
            'formatted_amount': formatted_amount,
            'total_balance': formatted_total,
            'growth_link': growth_link,
            'user_email': user.user_email,
        }
        
        subject = f"🎉 Congratulations! You've received {formatted_amount} in Ad Credit"
        
        send_mail.mailSender(
            'ad_credit_awarded.html',
            subject,
            [user.user_email],
            context
        )
        return f"Successfully sent ad credit awarded email to {user.user_email}"
    except Exception as e:
        logger.error(f"Failed to send ad credit awarded email to user {user_id}: {e}")
        return str(e)


@shared_task(name='api.tasks.send_ticket_email_task')
def send_ticket_email_task(ticket_id, action_type):
    from api.models import Ticket
    from api.functions import send_mail
    
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        subject = f"[{ticket.ticket_number}] {ticket.subject}"
        if action_type == 'created':
            title = "Ticket Created"
            message = "Your support ticket has been created and will be reviewed shortly."
        elif action_type == 'reply':
            title = "New Reply to Ticket"
            message = "A new reply has been added to your support ticket."
            subject = f"Re: {subject}"
        elif action_type == 'status_change':
            title = "Ticket Status Updated"
            message = f"Your support ticket status has been updated to: {ticket.status.upper()}."
        else:
            return "Unknown action type"
            
        thread_messages = ticket.messages.filter(message_type__in=['public_reply', 'system']).order_by('-created_at')
        
        context = {
            'ticket_number': ticket.ticket_number,
            'title': title,
            'message': message,
            'subject': ticket.subject,
            'status': ticket.status.upper(),
            'priority': ticket.priority.upper(),
            'department': ticket.department.name if ticket.department else 'General',
            'dashboard_link': f"{getattr(settings, 'FRONTEND_URL', 'https://flezpay.com').rstrip('/')}/support/tickets/{ticket.ticket_number}",
            'thread': thread_messages
        }
        
        emails = [user.user_email for user in ticket.affected_users.all() if user.user_email]
        if emails:
            send_mail.mailSender(
                'ticket_notification.html',
                subject,
                emails,
                context,
                reply_to=['info@flezpay.com']
            )
            return f"Sent ticket {action_type} email to {len(emails)} users."
        return "No affected users with email addresses."
    except Exception as e:
        logger.error(f"Error in send_ticket_email_task: {str(e)}")
        return str(e)

@shared_task(name='api.tasks.send_account_status_email_task')
def send_account_status_email_task(user_id, status_is_active):
    from api.models import UserSecure
    from api.functions import send_mail
    
    try:
        user = UserSecure.objects.get(user_id=user_id)
        if not user.user_email:
            return "User has no email"
            
        action = "activated" if status_is_active else "deactivated"
        subject = f"Your FlezPay account has been {action}"
        title = f"Account {action.capitalize()}"
        
        if status_is_active:
            message = "<p>Your FlezPay account has been successfully activated. You can now log in and use all our services.</p>"
        else:
            message = (
                "<p>Your FlezPay account has been deactivated following a review of your account activities.</p>"
                "<p>During this time, you will not be able to log in, initiate transactions, or access your wallet.</p>"
                "<p>If you believe this action was taken in error or if you have any questions regarding your account status, please contact our support team for further assistance.</p>"
            )
            
        context = {
            'title': title,
            'message': message,
            'first_name': user.details.first().first_name if user.details.exists() else "User",
            'support_email': "info@flezpay.com"
        }
        
        send_mail.mailSender(
            'account_status_notification.html',
            subject,
            [user.user_email],
            context,
            reply_to=['info@flezpay.com']
        )
        return f"Sent account {action} email to {user.user_email}"
    except Exception as e:
        logger.error(f"Error in send_account_status_email_task: {str(e)}")
        return str(e)


@shared_task
def refresh_instagram_gallery_task(business_id, username):
    """
    Background worker task to refresh cached Instagram gallery posts for a business.
    """
    try:
        from api.services.instagram_service import get_instagram_service
        service = get_instagram_service()
        result = service.refresh_gallery_cache(business_id, username)
        posts_count = len(result.get("posts", [])) if result else 0
        return f"Refreshed Instagram gallery for store {business_id} ({username}): {posts_count} posts"
    except Exception as e:
        logger.error(f"Error in refresh_instagram_gallery_task for store {business_id}: {e}")
        return str(e)

