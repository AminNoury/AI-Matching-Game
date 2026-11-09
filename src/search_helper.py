# ============================================
# File: search_helper.py
# Description: Optional on-demand web search via Parallel MCP (free, no API key)
# Author: Amin Nouri
# ============================================

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections import deque
from typing import Any

import httpx

from network_helper import configure_network_env, make_timeout, proxy_modes

PARALLEL_MCP_URL = os.getenv(
    "PARALLEL_MCP_URL",
    "https://search.parallel.ai/mcp",
)

configure_network_env()

# یک session پایدار برای rate-limit رایگان Parallel
_CLIENT_SESSION_ID = uuid.uuid4().hex
_REQUEST_ID = 0

# لاگ‌های اخیر برای نمایش در Streamlit
_RECENT_LOGS: deque[str] = deque(maxlen=80)

logger = logging.getLogger("parallel_mcp")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[ParallelMCP] %(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _log(level: int, message: str) -> None:
    logger.log(level, message)
    _RECENT_LOGS.append(f"{time.strftime('%H:%M:%S')} | {logging.getLevelName(level)} | {message}")


def get_recent_logs() -> list[str]:
    return list(_RECENT_LOGS)


def clear_recent_logs() -> None:
    _RECENT_LOGS.clear()


def search_available() -> bool:
    """Parallel MCP رایگان است؛ همیشه در دسترس فرض می‌شود مگر غیرفعال شود."""
    disabled = os.getenv("PARALLEL_SEARCH_DISABLED", "").strip().lower()
    return disabled not in {"1", "true", "yes", "on"}


def _next_id() -> int:
    global _REQUEST_ID
    _REQUEST_ID += 1
    return _REQUEST_ID


def _parse_mcp_response(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    text = response.text
    if "text/event-stream" in content_type:
        data_lines = [
            line[5:].strip()
            for line in text.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            raise RuntimeError("Empty MCP SSE response from Parallel.")
        return json.loads(data_lines[-1])
    return response.json()


def _mcp_call_once(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    trust_env: bool,
    mode_name: str,
) -> dict[str, Any]:
    """یک بار کامل: initialize → initialized → tools/call"""
    headers_base = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    started = time.perf_counter()

    with httpx.Client(
        timeout=make_timeout(75.0),
        follow_redirects=True,
        trust_env=trust_env,
    ) as client:
        _log(logging.INFO, f"MCP initialize ... mode={mode_name}")
        init_resp = client.post(
            PARALLEL_MCP_URL,
            headers=headers_base,
            json={
                "jsonrpc": "2.0",
                "id": _next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "ai-matching-game", "version": "0.1.0"},
                },
            },
        )
        init_resp.raise_for_status()
        session_id = init_resp.headers.get("mcp-session-id")
        if not session_id:
            raise RuntimeError("Parallel MCP did not return Mcp-Session-Id.")
        _log(
            logging.INFO,
            f"MCP initialize OK mode={mode_name} status={init_resp.status_code} "
            f"session={session_id[:8]}...",
        )

        headers = {
            **headers_base,
            "Mcp-Session-Id": session_id,
            "MCP-Protocol-Version": "2024-11-05",
        }

        api_key = os.getenv("PARALLEL_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            _log(logging.INFO, "Using PARALLEL_API_KEY for higher rate limits")
        else:
            _log(logging.INFO, "Anonymous free tier (no PARALLEL_API_KEY)")

        client.post(
            PARALLEL_MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        _log(logging.INFO, f"MCP notifications/initialized sent mode={mode_name}")

        _log(logging.INFO, f"MCP tools/call {tool_name} mode={mode_name} ...")
        call_resp = client.post(
            PARALLEL_MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": _next_id(),
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )
        call_resp.raise_for_status()
        payload = _parse_mcp_response(call_resp)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        _log(
            logging.INFO,
            f"MCP tools/call OK mode={mode_name} status={call_resp.status_code} "
            f"elapsed_ms={elapsed_ms}",
        )

    if "error" in payload:
        raise RuntimeError(f"Parallel MCP error: {payload['error']}")

    result = payload.get("result") or {}
    if result.get("isError"):
        content = result.get("content") or []
        message = content[0].get("text") if content else "unknown tool error"
        raise RuntimeError(f"Parallel MCP tool error: {message}")

    usage = (result.get("_meta") or {}).get("parallel/usage")
    if usage:
        _log(logging.INFO, f"MCP usage meta: {usage}")
    return result


def _mcp_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Parallel MCP با fallback شبکه:
    اول از پروکسی VPN، اگر timeout/refuse شد مستقیم بدون پروکسی.
    """
    queries = arguments.get("search_queries") or []
    _log(logging.INFO, f"MCP call start tool={tool_name} queries={queries}")

    errors: list[str] = []
    saved_proxy: dict[str, str] = {}

    for mode_name, use_proxy in proxy_modes():
        try:
            if not use_proxy:
                # موقتاً پروکسی env را کنار بگذار تا httpx مستقیم برود
                keys = (
                    "ALL_PROXY",
                    "all_proxy",
                    "HTTP_PROXY",
                    "http_proxy",
                    "HTTPS_PROXY",
                    "https_proxy",
                )
                saved_proxy = {k: os.environ[k] for k in keys if k in os.environ}
                for key in saved_proxy:
                    os.environ.pop(key, None)
                _log(logging.WARNING, f"Retrying MCP in DIRECT mode (proxy bypass)")

            return _mcp_call_once(
                tool_name,
                arguments,
                trust_env=use_proxy,
                mode_name=mode_name,
            )
        except Exception as exc:
            msg = f"{mode_name}: {type(exc).__name__}: {exc}"
            errors.append(msg)
            _log(logging.ERROR, f"MCP attempt failed ({msg})")
        finally:
            if saved_proxy:
                for key, value in saved_proxy.items():
                    os.environ[key] = value
                saved_proxy = {}

    raise RuntimeError("Parallel MCP failed on all network modes: " + " | ".join(errors))


def _normalize_search_result(raw: dict[str, Any], query: str) -> list[dict[str, Any]]:
    results = []
    for item in (raw.get("results") or [])[:5]:
        excerpts = item.get("excerpts") or []
        content = " ".join(str(x) for x in excerpts if x).strip()
        results.append(
            {
                "query": query,
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "content": content[:500],
            }
        )
    return results


def web_search(query: str, max_results: int = 3) -> list[dict[str, Any]]:
    """
    جستجوی وب با Parallel MCP (web_search).
    بدون API key هم کار می‌کند (free tier).
    """
    if not search_available():
        _log(logging.WARNING, "web_search skipped: Parallel search disabled")
        return []

    query = (query or "").strip()
    if not query:
        _log(logging.WARNING, "web_search skipped: empty query")
        return []

    _log(logging.INFO, f"web_search query={query!r} max_results={max_results}")
    try:
        result = _mcp_call(
            "web_search",
            {
                "objective": f"Find reliable facts relevant to: {query}",
                "search_queries": [query],
                "session_id": _CLIENT_SESSION_ID,
                "model_name": os.getenv("OPENAI_MODEL", "openai/gpt-5.6-luna"),
            },
        )
    except Exception as exc:
        _log(logging.ERROR, f"web_search failed: {exc}")
        raise

    content_blocks = result.get("content") or []
    text = ""
    for block in content_blocks:
        if block.get("type") == "text" and block.get("text"):
            text = block["text"]
            break
    if not text:
        _log(logging.WARNING, "web_search: empty content from MCP")
        return []

    raw = json.loads(text)
    hits = _normalize_search_result(raw, query)[:max_results]
    _log(logging.INFO, f"web_search OK hits={len(hits)}")
    for i, hit in enumerate(hits, start=1):
        _log(logging.INFO, f"  hit[{i}] {hit.get('title')[:80]} | {hit.get('url')}")
    return hits


def run_searches(queries: list[str], max_results_per_query: int = 3) -> list[dict[str, Any]]:
    """
    چند کوئری را در یک objective دسته‌بندی می‌کند تا یک بار Parallel صدا زده شود.
    """
    clean_queries = [str(q).strip() for q in (queries or []) if str(q).strip()][:3]
    _log(logging.INFO, f"run_searches queries={clean_queries}")

    if not clean_queries:
        _log(logging.WARNING, "run_searches: no queries")
        return []
    if not search_available():
        _log(logging.WARNING, "run_searches skipped: Parallel search disabled")
        return []

    if len(clean_queries) == 1:
        return web_search(clean_queries[0], max_results=max_results_per_query)

    try:
        result = _mcp_call(
            "web_search",
            {
                "objective": (
                    "Find concise, reliable facts for building an educational "
                    "matching game. Focus on accurate pairable concepts."
                ),
                "search_queries": clean_queries,
                "session_id": _CLIENT_SESSION_ID,
                "model_name": os.getenv("OPENAI_MODEL", "openai/gpt-5.6-luna"),
            },
        )
    except Exception as exc:
        _log(logging.ERROR, f"run_searches failed: {exc}")
        raise

    content_blocks = result.get("content") or []
    text = ""
    for block in content_blocks:
        if block.get("type") == "text" and block.get("text"):
            text = block["text"]
            break
    if not text:
        _log(logging.WARNING, "run_searches: empty content from MCP")
        return []

    raw = json.loads(text)
    bundled: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    label = " | ".join(clean_queries)

    for hit in _normalize_search_result(raw, label):
        url = hit.get("url") or ""
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        bundled.append(hit)
        if len(bundled) >= max_results_per_query * len(clean_queries):
            break

    _log(logging.INFO, f"run_searches OK hits={len(bundled)}")
    for i, hit in enumerate(bundled, start=1):
        _log(logging.INFO, f"  hit[{i}] {hit.get('title')[:80]} | {hit.get('url')}")
    return bundled
