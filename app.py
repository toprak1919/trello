#!/usr/bin/env python3
"""
app.py - Web UI for Trello Due Date Monitor

A Flask-based web application that provides a dashboard for viewing
Trello card due date changes and reminders.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

# Configuration: Get Trello API credentials from environment variables
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_BOARD_ID = os.getenv("TRELLO_BOARD_ID")
DATABASE = 'cards_due.db'
TRELLO_CARDS_DB = 'trello_cards.db'

app = Flask(__name__)

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
            due_date TEXT
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
    
    conn.commit()
    conn.close()

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
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching cards: {response.text}")
            return []
    except Exception as e:
        print(f"Exception fetching cards: {str(e)}")
        return []

def update_cards_database():
    """Update the cards database with the latest information from Trello."""
    cards = get_all_cards_from_trello()
    if not cards:
        return
    
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
    
    conn.commit()
    conn.close()

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
    
    return render_template('card.html', card=card)

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
    
    conn.close()
    
    return jsonify({
        'lists': lists_data,
        'activity': activity_data,
        'status': status_data
    })

if __name__ == '__main__':
    init_db()
    init_trello_cards_db()
    app.run(debug=True) 