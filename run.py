#!/usr/bin/env python3
"""
run.py

A helper script to run both the Trello monitor and web UI.
This allows users to start everything with a single command.
"""

import os
import sys
import subprocess
import threading
import time
import webbrowser
import signal
import platform

def run_trello_monitor():
    """Run the Trello monitor script in a separate process."""
    print("Starting Trello monitor...")
    if platform.system() == 'Windows':
        return subprocess.Popen(['python', 'trello.py'], 
                               creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        return subprocess.Popen(['python', 'trello.py'])

def run_web_server():
    """Run the Flask web server in a separate process."""
    print("Starting web server...")
    if platform.system() == 'Windows':
        return subprocess.Popen(['python', 'app.py'],
                               creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        return subprocess.Popen(['python', 'app.py'])

def open_browser():
    """Open the web browser to the dashboard after a short delay."""
    time.sleep(2)  # Wait for the server to start
    webbrowser.open('http://localhost:5000')
    print("Opened browser to http://localhost:5000")

def shutdown_handler(signum, frame):
    """Handle shutdown signal and terminate all processes."""
    print("\nShutting down all processes...")
    
    if monitor_process:
        monitor_process.terminate()
        print("Trello monitor stopped")
    
    if web_process:
        web_process.terminate()
        print("Web server stopped")
    
    print("Goodbye!")
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    if platform.system() != 'Windows':
        signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Start processes
    monitor_process = run_trello_monitor()
    web_process = run_web_server()
    
    # Open browser in a separate thread
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    print("Both services running! Press Ctrl+C to stop")
    
    try:
        # Keep the main thread alive to handle keyboard interrupts
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # This will be caught by the signal handler
        pass 