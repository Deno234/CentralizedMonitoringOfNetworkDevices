import sqlite3
from datetime import datetime

DB_NAME = "monitor.db"


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mac TEXT UNIQUE NOT NULL,
            device_type TEXT,
            last_seen TEXT,
            last_ip TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS ping_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            device_id INTEGER NOT NULL,
            ip TEXT,
            status INTEGER NOT NULL,
            latency_ms REAL,
            FOREIGN KEY(device_id) REFERENCES devices(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS metrics_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            device_id INTEGER NOT NULL,
            cpu REAL,
            ram REAL,
            disk REAL,
            net_sent REAL,
            net_recv REAL,
            FOREIGN KEY(device_id) REFERENCES devices(id)
        )
    ''')

    conn.commit()
    conn.close()


# ---------------------------
# DEVICE FUNCTIONS
# ---------------------------

def get_or_create_device(mac, name=None, device_type=None):
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id FROM devices WHERE mac = ?", (mac,))
    row = c.fetchone()

    if row:
        conn.close()
        return row[0]

    c.execute(
        "INSERT INTO devices (name, mac, device_type) VALUES (?, ?, ?)",
        (name or mac, mac, device_type)
    )
    conn.commit()

    device_id = c.lastrowid
    conn.close()
    return device_id


def update_device_seen(device_id, ip):
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        "UPDATE devices SET last_seen = ?, last_ip = ? WHERE id = ?",
        (datetime.now().isoformat(), ip, device_id)
    )
    conn.commit()
    conn.close()


def get_all_devices():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rows = c.execute("SELECT * FROM devices").fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ---------------------------
# LOGGING FUNCTIONS
# ---------------------------

def save_ping_log(device_id, ip, status, latency_ms=None):
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        INSERT INTO ping_logs (timestamp, device_id, ip, status, latency_ms)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), device_id, ip, int(status), latency_ms))

    conn.commit()
    conn.close()


def save_metrics_log(device_id, cpu, ram, disk, net_sent, net_recv):
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        INSERT INTO metrics_logs
        (timestamp, device_id, cpu, ram, disk, net_sent, net_recv)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), device_id, cpu, ram, disk, net_sent, net_recv))

    conn.commit()
    conn.close()


def get_ping_logs(limit=200):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rows = c.execute(
        "SELECT * FROM ping_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_metrics_logs(limit=200):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rows = c.execute(
        "SELECT * FROM metrics_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]
