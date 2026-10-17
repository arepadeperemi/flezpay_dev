from django import template
from django.conf import settings
from django.urls import reverse
from django.utils.html import format_html

register = template.Library()

@register.simple_tag(takes_context=True)
def store_url(context, slug, view_name='store_preview', *args, **kwargs):
    """
    Generates a subdomain-based URL for a store.
    Uses current request host to dynamically determine base domain, falling back to STORE_BASE_DOMAIN.
    """
    if not slug:
        return "#"

    request = context.get('request')
    base_domain_setting = getattr(settings, 'STORE_BASE_DOMAIN', 'localhost:8000')
    protocol = getattr(settings, 'STORE_PROTOCOL', 'http' if settings.DEBUG else 'https')

    if request:
        host = request.get_host()
        protocol = "https" if request.is_secure() else "http"
        
        if ':' in host:
            domain_part, port_part = host.split(':', 1)
            port_str = f":{port_part}"
        else:
            domain_part = host
            port_str = ""
            
        if ':' in base_domain_setting:
            base_domain_no_port, base_port = base_domain_setting.split(':', 1)
            if not port_str:
                port_str = f":{base_port}"
        else:
            base_domain_no_port = base_domain_setting
            
        is_main_or_subdomain = (domain_part == base_domain_no_port) or domain_part.endswith(f".{base_domain_no_port}")
        
        if domain_part == f"{slug}.{base_domain_no_port}":
            base_url = f"{protocol}://{host}"
        else:
            base_url = f"{protocol}://{slug}.{base_domain_no_port}{port_str}"
    else:
        base_url = f"{protocol}://{slug}.{base_domain_setting}"

    # If business in context has a connected custom domain, use it as base_url
    business = context.get('business')
    custom_domain = getattr(business, 'store_custom_domain', None) if business else None
    if custom_domain:
        custom_domain_clean = custom_domain.strip().rstrip('/')
        if not custom_domain_clean.startswith(('http://', 'https://')):
            base_url = f"{protocol}://{custom_domain_clean}"
        else:
            base_url = custom_domain_clean

    # Reconstruct path based on the view name.
    # Note: the subdomain middleware maps /preview/slug internally, 
    # but the external URL should not have /preview/slug
    if view_name == 'store_preview' or view_name == 'store_preview_alt':
        path = "/"
    elif view_name == 'store_item_preview':
        if args:
            item_id = args[0]
            path = f"/item/{item_id}"
        else:
            path = "/"
    elif view_name == 'store_page' or view_name == 'store_page_alt':
        if args:
            page_slug = args[0]
            path = f"/page/{page_slug}"
        else:
            path = "/"
    elif view_name == 'store_blog_list' or view_name == 'store_blog_list_alt':
        path = "/blog"
    elif view_name == 'store_blog_detail' or view_name == 'store_blog_detail_alt':
        if args:
            post_slug = args[0]
            path = f"/blog/{post_slug}"
        else:
            path = "/blog"
    elif view_name == 'store_checkout' or view_name == 'store_checkout_alt':
        path = "/checkout"
    elif view_name == 'store_contact_submit':
        path = "/contact-submit"
    else:
        # Fallback
        path = "/"

    return f"{base_url}{path}"

@register.simple_tag
def platform_url(view_name, *args, **kwargs):
    """
    Generates an absolute URL for the main platform, overriding any subdomain context.
    For example: http://localhost:8000/help-center/
    """
    base_domain = getattr(settings, 'STORE_BASE_DOMAIN', 'localhost:8000')
    protocol = getattr(settings, 'STORE_PROTOCOL', 'http' if settings.DEBUG else 'https')
    try:
        path = reverse(view_name, args=args, kwargs=kwargs)
    except Exception:
        path = f"/{view_name.replace('_', '-')}/"
    return f"{protocol}://{base_domain}{path}"


import re

@register.filter
def youtube_embed_url(url):
    """
    Converts standard YouTube URLs (watch?v=, youtu.be/, shorts/, embed/)
    to privacy-enhanced youtube-nocookie.com embed URLs.
    """
    if not url:
        return ""
    url_str = str(url).strip()
    regex = r'(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|v\/|shorts\/)|youtu\.be\/)([\w-]{11})'
    match = re.search(regex, url_str)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&enablejsapi=1"
    return url_str


@register.filter
def is_youtube_url(url):
    """Check if the provided URL is a YouTube link."""
    if not url:
        return False
    u = str(url).lower()
    return 'youtube.com' in u or 'youtu.be' in u


@register.simple_tag
def format_video_embed(youtube_url, autoplay=False, loop=False, muted=False, controls=True):
    """Format a YouTube embed URL with playback options."""
    if not youtube_url:
        return ""
    regex = r'(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|v\/|shorts\/)|youtu\.be\/)([\w-]{11})'
    match = re.search(regex, str(youtube_url).strip())
    if not match:
        return str(youtube_url)
    video_id = match.group(1)
    params = ['rel=0', 'enablejsapi=1']
    if autoplay:
        params.extend(['autoplay=1', 'mute=1'])
    elif muted:
        params.append('mute=1')
    if loop:
        params.extend(['loop=1', f'playlist={video_id}'])
    if not controls:
        params.append('controls=0')
    return f"https://www.youtube-nocookie.com/embed/{video_id}?{'&'.join(params)}"

