# ============================================
# File: image_helper.py
# Description: Game background image
#   - web search used  -> real photo first (several web sources in order), AI as fallback
#   - model knowledge  -> AI image first (hard time limit), real photo as fallback
#   Failure of every source never breaks the game.
#   Web sources are tried one by one; a source that fails with
#   401/403/429 is skipped for a few minutes (cooldown).
# Author: Amin Nouri
# ============================================

from __future__ import annotations

import base64
import logging
import os
import random
import re
import time
from typing import Any, Callable
from urllib.parse import quote, urlencode

import httpx

try:
    from .network_helper import proxy_modes, request_with_fallback
except ImportError:
    from network_helper import proxy_modes, request_with_fallback

logger = logging.getLogger("parallel_mcp")

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
OPENVERSE_SEARCH_URL = "https://api.openverse.org/v1/images/"
WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"
PIXABAY_API_URL = "https://pixabay.com/api/"
DEFAULT_POLLINATIONS_URL = "https://image.pollinations.ai/prompt"
USER_AGENT = "AI-Matching-Game/0.1 (university project)"  # ویکی‌مدیا بدون User-Agent رد می‌کند
MAX_IMAGE_BYTES = 3_000_000  # عکس بزرگ‌تر از این به CSS تزریق نمی‌شود

# پسوند ثابت تا عکس AI متن/لوگو نداشته باشد و برای پس‌زمینه مناسب باشد
AI_STYLE_SUFFIX = (
    ", soft colorful illustration, wide landscape, subtle background, "
    "no text, no letters, no numbers, no watermark"
)

VALID_MODES = {"auto", "web", "ai", "off"}

# ترتیب پیش‌فرض منابع وب (با IMAGE_WEB_ORDER در .env عوض می‌شود)
DEFAULT_WEB_ORDER = "pexels,unsplash,openverse,wikimedia,pixabay"

# منبعی که خطای محدودیت/دسترسی بدهد تا این مدت (ثانیه) کنار گذاشته می‌شود
COOLDOWN_BLOCKED = 300.0  # 401 / 403 / 429
COOLDOWN_OTHER = 60.0  # خطاهای دیگر (تایم‌اوت، 5xx، ...)
_cooldown_until: dict[str, float] = {}


# -------------------------
# Config (در لحظه‌ی صدا زدن خوانده می‌شود چون .env دیرتر لود می‌شود)
# -------------------------
def _mode(override: str | None = None) -> str:
    """auto | web | ai | off  (web/ai فقط اولویت‌اند؛ منبع دیگر همیشه fallback است)"""
    mode = (override or os.getenv("IMAGE_MODE", "auto")).strip().lower()
    return mode if mode in VALID_MODES else "auto"


def _log(message: str) -> None:
    logger.info("[image] %s", message)


def _to_data_uri(response: Any) -> str:
    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        raise ValueError(f"Not an image response (content-type={content_type!r})")
    data = response.content
    if not data:
        raise ValueError("Empty image body")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large ({len(data)} bytes)")
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _clean_credit(text: str, limit: int = 60) -> str:
    # تگ‌های HTML و کاراکترهای مارک‌داون لینک نباید متن اعتبار را خراب کنند
    text = re.sub(r"<[^>]+>", "", text or "")
    text = "".join(ch for ch in text if ch not in "[]()")
    return " ".join(text.split())[:limit].strip()


# -------------------------
# Web source A: Pexels (free API key)
# -------------------------
def _from_pexels(image_query: str) -> dict[str, Any] | None:
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    query = (image_query or "").strip()
    if not api_key:
        _log("PEXELS_API_KEY missing; Pexels skipped")
        return None
    if not query:
        return None

    params = urlencode(
        {"query": query, "per_page": 8, "orientation": "landscape", "size": "medium"}
    )
    response = request_with_fallback(
        "GET",
        f"{PEXELS_SEARCH_URL}?{params}",
        headers={"Authorization": api_key},
        timeout=20.0,
        log_fn=_log,
    )
    response.raise_for_status()
    photos = response.json().get("photos") or []
    if not photos:
        _log(f"Pexels returned no photos for {query!r}")
        return None

    photo = random.choice(photos)
    src = photo.get("src") or {}
    image_url = src.get("large") or src.get("medium") or src.get("original")
    if not image_url:
        return None

    image_resp = request_with_fallback("GET", image_url, timeout=30.0, log_fn=_log)
    image_resp.raise_for_status()

    photographer = _clean_credit(str(photo.get("photographer") or "")) or "Pexels"
    return {
        "data_uri": _to_data_uri(image_resp),
        "source": "web",
        "credit_text": f"{photographer} / Pexels",
        "credit_url": photo.get("url") or "https://www.pexels.com",
    }


# -------------------------
# Web source B: Unsplash (free API key; demo = 50 requests/hour)
# -------------------------
def _from_unsplash(image_query: str) -> dict[str, Any] | None:
    access_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
    query = (image_query or "").strip()
    if not access_key:
        _log("UNSPLASH_ACCESS_KEY missing; Unsplash skipped")
        return None
    if not query:
        return None

    auth_headers = {
        "Authorization": f"Client-ID {access_key}",
        "Accept-Version": "v1",
        "User-Agent": USER_AGENT,
    }
    params = urlencode(
        {"query": query, "per_page": 10, "orientation": "landscape", "content_filter": "high"}
    )
    response = request_with_fallback(
        "GET",
        f"{UNSPLASH_SEARCH_URL}?{params}",
        headers=auth_headers,
        timeout=20.0,
        log_fn=_log,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        _log(f"Unsplash returned no photos for {query!r}")
        return None

    photo = random.choice(results)
    urls = photo.get("urls") or {}
    image_url = urls.get("regular") or urls.get("small")
    if not image_url:
        return None

    image_resp = request_with_fallback("GET", image_url, timeout=30.0, log_fn=_log)
    image_resp.raise_for_status()

    # طبق قوانین Unsplash باید دانلود ثبت شود (best-effort، خطایش مهم نیست)
    download_location = (photo.get("links") or {}).get("download_location")
    if download_location:
        try:
            request_with_fallback(
                "GET", download_location, headers=auth_headers, timeout=10.0, log_fn=_log
            )
        except Exception as exc:
            _log(f"Unsplash download ping failed: {type(exc).__name__}")

    user = photo.get("user") or {}
    name = _clean_credit(str(user.get("name") or "")) or "Unsplash"
    return {
        "data_uri": _to_data_uri(image_resp),
        "source": "web",
        "credit_text": f"{name} / Unsplash",
        "credit_url": (photo.get("links") or {}).get("html") or "https://unsplash.com",
    }


# -------------------------
# Web source C: Openverse (no key needed; optional OPENVERSE_TOKEN for higher limits)
# -------------------------
def _from_openverse(image_query: str) -> dict[str, Any] | None:
    query = (image_query or "").strip()
    if not query:
        return None

    headers = {"User-Agent": USER_AGENT}
    token = os.getenv("OPENVERSE_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = urlencode(
        {
            "q": query,
            "page_size": 10,
            "aspect_ratio": "wide",
            "mature": "false",
            "license_type": "commercial,modification",
        }
    )
    response = request_with_fallback(
        "GET",
        f"{OPENVERSE_SEARCH_URL}?{params}",
        headers=headers,
        timeout=20.0,
        log_fn=_log,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        _log(f"Openverse returned no photos for {query!r}")
        return None

    item = random.choice(results)
    # thumbnail کوچک‌تر و پایدارتر از لینک اصلیِ سایت مبدأ است
    image_url = item.get("thumbnail") or item.get("url")
    if not image_url:
        return None

    image_resp = request_with_fallback(
        "GET", image_url, headers=headers, timeout=30.0, log_fn=_log
    )
    image_resp.raise_for_status()

    creator = _clean_credit(str(item.get("creator") or "")) or "Unknown"
    license_name = " ".join(
        part
        for part in (
            str(item.get("license") or "").upper(),
            str(item.get("license_version") or ""),
        )
        if part
    )
    credit = f"{creator} / Openverse"
    if license_name:
        credit += f" (CC {license_name})"
    return {
        "data_uri": _to_data_uri(image_resp),
        "source": "web",
        "credit_text": credit,
        "credit_url": item.get("foreign_landing_url") or "https://openverse.org",
    }


# -------------------------
# Web source D: Wikimedia Commons (no key needed)
# -------------------------
def _from_wikimedia(image_query: str) -> dict[str, Any] | None:
    query = (image_query or "").strip()
    if not query:
        return None

    params = urlencode(
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrnamespace": 6,  # فقط فایل‌ها
            "gsrlimit": 10,
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": 1024,
        }
    )
    headers = {"User-Agent": USER_AGENT}
    response = request_with_fallback(
        "GET",
        f"{WIKIMEDIA_API_URL}?{params}",
        headers=headers,
        timeout=20.0,
        log_fn=_log,
    )
    response.raise_for_status()

    pages = (response.json().get("query") or {}).get("pages") or {}
    candidates = []
    for page in pages.values():
        info = (page.get("imageinfo") or [None])[0]
        if not info or not info.get("thumburl"):
            continue
        if info.get("mime") not in {"image/jpeg", "image/png"}:
            continue
        candidates.append(info)
    if not candidates:
        _log(f"Wikimedia returned no usable images for {query!r}")
        return None

    info = random.choice(candidates)
    image_resp = request_with_fallback(
        "GET", info["thumburl"], headers=headers, timeout=30.0, log_fn=_log
    )
    image_resp.raise_for_status()

    artist = _clean_credit(
        ((info.get("extmetadata") or {}).get("Artist") or {}).get("value", "")
    )
    return {
        "data_uri": _to_data_uri(image_resp),
        "source": "web",
        "credit_text": f"{artist + ' / ' if artist else ''}Wikimedia Commons",
        "credit_url": info.get("descriptionurl") or "https://commons.wikimedia.org",
    }


# -------------------------
# Web source E: Pixabay (free API key; strict rate limit, so last by default)
# -------------------------
def _from_pixabay(image_query: str) -> dict[str, Any] | None:
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()
    query = (image_query or "").strip()[:100]  # Pixabay: حداکثر ۱۰۰ کاراکتر
    if not api_key:
        _log("PIXABAY_API_KEY missing; Pixabay skipped")
        return None
    if not query:
        return None

    params = urlencode(
        {
            "key": api_key,
            "q": query,
            "image_type": "photo",
            "orientation": "horizontal",
            "safesearch": "true",
            "per_page": 10,
        }
    )
    headers = {"User-Agent": USER_AGENT}
    response = request_with_fallback(
        "GET",
        f"{PIXABAY_API_URL}?{params}",
        headers=headers,
        timeout=20.0,
        log_fn=_log,
    )
    response.raise_for_status()
    hits = response.json().get("hits") or []
    if not hits:
        _log(f"Pixabay returned no photos for {query!r}")
        return None

    hit = random.choice(hits)
    image_url = hit.get("largeImageURL") or hit.get("webformatURL")
    if not image_url:
        return None

    image_resp = request_with_fallback(
        "GET", image_url, headers=headers, timeout=30.0, log_fn=_log
    )
    image_resp.raise_for_status()

    user = _clean_credit(str(hit.get("user") or "")) or "Pixabay"
    return {
        "data_uri": _to_data_uri(image_resp),
        "source": "web",
        "credit_text": f"{user} / Pixabay",
        "credit_url": hit.get("pageURL") or "https://pixabay.com",
    }


WEB_SOURCES: dict[str, Callable[[str], dict[str, Any] | None]] = {
    "pexels": _from_pexels,
    "unsplash": _from_unsplash,
    "openverse": _from_openverse,
    "wikimedia": _from_wikimedia,
    "pixabay": _from_pixabay,
}


def _web_order() -> list[str]:
    """ترتیب منابع وب از IMAGE_WEB_ORDER (مثلاً 'openverse,pexels'). نام نامعتبر نادیده گرفته می‌شود."""
    raw = os.getenv("IMAGE_WEB_ORDER", DEFAULT_WEB_ORDER)
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    ordered = [n for n in names if n in WEB_SOURCES]
    return ordered or [n for n in DEFAULT_WEB_ORDER.split(",") if n in WEB_SOURCES]


def _cooldown_for(exc: Exception) -> float:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (401, 403, 429):
        return COOLDOWN_BLOCKED
    return COOLDOWN_OTHER


def _from_web(image_query: str, image_prompt: str) -> dict[str, Any] | None:
    """منابع وب را به ترتیب امتحان می‌کند؛ هرکدام شکست خورد، بعدی."""
    for name in _web_order():
        wait = _cooldown_until.get(name, 0.0) - time.monotonic()
        if wait > 0:
            _log(f"web/{name} in cooldown ({wait:.0f}s left); skipped")
            continue
        try:
            result = WEB_SOURCES[name](image_query)
        except Exception as exc:
            _cooldown_until[name] = time.monotonic() + _cooldown_for(exc)
            logger.warning("[image] web/%s failed: %s: %s", name, type(exc).__name__, exc)
            continue
        if result:
            return result
    return None


# -------------------------
# AI source: Pollinations (free, no key) with a HARD total time limit
# -------------------------
def _get_with_deadline(url: str, total_seconds: float) -> httpx.Response:
    """
    یک GET با سقف زمانی کل (نه برای هر حالت پروکسی جداگانه).
    اگر پاسخ دیر برسد TimeoutError می‌دهد تا بلافاصله منبع بعدی امتحان شود.
    بدون دست‌زدن به env پروکسی: حالت مستقیم با trust_env=False انجام می‌شود.
    """
    deadline = time.monotonic() + total_seconds
    errors: list[str] = []

    for mode_name, use_proxy in proxy_modes():
        remaining = deadline - time.monotonic()
        if remaining <= 1.0:
            break
        timeout = httpx.Timeout(
            connect=min(10.0, remaining), read=remaining, write=10.0, pool=10.0
        )
        try:
            _log(f"AI image GET mode={mode_name} budget={remaining:.0f}s")
            with httpx.Client(
                timeout=timeout, follow_redirects=True, trust_env=use_proxy
            ) as client:
                return client.get(url, headers={"User-Agent": USER_AGENT})
        except httpx.ReadTimeout as exc:
            # مدل دارد تصویر می‌سازد ولی دیر شد؛ حالت دیگر هم کمکی نمی‌کند
            raise TimeoutError(f"AI image timed out after {total_seconds:.0f}s") from exc
        except Exception as exc:
            errors.append(f"{mode_name}: {type(exc).__name__}: {exc}")

    raise RuntimeError("AI image request failed: " + " | ".join(errors or ["no time left"]))


def _from_ai(image_query: str, image_prompt: str) -> dict[str, Any] | None:
    prompt = (image_prompt or image_query or "").strip()
    if not prompt:
        return None

    base = os.getenv("POLLINATIONS_URL", DEFAULT_POLLINATIONS_URL).strip().rstrip("/")
    timeout = float(os.getenv("IMAGE_AI_TIMEOUT", "25"))
    params = urlencode(
        {
            "width": 1024,
            "height": 640,
            "nologo": "true",
            "seed": random.randint(1, 999_999),
        }
    )
    url = f"{base}/{quote(prompt + AI_STYLE_SUFFIX, safe='')}?{params}"

    response = _get_with_deadline(url, timeout)
    response.raise_for_status()
    return {
        "data_uri": _to_data_uri(response),
        "source": "ai",
        "credit_text": "Pollinations.ai",
        "credit_url": "https://pollinations.ai",
    }


# -------------------------
# Public API
# -------------------------
def _sources(
    used_search: bool,
    mode: str | None = None,
) -> list[Callable[[str, str], dict[str, Any] | None]]:
    mode = _mode(mode)
    if mode == "off":
        return []
    if mode == "web":
        return [_from_web, _from_ai]
    if mode == "ai":
        return [_from_ai, _from_web]
    # auto: پیش‌فرض عکس واقعی اول (سریع، ~۱ تا ۳ ثانیه) و AI فقط fallback است.
    # با IMAGE_AUTO_FIRST=ai در .env، وقتی سرچ استفاده نشده AI اول می‌شود (کُندتر).
    if os.getenv("IMAGE_AUTO_FIRST", "web").strip().lower() == "ai" and not used_search:
        return [_from_ai, _from_web]
    return [_from_web, _from_ai]


def get_background(
    image_query: str,
    image_prompt: str,
    used_search: bool,
    mode: str | None = None,
) -> dict[str, Any] | None:
    """
    mode: None (از IMAGE_MODE در .env) | "auto" | "web" | "ai" | "off"
    خروجی: {"data_uri", "source": "web"|"ai", "credit_text", "credit_url"}
    یا None اگر هیچ منبعی عکس نداد (یا mode=off باشد).
    """
    for source in _sources(used_search, mode):
        try:
            result = source(image_query, image_prompt)
        except Exception as exc:
            logger.warning(
                "[image] %s failed (%s: %s); trying next source",
                source.__name__,
                type(exc).__name__,
                exc,
            )
            continue
        if result:
            _log(f"background ready via {result['source']} ({result['credit_text']})")
            return result
    _log("no background image available")
    return None