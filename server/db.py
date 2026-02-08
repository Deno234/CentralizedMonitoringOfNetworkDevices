import sqlite3
import os
from datetime import datetime

# Use proper database path relative to this file
DB_NAME = "monitor.db"


def get_connection():
    """Get database connection with proper path"""
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    """Initialize database with all required tables"""
    conn = get_connection()
    c = conn.cursor()

    # Devices table
    c.execute('''
              CREATE TABLE IF NOT EXISTS devices
              (
                  id          INTEGER PRIMARY KEY AUTOINCREMENT,
                  name        TEXT        NOT NULL,
                  mac         TEXT UNIQUE NOT NULL,
                  device_type TEXT,
                  last_seen   TEXT,
                  last_ip     TEXT
              )
              ''')

    # Ping logs table
    c.execute('''
              CREATE TABLE IF NOT EXISTS ping_logs
              (
                  id         INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp  TEXT    NOT NULL,
                  device_id  INTEGER NOT NULL,
                  ip         TEXT,
                  status     INTEGER NOT NULL,
                  latency_ms REAL,
                  FOREIGN KEY (device_id) REFERENCES devices (id)
              )
              ''')

    # Metrics logs table
    c.execute('''
              CREATE TABLE IF NOT EXISTS metrics_logs
              (
                  id        INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT    NOT NULL,
                  device_id INTEGER NOT NULL,
                  cpu       REAL,
                  ram       REAL,
                  disk      REAL,
                  net_sent  REAL,
                  net_recv  REAL,
                  FOREIGN KEY (device_id) REFERENCES devices (id)
              )
              ''')

    # Anomalies table
    c.execute('''
              CREATE TABLE IF NOT EXISTS anomalies
              (
                  id               INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp        TEXT    NOT NULL,
                  device_id        INTEGER NOT NULL,
                  detection_method TEXT    NOT NULL,
                  severity         TEXT    NOT NULL,
                  details          TEXT    NOT NULL,
                  acknowledged     INTEGER DEFAULT 0,
                  FOREIGN KEY (device_id) REFERENCES devices (id)
              )
              ''')

    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL;")

    conn.commit()
    conn.close()

    print(f"✅ Database initialized at: {DB_NAME}")


# ---------------------------
# DEVICE FUNCTIONS
# ---------------------------

def get_or_create_device(mac, name=None, device_type=None):
    """
    Get existing device by MAC or create new one
    MAC addresses are normalized to lowercase with colons
    """
    conn = get_connection()
    c = conn.cursor()

    # Normalize MAC address to lowercase with colons
    mac_normalized = mac.lower().replace("-", ":")

    c.execute("SELECT id FROM devices WHERE mac = ?", (mac_normalized,))
    row = c.fetchone()

    if row:
        conn.close()
        return row[0]

    # Create new device
    c.execute(
        "INSERT INTO devices (name, mac, device_type) VALUES (?, ?, ?)",
        (name or mac_normalized, mac_normalized, device_type)
    )
    conn.commit()

    device_id = c.lastrowid
    conn.close()
    return device_id


def update_device_seen(device_id, ip):
    """Update last seen timestamp and IP for a device"""
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        "UPDATE devices SET last_seen = ?, last_ip = ? WHERE id = ?",
        (datetime.now().isoformat(), ip, device_id)
    )
    conn.commit()
    conn.close()


def get_all_devices():
    """Get all devices from database"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rows = c.execute("SELECT * FROM devices ORDER BY id ASC").fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_device_by_id(device_id):
    """Get a specific device by ID"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    row = c.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    conn.close()

    return dict(row) if row else None


# ---------------------------
# LOGGING FUNCTIONS
# ---------------------------

def save_ping_log(device_id, ip, status, latency_ms=None):
    """Save ping result to database"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
              INSERT INTO ping_logs (timestamp, device_id, ip, status, latency_ms)
              VALUES (?, ?, ?, ?, ?)
              ''', (datetime.now().isoformat(), device_id, ip, int(status), latency_ms))

    conn.commit()
    conn.close()


def save_metrics_log(device_id, cpu, ram, disk, net_sent, net_recv):
    """Save system metrics to database"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
              INSERT INTO metrics_logs
                  (timestamp, device_id, cpu, ram, disk, net_sent, net_recv)
              VALUES (?, ?, ?, ?, ?, ?, ?)
              ''', (datetime.now().isoformat(), device_id, cpu, ram, disk, net_sent, net_recv))

    conn.commit()
    conn.close()


def get_ping_logs(limit=200, device_id=None):
    """Get ping logs, optionally filtered by device"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if device_id:
        rows = c.execute(
            "SELECT * FROM ping_logs WHERE device_id = ? ORDER BY id DESC LIMIT ?",
            (device_id, limit)
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM ping_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_metrics_logs(limit=200, device_id=None):
    """Get metrics logs, optionally filtered by device"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if device_id:
        rows = c.execute(
            "SELECT * FROM metrics_logs WHERE device_id = ? ORDER BY id DESC LIMIT ?",
            (device_id, limit)
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM metrics_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


# ---------------------------
# UTILITY FUNCTIONS
# ---------------------------

def get_database_stats():
    """Get statistics about database contents"""
    conn = get_connection()
    c = conn.cursor()

    stats = {
        'devices': c.execute("SELECT COUNT(*) FROM devices").fetchone()[0],
        'ping_logs': c.execute("SELECT COUNT(*) FROM ping_logs").fetchone()[0],
        'metrics_logs': c.execute("SELECT COUNT(*) FROM metrics_logs").fetchone()[0],
        'anomalies': c.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0],
    }

    conn.close()
    return stats


def vacuum_database():
    """Optimize database (removes deleted records, defragments)"""
    conn = get_connection()
    conn.execute("VACUUM;")
    conn.close()
    print("✅ Database optimized")


if __name__ == "__main__":
    # Initialize database when run directly
    print("Initializing database...")
    init_db()

    # Show stats
    stats = get_database_stats()
    print("\nDatabase Statistics:")
    for table, count in stats.items():
        print(f"  {table}: {count} records")