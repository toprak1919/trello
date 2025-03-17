# Trello Due Date Monitor

A Python utility that monitors a Trello board for changes in card due dates and provides reminders.

## Overview

This tool continuously polls a specified Trello board for cards with due dates. When a card's due date changes, it logs the change and can provide notifications. This is useful for:

- Tracking task deadlines
- Getting reminders when due dates are modified
- Maintaining a history of due date changes

## Requirements

- Python 3.x
- A Trello account
- Trello API key and token

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/trello-due-date-monitor.git
   cd trello-due-date-monitor
   ```

2. Install required dependencies:
   ```
   pip install requests python-dotenv
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

Run the main script to start monitoring:

```
python trello.py
```

To test your Trello connection:

```
python test_trello_connection.py
```

## Features

- **Continuous Monitoring**: Polls the Trello board at configurable intervals
- **Change Detection**: Identifies when card due dates are modified
- **Persistent Storage**: Stores card information in SQLite database
- **Reminders**: Displays notifications when due dates change
- **Connection Testing**: Includes a test script to verify Trello API connection

## Database

The application uses a SQLite database (`cards_due.db`) to store card due dates. This allows it to:
- Track historical due date changes
- Compare current due dates with previous ones
- Persist data between program restarts

## Extending

You can modify the `send_reminder` function in `trello.py` to:
- Send email notifications
- Post to Slack or Discord
- Integrate with calendar systems
- Create system notifications

## License

[Your License Here] 