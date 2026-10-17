import uuid

from rest_framework.views import APIView
import traceback
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone

from api.external.paystack_api import PaystackAPI
from api.functions import misc
from api import models
from api.user_data.data_views import calculate_total_balance


class Withdraw(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'manage_finances'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_finances' permission."}, status=status.HTTP_403_FORBIDDEN)
            with transaction.atomic():
                instance = models.UserSecure.objects.get(user_id=user_id)
                details = models.UserDetails.objects.get(user=instance)
                balance = calculate_total_balance(instance)
                amount = float(request.data['amount'])
                withdrawal_id = request.data['id']
                currency = "NGN" if details.user_country == "NG" else details.user_country

                # Check if withdrawals are disabled for acting user (e.g., staff/manager) or account owner
                actual_user_id = getattr(request, 'actual_user_id', None)
                if actual_user_id:
                    actual_user = models.UserSecure.objects.filter(user_id=actual_user_id).first()
                    if actual_user and actual_user.withdrawals_disabled:
                        raise Exception('Withdrawals have been temporarily disabled for your account. Please contact support for assistance.')

                if instance.withdrawals_disabled:
                    raise Exception('Withdrawals have been temporarily disabled for your account. Please contact support for assistance.')

                if not instance.is_verified and not instance.kyc_verified:
                    raise Exception("Please verify your account to activate withdrawals.")

                if not isinstance(amount, (int, float)) or (isinstance(amount, str) and amount.replace('.', '', 1).isdigit()):
                    raise Exception('amount must be a valid number')

                if amount <= 0:
                    raise Exception('Invalid amount')

                if amount > balance:
                    raise Exception('Insufficient balance')

                # Look up merchant's regional configuration
                user_country = details.user_country
                country_config = None
                if user_country:
                    country_config = models.AllowedCountries.objects.filter(
                        Q(code__iexact=user_country) | Q(name__iexact=user_country)
                    ).first()
                if not country_config and details.currency:
                    country_config = models.AllowedCountries.objects.filter(currency__iexact=details.currency).first()

                currency_label = country_config.currency if (country_config and country_config.currency) else currency

                # Minimum withdrawal enforcement per region
                min_withdrawal = 100.00
                if country_config and country_config.min_withdrawal_amount is not None:
                    min_withdrawal = float(country_config.min_withdrawal_amount)

                if amount < min_withdrawal:
                    raise Exception(f"Minimum withdrawal amount for your region is {currency_label} {min_withdrawal:,.2f}.")

                # Tier 1 Daily Limit Enforcement (Tier 2 / is_verified has unlimited withdrawals)
                if not instance.is_verified and instance.kyc_verified:
                    tier1_limit = 50000.00
                    if country_config and country_config.tier1_daily_limit is not None:
                        tier1_limit = float(country_config.tier1_daily_limit)

                    today = timezone.now().date()
                    todays_withdrawals = models.UserTransactions.objects.filter(
                        user=instance,
                        trx_type='withdrawal',
                        timestamp__date=today
                    ).exclude(trx_status='failed').aggregate(total=Sum('trx_amount'))['total'] or 0.0

                    if (todays_withdrawals + amount) > tier1_limit:
                        remaining_limit = max(0.0, tier1_limit - todays_withdrawals)
                        raise Exception(
                            f"Daily withdrawal limit exceeded. As a Tier 1 verified merchant, your daily limit is {currency_label} {tier1_limit:,.2f} "
                            f"(Remaining today: {currency_label} {remaining_limit:,.2f}). Complete Tier 2 verification for unlimited withdrawals."
                        )

                data = request.data.copy()

                pin = data.get('pin', '')
                pin_exists = models.AuthenticationPin.objects.filter(user_pin=pin, user_phone=instance.user_email, user_pin_type="withdrawal")

                if not pin_exists.exists():
                    return Response({
                        'status': False,
                        'message': "Enter a valid pin to complete withdrawal",
                    }, status=status.HTTP_401_UNAUTHORIZED)

                pin_exists.delete()
                
                # Withdrawal local account details
                bank = models.UserWithdrawalAccounts.objects.get(uniq_id=withdrawal_id)

                # ---------------- PAYSTACK ----------------
                paystack = PaystackAPI()

                # Create recipient if not already saved
                if not bank.paystack_recipient_code:
                    recipient_resp = paystack.create_transfer_recipient(
                        name=bank.account_name,
                        account_number=bank.account_number,
                        bank_code=bank.bank_code,
                        currency=currency
                    )
                    if recipient_resp.get("status") is not True:
                        raise Exception(f"Paystack recipient creation failed: {recipient_resp}")

                    recipient_code = recipient_resp["data"]["recipient_code"]
                    bank.paystack_recipient_code = recipient_code
                    bank.save(update_fields=["paystack_recipient_code"])
                else:
                    recipient_code = bank.paystack_recipient_code

                # Unique reference
                reference = f"WDR-{uuid.uuid4().hex[:12].upper()}"

                # Save Paystack reference
                bank.paystack_reference = reference
                bank.save(update_fields=["paystack_reference"])

                # Withdraw from
                withdraw = models.UserTransactions.objects.create(
                    user=instance,
                    trx_status='pending',
                    trx_amount=amount,
                    trx_type='withdrawal',
                    trx_currency=currency,
                    description=reference,
                    user_collection_id=recipient_code,  # Stored here for batch retries
                    destination_id=instance.uniq_id
                )

                # Backup transaction
                models.TransactionBackup.objects.create(
                    trx_uniq=withdraw,
                    trx_amount=amount,
                    trx_id=withdraw.trx_id,
                    sender=instance.user_id,
                    recipient=instance.user_id,
                    trx_currency=currency,
                )

                # Initiate transfer
                transfer_resp = paystack.initiate_transfer(
                    amount=int(amount * 100),  # Paystack expects kobo
                    recipient_code=recipient_code,
                    reference=reference,
                    reason=f"Withdrawal to {bank.bank_name} - {bank.account_number}"
                )

                if transfer_resp.get("status") is not True:
                    code = transfer_resp.get("code", "")
                    message = transfer_resp.get("message", "").lower()
                    if code == "insufficient_balance" or "balance is not enough" in message:
                        # Insufficient Paystack balance - keep it pending for batch retry
                        withdraw.description = "Pending: Paystack Insufficient Balance"
                        withdraw.save(update_fields=["description"])
                        return Response({'status': True, 'message': 'Withdrawal queued successfully'})
                    else:
                        raise Exception(f"Transfer failed: {transfer_resp.get('message')}")

                models.Notifications.objects.create(
                    user=instance,
                    title='Transfer',
                    description= f'You made a withdrawal of {currency}{amount} to your {bank.bank_name} account',
                    notification_type='tranc_success'
                )
                
                return Response({'status': True, 'message': 'Transaction successful'})

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            
            try:
                models.SystemErrorLog.objects.create(
                    log_type='withdrawal',
                    message=error,
                    traceback=traceback_message,
                    user=instance if 'instance' in locals() else None,
                )
            except Exception:
                pass

            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)

def deposit():
    pass