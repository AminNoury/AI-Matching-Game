# ============================================
# File: app.py
# Description: Streamlit UI - Matching Game with "New Game" button
# Author: Amin Nouri
# ============================================

import streamlit as st
import random
import time
from ai_helper import generate_matching_game_data

# ---------- FUNCTION: INITIALIZE GAME ----------
def initialize_game():
    game_data = generate_matching_game_data()  
    st.session_state.game_title = game_data['title']

    all_cards = []
    pairs = game_data['pairs']

    for i, pair in enumerate(pairs):
        match_key = str(i)
        all_cards.append({
            "id": len(all_cards),
            "value": pair['left'],
            "type": "left",
            "match_key": match_key,
            "matched": False,
            "color": "white"
        })
        all_cards.append({
            "id": len(all_cards),
            "value": pair['right'],
            "type": "right",
            "match_key": match_key,
            "matched": False,
            "color": "white"
        })

    random.shuffle(all_cards)
    return all_cards

# ---------- BUTTON: NEW GAME ----------
if "cards" not in st.session_state:
    st.session_state.cards = initialize_game()
if st.button("🎲 New Game"):
    st.session_state.cards = initialize_game()
    st.session_state.first_click = None
    st.session_state.mistake_timer = None
    st.session_state.mistake_cards = []

# ---------- SESSION STATE DEFAULTS ----------
if "first_click" not in st.session_state:
    st.session_state.first_click = None
if "mistake_timer" not in st.session_state:
    st.session_state.mistake_timer = None
if "mistake_cards" not in st.session_state:
    st.session_state.mistake_cards = []

# ---------- DISPLAY GAME TITLE ----------
st.markdown(
    "<h4 style='margin-bottom:0;'>Academic Supervisor: Dr. Shermin Mousavei</h4>",
    unsafe_allow_html=True
)

st.markdown(
    "<h5 style='margin-top:0; color: gray;'>Developer: Amin Nouri</h5>",
    unsafe_allow_html=True
)

st.title(f"🧩 {st.session_state.get('game_title','Matching Game')}")

# ---------- CLICK HANDLER ----------
def click_card(card_id):
    current_time = time.time()

    if st.session_state.mistake_timer:
        if current_time - st.session_state.mistake_timer < 0.5:
            return
        else:
            for c in st.session_state.mistake_cards:
                c["color"] = "white"
            st.session_state.mistake_cards = []
            st.session_state.mistake_timer = None
            st.session_state.first_click = None

    card = next(c for c in st.session_state.cards if c["id"] == card_id)
    if card["matched"]:
        return

    if st.session_state.first_click is None:
        st.session_state.first_click = card
        card["color"] = "white"
    else:
        first_card = st.session_state.first_click
        second_card = card

        if first_card["match_key"] == second_card["match_key"] and first_card["id"] != second_card["id"]:
            first_card["color"] = "green"
            second_card["color"] = "green"
            first_card["matched"] = True
            second_card["matched"] = True
        else:
            first_card["color"] = "red"
            second_card["color"] = "red"
            st.session_state.mistake_cards = [first_card, second_card]
            st.session_state.mistake_timer = current_time

        st.session_state.first_click = None

# ---------- UI RENDER ----------
cols = st.columns(4)

if st.session_state.mistake_timer:
    if time.time() - st.session_state.mistake_timer >= 0.5:
        for c in st.session_state.mistake_cards:
            c["color"] = "white"
        st.session_state.mistake_timer = None
        st.session_state.mistake_cards = []

for i, card in enumerate(st.session_state.cards):
    col = cols[i % 4]
    if col.button(card["value"], key=str(card["id"]), use_container_width=True):
        click_card(card["id"])
    col.markdown(
        f"""
        <div style="
            background-color:{card['color']};
            height:50px;
            width:100%;
            margin-top:5px;
            border-radius:5px;
        "></div>
        """,
        unsafe_allow_html=True
    )
    
# ---------- CHECK WIN ----------
if all(c["matched"] for c in st.session_state.cards):
    st.balloons()
    st.success("🎉 Congratulations! You matched all pairs! 🎉")
