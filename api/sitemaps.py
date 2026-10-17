from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.http import HttpResponse
from .models import BlogPost, BusinessDetails, HelpArticle
import os


STORE_BASE_DOMAIN = os.environ.get('STORE_BASE_DOMAIN', 'flezpay.com')


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return [
            'landing',
            'blog',
            'help_center',
            'about_us',
            'careers',
            'contact_page',
            'login',
            'register',
        ]

    def location(self, item):
        return reverse(item)


class StaticLegalSitemap(Sitemap):
    priority = 0.4
    changefreq = 'monthly'
    protocol = 'https'

    def items(self):
        return [
            '/privacy-policy/',
            '/terms/',
            '/public/cookie-policy/',
            '/public/ai-manager/',
            '/public/pos-system/',
            '/public/online-store/',
            '/public/payroll/',
        ]

    def location(self, item):
        return item


class BlogSitemap(Sitemap):
    priority = 0.9
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        return BlogPost.objects.filter(is_published=True).order_by('-timestamp')

    def lastmod(self, obj):
        return obj.timestamp

    def location(self, obj):
        return reverse('blog_details', args=[obj.slug])


class HelpCenterSitemap(Sitemap):
    priority = 0.7
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return HelpArticle.objects.filter(slug__isnull=False).exclude(slug='').order_by('-timestamp')

    def lastmod(self, obj):
        return obj.timestamp

    def location(self, obj):
        return reverse('help_center_details', args=[obj.slug])


class StoreSitemap(Sitemap):
    """
    Generates sitemap entries for all published online stores.
    Uses the custom domain if set, otherwise uses the default slug.flezpay.com format.
    """
    priority = 0.6
    changefreq = 'daily'
    protocol = 'https'

    def items(self):
        return BusinessDetails.objects.filter(
            is_published=True,
            store_slug__isnull=False,
        ).exclude(store_slug='').order_by('-id')

    def lastmod(self, obj):
        return None  # No updated_at field; omit lastmod

    def location(self, obj):
        if obj.store_custom_domain:
            domain = obj.store_custom_domain.strip().rstrip('/')
            if not domain.startswith('http'):
                domain = f'https://{domain}'
            return '/'  # The location is relative; we override get_urls below
        # Default: /slug (relative path for the main flezpay.com site)
        return f'/{obj.store_slug}/'

    def get_urls(self, page=1, site=None, protocol=None):
        """
        Override to emit full absolute URLs for stores with custom domains.
        """
        protocol = self.get_protocol(protocol)
        urls = []
        for item in self.paginator.page(page).object_list:
            if item.store_custom_domain:
                domain = item.store_custom_domain.strip().rstrip('/')
                if not domain.startswith('http'):
                    url = f'https://{domain}/'
                else:
                    url = f'{domain}/'
            else:
                url = f'https://{item.store_slug}.{STORE_BASE_DOMAIN}/'

            url_info = {
                'item': item,
                'location': url,
                'lastmod': None,
                'changefreq': self.changefreq,
                'priority': str(self.priority),
                'alternates': [],
                'x_default': None,
            }
            urls.append(url_info)
        return urls

# ── Grouped sitemap dicts (used by sitemap views in urls.py) ─────────────────

# Public site pages: landing, blog, help center, legal
site_sitemaps = {
    'static': StaticViewSitemap,
    'legal':  StaticLegalSitemap,
    'blog':   BlogSitemap,
    'help':   HelpCenterSitemap,
}

# Online stores only
store_sitemaps = {
    'stores': StoreSitemap,
}


# ── Sitemap index view ────────────────────────────────────────────────────────

def sitemap_index_view(request):
    """
    Renders a sitemap index that references the two child sitemaps:
      /sitemap-site.xml   – public site pages (landing, blog, help, legal)
      /sitemap-stores.xml – published online stores
    No static XML file is needed; everything is rendered on-the-fly.
    """
    site_url    = request.build_absolute_uri('/sitemap-site.xml')
    stores_url  = request.build_absolute_uri('/sitemap-stores.xml')

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <sitemap><loc>{site_url}</loc></sitemap>\n'
        f'  <sitemap><loc>{stores_url}</loc></sitemap>\n'
        '</sitemapindex>'
    )
    return HttpResponse(xml, content_type='application/xml')
