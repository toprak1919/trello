#!/usr/bin/env python3
"""
trello_api_all_cards.py

A script that polls a Trello board for changes in the due dates of all cards using the Trello API.
When a card's due date changes, it stores the new due date in a SQLite database and sends a reminder.

Usage:
  Set the following environment variables in a .env file:
    TRELLO_API_KEY    - Your Trello API key.
    TRELLO_TOKEN      - Your Trello API token.
    TRELLO_BOARD_ID   - The ID of the Trello board to monitor.
  Optionally adjust POLL_INTERVAL (in seconds) as needed.
  
  Run the script:
    python trello.py
"""

import os
import sqlite3
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration: Get Trello API credentials and board id from environment variables
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_BOARD_ID = os.getenv("TRELLO_BOARD_ID")

# Debug prints
print(f"Using API Key: {TRELLO_API_KEY[:4]}...{TRELLO_API_KEY[-4:] if len(TRELLO_API_KEY) > 8 else ''}")
print(f"Using Token: {TRELLO_TOKEN[:4]}...{TRELLO_TOKEN[-4:] if len(TRELLO_TOKEN) > 8 else ''}")
print(f"Using Board ID: {TRELLO_BOARD_ID}")

# Polling interval in seconds
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
# Database file to store the cards' due dates
DATABASE = 'cards_due.db'

def init_db():
    """Initialize the SQLite database and create a table for storing each card's due date."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS card_due (
            card_id TEXT PRIMARY KEY,
            due_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_stored_due_date(card_id):
    """Retrieve the stored due date for a specific card from the database."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT due_date FROM card_due WHERE card_id = ?", (card_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def update_stored_due_date(card_id, new_due):
    """Update or insert the stored due date for a specific card in the database."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Insert or update the card's due date
    c.execute('''
        INSERT INTO card_due (card_id, due_date)
        VALUES (?, ?)
        ON CONFLICT(card_id) DO UPDATE SET due_date=excluded.due_date
    ''', (card_id, new_due))
    conn.commit()
    conn.close()

def get_all_cards(board_id):
    """Fetch all cards on a given Trello board from the Trello API."""
    url = f"https://api.trello.com/1/boards/{board_id}/cards"
    params = {
        "key": TRELLO_API_KEY,
        "token": TRELLO_TOKEN,
        # Request only the fields we need to reduce payload size
        "fields": "id,due,name"
    }
    print(f"Request URL: {url}")
    print(f"Request params: {params}")
    response = requests.get(url, params=params)
    print(f"Response status code: {response.status_code}")
    if response.ok:
        return response.json()
    else:
        print(f"Error fetching cards: {response.text}")
        return []

def send_reminder(card_id, card_name, new_due):
    """Send a reminder to the user (currently prints a message)."""
    reminder_message = (
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"Reminder: Card '{card_name}' (ID: {card_id}) has a new due date: {new_due}"
    )
    print(reminder_message)
    # Replace the print with an email/SMS integration if desired.

def main():
    init_db()
    print("Starting Trello board due date monitor...")
    while True:
        cards = get_all_cards(TRELLO_BOARD_ID)
        for card in cards:
            card_id = card.get("id")
            card_name = card.get("name")
            current_due = card.get("due")  # May be None if no due date is set
            stored_due = get_stored_due_date(card_id)
            # If there is a change in due date (including setting a new one or removing it)
            if current_due != stored_due:
                update_stored_due_date(card_id, current_due)
                send_reminder(card_id, card_name, current_due)
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
