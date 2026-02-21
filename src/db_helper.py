# ============================================
# File: database.py
# Description: SQLite database handler
# Author: Amin Nouri
# ============================================

# src/db_helper.py
import sqlite3

DB_FILE = "game.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_name TEXT,
            title TEXT
        )
        """)
        conn.commit()

def clear_cards():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM cards")
        conn.commit()

def insert_card(animal_name, title):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO cards (animal_name, title) VALUES (?, ?)", (animal_name, title))
        conn.commit()

def get_all_cards():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM cards")
        return c.fetchall()
