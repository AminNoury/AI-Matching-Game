# ============================================
# File: theme.py
# Description: Persian font (Vazirmatn, OFL) + full right-to-left layout
# Author: Amin Nouri
# ============================================

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# فونت داخل پروژه است (نیازی به اینترنت یا گوگل‌فونت نیست)
FONT_PATH = Path(__file__).resolve().parent / "assets" / "Vazirmatn-subset.woff2"
FONT_STACK = "'Vazirmatn', 'Tahoma', 'Segoe UI', sans-serif"

# آیکن‌های خود Streamlit با فونت مخصوص خودشان کشیده می‌شوند؛ دستشان نمی‌زنیم
# :where() خصوصیت (specificity) این شرط را صفر می‌کند تا قانون کد/لاگ بتواند فونت مونو را پس بگیرد
_NOT_ICON = ':where(:not([data-testid="stIconMaterial"]):not(.material-icons):not([class*="material-symbols"]))'


@st.cache_resource
def _font_face_css() -> str:
    try:
        data = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
    except OSError:
        return ""  # بدون فایل فونت، با Tahoma/Segoe UI ادامه می‌دهد
    return (
        "@font-face{font-family:'Vazirmatn';"
        f"src:url(data:font/woff2;base64,{data}) format('woff2');"
        "font-weight:100 900;font-style:normal;font-display:swap;}"
    )


def _rtl_css() -> str:
    return f"""
    html, body, .stApp,
    [data-testid="stAppViewContainer"], [data-testid="stMain"],
    [data-testid="stSidebar"], [data-testid="stHeader"] {{
        direction: rtl;
    }}

    /* فونت: همه چیز به جز آیکن‌ها و کد */
    .stApp *{_NOT_ICON} {{
        font-family: {FONT_STACK} !important;
        letter-spacing: 0 !important;  /* فاصله حروف اتصال فارسی را خراب می‌کند */
    }}
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] li {{
        line-height: 1.9;
    }}
    .stApp h1, .stApp h2, .stApp h3 {{ font-weight: 800; }}

    /* Streamlit روی کانتینر متن و عنوان text-align:left گذاشته؛ start یعنی راست در RTL */
    .stApp [data-testid="stElementContainer"],
    .stApp [data-testid="stMarkdown"],
    .stApp [data-testid="stMarkdownContainer"],
    .stApp [data-testid="stHeading"],
    .stApp [data-testid="stHeadingWithActionElements"],
    .stApp [data-testid="stAlert"],
    .stApp [data-testid="stCaptionContainer"] {{
        text-align: start !important;
    }}

    /* متن مخلوط فارسی/انگلیسی: جهت هر کارت یا کادر از اولین حرفش تعیین شود */
    .stApp button, .stApp textarea {{ unicode-bidi: plaintext; }}

    /* بخش‌های فنی (لاگ و کد) چپ‌به‌راست و با فونت مونو بمانند */
    .stApp pre, .stApp code, .stApp [data-testid="stCode"],
    .stApp [data-testid="stCode"] * {{
        direction: ltr !important;
        text-align: left !important;
        font-family: 'Source Code Pro', ui-monospace, Menlo, Consolas, monospace !important;
    }}
    """


def apply_language_theme(lang: str) -> None:
    """برای فارسی: فونت Vazirmatn و جهت راست‌به‌چپ؛ برای انگلیسی هیچ تغییری."""
    if lang != "fa":
        return
    st.markdown(f"<style>{_font_face_css()}{_rtl_css()}</style>", unsafe_allow_html=True)
