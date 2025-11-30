import sqlite3 # For working with the SQLite database
from datetime import datetime # For retrieving the current time

DB_NAME = "monitor.db" # Name of the database

"""
The function opens a connection to the 'monitor.db' database.
A cursor is created for executing SQL commands.
"""
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    """
    SQL statement that creates the ping_status table if it does not already exist.
    The table has the following fields:
        - id (unique identifier, auto-incremented)
        - timestamp (time the record was printed, can't be empty)
        - device_name (device name, can't be empty)
        - mac (device MAC address, can't be empty)
        - ip (IP address, can be empty)
        - status (integer indicating the ping status, e.g. 0 or 1, can't be empty)
    """
    c.execute('''
        CREATE TABLE IF NOT EXISTS ping_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            device_name TEXT NOT NULL,
            mac TEXT NOT NULL,
            ip TEXT,
            status INTEGER NOT NULL
        )
    ''')

    # The changes are saved (commited) to the database and the connection is closed.
    conn.commit()
    conn.close()


# The function opens a connection and cursor to the same database
def save_ping_result(device_name, mac, ip, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    """
    Inserts a new record in the ping_status table with data (This method with ? prevents SQL injection attacks):
        - current timestamp in ISO format
        - device_name
        - MAC address
        - IP address
        - status (converted to integer)
    """
    c.execute('''
        INSERT INTO ping_status (timestamp, device_name, mac, ip, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), device_name, mac, ip, int(status)))

    # The entry is saved to the database and the connection is closed
    conn.commit()
    conn.close()
