# 🚀 Project Description

Add LangChain LLM game engine, Streamlit UI, and database support

- Implemented `ai_helper.py`:
    * Generate matching game data using LLM (DeepSeek Chat)
    * Ensure random domain selection without repetition
    * Validate JSON output structure from LLM
- Implemented `app.py` Streamlit interface:
    * Initialize game board with shuffled card pairs
    * Handle card clicks, matches, and mistake feedback
    * Show game title, developer info, and celebration on win
- Implemented `database.py` SQLite backend:
    * Initialize, insert, clear, and fetch cards
    * Support FastAPI endpoints for game state management
- Overall:
    * Balanced AI game logic to ensure fair matching
    * Integrated LLM-generated content with frontend UI
    * Prepared backend for persistent storage and API access
---

# Features

✅ Generate matching game data using LLM (DeepSeek Chat)

✅ Random domain selection without repetition

✅ Validate JSON output structure from LLM

✅ Interactive Streamlit UI with card click handling

✅ Mistake feedback and match highlighting

✅ Persistent storage using SQLite + FastAPI endpoints

✅ Balanced AI matching logic for fair gameplay
---

## 🛠 Tech Stack

- Python 3.10+
- Git
- (Add framework here if needed: Odoo / Flask / Django / FastAPI)
- Virtual Environment

---

## 📂 Project Structure
project-root/
│
├── src/ # Source code
├── .env # Environment variables (not tracked)
├── requirements.txt # Python dependencies
├── .gitignore
└── README.md


---

## ⚙️ Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/AminNoury/AI-Matching-Game
cd AI-Matching-Game

2️⃣ Create Virtual Environment

python -m venv venv

Windows

venv\Scripts\activate

Mac/Linux

source venv/bin/activate

3️⃣ Install Dependencies

pip install -r requirements.txt

4️⃣ Configure Environment Variables

touch .env

DEBUG=True
DATABASE_URL=your_database_url
SECRET_KEY=your_secret_key

5 Create an API Key

Go to: https://openrouter.ai

Sign in or create an account

Navigate to API Keys

Generate a new key

Add the following:

OPENAI_API_KEY=your_openrouter_api_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1

▶️ Running the Project

uvicorn src.server:app --reload --port 8000