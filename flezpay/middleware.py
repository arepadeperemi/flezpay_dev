import re
from django.utils.deprecation import MiddlewareMixin
from api.models import BusinessDetails

class CustomDomainMiddleware(MiddlewareMixin):
    def process_request(self, request):
        host = request.get_host().split(':')[0].lower()
        
        # Strip 'www.' if present
        if host.startswith('www.'):
            host = host[4:]
            
        # Ignore main app domains
        ignored_hosts = ['localhost', '127.0.0.1', 'flezpay.com', 'flezpay.ng', 'flezpay.io']
        if host in ignored_hosts:
            return None
            
        # Ignore static and media files
        if request.path_info.startswith('/static/') or request.path_info.startswith('/media/') or request.path_info.startswith('/api/'):
            return None
            
        try:
            # Query business by custom domain
            business = BusinessDetails.objects.filter(custom_domain=host, custom_domain_status='active').first()
            if business and business.store_slug:
                store_slug = business.store_slug
                
                # Rewrite path
                original_path = request.path_info
                
                if original_path == '/' or original_path == '':
                    request.path_info = f'/preview/{store_slug}'
                else:
                    request.path_info = f'/preview/{store_slug}{original_path}'
                    
        except Exception as e:
            # Logging could be added here
            pass
            
        return None

from django.template.loader import render_to_string
from django.http import HttpResponse

class SubscriptionOverlayMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        path = request.path
        
        # 1. Check if user is authenticated
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return response
            
        # 2. Only process HTML responses
        content_type = response.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response
            
        # 3. Exclude specific paths
        excluded_prefixes = ['/wallet', '/admin', '/login', '/signup', '/logout', '/2fa', '/forgot-password', '/reset-password']
        if path == '/' or any(path.startswith(prefix) for prefix in excluded_prefixes):
            return response
            
        # 5. Check subscription
        try:
            from api.functions.misc import get_owner_from_user
            from api.functions.subscription_validation import SubscriptionManager
            from api.models import SubscriptionPlans
            
            try:
                user = get_owner_from_user(request.user)
            except Exception:
                return response
                
            sub_manager = SubscriptionManager(user)
            
            if not sub_manager.is_active():
                from api.functions.subscription_validation import get_processed_subscription_context, format_currency_amount
                sub_ctx = get_processed_subscription_context(request.user)
                
                # We need wallet balance to show to the user
                wallet_balance = 0
                business_name = 'Your Business'
                try:
                    from api.user_data.data_views import calculate_total_balance
                    wallet_balance = calculate_total_balance(user)
                    from api.models import BusinessDetails, SiteSettings
                    b = BusinessDetails.objects.filter(user=request.user).first()
                    if b:
                        business_name = b.business_name
                    site = SiteSettings.objects.first()
                except Exception:
                    site = None

                wallet_balance_display = format_currency_amount(wallet_balance, sub_ctx['user_currency'])

                context = {
                    'plans': sub_ctx['plans'],
                    'currency_symbol': sub_ctx['currency_symbol'],
                    'wallet_balance': wallet_balance,
                    'wallet_balance_display': wallet_balance_display,
                    'business_name': business_name,
                    'site': site,
                    'is_subscription_overlay': True,
                    'disable_banner': sub_ctx.get('disable_banner', False),
                    'promo_plan_uniq_id': sub_ctx.get('promo_plan_uniq_id'),
                    'promo_amount_display': sub_ctx.get('promo_amount_display'),
                    'promo_duration': sub_ctx.get('promo_duration', 'one_amount')
                }
                
                overlay_html = render_to_string('views/dashboard/partials/subscription_overlay.html', context, request=request)
                
                content = response.content.decode('utf-8')
                if '</main>' in content:
                    content = content.replace('</main>', f'{overlay_html}</main>', 1)
                elif '</body>' in content:
                    content = content.replace('</body>', f'{overlay_html}</body>')
                    
                response.content = content.encode('utf-8')
                if 'Content-Length' in response:
                    del response['Content-Length']
                        
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[SubscriptionOverlayMiddleware] Error: {e}")
            pass
            
        return response

from django.utils import timezone

class TimezoneMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                details = request.user.details.first()
                if details and details.user_timezone:
                    timezone.activate(details.user_timezone)
                else:
                    timezone.deactivate()
            except Exception:
                timezone.deactivate()
        else:
            timezone.deactivate()

from django.shortcuts import redirect

class AdminSubdomainRedirectMiddleware(MiddlewareMixin):
    def process_request(self, request):
        host = request.get_host().split(':')[0].lower()
        if host.startswith('admin.'):
            base_domain = host[6:]
            
            # Re-append port if it was there
            host_with_port = request.get_host()
            if ':' in host_with_port:
                port = host_with_port.split(':')[1]
                base_domain = f"{base_domain}:{port}"
                
            path = request.path_info
            scheme = request.scheme
            
            if path.startswith('/admin'):
                if path == '/admin':
                    new_url = f"{scheme}://{base_domain}/admin/"
                else:
                    new_url = f"{scheme}://{base_domain}{path}"
            else:
                if path == '/':
                    new_url = f"{scheme}://{base_domain}/admin/"
                else:
                    new_url = f"{scheme}://{base_domain}/admin{path}"
                
            query_string = request.META.get('QUERY_STRING')
            if query_string:
                new_url += f"?{query_string}"
                
            return redirect(new_url)
