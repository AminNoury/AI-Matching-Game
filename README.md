# 🚀 Project Name

A brief description of your project.  
Explain what the project does in 2–3 clear sentences.

Example:
This project is a web-based application designed to manage employee attendance, overtime, and undertime calculations efficiently. It integrates business logic with automated time interval processing.

---

## 📌 Features

- ✅ Attendance tracking
- ✅ Overtime calculation
- ✅ Undertime calculation
- ✅ Calendar-based break handling
- ✅ Clean modular architecture

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