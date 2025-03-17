# Trello Due Date Monitor

A Python utility that monitors a Trello board for changes in card due dates and provides reminders.

## Overview

This tool continuously polls a specified Trello board for cards with due dates. When a card's due date changes, it logs the change and can provide notifications. This is useful for:

- Tracking task deadlines
- Getting reminders when due dates are modified
- Maintaining a history of due date changes

## Features

- **Continuous Monitoring**: Polls the Trello board at configurable intervals
- **Change Detection**: Identifies when card due dates are modified
- **Persistent Storage**: Stores card information in SQLite database
- **Reminders**: Displays notifications when due dates change
- **Connection Testing**: Includes a test script to verify Trello API connection
- **Web Dashboard**: Beautiful web interface to track and manage reminders

### Web UI Features

- **Reminders Dashboard**: View all due date change notifications in one place
- **Analytics**: Charts and graphs showing statistics about your cards and due dates
- **Card Details**: Detailed view of each card with its due date history
- **List View**: See all cards organized by their Trello lists
- **Responsive Design**: Works on desktop and mobile devices

## Requirements

- Python 3.x
- A Trello account
- Trello API key and token
- Web browser (for the UI)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/trello-due-date-monitor.git
   cd trello-due-date-monitor
   ```

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

Create a `.env` file in the project directory with the following variables:

```
TRELLO_API_KEY=your_trello_api_key
TRELLO_TOKEN=your_trello_token
TRELLO_BOARD_ID=your_board_id
REMINDER_DELAY_HOURS=24
POLL_INTERVAL_MINUTES=0.1
WEBHOOK_URL=
WEBHOOK_SECRET=your_webhook_secret
```

### How to get your Trello credentials:

1. **API Key**: Obtain from [Trello Developer API Keys](https://trello.com/app-key)
2. **Token**: Generate from the API Key page
3. **Board ID**: Found in the URL of your Trello board: `https://trello.com/b/[BOARD_ID]/[BOARD_NAME]`

## Usage

### Command-line Monitoring

Run the main script to start monitoring in the background:

```
python trello.py
```

To test your Trello connection:

```
python test_trello_connection.py
```

### Web Interface

Start the web server:

```
python app.py
```

Then open your browser and navigate to:

```
http://localhost:5000
```

## Web UI Screenshots

### Reminders Dashboard
![Reminders Dashboard](reminders.png)

### Analytics View
![Analytics View](analytics.png)

### Card Details
![Card Details](https://placeholder-image-url.com/card-details.png)

## Database

The application uses two SQLite databases:

1. **cards_due.db**: Stores card due dates and reminders history
   - `card_due`: Tracks the current due date for each card
   - `reminders`: Stores a history of all due date changes with status

2. **trello_cards.db**: Stores detailed card information
   - `cards`: Contains full card details including descriptions, URLs, and list names

## Extending

### Custom Notifications

You can modify the `send_reminder` function in `trello.py` to:
- Send email notifications
- Post to Slack or Discord
- Integrate with calendar systems
- Create system notifications

### Web UI Customization

The web interface can be customized by:
- Modifying the templates in the `templates` directory
- Updating CSS in the `static/css` directory
- Extending functionality through the Flask routes in `app.py`

## Deployment

For production deployment, consider:

1. Using a production-ready WSGI server like Gunicorn:
   ```
   gunicorn app:app
   ```

2. Setting `debug=False` in `app.py` before deployment

3. Using a reverse proxy like Nginx or Apache

## License

[Your License Here] 