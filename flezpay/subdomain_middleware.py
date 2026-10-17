"""
Subdomain Middleware for Store URLs.

Maps requests like  shopname.localhost:8000/item/123
to the internal path  /preview/shopname/item/123

This lets existing URL patterns and views work unchanged.
"""
from django.conf import settings
from django.shortcuts import redirect


class StoreSubdomainMiddleware:
    """
    Inspects the Host header for store subdomains.
    If found, rewrites request.path_info so Django's URL resolver
    sees /preview/<slug>/... and routes to existing store views.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.base_domain_full = getattr(settings, 'STORE_BASE_DOMAIN', 'localhost:8000')
        self.base_domain = self.base_domain_full.split(':')[0]  # 'localhost' or 'flezpay.com'
        self.reserved = getattr(settings, 'RESERVED_SUBDOMAINS', set())

    def __call__(self, request):
        host = request.get_host()  # e.g. 'shopname.localhost:8000'
        host_without_port = host.split(':')[0]  # 'shopname.localhost'

        subdomain = self._extract_subdomain(host_without_port)
        is_custom_domain = False

        if not subdomain:
            # Check if this is a custom domain or Cloudflare-managed store domain
            from api.models import BusinessDetails
            host_for_lookup = host_without_port
            if host_for_lookup.startswith('www.'):
                host_for_lookup = host_for_lookup[4:]
            
            # Don't look up the base domain itself
            if host_for_lookup != self.base_domain:
                try:
                    # Check store_custom_domain first (purchased custom domains)
                    business = BusinessDetails.objects.filter(store_custom_domain=host_for_lookup).first()
                    if business and business.store_slug:
                        subdomain = business.store_slug
                        is_custom_domain = True
                    else:
                        # Also check store_domain (Cloudflare-managed subdomains)
                        business = BusinessDetails.objects.filter(store_domain=host_for_lookup).first()
                        if not business:
                            # Try matching with just the subdomain part stored
                            cloudflare_domain = getattr(settings, 'CLOUDFLARE_TARGET_DOMAIN', '')
                            if cloudflare_domain and host_for_lookup.endswith(f'.{cloudflare_domain}'):
                                subdomain_part = host_for_lookup[:-(len(cloudflare_domain) + 1)]
                                business = BusinessDetails.objects.filter(store_domain=subdomain_part).first()
                        if business and business.store_slug:
                            subdomain = business.store_slug
                            is_custom_domain = True
                except Exception:
                    pass

        if not subdomain and not is_custom_domain:
            if not self._is_allowed_core_host(host_without_port):
                from django.http import HttpResponseBadRequest
                return HttpResponseBadRequest("Invalid Host header")

        if subdomain:
            request.store_slug = subdomain
            request.is_custom_domain = is_custom_domain
            original_path = request.path_info
            
            # Do not rewrite static, media, API, or admin paths
            excluded_prefixes = ['/media/', '/static/', '/api/', '/admin/']
            should_rewrite = not any(original_path.startswith(prefix) for prefix in excluded_prefixes)
            
            if should_rewrite:
                if original_path == '/':
                    request.path_info = f'/{subdomain}'
                elif original_path == f'/{subdomain}' or original_path.startswith(f'/{subdomain}/'):
                    pass # Already contains the subdomain path prefix, do not prepend again
                else:
                    request.path_info = f'/{subdomain}{original_path}'
            request.original_path = original_path
        else:
            request.store_slug = None
            request.is_custom_domain = False
            
            # If they hit the legacy /preview/<slug> path directly on the main domain, redirect to subdomain
            if request.path_info.startswith('/preview/'):
                parts = request.path_info.split('/')
                if len(parts) >= 3 and parts[1] == 'preview':
                    slug = parts[2]
                    rest_of_path = '/' + '/'.join(parts[3:]) if len(parts) > 3 else '/'
                    protocol = getattr(settings, 'STORE_PROTOCOL', 'http' if settings.DEBUG else 'https')
                    new_url = f"{protocol}://{slug}.{self.base_domain_full}{rest_of_path}"
                    return redirect(new_url)

        response = self.get_response(request)
        return response

    def _extract_subdomain(self, host_without_port):
        """
        Extract store subdomain from the host.
        
        Examples:
          'shopname.localhost'     → 'shopname'
          'shopname.flezpay.com'  → 'shopname'
          'localhost'             → None
          'flezpay.com'           → None
          'www.flezpay.com'       → None  (reserved)
          'api.flezpay.com'       → None  (reserved)
        """
        base = self.base_domain  # 'localhost' or 'flezpay.com'

        if not host_without_port.endswith(base):
            return None

        # Strip the base domain
        prefix = host_without_port[: -(len(base))]
        if not prefix:
            return None

        # Remove trailing dot
        if prefix.endswith('.'):
            prefix = prefix[:-1]

        if not prefix:
            return None

        # Must be a single-level subdomain (no dots)
        if '.' in prefix:
            return None

        # Skip reserved subdomains
        if prefix.lower() in self.reserved:
            return None

        return prefix.lower()

    def _is_allowed_core_host(self, host_without_port):
        allowed_hosts = getattr(settings, 'ALLOWED_CORE_HOSTS', ['localhost', '127.0.0.1'])
        for allowed in allowed_hosts:
            if allowed.startswith('.'):
                if host_without_port == allowed[1:] or host_without_port.endswith(allowed):
                    return True
            else:
                if host_without_port == allowed:
                    return True
        return False
