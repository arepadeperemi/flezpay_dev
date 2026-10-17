#!/usr/bin/env python3
"""
Stock photo downloader — free, commercially-usable, high-resolution images.

Searches Pexels, Unsplash and Openverse through their official APIs and
downloads the largest available file for each result, plus an ATTRIBUTION.md
file with creator / licence info for every image.

You can pass either a plain search query or a paid-stock URL (iStock, Getty,
Shutterstock, Adobe Stock). For URLs, the keywords are taken from the slug so
you get visually similar free alternatives, e.g.

    python scripts/stock_photo_downloader.py \
        "https://www.istockphoto.com/photo/smiling-businesswoman-using-smartphone-gm2225938373-641919894"

    python scripts/stock_photo_downloader.py "modern office team" -n 10 --orientation landscape

API keys (optional — Openverse works without any key):
    PEXELS_API_KEY        https://www.pexels.com/api/            (free)
    UNSPLASH_ACCESS_KEY   https://unsplash.com/oauth/applications (free)

Keys are read from the environment or from a .env file in the current
working directory / project root.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

USER_AGENT = "FlezPayStockDownloader/1.0 (+https://flezpay.com)"
TIMEOUT = 30

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for", "with",
    "from", "by", "into", "front", "using", "while", "over", "under", "near",
    "photo", "stock", "image", "picture", "royalty", "free", "vector", "video",
}

# Paid stock hosts we know how to pull keywords from.
STOCK_HOSTS = ("istockphoto.com", "gettyimages.", "shutterstock.com", "stock.adobe.com")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Photo:
    provider: str
    id: str
    download_url: str
    page_url: str
    title: str = ""
    creator: str = ""
    creator_url: str = ""
    license: str = ""
    license_url: str = ""
    width: int | None = None
    height: int | None = None
    # Provider-specific callback that must be hit when a download happens
    # (required by Unsplash API guidelines).
    track_url: str | None = field(default=None, repr=False)

    @property
    def pixels(self) -> int:
        return (self.width or 0) * (self.height or 0)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_dotenv() -> None:
    """Minimal .env loader (no extra dependency)."""
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().removeprefix("export ").strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def query_from_input(text: str) -> str:
    """Turn a search string or a stock-site URL into a keyword query."""
    text = text.strip()
    if not re.match(r"^https?://", text, re.I):
        return text

    parsed = urlparse(text)
    host = parsed.netloc.lower()
    if not any(h in host for h in STOCK_HOSTS):
        raise SystemExit(f"Unsupported URL host: {host}. Pass a search query instead.")

    # Longest path segment is the descriptive slug on all supported sites.
    segments = [unquote(s) for s in parsed.path.split("/") if s]
    slug = max(segments, key=len, default="")
    slug = re.sub(r"\.(jpe?g|png|html?)$", "", slug, flags=re.I)
    slug = re.sub(r"-?gm\d+(-\d+)?$", "", slug)        # iStock:  ...-gm2225938373-641919894
    slug = re.sub(r"-?id\d+$", "", slug)               # Getty:   ...-id123456
    slug = re.sub(r"-\d{5,}$", "", slug)                # Shutterstock / Adobe trailing ids
    words = [w for w in re.split(r"[-_\s]+", slug) if w and not w.isdigit()]
    if not words:
        raise SystemExit("Could not extract keywords from that URL.")
    return " ".join(words)


def keywords(query: str) -> list[str]:
    return [w for w in re.findall(r"[a-zA-Z0-9]+", query.lower()) if w not in STOPWORDS]


def relaxed_queries(query: str) -> list[str]:
    """Full query first, then progressively shorter keyword sets."""
    kws = keywords(query) or query.split()
    out = [query]
    for n in range(len(kws), 1, -1):
        q = " ".join(kws[:n])
        if q not in out:
            out.append(q)
    return out


def safe_name(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "photo"


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
class Provider:
    name = "base"

    def __init__(self, session: requests.Session):
        self.session = session

    @classmethod
    def available(cls) -> bool:
        return True

    def search(self, query: str, count: int, orientation: str | None) -> list[Photo]:
        raise NotImplementedError


class PexelsProvider(Provider):
    name = "pexels"
    ENDPOINT = "https://api.pexels.com/v1/search"

    @classmethod
    def available(cls) -> bool:
        return bool(os.getenv("PEXELS_API_KEY"))

    def search(self, query, count, orientation):
        params = {"query": query, "per_page": min(count, 80)}
        if orientation:
            params["orientation"] = orientation  # landscape | portrait | square
        r = self.session.get(
            self.ENDPOINT, params=params, timeout=TIMEOUT,
            headers={"Authorization": os.environ["PEXELS_API_KEY"]},
        )
        r.raise_for_status()
        photos = []
        for p in r.json().get("photos", []):
            photos.append(Photo(
                provider=self.name,
                id=str(p["id"]),
                download_url=p["src"]["original"],  # full-resolution original
                page_url=p["url"],
                title=p.get("alt") or "",
                creator=p.get("photographer", ""),
                creator_url=p.get("photographer_url", ""),
                license="Pexels License",
                license_url="https://www.pexels.com/license/",
                width=p.get("width"),
                height=p.get("height"),
            ))
        return photos


class UnsplashProvider(Provider):
    name = "unsplash"
    ENDPOINT = "https://api.unsplash.com/search/photos"

    @classmethod
    def available(cls) -> bool:
        return bool(os.getenv("UNSPLASH_ACCESS_KEY"))

    def _headers(self):
        return {"Authorization": f"Client-ID {os.environ['UNSPLASH_ACCESS_KEY']}",
                "Accept-Version": "v1"}

    def search(self, query, count, orientation):
        params = {"query": query, "per_page": min(count, 30)}
        if orientation:
            params["orientation"] = "squarish" if orientation == "square" else orientation
        r = self.session.get(self.ENDPOINT, params=params, headers=self._headers(), timeout=TIMEOUT)
        r.raise_for_status()
        photos = []
        for p in r.json().get("results", []):
            user = p.get("user", {})
            # urls.raw is the original upload; add params for a good-quality JPG.
            raw = p["urls"]["raw"]
            sep = "&" if "?" in raw else "?"
            photos.append(Photo(
                provider=self.name,
                id=p["id"],
                download_url=f"{raw}{sep}fm=jpg&q=90",
                page_url=p["links"]["html"],
                title=p.get("alt_description") or p.get("description") or "",
                creator=user.get("name", ""),
                creator_url=user.get("links", {}).get("html", ""),
                license="Unsplash License",
                license_url="https://unsplash.com/license",
                width=p.get("width"),
                height=p.get("height"),
                track_url=p["links"].get("download_location"),
            ))
        return photos

    def track(self, photo: Photo) -> None:
        if photo.track_url:
            try:
                self.session.get(photo.track_url, headers=self._headers(), timeout=TIMEOUT)
            except requests.RequestException:
                pass


class OpenverseProvider(Provider):
    """Creative Commons search (Flickr, Wikimedia, etc.). No key required."""
    name = "openverse"
    ENDPOINT = "https://api.openverse.org/v1/images/"

    def search(self, query, count, orientation):
        base = {
            "q": query,
            "page_size": min(count * 2, 20),       # anonymous limit is 20
            "license_type": "commercial,modification",
            "mature": "false",
        }
        if orientation:
            base["aspect_ratio"] = {"landscape": "wide", "portrait": "tall",
                                    "square": "square"}[orientation]

        # Prefer large images, fall back to any size.
        results = []
        for extra in ({"size": "large"}, {}):
            data = self._get({**base, **extra})
            results = data.get("results", []) if data else []
            if results:
                break

        photos = []
        for p in results:
            lic = p.get("license", "")
            version = p.get("license_version") or ""
            photos.append(Photo(
                provider=self.name,
                id=p["id"],
                download_url=p["url"],
                page_url=p.get("foreign_landing_url") or "",
                title=p.get("title") or "",
                creator=p.get("creator") or "",
                creator_url=p.get("creator_url") or "",
                license=f"CC {lic.upper()} {version}".strip() if lic not in ("cc0", "pdm") else lic.upper(),
                license_url=p.get("license_url") or "",
                width=p.get("width"),
                height=p.get("height"),
            ))
        return photos

    def _get(self, params, retries: int = 3):
        # The anonymous Openverse endpoint is occasionally flaky / throttled.
        for attempt in range(retries):
            try:
                r = self.session.get(self.ENDPOINT, params=params, timeout=TIMEOUT)
                if r.status_code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue
                r.raise_for_status()
                data = r.json()
                if data.get("results") or attempt == retries - 1:
                    return data
            except requests.RequestException:
                if attempt == retries - 1:
                    raise
            time.sleep(1 + attempt)
        return None


PROVIDERS = {cls.name: cls for cls in (PexelsProvider, UnsplashProvider, OpenverseProvider)}


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
EXT_BY_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
               "image/gif": ".gif", "image/tiff": ".tif"}


def download(session: requests.Session, photo: Photo, out_dir: Path, index: int) -> Path | None:
    try:
        with session.get(photo.download_url, stream=True, timeout=TIMEOUT * 2) as r:
            r.raise_for_status()
            ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if not ctype.startswith("image/"):
                print(f"   ! skipped (not an image: {ctype or 'unknown'})")
                return None
            ext = EXT_BY_TYPE.get(ctype, ".jpg")
            name = f"{index:02d}-{photo.provider}-{safe_name(photo.title or photo.id)}{ext}"
            path = out_dir / name
            tmp = path.with_suffix(path.suffix + ".part")
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
            tmp.rename(path)
            return path
    except requests.RequestException as exc:
        print(f"   ! download failed: {exc}")
        return None


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image  # optional
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def write_attribution(out_dir: Path, query: str, saved: list[tuple[Path, Photo]]) -> None:
    lines = [f"# Image credits\n", f"Search: `{query}`\n"]
    for path, ph in saved:
        creator = f"[{ph.creator}]({ph.creator_url})" if ph.creator_url else (ph.creator or "Unknown")
        lic = f"[{ph.license}]({ph.license_url})" if ph.license_url else ph.license
        lines.append(f"- **{path.name}** — {ph.title or 'Untitled'} by {creator} "
                     f"on {ph.provider.title()} · {lic} · [source]({ph.page_url})")
    (out_dir / "ATTRIBUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "credits.json").write_text(
        json.dumps([{**asdict(ph), "file": p.name} for p, ph in saved], indent=2, default=str),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    ap = argparse.ArgumentParser(description="Download free, high-res, commercially-usable stock photos.")
    ap.add_argument("query", help="Search text, or an iStock/Getty/Shutterstock/Adobe URL to find free alternatives")
    ap.add_argument("-n", "--count", type=int, default=5, help="Number of images to download (default 5)")
    ap.add_argument("-o", "--out", default="downloads/stock_photos", help="Output folder")
    ap.add_argument("-p", "--provider", action="append", choices=list(PROVIDERS),
                    help="Provider(s) to use. Default: every provider with a configured key, plus openverse")
    ap.add_argument("--orientation", choices=["landscape", "portrait", "square"])
    ap.add_argument("--min-width", type=int, default=1600,
                    help="Skip images narrower than this when the width is known (default 1600)")
    args = ap.parse_args(argv)

    query = query_from_input(args.query)
    names = args.provider or [n for n, cls in PROVIDERS.items() if cls.available()]
    session = make_session()

    providers = []
    for n in names:
        cls = PROVIDERS[n]
        if not cls.available():
            print(f"- {n}: skipped (set {'PEXELS_API_KEY' if n == 'pexels' else 'UNSPLASH_ACCESS_KEY'})")
            continue
        providers.append(cls(session))
    if not providers:
        print("No providers available.")
        return 1

    print(f"Search query: \"{query}\"")
    print(f"Providers:    {', '.join(p.name for p in providers)}\n")

    # Collect candidates. Start with the full query (most relevant) and keep
    # relaxing it until we have enough images that meet --min-width.
    def big_enough(ph: Photo) -> bool:
        return not ph.width or ph.width >= args.min_width

    candidates: list[tuple[Provider, Photo]] = []
    for prov in providers:
        pool: dict[str, Photo] = {}
        for q in relaxed_queries(query):
            try:
                found = prov.search(q, args.count, args.orientation)
            except requests.HTTPError as exc:
                print(f"- {prov.name}: API error {exc.response.status_code} — {exc.response.text[:150]}")
                break
            except requests.RequestException as exc:
                print(f"- {prov.name}: request failed — {exc}")
                break
            new = [ph for ph in found if ph.id not in pool]
            if new:
                n_big = sum(big_enough(ph) for ph in new)
                print(f"- {prov.name}: {len(new)} result(s) ({n_big} ≥ {args.min_width}px) for \"{q}\"")
                pool.update((ph.id, ph) for ph in new)
            if sum(big_enough(ph) for ph in pool.values()) >= args.count:
                break
        if not pool:
            print(f"- {prov.name}: no results")
            continue
        # Keep relevance order, but put images that meet --min-width first.
        ranked = sorted(pool.values(), key=lambda ph: not big_enough(ph))
        candidates.extend((prov, ph) for ph in ranked)

    if not candidates:
        print("\nNothing found. Try a shorter or different query.")
        return 1

    # Interleave providers so we get variety, then take the requested count.
    by_prov: dict[str, list] = {}
    for prov, ph in candidates:
        by_prov.setdefault(prov.name, []).append((prov, ph))
    ordered = []
    while any(by_prov.values()):
        for lst in by_prov.values():
            if lst:
                ordered.append(lst.pop(0))

    out_dir = Path(args.out) / safe_name(query, 50)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nDownloading to {out_dir}/\n")

    saved: list[tuple[Path, Photo]] = []
    seen_urls = set()
    for prov, ph in ordered:
        if len(saved) >= args.count:
            break
        if ph.download_url in seen_urls:
            continue
        seen_urls.add(ph.download_url)
        print(f"[{len(saved) + 1}/{args.count}] {ph.provider}: {ph.title[:70] or ph.id}")
        path = download(session, ph, out_dir, len(saved) + 1)
        if not path:
            continue
        if hasattr(prov, "track"):
            prov.track(ph)
        dims = image_size(path) or ((ph.width, ph.height) if ph.width else None)
        size_mb = path.stat().st_size / 1_048_576
        dim_txt = f"{dims[0]}x{dims[1]}" if dims else "?x?"
        print(f"   ✓ {path.name}  ({dim_txt}, {size_mb:.2f} MB, {ph.license})")
        saved.append((path, ph))

    if saved:
        write_attribution(out_dir, query, saved)
        print(f"\nSaved {len(saved)} image(s) + ATTRIBUTION.md to {out_dir}/")
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
