import http.cookiejar
import json
import logging
import re
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache prefix and timeout constants
INSTAGRAM_CACHE_PREFIX = "social:instagram"
INSTAGRAM_CACHE_TIMEOUT = 7200  # 2 hours (successful fetch)
INSTAGRAM_EMPTY_CACHE_TIMEOUT = 600  # 10 minutes (failed / empty fetch, retry soon)
INSTAGRAM_STALE_CACHE_TIMEOUT = 60 * 60 * 24 * 14  # 14 days (last known good feed)
INSTAGRAM_REFRESH_LOCK_TIMEOUT = 300  # 5 minutes (prevents queueing duplicate refreshes)


def validate_instagram_url(url_or_handle: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates and normalizes an Instagram profile URL or handle.
    
    Returns:
        (is_valid, username, canonical_url)
    """
    if not url_or_handle or not isinstance(url_or_handle, str):
        return False, None, None

    raw = url_or_handle.strip()
    if not raw:
        return False, None, None

    # Handle direct @handle notation (e.g. "@my_store")
    if raw.startswith('@'):
        handle = raw[1:].strip().lower()
        if re.match(r'^[a-zA-Z0-9._]{1,30}$', handle):
            return True, handle, f"https://www.instagram.com/{handle}/"
        return False, None, None

    # Add scheme if omitted
    if not raw.startswith(('http://', 'https://')):
        raw = 'https://' + raw

    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return False, None, None

    hostname = (parsed.hostname or '').lower()
    # Accept valid Instagram hostnames
    if hostname not in ('instagram.com', 'www.instagram.com', 'instagr.am'):
        return False, None, None

    # Extract username from path
    path = parsed.path.strip('/')
    parts = [p for p in path.split('/') if p]
    if not parts:
        return False, None, None

    # Exclude Instagram system / post paths
    system_paths = {
        'p', 'reel', 'reels', 'stories', 'explore', 'direct',
        'accounts', 'developer', 'about', 'legal', 'privacy',
        'terms', 'directory', 'tags', 'tv'
    }
    first_part = parts[0]
    if first_part.lower() in system_paths:
        return False, None, None

    # Username pattern: 1-30 characters, alphanumeric, dots, underscores
    if not re.match(r'^[a-zA-Z0-9._]{1,30}$', first_part):
        return False, None, None

    username = first_part.lower()
    canonical_url = f"https://www.instagram.com/{username}/"
    return True, username, canonical_url


class BaseInstagramProvider(ABC):
    """
    Abstract interface for Instagram content retrieval.
    Allows easy replacement (Scraper, Official Graph API, or Alternative Provider)
    without touching the Social Gallery UI or storefront renderers.
    """

    @abstractmethod
    def fetch_posts(self, username: str, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Retrieves public posts for a given username and returns normalized post dictionaries.
        Each post dict format:
        {
            "id": str,
            "imageUrl": str,
            "permalink": str,
            "caption": str,
            "timestamp": str or int
        }
        """
        pass


class PublicScraperInstagramProvider(BaseInstagramProvider):
    """
    Unauthenticated public Instagram scraper provider.
    Retrieves public media without requiring merchant login or tokens.
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    ]

    def fetch_posts(self, username: str, limit: int = 12) -> List[Dict[str, Any]]:
        strategies = (
            self._fetch_via_web_profile_info,
            self._fetch_via_session_profile_info,
            self._fetch_via_public_embed_or_page,
        )
        for strategy in strategies:
            try:
                posts = strategy(username, limit)
            except Exception as e:
                logger.debug("Instagram strategy %s failed for %s: %s", strategy.__name__, username, e)
                posts = []
            if posts:
                return posts

        logger.info("Instagram returned no public posts for %s (likely rate-limited or private)", username)
        return []

    def _fetch_via_session_profile_info(self, username: str, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Bootstraps anonymous web cookies (csrftoken / mid) first, then queries the
        public profile info endpoint the same way the Instagram web client does.
        """
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        ua = self.USER_AGENTS[1]

        opener.open(urllib.request.Request("https://www.instagram.com/", headers={"User-Agent": ua}), timeout=6).read()
        csrf = next((c.value for c in jar if c.name == "csrftoken"), "")

        headers = {
            "User-Agent": ua,
            "X-IG-App-ID": "936619743392459",
            "X-CSRFToken": csrf,
            "X-ASBD-ID": "129477",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.instagram.com/{username}/",
            "Accept": "*/*",
        }
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        with opener.open(urllib.request.Request(url, headers=headers), timeout=6) as response:
            if response.status == 200:
                raw_data = json.loads(response.read().decode("utf-8"))
                edges = (
                    raw_data.get("data", {}).get("user", {})
                    .get("edge_owner_to_timeline_media", {}).get("edges", [])
                )
                return self._normalize_edges(edges, username, limit)
        return []

    def _fetch_via_web_profile_info(self, username: str, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Queries Instagram's public web profile info API endpoint.
        """
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        headers = {
            "User-Agent": self.USER_AGENTS[0],
            "X-IG-App-ID": "936619743392459",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as response:
                if response.status == 200:
                    raw_data = json.loads(response.read().decode("utf-8"))
                    user_data = raw_data.get("data", {}).get("user", {})
                    timeline = user_data.get("edge_owner_to_timeline_media", {})
                    edges = timeline.get("edges", [])
                    return self._normalize_edges(edges, username, limit)
        except Exception as e:
            logger.debug("Instagram web_profile_info request failed for %s: %s", username, e)

        return []

    def _fetch_via_public_embed_or_page(self, username: str, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Fallback public HTML scraper extracting post metadata from public scripts.
        """
        url = f"https://www.instagram.com/{username}/"
        headers = {
            "User-Agent": self.USER_AGENTS[1],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as response:
                if response.status == 200:
                    html = response.read().decode("utf-8", errors="ignore")
                    # Search for embedded json blobs in script tags
                    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
                    for s in scripts:
                        if 'edge_owner_to_timeline_media' in s or 'shortcode' in s and 'display_url' in s:
                            m = re.search(r'(\{.*\})', s)
                            if m:
                                try:
                                    data = json.loads(m.group(1))
                                    found_posts = []
                                    self._extract_posts_recursive(data, found_posts, limit)
                                    if found_posts:
                                        return found_posts[:limit]
                                except Exception:
                                    continue
        except Exception as e:
            logger.debug("Instagram public page scrape failed for %s: %s", username, e)

        return []

    def _extract_posts_recursive(self, obj: Any, results: List[Dict[str, Any]], limit: int) -> None:
        if len(results) >= limit:
            return
        if isinstance(obj, dict):
            if "display_url" in obj and "shortcode" in obj:
                shortcode = obj["shortcode"]
                caption = ""
                edges = obj.get("edge_media_to_caption", {}).get("edges", [])
                if edges and isinstance(edges, list) and edges[0].get("node"):
                    caption = edges[0]["node"].get("text", "")

                results.append({
                    "id": str(obj.get("id") or shortcode),
                    "imageUrl": obj["display_url"],
                    "permalink": f"https://www.instagram.com/p/{shortcode}/",
                    "caption": caption,
                    "timestamp": obj.get("taken_at_timestamp") or "",
                })
            for k, v in obj.items():
                self._extract_posts_recursive(v, results, limit)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_posts_recursive(item, results, limit)

    def _normalize_edges(self, edges: List[Dict[str, Any]], username: str, limit: int = 12) -> List[Dict[str, Any]]:
        posts = []
        for edge in edges[:limit]:
            node = edge.get("node", {})
            shortcode = node.get("shortcode")
            display_url = node.get("display_url")
            if not shortcode or not display_url:
                continue

            caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            caption = ""
            if caption_edges and isinstance(caption_edges, list) and caption_edges[0].get("node"):
                caption = caption_edges[0]["node"].get("text", "")

            posts.append({
                "id": str(node.get("id") or shortcode),
                "imageUrl": display_url,
                "permalink": f"https://www.instagram.com/p/{shortcode}/",
                "caption": caption,
                "timestamp": node.get("taken_at_timestamp") or "",
            })
        return posts


class InstagramService:
    """
    Coordinates Instagram validation, store isolation, caching,
    and provider execution for FlezPay Social Gallery.
    """

    def __init__(self, provider: Optional[BaseInstagramProvider] = None):
        self.provider = provider or PublicScraperInstagramProvider()

    @staticmethod
    def _cache_keys(store_id: Any, username: str) -> Tuple[str, str, str]:
        base = f"{INSTAGRAM_CACHE_PREFIX}:{store_id}:{username}"
        return base, f"{base}:last_good", f"{base}:refresh_lock"

    @staticmethod
    def _safe_cache_get(key: str) -> Any:
        try:
            return cache.get(key)
        except Exception as e:
            logger.warning("Instagram cache read failed for %s: %s", key, e)
            return None

    @staticmethod
    def _safe_cache_set(key: str, value: Any, timeout: int) -> None:
        try:
            cache.set(key, value, timeout)
        except Exception as e:
            logger.warning("Instagram cache write failed for %s: %s", key, e)

    def get_gallery_for_business(
        self,
        business,
        force_refresh: bool = False,
        limit: int = 12,
        blocking: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrieves normalized social gallery data for a specific store business instance.
        Enforces store isolation and caching.

        blocking=False is used by storefront page renders: on a cache miss it never
        waits on Instagram. It serves the last known good feed (or an empty feed) and
        queues a background refresh instead.
        """
        if not business:
            return {"configured": False, "profile": None, "posts": []}

        instagram_url = getattr(business, "store_social_instagram", "") or ""
        is_valid, username, canonical_url = validate_instagram_url(instagram_url)

        if not is_valid or not username:
            return {"configured": False, "profile": None, "posts": []}

        store_id = getattr(business, "id", None) or "default"
        cache_key, stale_key, lock_key = self._cache_keys(store_id, username)
        profile = {"username": username, "url": canonical_url}

        if not force_refresh:
            cached_data = self._safe_cache_get(cache_key)
            if cached_data is not None:
                return cached_data

        if not blocking and not force_refresh:
            self._queue_refresh(store_id, username, lock_key)
            stale = self._safe_cache_get(stale_key)
            if stale and stale.get("posts"):
                return stale
            return {"configured": True, "profile": profile, "posts": []}

        # Fetch posts via provider
        posts = []
        try:
            posts = self.provider.fetch_posts(username, limit=limit)
        except Exception as e:
            logger.error("Error fetching Instagram posts for %s (store %s): %s", username, store_id, e)
            posts = []

        if posts:
            result = {"configured": True, "profile": profile, "posts": posts}
            self._safe_cache_set(cache_key, result, INSTAGRAM_CACHE_TIMEOUT)
            self._safe_cache_set(stale_key, result, INSTAGRAM_STALE_CACHE_TIMEOUT)
            return result

        # Fetch failed / empty: fall back to last known good feed, and only cache
        # the miss briefly so we retry soon instead of hiding posts for hours.
        stale = self._safe_cache_get(stale_key)
        if stale and stale.get("posts"):
            self._safe_cache_set(cache_key, stale, INSTAGRAM_EMPTY_CACHE_TIMEOUT)
            return stale

        result = {"configured": True, "profile": profile, "posts": []}
        self._safe_cache_set(cache_key, result, INSTAGRAM_EMPTY_CACHE_TIMEOUT)
        return result

    def _queue_refresh(self, store_id: Any, username: str, lock_key: str) -> None:
        """Queues a background Celery refresh at most once per lock window."""
        try:
            if not cache.add(lock_key, 1, INSTAGRAM_REFRESH_LOCK_TIMEOUT):
                return
        except Exception:
            return
        try:
            from api.tasks import refresh_instagram_gallery_task
            refresh_instagram_gallery_task.delay(store_id, username)
        except Exception as e:
            logger.warning("Could not queue Instagram refresh for store %s: %s", store_id, e)

    def refresh_gallery_cache(self, business_id: Any, username: str, limit: int = 12) -> Optional[Dict[str, Any]]:
        """
        Forces a cache refresh, typically executed in a background worker task.
        """
        from api import models
        business = models.BusinessDetails.objects.filter(id=business_id).first()
        if not business:
            return None
        return self.get_gallery_for_business(business, force_refresh=True, limit=limit)


# Global singleton instance
_instagram_service_instance: Optional[InstagramService] = None


def get_instagram_service() -> InstagramService:
    global _instagram_service_instance
    if _instagram_service_instance is None:
        _instagram_service_instance = InstagramService()
    return _instagram_service_instance
