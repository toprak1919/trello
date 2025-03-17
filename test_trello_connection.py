import os
import json
import logging
import requests
from dotenv import load_dotenv

# Configure logging to console for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Configuration
TRELLO_API_KEY = os.getenv('TRELLO_API_KEY')
TRELLO_TOKEN = os.getenv('TRELLO_TOKEN')
TRELLO_BOARD_ID = os.getenv('TRELLO_BOARD_ID')

def test_trello_connection():
    """Test if we can connect to Trello API successfully."""
    logging.info("Testing Trello API connection...")
    
    if not TRELLO_API_KEY or not TRELLO_TOKEN:
        logging.error("❌ TRELLO_API_KEY or TRELLO_TOKEN is missing in .env file")
        return False
    
    url = "https://api.trello.com/1/members/me"
    params = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_TOKEN
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        user_data = response.json()
        logging.info(f"✅ Successfully connected to Trello API as: {user_data.get('fullName', user_data.get('username'))}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to connect to Trello API: {str(e)}")
        return False

def test_board_access():
    """Test if we can access the specified Trello board."""
    logging.info("Testing board access...")
    
    if not TRELLO_BOARD_ID:
        logging.error("❌ TRELLO_BOARD_ID is missing in .env file")
        return False
    
    url = f"https://api.trello.com/1/boards/{TRELLO_BOARD_ID}"
    params = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_TOKEN,
        'fields': 'name,url'
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        board_data = response.json()
        logging.info(f"✅ Successfully accessed board: {board_data.get('name')}")
        logging.info(f"   Board URL: {board_data.get('url')}")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to access board: {str(e)}")
        return False

def test_board_activity():
    """Test if we can get recent activity from the board."""
    logging.info("Testing board activity retrieval...")
    
    url = f"https://api.trello.com/1/boards/{TRELLO_BOARD_ID}/actions"
    params = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_TOKEN,
        'limit': 10  # Get just the 10 most recent actions
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        actions = response.json()
        
        if actions:
            logging.info(f"✅ Successfully retrieved {len(actions)} recent activities")
            
            # Show the most recent action
            if len(actions) > 0:
                recent = actions[0]
                action_type = recent.get('type', 'unknown')
                member = recent.get('memberCreator', {}).get('fullName', 'Unknown')
                date = recent.get('date', 'Unknown date')
                logging.info(f"   Most recent activity: {action_type} by {member} on {date}")
                
            # Check specifically for updateCard actions that might involve due date changes
            due_date_changes = [a for a in actions if a.get('type') == 'updateCard' and 'due' in a.get('data', {}).get('old', {})]
            if due_date_changes:
                logging.info(f"✅ Found {len(due_date_changes)} recent due date changes!")
                
                # Show the most recent due date change
                if len(due_date_changes) > 0:
                    change = due_date_changes[0]
                    card_name = change.get('data', {}).get('card', {}).get('name', 'Unknown card')
                    old_due = change.get('data', {}).get('old', {}).get('due', 'None')
                    member = change.get('memberCreator', {}).get('fullName', 'Unknown')
                    date = change.get('date', 'Unknown date')
                    logging.info(f"   Most recent due date change: '{card_name}' by {member} on {date}")
                    logging.info(f"   Old due date: {old_due}")
            else:
                logging.info("ℹ️ No recent due date changes found. Try changing a due date to test.")
                
            return True
        else:
            logging.warning("⚠️ No recent board activity found")
            return True  # Still consider this a success as the API call worked
    except Exception as e:
        logging.error(f"❌ Failed to retrieve board activity: {str(e)}")
        return False

def run_all_tests():
    """Run all Trello connection tests."""
    logging.info("=== TRELLO CONNECTION TESTS ===")
    
    connection_ok = test_trello_connection()
    if not connection_ok:
        logging.error("❌ CRITICAL: Cannot connect to Trello API. Check your API key and token.")
        return False
    
    board_ok = test_board_access()
    if not board_ok:
        logging.error("❌ CRITICAL: Cannot access the specified board. Check your board ID.")
        return False
    
    activity_ok = test_board_activity()
    
    if connection_ok and board_ok and activity_ok:
        logging.info("✅ All tests passed! Your polling.py should work correctly.")
        return True
    else:
        logging.error("❌ Some tests failed. Check the issues above.")
        return False

if __name__ == "__main__":
    run_all_tests() 