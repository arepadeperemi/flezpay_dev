from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
import traceback
import requests
import json
import os
import re

from api.openprovider import OpenproviderAPI
from api.functions import misc
from api.tasks import provision_ssl_task
from api import models
from api.user_data.data_views import calculate_total_balance

def get_exchange_rate(base_currency='USD', target_currency='NGN'):
    if base_currency == target_currency:
        return 1.0
    try:
        r = requests.get(f'https://api.exchangerate-api.com/v4/latest/{base_currency}', timeout=5)
        if r.status_code == 200:
            rates = r.json().get('rates', {})
            return rates.get(target_currency, 1500.0) # default fallback for NGN
    except Exception:
        pass
    
    # Fallbacks for common currencies if API fails
    fallbacks = {
        'NGN': 1500.0,
        'GHS': 15.0,
        'KES': 130.0,
        'ZAR': 18.0
    }
    return fallbacks.get(target_currency, 1.0)


def get_user_currency(user_id):
    try:
        user = models.UserSecure.objects.get(user_id=user_id)
        details = models.UserDetails.objects.get(user=user)
        if details.currency:
            return details.currency
        return "NGN"
    except Exception:
        return "NGN"

ALLOWED_EXTENSIONS = ['com', 'net', 'org', 'store', 'online', 'co', 'io', 'biz']

def validate_domain_input(domain_name, extension):
    if not domain_name or not extension:
        return False, 'Domain name and extension are required'
    
    domain_name = domain_name.strip().lower()
    extension = extension.strip().lower()
    
    if not re.match(r'^[a-z0-9-]+$', domain_name):
        return False, 'Domain name contains invalid characters. Only letters, numbers, and hyphens are allowed.'
        
    if domain_name.startswith('-') or domain_name.endswith('-'):
        return False, 'Domain name cannot start or end with a hyphen.'
        
    if extension not in ALLOWED_EXTENSIONS:
        return False, f'Unsupported domain extension. Allowed extensions are: {", ".join(ALLOWED_EXTENSIONS)}'
        
    return True, None


class DomainCheckView(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            data = request.data
            domain_name = data.get('domain_name')
            extension = data.get('extension')
            
            is_valid, err_msg = validate_domain_input(domain_name, extension)
            if not is_valid:
                return Response({'status': False, 'message': err_msg}, status=status.HTTP_400_BAD_REQUEST)
                
            op = OpenproviderAPI()
            result = op.check_domain(domain_name, extension)
            
            if result.get('status') == 'success':
                base_price = result.get('price', 0)
                # Add $2 profit
                if base_price > 0 or result.get('availability') in ['free', 'active']:
                    price_with_profit = base_price + 2.0
                else:
                    price_with_profit = 0
                
                user_currency = get_user_currency(user_id)
                base_currency = result.get('currency', 'USD')
                rate = get_exchange_rate(base_currency, user_currency)
                
                final_price_local = round(price_with_profit * rate, 2)
                
                result['original_price'] = base_price
                result['price'] = final_price_local
                result['currency'] = user_currency
                
                # Process suggestions
                if 'suggestions' in result:
                    for sug in result['suggestions']:
                        s_base_price = sug.get('price', 0)
                        s_price_with_profit = s_base_price + 2.0 if s_base_price > 0 or sug.get('availability') in ['free', 'active'] else 0
                        s_rate = get_exchange_rate(sug.get('currency', 'USD'), user_currency)
                        sug['original_price'] = s_base_price
                        sug['price'] = round(s_price_with_profit * s_rate, 2)
                        sug['currency'] = user_currency
                
                return Response({'status': True, 'data': result})
            else:
                return Response({'status': False, 'message': result.get('message', 'Failed to check domain')})
        except Exception as e:
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': str(e), 'traceback': traceback_message}, status=status.HTTP_400_BAD_REQUEST)


class DomainBuyView(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            data = request.data
            domain_name = data.get('domain_name')
            extension = data.get('extension')
            price_local = data.get('price') # The price shown to the user in their currency
            currency = data.get('currency', 'NGN')
            
            if price_local is None:
                return Response({'status': False, 'message': 'Price is required'}, status=status.HTTP_400_BAD_REQUEST)
                
            is_valid, err_msg = validate_domain_input(domain_name, extension)
            if not is_valid:
                return Response({'status': False, 'message': err_msg}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                price_local = float(price_local)
            except ValueError:
                return Response({'status': False, 'message': 'Invalid price format'}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                instance = models.UserSecure.objects.get(user_id=user_id)
                balance = calculate_total_balance(instance)
                
                if balance < price_local:
                    return Response({'status': False, 'message': 'Insufficient wallet balance to purchase this domain.'}, status=status.HTTP_400_BAD_REQUEST)
                
                # Deduct balance immediately
                models.UserTransactions.objects.create(
                    user=instance,
                    trx_status='completed',
                    trx_amount=price_local,
                    trx_type='payment',
                    trx_source='Domain Purchase',
                    trx_currency=currency,
                    description=f"Purchased custom domain: {domain_name}.{extension}",
                    user_collection_id='DOMAIN-PURCHASE',
                    destination_id='Openprovider'
                )
                    
                # Call Openprovider to register
                from api.openprovider import OpenproviderAPI
                op = OpenproviderAPI()
                reg_result = op.register_domain(domain_name, extension)
                
                if reg_result.get('status') != 'success':
                    # Send error to SiteSettings email
                    try:
                        from django.core.mail import send_mail
                        from django.template.loader import render_to_string
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
                    
                    # Raise exception to trigger atomic rollback and instantly reverse the debit
                    raise Exception("Temporary error. try again after 30 mins")
                
                # Setup DNS Zone automatically
                server_ip = os.getenv('SERVER_IP', '127.0.0.1')
                op.create_dns_zone(domain_name, extension, server_ip)
                
                # Schedule SSL provisioning after 5 minutes to allow DNS propagation
                from api.tasks import provision_ssl_task
                provision_ssl_task.apply_async(args=[domain_name, extension], countdown=300)
                
                # Update store custom domain
                business = models.BusinessDetails.objects.filter(user=instance, store_setup=True).first() or models.BusinessDetails.objects.filter(user=instance).first()
                if business:
                    business.store_custom_domain = f"{domain_name}.{extension}"
                    business.save(update_fields=['store_custom_domain'])
                
                # Optionally send a notification
                models.Notifications.objects.create(
                    user=instance,
                    title='Domain Purchased',
                    description=f'You have successfully purchased and connected {domain_name}.{extension} to your store.',
                    notification_type='tranc_success'
                )
                
            return Response({'status': True, 'message': 'Domain purchased successfully'})
                
        except Exception as e:
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class DomainTransferView(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            data = request.data
            domain_name = data.get('domain_name')
            extension = data.get('extension')
            auth_code = data.get('auth_code')
            price_local = data.get('price')
            currency = data.get('currency', 'NGN')
            
            if not auth_code:
                return Response({'status': False, 'message': 'Auth code is required'}, status=status.HTTP_400_BAD_REQUEST)
                
            if price_local is None:
                return Response({'status': False, 'message': 'Price is required'}, status=status.HTTP_400_BAD_REQUEST)
                
            is_valid, err_msg = validate_domain_input(domain_name, extension)
            if not is_valid:
                return Response({'status': False, 'message': err_msg}, status=status.HTTP_400_BAD_REQUEST)
                
            try:
                price_local = float(price_local)
            except (ValueError, TypeError):
                return Response({'status': False, 'message': 'Invalid price format'}, status=status.HTTP_400_BAD_REQUEST)
            
            user_currency = get_user_currency(user_id)
            
            with transaction.atomic():
                instance = models.UserSecure.objects.get(user_id=user_id)
                balance = calculate_total_balance(instance)
                
                if balance < price_local:
                    return Response({'status': False, 'message': f'Insufficient wallet balance. Transfer costs {user_currency} {price_local}'}, status=status.HTTP_400_BAD_REQUEST)
                
                # Deduct balance immediately
                models.UserTransactions.objects.create(
                    user=instance,
                    trx_status='completed',
                    trx_amount=price_local,
                    trx_type='payment',
                    trx_source='Domain Transfer',
                    trx_currency=user_currency,
                    description=f"Transferred custom domain: {domain_name}.{extension}",
                    user_collection_id='DOMAIN-TRANSFER',
                    destination_id='Openprovider'
                )
                
                # Call Openprovider to transfer
                from api.openprovider import OpenproviderAPI
                op = OpenproviderAPI()
                trans_result = op.transfer_domain(domain_name, extension, auth_code)
                
                if trans_result.get('status') != 'success':
                    # Check if error is related to auth code to provide better feedback
                    err_msg = str(trans_result.get('message', '')).lower()
                    
                    if 'auth' in err_msg or 'epp' in err_msg or 'password' in err_msg:
                        raise Exception("Invalid authorization code. Please verify the code with your current registrar.")
                    else:
                        raise Exception(f"Transfer failed: {trans_result.get('message')}")
                        
                # Update store custom domain
                business = models.BusinessDetails.objects.filter(user=instance, store_setup=True).first() or models.BusinessDetails.objects.filter(user=instance).first()
                if business:
                    business.store_custom_domain = f"{domain_name}.{extension}"
                    business.save(update_fields=['store_custom_domain'])
                
                # Optionally send a notification
                models.Notifications.objects.create(
                    user=instance,
                    title='Domain Transfer Initiated',
                    description=f'Transfer process started for {domain_name}.{extension}. This usually takes a few days.',
                    notification_type='tranc_success'
                )
                
            return Response({'status': True, 'message': 'Domain transfer initiated successfully'})
            
        except Exception as e:
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
