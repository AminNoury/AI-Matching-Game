
# ============================================
# File: ai_helper.py
# Description: DeepSeek Matching Game Data Generator
# Author: Amin Nouri
# ============================================

import os
import random
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# -------------------------
# API Setup
# -------------------------
os.environ["OPENAI_API_KEY"] = "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"
os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"

llm = ChatOpenAI(model="deepseek/deepseek-chat", temperature=0.7)

# -------------------------
# Domains & Used Tracker
# -------------------------
DOMAINS = [
    "sports", "movies", "food", "tools", 
    "technology", "daily life", "music", "literature",
    "animals", "geography", "famous people", "history"
]

USED_DOMAINS = set()

# -------------------------
# Prompt templates
# -------------------------
HUMAN_PROMPT_TEMPLATE = """
Return the result strictly in the following JSON format:

{{
  "title": "Game title here",
  "pairs": [
    {{ "left": "Item A1", "right": "Item B1" }},
    {{ "left": "Item A2", "right": "Item B2" }},
    {{ "left": "Item A3", "right": "Item B3" }},
    {{ "left": "Item A4", "right": "Item B4" }}
  ]
}}
"""

# -------------------------
# Main function
# -------------------------
def generate_matching_game_data() -> dict:
    """
    Generate a new matching game dataset:
    - Randomly selects a domain not used before
    - Requests LLM to generate title + 4 pairs
    - Returns a dict ready for Streamlit
    """
    global USED_DOMAINS


    available_domains = [d for d in DOMAINS if d not in USED_DOMAINS]
    if not available_domains:
        USED_DOMAINS.clear()  
        available_domains = DOMAINS.copy()

    domain = random.choice(available_domains)
    USED_DOMAINS.add(domain)

    system_prompt = f"""
You are a creative game content generator.

Focus ONLY on the domain: {domain}.

Your task:
- Generate 4 complementary pairs of concepts
- Each pair MUST be strongly related, matchable, commonly known
- Work well in a memory matching game

Rules:
- Generate a creative title (7 to 12 words)
- Use simple words
- No explanations
- Output ONLY valid JSON
- Ensure the JSON is valid and parsable
- Do not include any extra text or markdown
"""

    messages = [
        SystemMessage(content=system_prompt.strip()),
        HumanMessage(content=HUMAN_PROMPT_TEMPLATE.strip())
    ]


    response = llm.invoke(messages)
    content = response.content.strip()

    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid JSON:\n" + content)

    if "title" not in data or "pairs" not in data or len(data["pairs"]) != 4:
        raise ValueError("LLM returned invalid structure:\n" + json.dumps(data, indent=2, ensure_ascii=False))

    return data

# -------------------------
# Debug / manual test
# -------------------------
if __name__ == "__main__":
    print("Generating new matching game data...")
    game_data = generate_matching_game_data()
    print(json.dumps(game_data, indent=2, ensure_ascii=False))
