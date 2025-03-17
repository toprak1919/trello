#!/usr/bin/env python3
"""
trello.py

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
REMINDER_DELAY_HOURS = float(os.getenv("REMINDER_DELAY_HOURS", "24"))

# Debug prints
print(f"Using API Key: {TRELLO_API_KEY[:4]}...{TRELLO_API_KEY[-4:] if len(TRELLO_API_KEY) > 8 else ''}")
print(f"Using Token: {TRELLO_TOKEN[:4]}...{TRELLO_TOKEN[-4:] if len(TRELLO_TOKEN) > 8 else ''}")
print(f"Using Board ID: {TRELLO_BOARD_ID}")

# Polling interval in seconds
POLL_INTERVAL_MINUTES = float(os.getenv("POLL_INTERVAL_MINUTES", "1"))
POLL_INTERVAL = POLL_INTERVAL_MINUTES * 60

# Database files
CARDS_DUE_DB = 'cards_due.db'
TRELLO_CARDS_DB = 'trello_cards.db'

def init_db():
    """Initialize the SQLite database and create necessary tables."""
    # Initialize cards_due.db
    conn = sqlite3.connect(CARDS_DUE_DB)
    c = conn.cursor()
    
    # Table for storing each card's due date
    c.execute('''
        CREATE TABLE IF NOT EXISTS card_due (
            card_id TEXT PRIMARY KEY,
            due_date TEXT
        )
    ''')
    
    # Table for storing reminders history
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT,
            card_name TEXT,
            old_due TEXT,
            new_due TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Initialize trello_cards.db
    conn = sqlite3.connect(TRELLO_CARDS_DB)
    c = conn.cursor()
    
    # Table for storing card details
    c.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            card_id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            url TEXT,
            list_name TEXT,
            due_date TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_stored_due_date(card_id):
    """Retrieve the stored due date for a specific card from the database."""
    conn = sqlite3.connect(CARDS_DUE_DB)
    c = conn.cursor()
    c.execute("SELECT due_date FROM card_due WHERE card_id = ?", (card_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def update_stored_due_date(card_id, new_due):
    """Update or insert the stored due date for a specific card in the database."""
    conn = sqlite3.connect(CARDS_DUE_DB)
    c = conn.cursor()
    # Insert or update the card's due date
    c.execute('''
        INSERT INTO card_due (card_id, due_date)
        VALUES (?, ?)
        ON CONFLICT(card_id) DO UPDATE SET due_date=excluded.due_date
    ''', (card_id, new_due))
    conn.commit()
    conn.close()

def add_reminder(card_id, card_name, old_due, new_due):
    """Add a reminder to the reminders table."""
    conn = sqlite3.connect(CARDS_DUE_DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO reminders (card_id, card_name, old_due, new_due)
        VALUES (?, ?, ?, ?)
    ''', (card_id, card_name, old_due, new_due))
    conn.commit()
    conn.close()

def update_card_details(card):
    """Update or insert card details in the trello_cards.db database."""
    conn = sqlite3.connect(TRELLO_CARDS_DB)
    c = conn.cursor()
    
    card_id = card.get("id")
    name = card.get("name")
    description = card.get("desc", "")
    url = card.get("url", f"https://trello.com/c/{card_id}")
    due_date = card.get("due")
    
    # Try to get the list name - may require additional API call
    list_id = card.get("idList")
    list_name = "Unknown"
    
    if list_id:
        list_url = f"https://api.trello.com/1/lists/{list_id}"
        params = {
            "key": TRELLO_API_KEY,
            "token": TRELLO_TOKEN
        }
        
        try:
            response = requests.get(list_url, params=params)
            if response.ok:
                list_data = response.json()
                list_name = list_data.get("name", "Unknown")
        except Exception as e:
            print(f"Error fetching list name: {str(e)}")
    
    c.execute('''
        INSERT INTO cards (card_id, name, description, url, list_name, due_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(card_id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            url = excluded.url,
            list_name = excluded.list_name,
            due_date = excluded.due_date,
            last_updated = CURRENT_TIMESTAMP
    ''', (card_id, name, description, url, list_name, due_date))
    
    conn.commit()
    conn.close()

def get_all_cards(board_id):
    """Fetch all cards on a given Trello board from the Trello API."""
    url = f"https://api.trello.com/1/boards/{board_id}/cards"
    params = {
        "key": TRELLO_API_KEY,
        "token": TRELLO_TOKEN,
        # Request additional fields for web UI
        "fields": "id,due,name,desc,url,idList",
    }
    
    print(f"Request URL: {url}")
    print(f"Request params: {params}")
    
    try:
        response = requests.get(url, params=params)
        print(f"Response status code: {response.status_code}")
        
        if response.ok:
            return response.json()
        else:
            print(f"Error fetching cards: {response.text}")
            return []
    except Exception as e:
        print(f"Exception fetching cards: {str(e)}")
        return []

def send_reminder(card_id, card_name, old_due, new_due):
    """Send a reminder and log it to the database."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Log reminder to the console
    reminder_message = (
        f"[{timestamp}] "
        f"Reminder: Card '{card_name}' (ID: {card_id}) "
        f"due date changed from {old_due or 'None'} to {new_due or 'None'}"
    )
    print(reminder_message)
    
    # Add reminder to the database
    add_reminder(card_id, card_name, old_due, new_due)
    
    # Here you could add additional functionality:
    # - Send an email notification
    # - Send a desktop notification
    # - Send a message to Slack or Discord
    # - etc.

def main():
    """Main function to poll the Trello board and check for due date changes."""
    init_db()
    print(f"Starting Trello board due date monitor (polling every {POLL_INTERVAL_MINUTES} minutes)...")
    
    while True:
        cards = get_all_cards(TRELLO_BOARD_ID)
        print(f"Found {len(cards)} cards on the board")
        
        for card in cards:
            card_id = card.get("id")
            card_name = card.get("name")
            current_due = card.get("due")  # May be None if no due date is set
            stored_due = get_stored_due_date(card_id)
            
            # Update card details in trello_cards.db
            update_card_details(card)
            
            # If there is a change in due date (including setting a new one or removing it)
            if current_due != stored_due:
                print(f"Due date change detected for '{card_name}': {stored_due} -> {current_due}")
                update_stored_due_date(card_id, current_due)
                send_reminder(card_id, card_name, stored_due, current_due)
        
        print(f"Sleeping for {POLL_INTERVAL_MINUTES} minutes before next check...")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
