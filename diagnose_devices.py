#!/usr/bin/env python3
"""
Database Diagnostic Tool
Helps identify issues with device IDs, metrics, and data consistency
"""

import sqlite3
import json
from datetime import datetime, timedelta
from tabulate import tabulate

DB_NAME = "monitor.db"


def get_db_connection():
    """Get database connection"""
    try:
        return sqlite3.connect(DB_NAME)
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return None


def analyze_devices():
    """Analyze devices table"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("📋 DEVICES ANALYSIS")
    print("=" * 80)

    # Get all devices
    cursor.execute("SELECT id, name, mac, last_seen, last_ip FROM devices")
    devices = cursor.fetchall()

    if not devices:
        print("⚠️  No devices found in database!")
        conn.close()
        return

    # Prepare table data
    table_data = []
    for device_id, name, mac, last_seen, last_ip in devices:
        # Calculate time since last seen
        if last_seen:
            try:
                last_seen_dt = datetime.fromisoformat(last_seen)
                time_ago = datetime.now() - last_seen_dt

                if time_ago < timedelta(minutes=2):
                    status = "🟢 Online"
                elif time_ago < timedelta(minutes=10):
                    status = "🟡 Recent"
                else:
                    status = "🔴 Offline"

                time_ago_str = str(time_ago).split('.')[0]  # Remove microseconds
            except:
                status = "❓ Unknown"
                time_ago_str = "N/A"
        else:
            status = "⚪ Never seen"
            time_ago_str = "Never"

        table_data.append([
            device_id,
            name,
            mac,
            last_ip or "N/A",
            time_ago_str,
            status
        ])

    print(tabulate(
        table_data,
        headers=["ID", "Name", "MAC", "Last IP", "Last Seen", "Status"],
        tablefmt="grid"
    ))

    conn.close()
    print(f"\nTotal devices: {len(devices)}")


def analyze_metrics():
    """Analyze metrics logs"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("📊 METRICS ANALYSIS")
    print("=" * 80)

    # Get metrics count per device
    cursor.execute("""
                   SELECT d.id,
                          d.name,
                          d.mac,
                          COUNT(m.id)      as metric_count,
                          MIN(m.timestamp) as first_metric,
                          MAX(m.timestamp) as last_metric
                   FROM devices d
                            LEFT JOIN metrics_logs m ON d.id = m.device_id
                   GROUP BY d.id, d.name, d.mac
                   ORDER BY metric_count DESC
                   """)

    metrics_data = cursor.fetchall()

    if not metrics_data:
        print("⚠️  No metrics data found!")
        conn.close()
        return

    table_data = []
    for device_id, name, mac, count, first, last in metrics_data:
        if count > 0:
            try:
                first_dt = datetime.fromisoformat(first)
                last_dt = datetime.fromisoformat(last)
                time_span = last_dt - first_dt
                time_span_str = str(time_span).split('.')[0]
            except:
                time_span_str = "N/A"

            table_data.append([
                device_id,
                name,
                mac,
                count,
                time_span_str
            ])
        else:
            table_data.append([
                device_id,
                name,
                mac,
                0,
                "No metrics"
            ])

    print(tabulate(
        table_data,
        headers=["Device ID", "Name", "MAC", "Metric Count", "Time Span"],
        tablefmt="grid"
    ))

    # Show recent metrics
    print("\n📈 Recent Metrics (last 10):")
    cursor.execute("""
                   SELECT m.id,
                          d.name,
                          m.device_id,
                          m.timestamp,
                          m.cpu,
                          m.ram,
                          m.disk
                   FROM metrics_logs m
                            JOIN devices d ON m.device_id = d.id
                   ORDER BY m.id DESC
                   LIMIT 10
                   """)

    recent_metrics = cursor.fetchall()

    if recent_metrics:
        metrics_table = []
        for metric_id, name, device_id, timestamp, cpu, ram, disk in recent_metrics:
            metrics_table.append([
                metric_id,
                name,
                device_id,
                timestamp,
                f"{cpu:.1f}%" if cpu else "N/A",
                f"{ram:.1f}%" if ram else "N/A",
                f"{disk:.1f}%" if disk else "N/A"
            ])

        print(tabulate(
            metrics_table,
            headers=["ID", "Device", "Dev ID", "Timestamp", "CPU", "RAM", "Disk"],
            tablefmt="grid"
        ))
    else:
        print("No recent metrics found")

    conn.close()


def analyze_ping_logs():
    """Analyze ping logs"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("📶 PING LOGS ANALYSIS")
    print("=" * 80)

    # Get ping stats per device
    cursor.execute("""
                   SELECT d.id,
                          d.name,
                          COUNT(p.id)                                   as total_pings,
                          SUM(CASE WHEN p.status = 1 THEN 1 ELSE 0 END) as online_count,
                          MAX(p.timestamp)                              as last_ping
                   FROM devices d
                            LEFT JOIN ping_logs p ON d.id = p.device_id
                   GROUP BY d.id, d.name
                   ORDER BY total_pings DESC
                   """)

    ping_data = cursor.fetchall()

    if not ping_data:
        print("⚠️  No ping data found!")
        conn.close()
        return

    table_data = []
    for device_id, name, total, online, last_ping in ping_data:
        if total > 0:
            uptime = (online / total) * 100 if total > 0 else 0
            table_data.append([
                device_id,
                name,
                total,
                online,
                total - online,
                f"{uptime:.1f}%",
                last_ping or "N/A"
            ])
        else:
            table_data.append([
                device_id,
                name,
                0,
                0,
                0,
                "N/A",
                "Never"
            ])

    print(tabulate(
        table_data,
        headers=["Device ID", "Name", "Total Pings", "Online", "Offline", "Uptime %", "Last Ping"],
        tablefmt="grid"
    ))

    conn.close()


def check_device_config():
    """Check devices.json configuration"""
    print("\n" + "=" * 80)
    print("⚙️  DEVICE CONFIGURATION CHECK")
    print("=" * 80)

    try:
        with open("devices.json", "r", encoding="utf-8") as f:
            devices = json.load(f)

        print(f"\n✅ Found {len(devices)} devices in devices.json\n")

        for i, device in enumerate(devices, 1):
            print(f"{i}. {device.get('name', 'UNNAMED')}")
            print(f"   MAC: {device.get('mac', 'MISSING')}")
            print(f"   Self: {device.get('self', False)}")
            print()

    except FileNotFoundError:
        print("❌ devices.json not found!")
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing devices.json: {e}")


def find_mac_mismatches():
    """Find mismatches between devices.json and database"""
    print("\n" + "=" * 80)
    print("🔍 MAC ADDRESS MISMATCH CHECK")
    print("=" * 80)

    # Load config
    try:
        with open("devices.json", "r", encoding="utf-8") as f:
            config_devices = json.load(f)
    except:
        print("❌ Cannot read devices.json")
        return

    # Load DB devices
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()
    cursor.execute("SELECT id, name, mac FROM devices")
    db_devices = cursor.fetchall()
    conn.close()

    # Create MAC mappings
    config_macs = {d['mac'].lower().replace('-', ':'): d['name'] for d in config_devices}
    db_macs = {mac.lower().replace('-', ':'): (device_id, name) for device_id, name, mac in db_devices}

    # Find devices in config but not in DB
    print("\n📋 Devices in config but NOT in database:")
    config_only = set(config_macs.keys()) - set(db_macs.keys())
    if config_only:
        for mac in config_only:
            print(f"  • {config_macs[mac]} - {mac}")
    else:
        print("  ✅ All config devices are in database")

    # Find devices in DB but not in config
    print("\n💾 Devices in database but NOT in config:")
    db_only = set(db_macs.keys()) - set(config_macs.keys())
    if db_only:
        for mac in db_only:
            device_id, name = db_macs[mac]
            print(f"  • {name} (ID: {device_id}) - {mac}")
    else:
        print("  ✅ All database devices are in config")

    # Check name mismatches
    print("\n🏷️  Name mismatches (same MAC, different name):")
    found_mismatch = False
    for mac in set(config_macs.keys()) & set(db_macs.keys()):
        config_name = config_macs[mac]
        db_id, db_name = db_macs[mac]
        if config_name != db_name:
            print(f"  • MAC {mac}:")
            print(f"    Config: {config_name}")
            print(f"    Database: {db_name} (ID: {db_id})")
            found_mismatch = True

    if not found_mismatch:
        print("  ✅ No name mismatches found")


def main():
    """Run all diagnostics"""
    print("\n" + "=" * 80)
    print("🔧 NETWORK MONITORING DIAGNOSTIC TOOL")
    print("=" * 80)

    # Run all checks
    check_device_config()
    analyze_devices()
    analyze_metrics()
    analyze_ping_logs()
    find_mac_mismatches()

    print("\n" + "=" * 80)
    print("✅ DIAGNOSTIC COMPLETE")
    print("=" * 80)
    print()


if __name__ == "__main__":
    try:
        # Try to import tabulate, install if needed
        import tabulate
    except ImportError:
        print("Installing required package: tabulate")
        import subprocess

        subprocess.check_call(["pip", "install", "tabulate"])
        import tabulate

    main()