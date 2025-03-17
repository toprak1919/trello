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
import logging
from datetime import datetime
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('timestamp_debug.log'),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger('trello_monitor')

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
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(CARDS_DUE_DB)
    c = conn.cursor()
    
    # Create table for card due dates
    c.execute('''
        CREATE TABLE IF NOT EXISTS card_due (
            card_id TEXT PRIMARY KEY,
            name TEXT,
            due_date TEXT,
            due_date_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create table for due date change reminders
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
    
    # Create table for card comments
    c.execute('''
        CREATE TABLE IF NOT EXISTS card_comments (
            comment_id TEXT PRIMARY KEY,
            card_id TEXT,
            comment_text TEXT,
            created_at TIMESTAMP,
            suppressed_notification INTEGER DEFAULT 0
        )
    ''')
    
    # Check if name column exists in card_due table, add it if it doesn't
    try:
        c.execute("SELECT name FROM card_due LIMIT 1")
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        logger.info("Adding 'name' column to card_due table")
        c.execute("ALTER TABLE card_due ADD COLUMN name TEXT")
    
    # Check if suppressed_notification column exists in card_comments table, add it if it doesn't
    try:
        c.execute("SELECT suppressed_notification FROM card_comments LIMIT 1")
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        logger.info("Adding 'suppressed_notification' column to card_comments table")
        c.execute("ALTER TABLE card_comments ADD COLUMN suppressed_notification INTEGER DEFAULT 0")
    
    conn.commit()
    conn.close()
    
    logger.info("Database initialized successfully")

def get_stored_due_date(card_id):
    """Retrieve the stored due date for a specific card from the database."""
    conn = sqlite3.connect(CARDS_DUE_DB)
    c = conn.cursor()
    c.execute("SELECT due_date, due_date_updated_at FROM card_due WHERE card_id = ?", (card_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"due_date": row[0], "updated_at": row[1]}
    return {"due_date": None, "updated_at": None}

def get_due_date_change_time_from_trello(card_id):
    """
    Get the actual timestamp when the due date was last changed from Trello API.
    Returns ISO timestamp string or None if no due date change found.
    """
    # Trello API credentials
    api_key = os.getenv("TRELLO_API_KEY")
    api_token = os.getenv("TRELLO_TOKEN")  # Make sure this matches your env var name
    
    # Log the credentials being used (without revealing full values)
    logger.debug(f"Using API key starting with: {api_key[:4]}... and token: {api_token[:4]}..." if api_key and api_token else "Missing API credentials")
    
    if not api_key or not api_token:
        logger.error("Missing Trello API credentials. Check your .env file.")
        return None
    
    # Build API URL to get card actions with updateCard filter for due date changes
    api_url = f"https://api.trello.com/1/cards/{card_id}/actions"
    params = {
        "key": api_key,
        "token": api_token,
        "filter": "updateCard",
        "limit": 100  # Get enough actions to find due date changes
    }
    
    try:
        logger.debug(f"Making API request to {api_url} with filter=updateCard")
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        actions = response.json()
        
        # Find the most recent due date change action
        for action in actions:
            # Check if this action involved changing the due date
            if "data" in action and "card" in action["data"]:
                if "due" in action["data"]["card"]:
                    # Found a due date change, return its timestamp
                    logger.debug(f"Found due date change action: {action['date']} for card {card_id}")
                    return action["date"]  # This is the ISO timestamp of the action
        
        logger.debug(f"No due date change actions found for card {card_id}")
        return None
    except Exception as e:
        logger.error(f"Error fetching due date change time from Trello for card {card_id}: {str(e)}")
        return None

def update_stored_due_date(card_id, card_name, new_due_date, old_due_date=None):
    """Update the stored due date for a card, creating a new record if needed."""
    
    # Get the actual timestamp from Trello when the due date was changed
    trello_change_time = get_due_date_change_time_from_trello(card_id)
    
    # If we couldn't get the timestamp from Trello, use current time as fallback
    timestamp = trello_change_time if trello_change_time else datetime.now().isoformat()
    
    logger.debug(f"Updating stored due date for card {card_id} with timestamp {timestamp}")
    
    conn = sqlite3.connect(CARDS_DUE_DB)
    c = conn.cursor()
    
    # Check if the card already exists in the database
    c.execute('SELECT * FROM card_due WHERE card_id = ?', (card_id,))
    result = c.fetchone()
    
    if result:
        c.execute('''
            UPDATE card_due 
            SET due_date = ?, due_date_updated_at = ?, name = ?
            WHERE card_id = ?
        ''', (new_due_date, timestamp, card_name, card_id))
    else:
        c.execute('''
            INSERT INTO card_due (card_id, name, due_date, due_date_updated_at)
            VALUES (?, ?, ?, ?)
        ''', (card_id, card_name, new_due_date, timestamp))
    
    conn.commit()
    conn.close()
    
    # If this is a due date change (not a new card), send reminder
    if old_due_date is not None and old_due_date != new_due_date:
        send_reminder(card_id, card_name, old_due_date, new_due_date)

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

def get_last_comment_timestamp(card_id):
    """Get the timestamp of the most recent comment on a card."""
    conn = sqlite3.connect(CARDS_DUE_DB)
    c = conn.cursor()
    c.execute('''
        SELECT created_at FROM card_comments 
        WHERE card_id = ? 
        ORDER BY created_at DESC 
        LIMIT 1
    ''', (card_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return result[0]
    return None

def store_card_comment(comment_id, card_id, comment_text, created_at):
    """Store a card comment in the database."""
    conn = sqlite3.connect(CARDS_DUE_DB)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO card_comments 
        (comment_id, card_id, comment_text, created_at)
        VALUES (?, ?, ?, ?)
    ''', (comment_id, card_id, comment_text, created_at))
    conn.commit()
    conn.close()

def get_card_comments(card_id):
    """
    Get all comments for a specific card from Trello API.
    Returns the timestamp of the latest comment and stores all comments in the DB.
    """
    # Trello API credentials
    api_key = os.getenv("TRELLO_API_KEY")
    api_token = os.getenv("TRELLO_TOKEN")  # Make sure this matches your env var name
    
    # Log the credentials being used (without revealing full values)
    logger.debug(f"Using API key starting with: {api_key[:4]}... and token: {api_token[:4]}..." if api_key and api_token else "Missing API credentials")
    
    if not api_key or not api_token:
        logger.error("Missing Trello API credentials. Check your .env file.")
        return None
    
    # Build API URL to get card actions with commentCard filter
    api_url = f"https://api.trello.com/1/cards/{card_id}/actions"
    params = {
        "key": api_key,
        "token": api_token,  # This was missing or named incorrectly
        "filter": "commentCard",
        "limit": 100  # Adjust if you need more comments
    }
    
    try:
        logger.debug(f"Making API request to {api_url} with params: {params}")
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        
        # Get the card's due date change time for comparison
        due_date_info = get_stored_due_date(card_id)
        due_date_changed_at = due_date_info.get("updated_at")
        
        # Parse due date change time for comparison
        if due_date_changed_at:
            try:
                if 'Z' in due_date_changed_at:
                    due_date_dt = datetime.fromisoformat(due_date_changed_at.replace('Z', '+00:00'))
                else:
                    due_date_dt = datetime.fromisoformat(due_date_changed_at)
                # Make it naive to ensure consistent comparison
                if due_date_dt.tzinfo is not None:
                    due_date_dt = due_date_dt.replace(tzinfo=None)
            except Exception as e:
                logger.error(f"Error parsing due date change time for card {card_id}: {str(e)}")
                due_date_dt = None
        else:
            due_date_dt = None
        
        # Process comments
        comments = response.json()
        
        if not comments:
            logger.debug(f"No comments found for card {card_id}")
            return None
        
        # Connect to database
        conn = sqlite3.connect(CARDS_DUE_DB)
        c = conn.cursor()
        
        # Store all comments
        latest_timestamp = None
        for comment in comments:
            comment_id = comment["id"]
            comment_text = comment["data"]["text"]
            created_at = comment["date"]
            
            # Check if this comment suppressed a notification
            suppressed_notification = False
            if due_date_dt:
                try:
                    # Parse comment date for comparison
                    if 'Z' in created_at:
                        comment_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        comment_dt = datetime.fromisoformat(created_at)
                    
                    # Make it naive for comparison
                    if comment_dt.tzinfo is not None:
                        comment_dt = comment_dt.replace(tzinfo=None)
                    
                    # Check if this comment was posted after due date change
                    suppressed_notification = comment_dt > due_date_dt
                    
                    logger.debug(f"Comment timestamp: {created_at}, Due date change: {due_date_changed_at}")
                    logger.debug(f"Comment suppressed notification: {suppressed_notification}")
                except Exception as e:
                    logger.error(f"Error comparing dates for comment {comment_id}: {str(e)}")
            
            # Store comment in database
            c.execute('''
                INSERT OR REPLACE INTO card_comments 
                (comment_id, card_id, comment_text, created_at, suppressed_notification)
                VALUES (?, ?, ?, ?, ?)
            ''', (comment_id, card_id, comment_text, created_at, 1 if suppressed_notification else 0))
            
            # Update latest comment timestamp
            if latest_timestamp is None or created_at > latest_timestamp:
                latest_timestamp = created_at
        
        conn.commit()
        conn.close()
        
        return latest_timestamp
    except Exception as e:
        logger.error(f"Error retrieving comments for card {card_id}: {str(e)}")
        return None

def has_comment_after_due_date_change(card_id):
    """Check if there's a comment posted after the last due date change."""
    due_date_info = get_stored_due_date(card_id)
    if not due_date_info["updated_at"]:
        return False
    
    due_date_updated_at = due_date_info["updated_at"]
    
    # Get the most recent comment from Trello API and store it
    latest_comment_timestamp = get_card_comments(card_id)
    
    if not latest_comment_timestamp:
        return False
    
    # Log the raw timestamps for debugging
    logger.debug(f"Card ID: {card_id}")
    logger.debug(f"Due date changed at: {due_date_updated_at}")
    logger.debug(f"Latest comment at: {latest_comment_timestamp}")
    
    # Convert both timestamps to datetime objects for comparison
    try:
        # Handle potential timezone issues by ensuring both are in the same format
        # For due_date_updated_at from SQLite
        if 'Z' in due_date_updated_at:
            due_date_dt = datetime.fromisoformat(due_date_updated_at.replace('Z', '+00:00'))
        else:
            # If it's a naive datetime string from SQLite (no Z or timezone info)
            due_date_dt = datetime.fromisoformat(due_date_updated_at)
            # Make it timezone-aware by assuming UTC
            due_date_dt = due_date_dt.replace(tzinfo=None)
        
        # For latest_comment_timestamp from Trello API
        if 'Z' in latest_comment_timestamp:
            comment_dt = datetime.fromisoformat(latest_comment_timestamp.replace('Z', '+00:00'))
        else:
            comment_dt = datetime.fromisoformat(latest_comment_timestamp)
            comment_dt = comment_dt.replace(tzinfo=None)
        
        # Ensure both are naive for comparison to avoid timezone issues
        if due_date_dt.tzinfo is not None:
            due_date_dt = due_date_dt.replace(tzinfo=None)
        if comment_dt.tzinfo is not None:
            comment_dt = comment_dt.replace(tzinfo=None)
        
        # Log the parsed datetime objects for debugging
        logger.debug(f"Parsed due date: {due_date_dt} (type: {type(due_date_dt)}, tzinfo: {due_date_dt.tzinfo})")
        logger.debug(f"Parsed comment: {comment_dt} (type: {type(comment_dt)}, tzinfo: {comment_dt.tzinfo})")
        logger.debug(f"Comparison result: comment after due date = {comment_dt > due_date_dt}")
            
        # Check if the comment was posted after the due date change
        return comment_dt > due_date_dt
    except Exception as e:
        logger.error(f"Error comparing timestamps for card {card_id}: {str(e)}")
        logger.error(f"Debug - due_date_updated_at: {due_date_updated_at} (type: {type(due_date_updated_at)})")
        logger.error(f"Debug - latest_comment_timestamp: {latest_comment_timestamp} (type: {type(latest_comment_timestamp)})")
        return False

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
    # Check if there's a comment after the due date change
    logger.info(f"Checking if card {card_id} ({card_name}) has comments after due date change")
    if has_comment_after_due_date_change(card_id):
        logger.info(f"Suppressing notification for card {card_name} - comment detected after due date change")
        # Still add to database but mark as read since we're suppressing the notification
        add_reminder(card_id, card_name, old_due, new_due)
        
        # Mark this reminder as read immediately since we're suppressing it
        # First get the newest reminder ID for this card
        conn = sqlite3.connect(CARDS_DUE_DB)
        c = conn.cursor()
        
        # Find the most recent unread reminder
        c.execute('''
            SELECT id FROM reminders 
            WHERE card_id = ? AND is_read = 0
            ORDER BY created_at DESC LIMIT 1
        ''', (card_id,))
        
        result = c.fetchone()
        if result:
            reminder_id = result[0]
            # Now update that specific reminder
            c.execute('UPDATE reminders SET is_read = 1 WHERE id = ?', (reminder_id,))
            
        conn.commit()
        conn.close()
        return
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Log reminder to the console
    reminder_message = (
        f"Reminder: Card '{card_name}' (ID: {card_id}) "
        f"due date changed from {old_due or 'None'} to {new_due or 'None'}"
    )
    logger.info(reminder_message)
    
    # Add reminder to the database
    add_reminder(card_id, card_name, old_due, new_due)
    
    # Here you could add additional functionality:
    # - Send an email notification
    # - Send a desktop notification
    # - Send a message to Slack or Discord
    # - etc.

def check_cards():
    """Check all cards in the specified list for due date changes."""
    # Get board ID, list ID, and cards from Trello API
    board_id, list_id, cards = get_trello_cards()
    
    for card in cards:
        card_id = card["id"]
        card_name = card["name"]
        card_url = card["url"]
        current_due = card.get("due", None)  # Get current due date from Trello
        
        # Get the stored due date from our database
        stored_card_info = get_stored_due_date(card_id)
        stored_due = stored_card_info["due_date"]
        
        if current_due is None and stored_due is None:
            # No due date set, nothing to track
            pass
        elif current_due is None and stored_due is not None:
            # Due date has been removed
            print(f"Due date removed for '{card_name}': {stored_due} -> None")
            update_stored_due_date(card_id, card_name, None, stored_due)
        elif stored_due is None and current_due is not None:
            # New due date set for the first time
            print(f"Due date set for '{card_name}': None -> {current_due}")
            update_stored_due_date(card_id, card_name, current_due, None)
        elif current_due != stored_due:
            # Due date changed
            print(f"Due date change detected for '{card_name}': {stored_due} -> {current_due}")
            update_stored_due_date(card_id, card_name, current_due, stored_due)
        else:
            # Make sure we have the card name in database (might have changed)
            conn = sqlite3.connect(CARDS_DUE_DB)
            c = conn.cursor()
            c.execute('UPDATE card_due SET name = ? WHERE card_id = ?', (card_name, card_id))
            conn.commit()
            conn.close()
    
    print(f"Sleeping for {POLL_INTERVAL_MINUTES} minutes before next check...")
    time.sleep(POLL_INTERVAL_MINUTES * 60)

def main():
    """Main function to poll the Trello board and check for due date changes."""
    # Initialize the database
    init_db()
    
    # Check environment variables
    required_vars = ["TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file")
        return
    
    logger.info("Starting Trello Due Date Monitor")
    logger.info(f"Checking for due date changes every {POLL_INTERVAL_MINUTES} minutes")
    
    # Continuous monitoring loop
    while True:
        try:
            check_cards()
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
            logger.error(f"Will retry in {POLL_INTERVAL_MINUTES} minutes")
            time.sleep(POLL_INTERVAL_MINUTES * 60)

def get_trello_cards():
    """Get board, list, and cards from Trello API."""
    # Trello API credentials
    api_key = os.getenv("TRELLO_API_KEY")
    api_token = os.getenv("TRELLO_TOKEN")
    
    # Log the credentials being used (without revealing full values)
    logger.debug(f"Using API key starting with: {api_key[:4]}... and token: {api_token[:4]}..." if api_key and api_token else "Missing API credentials")
    
    if not api_key or not api_token:
        logger.error("Missing Trello API credentials. Check your .env file.")
        return None, None, []
    
    # Get board ID from environment
    board_id = os.getenv("TRELLO_BOARD_ID")
    if not board_id:
        logger.error("Missing TRELLO_BOARD_ID in .env file.")
        return None, None, []
    
    # Get all lists on the board
    lists_url = f"https://api.trello.com/1/boards/{board_id}/lists"
    lists_params = {
        "key": api_key,
        "token": api_token
    }
    
    try:
        logger.debug(f"Fetching lists from board {board_id}")
        lists_response = requests.get(lists_url, params=lists_params)
        lists_response.raise_for_status()
        lists = lists_response.json()
        
        # Get all cards on the board
        cards_url = f"https://api.trello.com/1/boards/{board_id}/cards"
        cards_params = {
            "key": api_key,
            "token": api_token
        }
        
        logger.debug(f"Fetching cards from board {board_id}")
        cards_response = requests.get(cards_url, params=cards_params)
        cards_response.raise_for_status()
        cards = cards_response.json()
        
        # Return board ID, first list ID, and all cards
        list_id = lists[0]["id"] if lists else None
        
        logger.debug(f"Found {len(cards)} cards on board {board_id}")
        return board_id, list_id, cards
    except Exception as e:
        logger.error(f"Error fetching Trello data: {str(e)}")
        return None, None, []

if __name__ == "__main__":
    main()
