# ============================================
# File: ai_helper.py
# Description: Matching Game generator with optional on-demand web search
# Author: Amin Nouri
# ============================================

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import (
    APIStatusError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)

# هم با `streamlit run src/app.py` کار می‌کند (import ساده)
# هم با `uvicorn src.server:app` (import نسبی به عنوان package)
try:
    from .image_helper import get_background
    from .network_helper import build_openai_http_client, configure_network_env
    from .search_helper import (
        clear_recent_logs,
        get_recent_logs,
        run_searches,
        search_available,
    )
except ImportError:
    from image_helper import get_background
    from network_helper import build_openai_http_client, configure_network_env
    from search_helper import (
        clear_recent_logs,
        get_recent_logs,
        run_searches,
        search_available,
    )

_search_logger = logging.getLogger("parallel_mcp")

DEFAULT_PROMPT = "A fun, simple matching game for high school students"
MAX_GENERATE_ATTEMPTS = 2

# زبان بازی: "auto" یعنی همان زبان پرامپت کاربر
LANG_RULES = {
    "auto": "Use the same language as the user's request.",
    "en": "Write the game title and ALL card texts in English.",
    "fa": (
        "Write the game title and ALL card texts in Persian (Farsi, Persian script). "
        "Keep them short, simple and natural for Iranian high-school students."
    ),
}

# -------------------------
# API Setup (OpenRouter -> DeepSeek)
# -------------------------
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

# override=True: مقدار .env بر متغیرهای قدیمی شل (مثل کلید omniroute) غلبه کند
load_dotenv(ENV_PATH, override=True)
configure_network_env()


def _load_api_keys() -> list[str]:
    """
    چند کلید با کاما جدا می‌شوند: OPENAI_API_KEYS=key1,key2,key3
    (OPENAI_API_KEY تکی هم هنوز پشتیبانی می‌شود.)
    """
    raw = ",".join(
        filter(None, [os.getenv("OPENAI_API_KEYS"), os.getenv("OPENAI_API_KEY")])
    )
    keys: list[str] = []
    for item in re.split(r"[,\s]+", raw):
        item = item.strip()
        if item and item not in keys:
            keys.append(item)
    if not keys:
        raise RuntimeError(
            f"OPENAI_API_KEYS (or OPENAI_API_KEY) is missing. Add it to {ENV_PATH}"
        )
    return keys


API_KEYS = _load_api_keys()
base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1").strip()
model_name = os.getenv("OPENAI_MODEL", "deepseek/deepseek-chat").strip()
temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# network_helper مقدار base را از محیط می‌خواند
os.environ["OPENAI_BASE_URL"] = base_url

# http_client با fallback پروکسی/VPN برای پایداری اتصال
_http_client = build_openai_http_client()

# برای هر کلید یک کلاینت؛ max_retries=0 تا خطا فوراً به کلید بعدی منتقل شود
_llms = [
    ChatOpenAI(
        model=model_name,
        api_key=key,
        base_url=base_url,
        temperature=temperature,
        timeout=60,
        max_retries=0,
        http_client=_http_client,
    )
    for key in API_KEYS
]

RATE_LIMIT_COOLDOWN = 60  # ثانیه استراحت کلیدی که 429 گرفته
_DEAD = float("inf")  # کلید نامعتبر یا بدون اعتبار تا ری‌استارت کنار می‌رود
_blocked_until = [0.0] * len(_llms)
_active = 0


def _invoke(messages: list[Any]) -> Any:
    """با کلید فعلی درخواست بزن؛ اگر محدود/نامعتبر بود برو سراغ کلید بعدی."""
    global _active
    n = len(_llms)
    last_exc: Exception | None = None

    for step in range(n):
        idx = (_active + step) % n
        if _blocked_until[idx] > time.monotonic():
            continue
        try:
            response = _llms[idx].invoke(messages)
            _active = idx
            return response
        except (AuthenticationError, PermissionDeniedError) as exc:
            _blocked_until[idx] = _DEAD
            last_exc = exc
        except RateLimitError as exc:
            _blocked_until[idx] = time.monotonic() + RATE_LIMIT_COOLDOWN
            last_exc = exc
        except APIStatusError as exc:
            if exc.status_code != 402:  # 402 = اعتبار تمام شده
                raise
            _blocked_until[idx] = _DEAD
            last_exc = exc
        # فقط شماره کلید لاگ می‌شود، نه خود کلید
        _search_logger.warning(
            "API key #%d/%d failed (%s); switching to next key",
            idx + 1,
            n,
            type(last_exc).__name__,
        )

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(
        "All API keys are blocked (rate-limited or invalid). Try again in a minute."
    )


# -------------------------
# Helpers
# -------------------------
def _message_text(response: Any) -> str:
    """متن پاسخ مدل را چه رشته باشد چه لیست بخش‌ها برمی‌گرداند."""
    content = response.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for part in content or []:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and part.get("type") == "text":
            parts.append(part.get("text", ""))
    return "".join(parts)


def _extract_json(content: str) -> dict[str, Any]:
    text = (content or "").strip()

    # حذف ```json ... ``` اگر مدل دور JSON بلاک کد گذاشت
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    candidates = [text]
    # اگر مدل متن اضافه داد، اولین آبجکت JSON را پیدا کن
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data

    raise ValueError("LLM returned invalid JSON:\n" + (content or ""))


def _decide_search(user_prompt: str) -> dict[str, Any]:
    """
    مدل فقط وقتی سرچ می‌خواهد که مطمئن نباشد.
    خروجی نمونه:
    {"need_search": true, "queries": ["..."], "reason": "..."}
    """
    system_prompt = """
You decide whether web search is needed before building a matching game.

Search ONLY if you are unsure, missing facts, or need current/specific real-world details.
Do NOT search for common knowledge you already know well.
Do NOT search just to enrich a creative/fantasy theme.
Prefer need_search=false when your own knowledge is enough.

Return ONLY valid JSON:
{
  "need_search": true or false,
  "queries": ["short search query 1", "short search query 2"],
  "reason": "one short sentence"
}

Rules:
- queries: 0 to 3 items
- if need_search is false, queries must be []
- no markdown, no extra text
"""
    messages = [
        SystemMessage(content=system_prompt.strip()),
        HumanMessage(
            content=(
                "User matching-game request:\n"
                f'"""{user_prompt}"""\n\n'
                "Decide if search is needed."
            )
        ),
    ]
    response = _invoke(messages)
    data = _extract_json(_message_text(response))

    need_search = bool(data.get("need_search"))
    queries = data.get("queries") or []
    if not isinstance(queries, list):
        queries = []
    queries = [str(q).strip() for q in queries if str(q).strip()][:3]
    reason = str(data.get("reason") or "").strip()

    if not need_search:
        queries = []

    return {
        "need_search": need_search and bool(queries),
        "queries": queries,
        "reason": reason,
    }


def _validate_game_data(data: dict[str, Any]) -> dict[str, Any]:
    title = data.get("title")
    pairs = data.get("pairs")

    if not isinstance(title, str) or not title.strip() or not isinstance(pairs, list) or len(pairs) != 4:
        raise ValueError(
            "LLM returned invalid structure:\n"
            + json.dumps(data, indent=2, ensure_ascii=False)
        )

    seen: set[str] = set()
    cleaned: list[dict[str, str]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("Each pair must be an object with left and right.")
        left = str(pair.get("left") or "").strip()
        right = str(pair.get("right") or "").strip()
        if not left or not right:
            raise ValueError(
                "Each pair must include non-empty left and right:\n"
                + json.dumps(data, indent=2, ensure_ascii=False)
            )
        # کارت تکراری بازی را گیج‌کننده می‌کند
        for value in (left, right):
            key = value.casefold()
            if key in seen:
                raise ValueError(f"Duplicate card text: {value}")
            seen.add(key)
        cleaned.append({"left": left, "right": right})

    # فیلدهای عکس اختیاری‌اند؛ نبودنشان بازی را خراب نمی‌کند
    image_query = str(data.get("image_query") or "").strip()[:80]
    image_prompt = str(data.get("image_prompt") or "").strip()[:300]

    return {
        "title": title.strip(),
        "pairs": cleaned,
        "image_query": image_query,
        "image_prompt": image_prompt,
    }


def _generate_game(
    user_prompt: str,
    search_results: list[dict[str, Any]],
    lang: str = "auto",
) -> dict[str, Any]:
    evidence = "No web search was used. Rely on your own reliable knowledge."
    if search_results:
        evidence = json.dumps(search_results, ensure_ascii=False, indent=2)

    system_prompt = """
You are a creative matching-game content generator.

Build a memory matching game from the user's request.
If search evidence is provided, use it only to correct or confirm uncertain facts.
Do not turn the whole game into a web dump — keep cards short and playable.

Your task:
- Follow the user's theme, topic, language, difficulty, and style
- Generate exactly 4 complementary pairs
- Each pair MUST be strongly related and clearly matchable
- left and right should be distinct but belong together
- All 8 card texts must be different from each other
- Prefer accuracy when facts are involved

Rules:
- Creative title (7 to 12 words)
- Prefer the same language the user used, unless the Language rule says otherwise
- Short card texts (1 to 5 words when possible)
- image_query: 2 to 4 ENGLISH words for a stock-photo search matching the game's theme
  (a concrete scene, place or object; no people's names)
- image_prompt: ONE ENGLISH sentence (max 30 words) describing a calm background
  illustration for the theme; it must not ask for any text, letters, numbers or logos
- Output ONLY valid JSON
- No markdown, no explanations
"""

    language_rule = LANG_RULES.get(lang, LANG_RULES["auto"])

    human_prompt = f"""
User request for the matching game:
\"\"\"{user_prompt}\"\"\"

Language rule: {language_rule}

Search evidence (may be empty):
{evidence}

Return strictly this JSON:
{{
  "title": "Game title here",
  "image_query": "short english photo search",
  "image_prompt": "One english sentence describing a background illustration",
  "pairs": [
    {{ "left": "Item A1", "right": "Item B1" }},
    {{ "left": "Item A2", "right": "Item B2" }},
    {{ "left": "Item A3", "right": "Item B3" }},
    {{ "left": "Item A4", "right": "Item B4" }}
  ]
}}
"""
    messages = [
        SystemMessage(content=system_prompt.strip()),
        HumanMessage(content=human_prompt.strip()),
    ]

    # اگر خروجی مدل نامعتبر بود، یک بار دیگر تلاش کن
    last_error: ValueError | None = None
    for attempt in range(1, MAX_GENERATE_ATTEMPTS + 1):
        response = _invoke(messages)
        try:
            return _validate_game_data(_extract_json(_message_text(response)))
        except ValueError as exc:
            last_error = exc
            _search_logger.warning("generate attempt %s invalid: %s", attempt, exc)

    raise last_error  # type: ignore[misc]


# -------------------------
# Public API
# -------------------------
def generate_matching_game_data(
    user_prompt: str | None = None,
    lang: str = "auto",
    image_mode: str | None = None,
) -> dict[str, Any]:
    """
    ساخت بازی:
    1) تصمیم‌گیری: آیا سرچ لازم است؟
    2) فقط در صورت نیاز/شک -> Parallel MCP (رایگان)
    3) تولید title + 4 جفت
    4) عکس پس‌زمینه: سرچ استفاده شده -> عکس واقعی (Pexels)، وگرنه عکس AI

    lang: "auto" | "en" | "fa" — زبان عنوان و کارت‌های بازی.

    اگر user_prompt اصلاً داده نشود (مثلاً در server.py) از پرامپت پیش‌فرض
    استفاده می‌شود؛ ولی رشته خالی خطا می‌دهد.
    """
    if user_prompt is None:
        prompt = DEFAULT_PROMPT
    else:
        prompt = user_prompt.strip()
        if not prompt:
            raise ValueError("User prompt is empty.")

    clear_recent_logs()
    _search_logger.info("generate_matching_game_data start")

    decision: dict[str, Any] = {
        "need_search": False,
        "queries": [],
        "reason": "Search skipped.",
    }
    search_results: list[dict[str, Any]] = []

    # فاز ۱: فقط وقتی مدل شک دارد درخواست سرچ می‌دهد
    try:
        decision = _decide_search(prompt)
        _search_logger.info(
            "search decision need_search=%s queries=%s reason=%s",
            decision.get("need_search"),
            decision.get("queries"),
            decision.get("reason"),
        )
    except AuthenticationError:
        # کلید اشتباه است؛ ادامه دادن فقط یک 401 دیگر می‌گیرد
        raise
    except Exception as exc:
        decision = {
            "need_search": False,
            "queries": [],
            "reason": "Search decision failed; continued with model knowledge.",
        }
        _search_logger.warning("search decision failed: %s", exc)

    # فاز ۲: سرچ فقط در صورت نیاز — Parallel MCP (رایگان، بدون کلید)
    if decision["need_search"]:
        if search_available():
            try:
                search_results = run_searches(decision["queries"])
                _search_logger.info("parallel search finished hits=%s", len(search_results))
            except Exception as exc:
                search_results = []
                decision["reason"] = (
                    (decision.get("reason") or "Search requested")
                    + f" | Parallel search failed: {exc}"
                )
                _search_logger.error("parallel search failed: %s", exc)
            if not search_results and "failed" not in (decision.get("reason") or ""):
                decision["reason"] = (
                    decision.get("reason") or "Search requested"
                ) + " | Search returned no results."
        else:
            decision["need_search"] = False
            decision["reason"] = (
                "Model wanted search, but Parallel search is disabled; "
                "continued with model knowledge."
            )
            _search_logger.warning("parallel search disabled; skipped")
    else:
        _search_logger.info("no search needed; using model knowledge only")

    # فاز ۳: تولید بازی
    data = _generate_game(prompt, search_results, lang)

    # فاز ۴: عکس پس‌زمینه (هیچ‌وقت نباید بازی را خراب کند)
    used_search = bool(search_results)
    data["background"] = None
    try:
        data["background"] = get_background(
            data.get("image_query", ""),
            data.get("image_prompt", ""),
            used_search=used_search,
            mode=image_mode,
        )
    except Exception as exc:
        _search_logger.warning("background image failed: %s", exc)

    data["search_meta"] = {
        "used": used_search,
        "requested": bool(decision.get("need_search") or search_results),
        "queries": decision.get("queries") or [],
        "reason": decision.get("reason") or "",
        "results": search_results,
        "provider": "parallel-mcp",
        "provider_ready": search_available(),
        "logs": get_recent_logs(),
    }
    _search_logger.info(
        "generate done used_search=%s title=%s background=%s",
        used_search,
        data.get("title"),
        (data["background"] or {}).get("source"),
    )
    return data


if __name__ == "__main__":
    print("Generating new matching game data...")
    game_data = generate_matching_game_data(
        "A fun matching game about Persian foods and their cities"
    )
    # data_uri خیلی طولانی است؛ برای چاپ کوتاه می‌شود
    if game_data.get("background"):
        game_data["background"]["data_uri"] = game_data["background"]["data_uri"][:60] + "..."
    print(json.dumps(game_data, indent=2, ensure_ascii=False))