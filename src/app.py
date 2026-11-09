# ============================================
# File: app.py
# Description: Streamlit UI - Prompt page + Matching Game
# Author: Amin Nouri
# ============================================

import streamlit as st
import random
import time
from ai_helper import generate_matching_game_data
from i18n import DEFAULT_LANG, LANG_LABELS, t
from theme import apply_language_theme

# رنگ‌ها: خاکستری = عادی، آبی = انتخاب‌شده، سبز = مچ، قرمز = اشتباه
COLOR_IDLE = "#F5F5F5"
COLOR_SELECTED = "#3B82F6"
COLOR_MATCHED = "#22C55E"
COLOR_MISTAKE = "#EF4444"

st.set_page_config(page_title="AI Matching Game", page_icon="🧩", layout="centered")

# ---------- SESSION STATE ----------
if "lang" not in st.session_state:
    st.session_state.lang = DEFAULT_LANG
if "page" not in st.session_state:
    st.session_state.page = "prompt"
if "user_prompt" not in st.session_state:
    st.session_state.user_prompt = ""
if "cards" not in st.session_state:
    st.session_state.cards = None
if "game_title" not in st.session_state:
    st.session_state.game_title = None
if "first_click" not in st.session_state:
    st.session_state.first_click = None
if "mistake_timer" not in st.session_state:
    st.session_state.mistake_timer = None
if "mistake_cards" not in st.session_state:
    st.session_state.mistake_cards = []
if "search_meta" not in st.session_state:
    st.session_state.search_meta = None


def tr(key: str, **kwargs) -> str:
    return t(key, st.session_state.lang, **kwargs)


def render_language_switch():
    """سوییچ زبان؛ برای فارسی فونت و راست‌به‌چپ از theme.py اعمال می‌شود."""
    st.radio(
        "🌐",
        options=list(LANG_LABELS),
        format_func=LANG_LABELS.get,
        horizontal=True,
        key="lang",
    )
    apply_language_theme(st.session_state.lang)


def reset_game_state():
    st.session_state.first_click = None
    st.session_state.mistake_timer = None
    st.session_state.mistake_cards = []


def initialize_game(user_prompt: str):
    game_data = generate_matching_game_data(user_prompt, lang=st.session_state.lang)
    st.session_state.game_title = game_data["title"]
    st.session_state.search_meta = game_data.get("search_meta")

    all_cards = []
    for i, pair in enumerate(game_data["pairs"]):
        match_key = str(i)
        all_cards.append(
            {
                "id": len(all_cards),
                "value": pair["left"],
                "type": "left",
                "match_key": match_key,
                "matched": False,
                "selected": False,
                "color": COLOR_IDLE,
            }
        )
        all_cards.append(
            {
                "id": len(all_cards),
                "value": pair["right"],
                "type": "right",
                "match_key": match_key,
                "matched": False,
                "selected": False,
                "color": COLOR_IDLE,
            }
        )

    random.shuffle(all_cards)
    return all_cards


def click_card(card_id):
    current_time = time.time()

    # پاک کردن حالت اشتباه بعد از تاخیر کوتاه
    if st.session_state.mistake_timer:
        if current_time - st.session_state.mistake_timer < 0.5:
            return
        for c in st.session_state.mistake_cards:
            if not c["matched"]:
                c["color"] = COLOR_IDLE
                c["selected"] = False
        st.session_state.mistake_cards = []
        st.session_state.mistake_timer = None
        st.session_state.first_click = None

    card = next(c for c in st.session_state.cards if c["id"] == card_id)

    # کارت مچ‌شده یا انتخاب‌شده قفل است
    if card["matched"] or card["selected"]:
        return

    if st.session_state.first_click is None:
        st.session_state.first_click = card
        card["selected"] = True
        card["color"] = COLOR_SELECTED
        return

    first_card = st.session_state.first_click
    second_card = card

    if first_card["id"] == second_card["id"]:
        return

    second_card["selected"] = True

    # جفت درست → هر دو سبز و قفل دائمی
    if (
        first_card["match_key"] == second_card["match_key"]
        and first_card["type"] != second_card["type"]
    ):
        first_card["color"] = COLOR_MATCHED
        second_card["color"] = COLOR_MATCHED
        first_card["matched"] = True
        second_card["matched"] = True
        first_card["selected"] = False
        second_card["selected"] = False
        st.session_state.first_click = None
        return

    # جفت اشتباه → قرمز، بعد ریست
    first_card["color"] = COLOR_MISTAKE
    second_card["color"] = COLOR_MISTAKE
    st.session_state.mistake_cards = [first_card, second_card]
    st.session_state.mistake_timer = current_time
    st.session_state.first_click = None


def render_header():
    st.markdown(
        "<h4 style='margin-bottom:0;'>Academic Supervisor: Dr. Shermin Mousavei</h4>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<h5 style='margin-top:0; color: gray;'>Developer: Amin Nouri</h5>",
        unsafe_allow_html=True,
    )


render_language_switch()

# ==========================
# PAGE: PROMPT
# ==========================
if st.session_state.page == "prompt":
    render_header()
    st.title(f"🧩 {tr('build_title')}")
    st.write(tr("build_intro"))
    st.caption(tr("search_note"))

    user_prompt = st.text_area(
        tr("prompt_label"),
        value=st.session_state.user_prompt,
        height=180,
        placeholder=tr("prompt_placeholder"),
    )

    col_a, col_b = st.columns([1, 1])
    with col_a:
        create_clicked = st.button(tr("create"), use_container_width=True, type="primary")
    with col_b:
        if st.button(tr("clear"), use_container_width=True):
            st.session_state.user_prompt = ""
            st.rerun()

    if create_clicked:
        if not user_prompt.strip():
            st.warning(tr("need_prompt"))
        else:
            st.session_state.user_prompt = user_prompt.strip()
            with st.spinner(tr("generating")):
                try:
                    st.session_state.cards = initialize_game(st.session_state.user_prompt)
                    reset_game_state()
                    st.session_state.page = "game"
                    st.rerun()
                except Exception as exc:
                    st.error(tr("failed", err=exc))

# ==========================
# PAGE: GAME
# ==========================
elif st.session_state.page == "game":
    render_header()

    top_left, top_right = st.columns([3, 1])
    with top_left:
        st.title(f"🧩 {st.session_state.game_title or tr('default_title')}")
    with top_right:
        if st.button(tr("edit_prompt"), use_container_width=True):
            st.session_state.page = "prompt"
            st.rerun()
        if st.button(tr("new_game"), use_container_width=True):
            # بازی جدید با همان پرامپت کاربر
            with st.spinner(tr("generating_new")):
                try:
                    st.session_state.cards = initialize_game(st.session_state.user_prompt)
                    reset_game_state()
                    st.rerun()
                except Exception as exc:
                    st.error(tr("failed", err=exc))

    with st.expander(tr("your_prompt")):
        st.write(st.session_state.user_prompt)

    meta = st.session_state.search_meta or {}
    with st.expander(tr("search_usage"), expanded=False):
        if meta.get("used"):
            st.info(tr("search_used"))
            if meta.get("reason"):
                st.write(meta["reason"])
            if meta.get("queries"):
                st.write(tr("queries"), ", ".join(meta["queries"]))
            for hit in meta.get("results") or []:
                title = hit.get("title") or "Source"
                url = hit.get("url") or ""
                if url:
                    st.markdown(f"- [{title}]({url})")
                else:
                    st.markdown(f"- {title}")
        else:
            st.success(tr("no_search"))
            if meta.get("reason"):
                st.caption(meta["reason"])
            if meta.get("provider"):
                st.caption(tr("provider", name=meta["provider"]))
            if meta.get("provider_ready") is False:
                st.caption(tr("search_disabled"))

        logs = meta.get("logs") or []
        st.markdown(f"**{tr('logs_title')}**")
        if logs:
            st.code("\n".join(logs), language="text")
        else:
            st.caption(tr("no_logs"))

    if st.session_state.mistake_timer:
        if time.time() - st.session_state.mistake_timer >= 0.5:
            for c in st.session_state.mistake_cards:
                if not c["matched"]:
                    c["color"] = COLOR_IDLE
                    c["selected"] = False
            st.session_state.mistake_timer = None
            st.session_state.mistake_cards = []

    cols = st.columns(4)
    for i, card in enumerate(st.session_state.cards or []):
        col = cols[i % 4]
        disabled = card["matched"] or card["selected"]

        if col.button(
            card["value"],
            key=str(card["id"]),
            use_container_width=True,
            disabled=disabled,
        ):
            click_card(card["id"])
            st.rerun()

        status = (
            tr("matched")
            if card["matched"]
            else (tr("selected") if card["selected"] else tr("tap"))
        )
        text_color = "#FFFFFF" if card["color"] != COLOR_IDLE else "#333333"
        col.markdown(
            f"""
            <div style="
                background-color:{card['color']};
                color:{text_color};
                min-height:42px;
                width:100%;
                margin-top:4px;
                margin-bottom:14px;
                border-radius:8px;
                display:flex;
                align-items:center;
                justify-content:center;
                font-size:13px;
                font-weight:600;
            ">{status}</div>
            """,
            unsafe_allow_html=True,
        )

    if st.session_state.cards and all(c["matched"] for c in st.session_state.cards):
        st.balloons()
        st.success(tr("win"))
