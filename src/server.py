from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import random
from .ai_helper import generate_matching_game_data

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

game_data = None
cards = []


def initialize_game(
    user_prompt: str,
    lang: str = "auto",
    image_mode: str | None = None,
):
    global cards, game_data
    game_data = generate_matching_game_data(
        user_prompt,
        lang=lang,
        image_mode=image_mode,
    )
    cards = []
    for i, pair in enumerate(game_data["pairs"]):
        match_key = str(i)
        cards.append(
            {
                "id": len(cards),
                "value": pair["left"],
                "type": "left",
                "match_key": match_key,
                "matched": False,
                "selected": False,
            }
        )
        cards.append(
            {
                "id": len(cards),
                "value": pair["right"],
                "type": "right",
                "match_key": match_key,
                "matched": False,
                "selected": False,
            }
        )
    random.shuffle(cards)


class Click(BaseModel):
    card_id: int


class NewGame(BaseModel):
    prompt: str = Field(..., min_length=1)
    lang: str = "auto"  # auto | en | fa
    image_mode: str | None = None  # auto | web | ai | off


@app.post("/new-game")
def new_game(body: NewGame):
    try:
        initialize_game(body.prompt.strip(), body.lang, body.image_mode)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "title": game_data["title"],
        "background": game_data.get("background"),
        "cards": cards,
    }


@app.get("/cards")
def get_cards():
    if game_data is None:
        raise HTTPException(
            status_code=400,
            detail="No game yet. POST /new-game with a prompt first.",
        )
    return {
        "title": game_data["title"],
        "background": game_data.get("background"),
        "cards": cards,
    }


@app.post("/click")
def click_card(click: Click):
    if not cards:
        raise HTTPException(
            status_code=400,
            detail="No game yet. POST /new-game with a prompt first.",
        )

    clicked_card = next(c for c in cards if c["id"] == click.card_id)

    if clicked_card["matched"] or clicked_card.get("selected"):
        return {"cards": cards}

    first_click = next((c for c in cards if c.get("selected")), None)
    clicked_card["selected"] = True

    if first_click and first_click["id"] != clicked_card["id"]:
        if (
            first_click["match_key"] == clicked_card["match_key"]
            and first_click["type"] != clicked_card["type"]
        ):
            first_click["matched"] = True
            clicked_card["matched"] = True

        first_click["selected"] = False
        clicked_card["selected"] = False

    return {"cards": cards}