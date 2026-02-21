from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random
from .ai_helper import generate_matching_game_data

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ---------- GAME DATA ----------
game_data = generate_matching_game_data()  

cards = []
def initialize_game():
    global cards, game_data
    cards = []
    for pair in game_data["pairs"]:
        # left card
        cards.append({
            "id": len(cards),
            "value": pair["left"],
            "type": "left",
            "match_key": pair["left"],  
            "matched": False,
            "selected": False
        })
        # right card
        cards.append({
            "id": len(cards),
            "value": pair["right"],
            "type": "right",
            "match_key": pair["left"],  
            "matched": False,
            "selected": False
        })
    random.shuffle(cards)

initialize_game()

# ---------- MODELS ----------
class Click(BaseModel):
    card_id: int

# ---------- ENDPOINTS ----------
@app.get("/cards")
def get_cards():
    return {"title": game_data["title"], "cards": cards}

@app.post("/click")
def click_card(click: Click):
    card_id = click.card_id
    clicked_card = next(c for c in cards if c["id"] == card_id)


    if clicked_card["matched"]:
        return {"cards": cards}


    first_click = next((c for c in cards if c.get("selected")), None)
    clicked_card["selected"] = True

    if first_click and first_click["id"] != clicked_card["id"]:
    
        if first_click["match_key"] == clicked_card["match_key"] and first_click["type"] != clicked_card["type"]:
          
            first_click["matched"] = True
            clicked_card["matched"] = True

        first_click["selected"] = False
        clicked_card["selected"] = False

    return {"cards": cards}
