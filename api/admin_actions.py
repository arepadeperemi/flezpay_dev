from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from api import models
import json

def check_admin_auth(request):
    """Check if user is authenticated as admin via session"""
    return request.session.get('admin_authenticated', False)

@csrf_exempt
def admin_countries_view(request):
    # Only allow admins or staff via session
    if not check_admin_auth(request):
        return JsonResponse({'status': False, 'message': 'Unauthorized'}, status=401)

    if request.method == 'GET':
        countries = models.AllowedCountries.objects.all().order_by('name')
        country_list = [{
            'id': c.id, 
            'name': c.name, 
            'code': c.code, 
            'currency': c.currency,
            'timezone': c.timezone,
            'is_active': c.is_active,
            'vat_percentage': float(c.vat_percentage) if c.vat_percentage is not None else 0.0,
            'tier1_daily_limit': float(c.tier1_daily_limit) if c.tier1_daily_limit is not None else 50000.0,
            'min_withdrawal_amount': float(c.min_withdrawal_amount) if c.min_withdrawal_amount is not None else 100.0,
            'system_delivery_pod_enabled': c.system_delivery_pod_enabled,
            'system_delivery_card_enabled': c.system_delivery_card_enabled,
            'system_arc_enabled': c.system_arc_enabled
        } for c in countries]
        return JsonResponse({'status': True, 'countries': country_list})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            code = data.get('code', '').upper()
            currency = data.get('currency', '').upper()
            timezone = data.get('timezone', 'Africa/Lagos')
            pod_enabled = data.get('system_delivery_pod_enabled', False)
            card_enabled = data.get('system_delivery_card_enabled', True)
            arc_enabled = data.get('system_arc_enabled', True)
            try:
                vat_percentage = float(data.get('vat_percentage', 0.0) or 0.0)
            except (ValueError, TypeError):
                vat_percentage = 0.0
            try:
                tier1_daily_limit = float(data.get('tier1_daily_limit', 50000.0) or 50000.0)
            except (ValueError, TypeError):
                tier1_daily_limit = 50000.0
            try:
                min_withdrawal_amount = float(data.get('min_withdrawal_amount', 100.0) or 100.0)
            except (ValueError, TypeError):
                min_withdrawal_amount = 100.0
            
            if not name or not code:
                return JsonResponse({'status': False, 'message': 'Name and code are required'})
            
            country, created = models.AllowedCountries.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'currency': currency,
                    'timezone': timezone,
                    'vat_percentage': vat_percentage,
                    'tier1_daily_limit': tier1_daily_limit,
                    'min_withdrawal_amount': min_withdrawal_amount,
                    'system_delivery_pod_enabled': pod_enabled,
                    'system_delivery_card_enabled': card_enabled,
                    'system_arc_enabled': arc_enabled
                }
            )
            
            if not created:
                return JsonResponse({'status': False, 'message': f'Country with code {code} already exists'})
                
            return JsonResponse({'status': True, 'message': 'Country added successfully'})
        except Exception as e:
            return JsonResponse({'status': False, 'message': str(e)})

@csrf_exempt
def admin_country_detail(request, pk):
    # Only allow admins or staff via session
    if not check_admin_auth(request):
        return JsonResponse({'status': False, 'message': 'Unauthorized'}, status=401)

    if request.method == 'DELETE':
        try:
            country = models.AllowedCountries.objects.get(pk=pk)
            country.delete()
            return JsonResponse({'status': True, 'message': 'Country deleted'})
        except models.AllowedCountries.DoesNotExist:
            return JsonResponse({'status': False, 'message': 'Country not found'})
        except Exception as e:
            return JsonResponse({'status': False, 'message': str(e)})
            
    elif request.method in ['PATCH', 'PUT']:
        try:
            data = json.loads(request.body)
            country = models.AllowedCountries.objects.get(pk=pk)
            update_fields = []
            if 'system_delivery_pod_enabled' in data:
                country.system_delivery_pod_enabled = data['system_delivery_pod_enabled']
                update_fields.append('system_delivery_pod_enabled')
            if 'system_delivery_card_enabled' in data:
                country.system_delivery_card_enabled = data['system_delivery_card_enabled']
                update_fields.append('system_delivery_card_enabled')
            if 'system_arc_enabled' in data:
                country.system_arc_enabled = data['system_arc_enabled']
                update_fields.append('system_arc_enabled')
            if 'currency' in data:
                country.currency = data['currency'].upper() if data['currency'] else data['currency']
                update_fields.append('currency')
            if 'timezone' in data:
                country.timezone = data['timezone']
                update_fields.append('timezone')
            if 'name' in data:
                country.name = data['name']
                update_fields.append('name')
            if 'code' in data:
                country.code = data['code'].upper() if data['code'] else data['code']
                update_fields.append('code')
            if 'vat_percentage' in data:
                try:
                    country.vat_percentage = float(data['vat_percentage'] or 0.0)
                except (ValueError, TypeError):
                    country.vat_percentage = 0.0
                update_fields.append('vat_percentage')
            if 'tier1_daily_limit' in data:
                try:
                    country.tier1_daily_limit = float(data['tier1_daily_limit'] or 0.0)
                except (ValueError, TypeError):
                    country.tier1_daily_limit = 50000.0
                update_fields.append('tier1_daily_limit')
            if 'min_withdrawal_amount' in data:
                try:
                    country.min_withdrawal_amount = float(data['min_withdrawal_amount'] or 0.0)
                except (ValueError, TypeError):
                    country.min_withdrawal_amount = 100.0
                update_fields.append('min_withdrawal_amount')
            
            if update_fields:
                country.save(update_fields=update_fields)
            return JsonResponse({'status': True, 'message': 'Country updated successfully'})
        except models.AllowedCountries.DoesNotExist:
            return JsonResponse({'status': False, 'message': 'Country not found'})
        except Exception as e:
            return JsonResponse({'status': False, 'message': str(e)})
    
    return JsonResponse({'status': False, 'message': 'Method not allowed'}, status=405)
