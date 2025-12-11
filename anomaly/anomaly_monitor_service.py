import time
import sqlite3
from datetime import datetime
from anomaly_detector import AnomalyDetector, save_anomaly_to_db

DB_NAME = "monitor.db"
CHECK_INTERVAL = 60  # Check for anomalies every 60 seconds


def get_all_device_ids():
    """Get list of all device IDs from database"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    rows = c.execute("SELECT id FROM devices").fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_device_name(device_id):
    """Get device name by ID"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    row = c.execute("SELECT name FROM devices WHERE id = ?", (device_id,)).fetchone()
    conn.close()
    return row[0] if row else f"Device {device_id}"


def monitor_anomalies():
    """
    Continuously monitor all devices for anomalies
    Runs in background and saves detected anomalies to database
    """
    detector = AnomalyDetector(contamination=0.1)

    print("🔍 Anomaly Monitor Service Started")
    print(f"Checking for anomalies every {CHECK_INTERVAL} seconds\n")

    consecutive_errors = 0
    max_errors = 5

    while True:
        try:
            device_ids = get_all_device_ids()

            if not device_ids:
                print("⚠️  No devices found in database. Waiting...")
                time.sleep(CHECK_INTERVAL)
                continue

            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking {len(device_ids)} devices for anomalies...")

            total_anomalies_found = 0

            for device_id in device_ids:
                device_name = get_device_name(device_id)

                try:
                    # Run all anomaly detection methods
                    anomaly_results = detector.detect_all_anomalies(device_id)

                    # Process and save each detected anomaly
                    for method, anomalies in anomaly_results.items():
                        for anomaly in anomalies:
                            # Check if this anomaly was already saved (within last 5 minutes)
                            if not is_duplicate_anomaly(anomaly):
                                save_anomaly_to_db(anomaly)
                                total_anomalies_found += 1

                                # Print alert
                                severity_emoji = "🔴" if anomaly['severity'] == 'high' else "🟡"
                                print(f"  {severity_emoji} ANOMALY DETECTED: {device_name}")
                                print(f"     Method: {method}")
                                print(f"     Severity: {anomaly['severity'].upper()}")
                                print(f"     Timestamp: {anomaly['timestamp']}")

                                # Print specific metric issues
                                if 'anomalous_metrics' in anomaly:
                                    for metric_info in anomaly['anomalous_metrics']:
                                        print(f"     - {metric_info['metric']}: {metric_info['value']:.2f}")
                                print()

                except Exception as e:
                    print(f"  ⚠️  Error analyzing device {device_name}: {e}")

            if total_anomalies_found == 0:
                print("  ✅ No new anomalies detected")
            else:
                print(f"  📊 Total new anomalies: {total_anomalies_found}")

            print()

            # Reset error counter on success
            consecutive_errors = 0

        except Exception as e:
            consecutive_errors += 1
            print(f"❌ Error in anomaly monitor: {e}")
            print(f"   Consecutive errors: {consecutive_errors}/{max_errors}\n")

            if consecutive_errors >= max_errors:
                print("❌ Too many consecutive errors. Stopping anomaly monitor.")
                break

        # Wait before next check
        time.sleep(CHECK_INTERVAL)


def is_duplicate_anomaly(anomaly, time_window_minutes=5):
    """
    Check if a similar anomaly was already recorded recently
    Prevents duplicate alerts for the same issue
    """
    from datetime import timedelta

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    cutoff_time = (datetime.fromisoformat(anomaly['timestamp']) -
                   timedelta(minutes=time_window_minutes)).isoformat()

    # Check for recent similar anomalies
    row = c.execute('''
                    SELECT COUNT(*)
                    FROM anomalies
                    WHERE device_id = ?
                      AND detection_method = ?
                      AND timestamp
                        > ?
                      AND timestamp <= ?
                    ''', (
                        anomaly['device_id'],
                        anomaly['method'],
                        cutoff_time,
                        anomaly['timestamp']
                    )).fetchone()

    conn.close()

    return row[0] > 0


def cleanup_old_anomalies(days=30):
    """
    Clean up anomaly records older than specified days
    Should be run periodically to prevent database bloat
    """
    from datetime import timedelta

    cutoff_time = (datetime.now() - timedelta(days=days)).isoformat()

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("DELETE FROM anomalies WHERE timestamp < ?", (cutoff_time,))
    deleted_count = c.rowcount

    conn.commit()
    conn.close()

    print(f"🗑️  Cleaned up {deleted_count} old anomaly records")
    return deleted_count


if __name__ == "__main__":
    # Optional: cleanup old records on startup
    # cleanup_old_anomalies(days=30)

    # Start monitoring
    monitor_anomalies()