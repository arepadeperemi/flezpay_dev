import os
import traceback
from dotenv import load_dotenv
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
import requests
from api.external.paystack_api import PaystackAPI
from api.external.kxpress_api import KxpressAPI

load_dotenv()


class BanksAPI(APIView):
    
    def get(self, request):
        url = "https://nigerianbanks.xyz"
        try:
            response = requests.get(url)
            if response.status_code in [200, 201]:
                data = response.json()
                return  Response({'status': True, 'message': "", "data": data})
        except Exception as e:
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': str(e), 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)



class ValidateAccount(APIView):

    def post(self, request):
        account_number = request.data.get('account_number')
        bank_code = request.data.get('bank_code')
        
        if not account_number or not bank_code:
            return Response(
                {'status': False, 'message': 'account_number and bank_code are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Use Paystack API to resolve account
            paystack = PaystackAPI()
            paystack_response = paystack.resolve_account_number(account_number, bank_code)
            
            # Check if Paystack request was successful
            if paystack_response.get('status'):
                # Transform Paystack response to match NUBAN API format
                # Paystack returns: {"status": true, "data": {"account_number": "...", "account_name": "..."}}
                # NUBAN returns: [{"account_number": "...", "account_name": "...", "bank_name": "..."}]
                
                paystack_data = paystack_response.get('data', {})
                
                # Fetch bank name from the banks API
                bank_name = self._get_bank_name(bank_code)
                
                # Transform to match NUBAN format (array of objects)
                transformed_data = [{
                    'account_number': paystack_data.get('account_number'),
                    'account_name': paystack_data.get('account_name'),
                    'bank_name': bank_name
                }]
                
                return Response({
                    'status': True, 
                    'message': '', 
                    'data': transformed_data
                })
            else:
                # Paystack returned an error
                error_message = paystack_response.get('message', 'Account validation failed')
                return Response({
                    'status': False, 
                    'message': error_message
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            traceback_message = traceback.format_exc()
            return Response({
                'status': False, 
                'message': str(e), 
                'traceback': traceback_message
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def _get_bank_name(self, bank_code):
        """
        Helper method to get bank name from bank code using the banks API.
        """
        try:
            response = requests.get("https://nigerianbanks.xyz")
            if response.status_code == 200:
                banks = response.json()
                for bank in banks:
                    if bank.get('code') == bank_code:
                        return bank.get('name', '')
        except:
            pass
        return ''



def _is_kxpress_allowed(request):
    from api.models import BusinessDetails
    
    if hasattr(request, 'store_slug') and request.store_slug:
        business = BusinessDetails.objects.filter(store_slug=request.store_slug).first()
        if business and business.user:
            details = business.user.details.first()
            if details:
                return details.user_country == 'NG'
                
    if request.user and request.user.is_authenticated:
        details = request.user.details.first()
        if details:
            return details.user_country == 'NG'
            
    return False

class KxpressStatesAPI(APIView):
    def get(self, request):
        store_slug = request.query_params.get('storeSlug', request.query_params.get('store_slug'))
        if store_slug:
            request.store_slug = store_slug
            
        # Optional country param for multi-region support
        country = request.query_params.get('country')
        if not country:
            if not _is_kxpress_allowed(request):
                return Response({'status': True, 'data': []})
            country = 'NG'

        try:
            if country.upper() == 'KE':
                from api.external.custom_logistics_api import CustomLogisticsAPI
                client = CustomLogisticsAPI()
                resp = client.get_states()
            else:
                client = KxpressAPI()
                resp = client.get_states()
                
            return Response({'status': True, 'data': resp.get('data', [])})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class KxpressLgasAPI(APIView):
    def get(self, request):
        store_slug = request.query_params.get('storeSlug', request.query_params.get('store_slug'))
        if store_slug:
            request.store_slug = store_slug
            
        country = request.query_params.get('country')
        if not country:
            if not _is_kxpress_allowed(request):
                return Response({'status': True, 'data': []})
            country = 'NG'

        state_id = request.query_params.get('state_id')
        if not state_id:
            return Response({'status': False, 'message': 'State ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if country.upper() == 'KE':
                from api.external.custom_logistics_api import CustomLogisticsAPI
                client = CustomLogisticsAPI()
                resp = client.get_lgas(state_id)
                final_data = resp.get('data', [])
            else:
                client = KxpressAPI()
                resp = client.get_lgas(state_id)
                lga_data = resp.get('data', {})
                final_data = lga_data.get('data', []) if isinstance(lga_data, dict) else []
                
            return Response({'status': True, 'data': final_data})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class KxpressCalculateAPI(APIView):
    def post(self, request):
        from_state = request.data.get('from_state', request.data.get('fromState'))
        from_lga = request.data.get('from_lga', request.data.get('fromLga'))
        to_state = request.data.get('to_state', request.data.get('toState'))
        to_lga = request.data.get('to_lga', request.data.get('toLga'))
        weight = request.data.get('weight')
        
        target_currency = request.data.get('currency', 'NGN')
        store_slug = request.data.get('store_slug', request.data.get('storeSlug'))
        if store_slug:
            request.store_slug = store_slug
        
        if not all([from_state, from_lga, to_state, to_lga, weight]):
            return Response({'status': False, 'message': 'from_state, from_lga, to_state, to_lga, and weight are required'}, status=status.HTTP_400_BAD_REQUEST)
            
        country = request.data.get('country', '')
        
        try:
            if country.upper() == 'KE':
                from api.external.custom_logistics_api import CustomLogisticsAPI
                client = CustomLogisticsAPI()
            elif _is_kxpress_allowed(request):
                client = KxpressAPI()
            else:
                from api.external.custom_logistics_api import CustomLogisticsAPI
                client = CustomLogisticsAPI()
                
            resp = client.calculate_shipping(from_state, from_lga, to_state, to_lga, weight)
            
            data_val = resp.get('data', {})
            amount = data_val.get('data') if isinstance(data_val, dict) else 0
            if not amount and isinstance(data_val, dict):
                amount = data_val.get('totalAmount', 0)
                
            amount = float(amount) if amount else 0.0
            
            # Add markup
            from api.models import UserSecure
            admin_settings = UserSecure.objects.filter(is_superuser=True).first().admin_settings or {}
            markup_val = admin_settings.get('system_delivery_markup_ngn')
            markup_ngn = float(markup_val) if markup_val is not None else 200.0
            amount += markup_ngn
            
            # Convert
            if target_currency != 'NGN':
                from api.user_data.domain_views import get_exchange_rate
                rate = get_exchange_rate(base_currency='NGN', target_currency=target_currency)
                if rate:
                    amount = amount * float(rate)
                    
            return Response({'status': True, 'data': {'totalAmount': amount}})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class KxpressTrackAPI(APIView):
    def get(self, request, order_no):
        try:
            client = KxpressAPI()
            resp = client.track_order(order_no)
            return Response({'status': True, 'data': resp.get('data', resp)})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
