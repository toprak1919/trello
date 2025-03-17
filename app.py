#!/usr/bin/env python3
"""
app.py - Web UI for Trello Due Date Monitor

A Flask-based web application that provides a dashboard for viewing
Trello card due date changes and reminders.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for
from dotenv import load_dotenv
import requests

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_timestamp_debug.log'),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger('trello_web_app')

# Load environment variables from .env file
load_dotenv()

# Configuration: Get Trello API credentials from environment variables
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_BOARD_ID = os.getenv("TRELLO_BOARD_ID")
DATABASE = 'cards_due.db'
TRELLO_CARDS_DB = 'trello_cards.db'

# Check and log credentials
logger.debug(f"API Key: {TRELLO_API_KEY[:4]}..." if TRELLO_API_KEY else "API Key not found")
logger.debug(f"Token: {TRELLO_TOKEN[:4]}..." if TRELLO_TOKEN else "Token not found")
logger.debug(f"Board ID: {TRELLO_BOARD_ID}" if TRELLO_BOARD_ID else "Board ID not found")

app = Flask(__name__)

# Add utility functions to Jinja environment
@app.context_processor
def utility_processor():
    def now():
        return datetime.now()
    return dict(now=now)

def get_db_connection(db_name=DATABASE):
    """Create a database connection and return connection and cursor."""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table for storing due date history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS card_due (
            card_id TEXT PRIMARY KEY,
            name TEXT,
            due_date TEXT,
            due_date_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table for storing reminders history
    cursor.execute('''
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
    
    # Table for tracking card comments
    cursor.execute('''
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
        cursor.execute("SELECT name FROM card_due LIMIT 1")
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        logger.info("Adding 'name' column to card_due table")
        cursor.execute("ALTER TABLE card_due ADD COLUMN name TEXT")
    
    # Check if suppressed_notification column exists in card_comments table, add it if it doesn't
    try:
        cursor.execute("SELECT suppressed_notification FROM card_comments LIMIT 1")
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        logger.info("Adding 'suppressed_notification' column to card_comments table")
        cursor.execute("ALTER TABLE card_comments ADD COLUMN suppressed_notification INTEGER DEFAULT 0")
    
    conn.commit()
    conn.close()
    
    logger.info("Database initialized successfully")

def init_trello_cards_db():
    """Initialize the Trello cards database."""
    conn = get_db_connection(TRELLO_CARDS_DB)
    cursor = conn.cursor()
    
    # Table for storing card details
    cursor.execute('''
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

def get_all_cards_from_trello():
    """Fetch all cards on the Trello board from the Trello API."""
    url = f"https://api.trello.com/1/boards/{TRELLO_BOARD_ID}/cards"
    params = {
        "key": TRELLO_API_KEY,
        "token": TRELLO_TOKEN,
        "fields": "id,due,name,desc,url",
        "list": "true"
    }
    
    if not TRELLO_API_KEY or not TRELLO_TOKEN:
        logger.error("Missing Trello API credentials. Check your .env file.")
        return []
    
    try:
        logger.debug(f"Fetching cards from board {TRELLO_BOARD_ID}")
        response = requests.get(url, params=params)
        response.raise_for_status()  # This will raise an exception for HTTP errors
        cards = response.json()
        logger.info(f"Successfully fetched {len(cards)} cards from Trello")
        return cards
    except requests.exceptions.HTTPError as he:
        logger.error(f"HTTP Error fetching cards: {he}")
        logger.error(f"Response: {he.response.text}")
        return []
    except Exception as e:
        logger.error(f"Exception fetching cards: {str(e)}")
        return []

def update_cards_database():
    """Update the cards database with the latest information from Trello."""
    cards = get_all_cards_from_trello()
    if not cards:
        return
    
    # Initialize databases if they don't exist
    init_db()
    init_trello_cards_db()
    
    conn = get_db_connection(TRELLO_CARDS_DB)
    cursor = conn.cursor()
    
    for card in cards:
        card_id = card.get("id")
        name = card.get("name")
        description = card.get("desc", "")
        url = card.get("url")
        due_date = card.get("due")
        list_name = card.get("list", {}).get("name", "Unknown List")
        
        cursor.execute('''
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
        
        # Also update the name in card_due table if it exists
        try:
            conn_due = get_db_connection()
            cursor_due = conn_due.cursor()
            cursor_due.execute('''
                UPDATE card_due 
                SET name = ? 
                WHERE card_id = ?
            ''', (name, card_id))
            conn_due.commit()
            conn_due.close()
        except Exception as e:
            logger.error(f"Error updating name in card_due: {str(e)}")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Updated {len(cards)} cards in database")

def get_card_details(card_id):
    """Get details for a specific card."""
    conn = get_db_connection(TRELLO_CARDS_DB)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM cards WHERE card_id = ?', (card_id,))
    card = cursor.fetchone()
    
    conn.close()
    
    if card:
        return dict(card)
    return None

def get_card_comments(card_id):
    """Get comments for a specific card."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM card_comments 
        WHERE card_id = ? 
        ORDER BY created_at DESC
    ''', (card_id,))
    
    comments = cursor.fetchall()
    conn.close()
    
    return [dict(comment) for comment in comments]

def get_reminders(limit=50, offset=0, is_read=None):
    """Get reminders with pagination and filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM reminders'
    params = []
    
    if is_read is not None:
        query += ' WHERE is_read = ?'
        params.append(is_read)
    
    query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    reminders = cursor.fetchall()
    
    conn.close()
    
    return [dict(reminder) for reminder in reminders]

def count_reminders(is_read=None):
    """Count total reminders for pagination."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT COUNT(*) FROM reminders'
    params = []
    
    if is_read is not None:
        query += ' WHERE is_read = ?'
        params.append(is_read)
    
    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    
    conn.close()
    
    return count

def add_reminder(card_id, card_name, old_due, new_due):
    """Add a new reminder to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO reminders (card_id, card_name, old_due, new_due)
        VALUES (?, ?, ?, ?)
    ''', (card_id, card_name, old_due, new_due))
    
    conn.commit()
    conn.close()

def mark_reminder_as_read(reminder_id):
    """Mark a reminder as read."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE reminders SET is_read = 1 WHERE id = ?', (reminder_id,))
    
    conn.commit()
    conn.close()

def get_card_notification_status(card_id):
    """Check if notifications for a card are muted due to comments."""
    # Get the last due date change
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the due date updated timestamp
    cursor.execute('SELECT due_date_updated_at FROM card_due WHERE card_id = ?', (card_id,))
    due_date_row = cursor.fetchone()
    
    if not due_date_row or not due_date_row[0]:
        conn.close()
        return {
            "notifications_muted": False,
            "reason": None
        }
    
    due_date_updated_at = due_date_row[0]
    
    # Get the most recent comment
    cursor.execute('''
        SELECT created_at FROM card_comments 
        WHERE card_id = ? 
        ORDER BY created_at DESC 
        LIMIT 1
    ''', (card_id,))
    
    comment_row = cursor.fetchone()
    conn.close()
    
    if not comment_row or not comment_row[0]:
        return {
            "notifications_muted": False,
            "reason": None
        }
    
    comment_timestamp = comment_row[0]
    
    # Log the raw timestamps for debugging
    logger.debug(f"Card ID: {card_id}")
    logger.debug(f"Due date changed at: {due_date_updated_at} (type: {type(due_date_updated_at)})")
    logger.debug(f"Latest comment at: {comment_timestamp} (type: {type(comment_timestamp)})")
    
    # Convert both timestamps to datetime objects for comparison
    try:
        # Handle potential timezone issues by ensuring both are in the same format
        # For due_date_updated_at from SQLite
        if isinstance(due_date_updated_at, str) and 'Z' in due_date_updated_at:
            due_date_dt = datetime.fromisoformat(due_date_updated_at.replace('Z', '+00:00'))
        else:
            # If it's a naive datetime string from SQLite (no Z or timezone info)
            due_date_dt = datetime.fromisoformat(due_date_updated_at if isinstance(due_date_updated_at, str) else str(due_date_updated_at))
            # Make it naive to ensure consistent comparison
            due_date_dt = due_date_dt.replace(tzinfo=None)
        
        # For comment_timestamp from database
        if isinstance(comment_timestamp, str) and 'Z' in comment_timestamp:
            comment_dt = datetime.fromisoformat(comment_timestamp.replace('Z', '+00:00'))
        else:
            comment_dt = datetime.fromisoformat(comment_timestamp if isinstance(comment_timestamp, str) else str(comment_timestamp))
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
        if comment_dt > due_date_dt:
            logger.info(f"Notifications muted for card {card_id}: Comment found after due date change")
            return {
                "notifications_muted": True,
                "reason": "Comment added after due date change"
            }
    except Exception as e:
        logger.error(f"Error comparing timestamps for card {card_id}: {str(e)}")
        logger.error(f"Debug - due_date_updated_at type: {type(due_date_updated_at)}, value: {due_date_updated_at}")
        logger.error(f"Debug - comment_timestamp type: {type(comment_timestamp)}, value: {comment_timestamp}")
    
    return {
        "notifications_muted": False,
        "reason": None
    }

@app.route('/')
def index():
    """Render the dashboard page."""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    is_read = request.args.get('is_read', None)
    
    if is_read is not None:
        is_read = int(is_read)
    
    offset = (page - 1) * per_page
    reminders = get_reminders(per_page, offset, is_read)
    
    # Count total for pagination
    total = count_reminders(is_read)
    total_pages = (total + per_page - 1) // per_page
    
    # Update card database to get latest info
    update_cards_database()
    
    return render_template(
        'index.html', 
        reminders=reminders,
        page=page, 
        total_pages=total_pages,
        is_read=is_read
    )

@app.route('/card/<card_id>')
def card_details(card_id):
    """Render the card details page."""
    card = get_card_details(card_id)
    if not card:
        return redirect(url_for('index'))
    
    # Get notification status
    notification_status = get_card_notification_status(card_id)
    
    # Get comments
    comments = get_card_comments(card_id)
    
    return render_template(
        'card.html', 
        card=card, 
        comments=comments, 
        notification_status=notification_status
    )

@app.route('/api/reminders')
def api_reminders():
    """API endpoint to get reminders in JSON format."""
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    is_read = request.args.get('is_read', None)
    
    if is_read is not None:
        is_read = int(is_read)
    
    reminders = get_reminders(limit, offset, is_read)
    return jsonify(reminders)

@app.route('/api/mark-read/<int:reminder_id>', methods=['POST'])
def api_mark_read(reminder_id):
    """API endpoint to mark a reminder as read."""
    mark_reminder_as_read(reminder_id)
    return jsonify({'success': True})

@app.route('/api/cards')
def api_cards():
    """API endpoint to get all cards."""
    conn = get_db_connection(TRELLO_CARDS_DB)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM cards ORDER BY due_date ASC')
    cards = cursor.fetchall()
    
    conn.close()
    
    return jsonify([dict(card) for card in cards])

@app.route('/api/card/<card_id>/comments')
def api_card_comments(card_id):
    """API endpoint to get comments for a specific card."""
    comments = get_card_comments(card_id)
    return jsonify(comments)

@app.route('/api/card/<card_id>/notification-status')
def api_card_notification_status(card_id):
    """API endpoint to get notification status for a specific card."""
    status = get_card_notification_status(card_id)
    return jsonify(status)

@app.route('/sync', methods=['POST'])
def sync_data():
    """Force synchronization with Trello."""
    update_cards_database()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    """Render the analytics dashboard."""
    return render_template('dashboard.html')

@app.route('/api/dashboard-data')
def dashboard_data():
    """API endpoint for dashboard analytics data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Cards with due dates by list
    cursor2 = get_db_connection(TRELLO_CARDS_DB).cursor()
    cursor2.execute('''
        SELECT list_name, COUNT(*) as count
        FROM cards 
        WHERE due_date IS NOT NULL
        GROUP BY list_name
    ''')
    lists_data = [dict(row) for row in cursor2.fetchall()]
    
    # Due date changes over time
    cursor.execute('''
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM reminders
        GROUP BY DATE(created_at)
        ORDER BY date
    ''')
    activity_data = [dict(row) for row in cursor.fetchall()]
    
    # Reminders status count
    cursor.execute('''
        SELECT is_read, COUNT(*) as count
        FROM reminders
        GROUP BY is_read
    ''')
    status_data = [dict(row) for row in cursor.fetchall()]
    
    # Get count of notification suppressions due to comments
    cursor.execute('''
        SELECT COUNT(*) as count FROM reminders WHERE is_read = 1
    ''')
    total_read = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'lists': lists_data,
        'activity': activity_data,
        'status': status_data,
        'auto_suppressed': total_read  # This is an approximation
    })

@app.route('/comments')
def comments_page():
    """Comments page showing all Trello card comments."""
    return render_template('comments.html', active_page='comments')

@app.route('/api/comments')
def api_comments():
    """API endpoint to get all comments."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT cc.*, 
               cd.due_date, 
               cd.due_date_updated_at
        FROM card_comments cc
        LEFT JOIN card_due cd ON cc.card_id = cd.card_id
        ORDER BY cc.created_at DESC
    ''')
    
    comments = cursor.fetchall()
    conn.close()
    
    # Format comments for JSON response
    formatted_comments = []
    for comment in comments:
        comment_dict = dict(comment)
        
        # Log timestamp information for debugging
        logger.debug(f"Comment {comment_dict['comment_id']}: created_at={comment_dict['created_at']}, " +
                    f"due_date_updated_at={comment_dict.get('due_date_updated_at')}")
        
        # Include the suppressed_notification field directly from database
        # It's already determined when comments are stored
        formatted_comments.append(comment_dict)
    
    return jsonify({'comments': formatted_comments})

if __name__ == '__main__':
    init_db()
    init_trello_cards_db()
    app.run(debug=True) 