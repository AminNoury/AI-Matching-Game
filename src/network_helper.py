# ============================================
# File: network_helper.py
# Description: Proxy/VPN resilient HTTP helpers
# Author: Amin Nouri
# ============================================

from __future__ import annotations

import logging
import os
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("parallel_mcp")

# با VPN روشن، دامنههای ایرانی مستقیم بروند (split tunnel در سطح اپ)
_DEFAULT_NO_PROXY = [
    "localhost",
    "127.0.0.1",
    "::1",
    ".ir",
    "iau.ac.ir",
    "google.com",
    "scholar.google.com",
]


def configure_network_env() -> None:
    """
    آماده‌سازی env شبکه:
    - socks:// → socks5:// (httpx این را می‌فهمد)
    - NO_PROXY برای دامنههای ایرانی/لوکال تا با VPN هم مستقیم باشند
    """
    for key in ("ALL_PROXY", "all_proxy"):
        value = os.environ.get(key, "").strip()
        if value.startswith("socks://"):
            fixed = "socks5://" + value[len("socks://") :]
            os.environ[key] = fixed
            logger.info("Normalized %s: socks:// → socks5://", key)

    existing = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    parts = [p.strip() for p in existing.split(",") if p.strip()]
    lowered = {p.lower() for p in parts}
    for item in _DEFAULT_NO_PROXY:
        if item.lower() not in lowered:
            parts.append(item)
    merged = ",".join(parts)
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged
    logger.info("NO_PROXY set for Iranian/local bypass: %s", merged)


def _proxy_env_snapshot() -> dict[str, str]:
    keys = (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "NO_PROXY",
        "no_proxy",
    )
    return {k: os.environ[k] for k in keys if k in os.environ}


def _clear_proxy_env() -> dict[str, str]:
    """پروکسی را موقتاً برمی‌دارد و مقادیر قبلی را برمی‌گرداند."""
    saved = _proxy_env_snapshot()
    for key in list(saved):
        os.environ.pop(key, None)
    return saved


def _restore_proxy_env(saved: dict[str, str]) -> None:
    for key, value in saved.items():
        os.environ[key] = value


def proxy_modes() -> list[tuple[str, bool]]:
    """
    ترتیب تلاش:
    1) با پروکسی سیستم (VPN روشن)
    2) مستقیم بدون پروکسی (وقتی پروکسی لوکال down است یا timeout)
    """
    has_proxy = any(
        os.environ.get(k)
        for k in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")
    )
    modes: list[tuple[str, bool]] = []
    if has_proxy:
        modes.append(("via_proxy", True))
    modes.append(("direct", False))
    if not has_proxy:
        # اگر پروکسی در env نبود، فقط direct
        pass
    return modes


def make_timeout(total: float = 60.0) -> httpx.Timeout:
    return httpx.Timeout(
        connect=20.0,
        read=total,
        write=20.0,
        pool=20.0,
    )


def request_with_fallback(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 60.0,
    log_fn=None,
) -> httpx.Response:
    """
    درخواست HTTP با fallback پروکسی ↔ مستقیم.
    برای VPN روشن + دسترسی پایدار به سرویسهای خارجی.
    """
    log = log_fn or (lambda msg: logger.info(msg))
    errors: list[str] = []

    for mode_name, use_proxy in proxy_modes():
        saved = {}
        try:
            if not use_proxy:
                saved = _clear_proxy_env()
                log(f"HTTP {method} {urlparse(url).netloc} mode={mode_name} (proxy cleared)")
            else:
                log(f"HTTP {method} {urlparse(url).netloc} mode={mode_name}")

            with httpx.Client(
                timeout=make_timeout(timeout),
                follow_redirects=True,
                trust_env=use_proxy,
            ) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                )
                log(f"HTTP {method} OK mode={mode_name} status={response.status_code}")
                return response
        except Exception as exc:
            msg = f"{mode_name} failed: {type(exc).__name__}: {exc}"
            errors.append(msg)
            log(msg)
        finally:
            if saved:
                _restore_proxy_env(saved)

    raise RuntimeError("All network modes failed: " + " | ".join(errors))


def build_openai_http_client() -> httpx.Client:
    """
    کلاینت برای LLM:
    اول پروکسی VPN، اگر پروکسی لوکال مرده باشد از env پروکسی را برمیداریم.
    """
    configure_network_env()
    # تست سریع پروکسی؛ اگر connection refused بود مستقیم شو
    proxy_keys = ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")
    has_proxy = any(os.environ.get(k) for k in proxy_keys)
    if has_proxy:
        try:
            with httpx.Client(timeout=make_timeout(8.0), trust_env=True) as probe:
                # فقط TCP/TLS به host مدل را چک نمیکنیم؛ پروکسی را با request کوتاه می‌سنجیم
                # اگر پروکسی down باشد اینجا معمولاً ConnectError میدهد
                base = os.getenv("OPENAI_BASE_URL", "")
                if base:
                    probe.get(base.rstrip("/") + "/models")
            logger.info("LLM HTTP client: using system proxy/VPN")
            return httpx.Client(timeout=make_timeout(90.0), trust_env=True, follow_redirects=True)
        except Exception as exc:
            logger.warning(
                "Proxy probe failed (%s); LLM client will use DIRECT mode. "
                "Keep VPN ON but ensure split-tunnel or working local proxy.",
                exc,
            )
            saved = _clear_proxy_env()
            # مقادیر را نگه نمیداریم در client؛ برای بقیه اپ NO_PROXY مهم است
            # پروکسی را restore میکنیم ولی client با trust_env=False میسازیم
            _restore_proxy_env(saved)
            return httpx.Client(timeout=make_timeout(90.0), trust_env=False, follow_redirects=True)

    logger.info("LLM HTTP client: direct (no proxy env)")
    return httpx.Client(timeout=make_timeout(90.0), trust_env=False, follow_redirects=True)
