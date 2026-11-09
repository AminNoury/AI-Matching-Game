# ============================================
# File: i18n.py
# Description: UI texts for English / Persian (fa)
# Author: Amin Nouri
# ============================================

DEFAULT_LANG = "en"

LANG_LABELS = {"en": "English", "fa": "فارسی"}

TEXTS = {
    "en": {
        "language": "Language",
        "build_title": "Build Your Matching Game",
        "build_intro": (
            "Describe the matching game you want. Theme, topic, language, and style — "
            "the AI will generate 4 matchable pairs from your prompt."
        ),
        "search_note": (
            "Web search is optional (Parallel MCP, free): the model searches only when it "
            "is unsure or needs specific facts. Common knowledge games skip the web."
        ),
        "prompt_label": "Your game idea",
        "prompt_placeholder": (
            "Example: A matching game about countries and their capitals. "
            "Keep the words short and suitable for students."
        ),
        "create": "🚀 Create Game",
        "clear": "🧹 Clear",
        "need_prompt": "Please write a prompt first.",
        "generating": "Generating your matching game...",
        "generating_new": "Generating a new board...",
        "failed": "Could not generate the game: {err}",
        "edit_prompt": "✏️ Edit Prompt",
        "new_game": "🎲 New Game",
        "your_prompt": "Your prompt",
        "search_usage": "Search usage",
        "search_used": "Web search was used for uncertain facts.",
        "queries": "Queries:",
        "no_search": "No web search — generated from model knowledge.",
        "provider": "Provider: {name}",
        "search_disabled": "Parallel search is disabled via PARALLEL_SEARCH_DISABLED.",
        "logs_title": "Parallel MCP logs",
        "no_logs": "No MCP logs for this run.",
        "matched": "Matched",
        "selected": "Selected",
        "tap": "Tap to pick",
        "win": "🎉 Congratulations! You matched all pairs! 🎉",
        "default_title": "Matching Game",
    },
    "fa": {
        "language": "زبان",
        "build_title": "بازی تطبیق خودت را بساز",
        "build_intro": (
            "بازی‌ای را که می‌خواهی توصیف کن: موضوع، زبان و سبک. "
            "هوش مصنوعی از روی توصیف تو ۴ جفت قابل‌تطبیق می‌سازد."
        ),
        "search_note": (
            "جستجوی وب اختیاری است (Parallel MCP، رایگان): مدل فقط وقتی مطمئن نیست "
            "یا به واقعیت‌های دقیق نیاز دارد جستجو می‌کند. بازی‌های دانستنی‌های "
            "عمومی بدون جستجو ساخته می‌شوند."
        ),
        "prompt_label": "ایده بازی تو",
        "prompt_placeholder": (
            "مثال: یک بازی تطبیق درباره شهرهای ایران و غذاهای معروفشان. "
            "کلمه‌ها کوتاه و مناسب دانش‌آموزان باشند."
        ),
        "create": "🚀 ساخت بازی",
        "clear": "🧹 پاک کردن",
        "need_prompt": "اول یک توصیف بنویس.",
        "generating": "در حال ساخت بازی تو...",
        "generating_new": "در حال ساخت یک صفحه جدید...",
        "failed": "ساخت بازی انجام نشد: {err}",
        "edit_prompt": "✏️ ویرایش توصیف",
        "new_game": "🎲 بازی جدید",
        "your_prompt": "توصیف تو",
        "search_usage": "استفاده از جستجو",
        "search_used": "برای واقعیت‌های نامطمئن از جستجوی وب استفاده شد.",
        "queries": "عبارت‌های جستجو:",
        "no_search": "بدون جستجوی وب؛ بازی از دانش مدل ساخته شد.",
        "provider": "ارائه‌دهنده: {name}",
        "search_disabled": "جستجوی Parallel با PARALLEL_SEARCH_DISABLED غیرفعال شده است.",
        "logs_title": "لاگ‌های Parallel MCP",
        "no_logs": "برای این اجرا لاگی ثبت نشده است.",
        "matched": "تطبیق داده شد",
        "selected": "انتخاب شد",
        "tap": "برای انتخاب بزن",
        "win": "🎉 تبریک! همه جفت‌ها را پیدا کردی! 🎉",
        "default_title": "بازی تطبیق",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """متن کلید را به زبان خواسته‌شده برمی‌گرداند؛ اگر نبود به انگلیسی برمی‌گردد."""
    table = TEXTS.get(lang) or TEXTS[DEFAULT_LANG]
    text = table.get(key) or TEXTS[DEFAULT_LANG].get(key) or key
    return text.format(**kwargs) if kwargs else text
