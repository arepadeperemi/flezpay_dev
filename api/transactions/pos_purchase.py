import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from api.functions import misc
from api import models
from api.user_data.data_views import calculate_total_balance
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
import decimal

class POSBuyKit(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            
            # Extract and validate units
            try:
                units = int(request.data.get('units', 1))
                if units < 1:
                    units = 1
            except (ValueError, TypeError):
                units = 1
            
            with transaction.atomic():
                instance = models.UserSecure.objects.get(user_id=user_id)
                details = models.UserDetails.objects.get(user=instance)
                balance = calculate_total_balance(instance)
                
                # Base price in USD * units
                usd_price = decimal.Decimal('100.00') * decimal.Decimal(units)
                target_currency = details.currency.upper() if details.currency else 'USD'
                
                # Fetch live exchange rate
                try:
                    res = requests.get('https://open.er-api.com/v6/latest/USD', timeout=5)
                    if res.status_code == 200:
                        rates = res.json().get('rates', {})
                        exchange_rate = rates.get(target_currency, 1.0)
                    else:
                        exchange_rate = 1.0
                except Exception:
                    exchange_rate = 1.0
                
                # Calculate final amount
                final_amount = usd_price * decimal.Decimal(str(exchange_rate))
                
                # Validate balance
                if final_amount > balance:
                    raise Exception(f'Insufficient balance. You need {target_currency} {final_amount:,.2f} to complete this purchase.')
                
                if final_amount <= 0:
                    raise Exception('Invalid conversion amount.')

                # Process transaction (deduct from user's balance)
                models.UserTransactions.objects.create(
                    user=instance,
                    trx_status='completed',
                    trx_amount=final_amount,
                    trx_type='payment', # payment type counts as an outgoing transaction
                    trx_source='POS Kit Purchase',
                    trx_currency=target_currency,
                    description=f'Purchased {units}x FlezPay POS Kit for {target_currency} {final_amount:,.2f}',
                    user_collection_id='POS-KIT',
                    destination_id='FlezPay Store'
                )
                
                # Notify User
                models.Notifications.objects.create(
                    user=instance,
                    title='POS Kit Purchased',
                    description=f'{units}x FlezPay POS Kit purchased. {target_currency} {final_amount:,.2f} deducted.',
                    notification_type='tranc_success'
                )

                # Save POS Order Delivery Details
                order = models.POSKitOrder.objects.create(
                    user=instance,
                    units=units,
                    email=request.data.get('email', instance.user_email),
                    phone=request.data.get('phone', instance.user_phone),
                    country=request.data.get('country', ''),
                    state=request.data.get('state', ''),
                    address=request.data.get('address', ''),
                    status='pending'
                )

                # Send Email asynchronously
                dashboard_url = f"{request.scheme}://{request.get_host()}/pos"
                from api.tasks import send_pos_order_status_email
                send_pos_order_status_email.delay(order.id, target_currency, final_amount, dashboard_url)

                return Response({'status': True, 'message': 'POS Kit purchased successfully.'})
                
        except models.UserSecure.DoesNotExist:
            return Response({'status': False, 'message': 'User not found'}, status=401)
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=400)
