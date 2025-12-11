from flask import Flask, request, jsonify
from flask_cors import CORS
from server.db import (
    init_db,
    get_or_create_device,
    update_device_seen,
    save_ping_log,
    save_metrics_log,
    get_all_devices,
    get_ping_logs,
    get_metrics_logs
)
from anomaly.anomaly_detector import (
    AnomalyDetector,
    get_all_anomalies,
    save_anomaly_to_db
)
import sqlite3

app = Flask(__name__)
CORS(app)

# Initialize anomaly detector
detector = AnomalyDetector()


@app.route("/api/ping", methods=["POST"])
def api_ping():
    """Store ping results"""
    data = request.json

    mac = data.get("mac")
    name = data.get("name", mac)
    status = data.get("status")
    ip = data.get("ip")
    latency = data.get("latency")

    if not mac or status is None:
        return jsonify({"error": "Missing mac or status"}), 400

    device_id = get_or_create_device(mac, name)
    update_device_seen(device_id, ip)
    save_ping_log(device_id, ip, status, latency)

    return jsonify({"message": "Ping stored", "device_id": device_id})


@app.route("/api/metrics", methods=["POST"])
def api_metrics():
    """Store system metrics"""
    data = request.json

    mac = data.get("mac")
    name = data.get("name", mac)

    if not mac:
        return jsonify({"error": "Missing mac"}), 400

    device_id = get_or_create_device(mac, name)

    save_metrics_log(
        device_id,
        cpu=data.get("cpu"),
        ram=data.get("ram"),
        disk=data.get("disk"),
        net_sent=data.get("net_sent"),
        net_recv=data.get("net_recv")
    )

    update_device_seen(device_id, data.get("ip"))

    return jsonify({"message": "Metrics stored", "device_id": device_id})


@app.route("/api/devices", methods=["GET"])
def api_devices():
    """Get all devices"""
    return jsonify(get_all_devices())


@app.route("/api/ping_logs", methods=["GET"])
def api_ping_logs():
    """Get ping logs"""
    limit = request.args.get('limit', 200, type=int)
    return jsonify(get_ping_logs(limit=limit))


@app.route("/api/metrics_logs", methods=["GET"])
def api_metrics_logs():
    """Get metrics logs"""
    limit = request.args.get('limit', 200, type=int)
    device_id = request.args.get('device_id', type=int)

    if device_id:
        # Filter by device_id
        all_metrics = get_metrics_logs(limit=limit)
        filtered = [m for m in all_metrics if m['device_id'] == device_id]
        return jsonify(filtered)

    return jsonify(get_metrics_logs(limit=limit))


@app.route("/api/anomalies", methods=["GET"])
def api_anomalies():
    """Get detected anomalies"""
    limit = request.args.get('limit', 100, type=int)
    device_id = request.args.get('device_id', type=int)

    anomalies = get_all_anomalies(limit=limit, device_id=device_id)
    return jsonify(anomalies)


@app.route("/api/anomalies/detect", methods=["POST"])
def api_detect_anomalies():
    """
    Manually trigger anomaly detection for a specific device
    Body: {"device_id": 1, "methods": ["z-score", "moving_average"]}
    """
    data = request.json
    device_id = data.get("device_id")
    methods = data.get("methods", ["z-score", "moving_average", "isolation_forest", "lof"])

    if not device_id:
        return jsonify({"error": "Missing device_id"}), 400

    try:
        # Run detection
        results = detector.detect_all_anomalies(device_id)

        # Filter by requested methods
        filtered_results = {
            method: anomalies
            for method, anomalies in results.items()
            if method in methods
        }

        # Save newly detected anomalies
        saved_count = 0
        for method, anomalies in filtered_results.items():
            for anomaly in anomalies:
                save_anomaly_to_db(anomaly)
                saved_count += 1

        return jsonify({
            "device_id": device_id,
            "methods_used": list(filtered_results.keys()),
            "anomalies_found": sum(len(a) for a in filtered_results.values()),
            "anomalies_saved": saved_count,
            "results": filtered_results
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/anomalies/summary", methods=["GET"])
def api_anomaly_summary():
    """Get anomaly summary for all devices or specific device"""
    device_id = request.args.get('device_id', type=int)

    if device_id:
        summary = detector.get_anomaly_summary(device_id)
        return jsonify(summary)
    else:
        # Get summary for all devices
        devices = get_all_devices()
        summaries = []

        for device in devices:
            try:
                summary = detector.get_anomaly_summary(device['id'])
                summary['device_name'] = device['name']
                summaries.append(summary)
            except Exception as e:
                print(f"Error getting summary for device {device['id']}: {e}")

        return jsonify({
            "total_devices": len(devices),
            "device_summaries": summaries,
            "total_anomalies": sum(s['total_anomalies'] for s in summaries)
        })


@app.route("/api/anomalies/<int:anomaly_id>/acknowledge", methods=["POST"])
def api_acknowledge_anomaly(anomaly_id):
    """Mark an anomaly as acknowledged"""
    try:
        conn = sqlite3.connect("monitor.db")
        c = conn.cursor()

        c.execute(
            "UPDATE anomalies SET acknowledged = 1 WHERE id = ?",
            (anomaly_id,)
        )

        if c.rowcount == 0:
            conn.close()
            return jsonify({"error": "Anomaly not found"}), 404

        conn.commit()
        conn.close()

        return jsonify({"message": "Anomaly acknowledged", "anomaly_id": anomaly_id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/statistics", methods=["GET"])
def api_statistics():
    """Get overall system statistics"""
    try:
        conn = sqlite3.connect("monitor.db")
        c = conn.cursor()

        # Device stats
        total_devices = c.execute("SELECT COUNT(*) FROM devices").fetchone()[0]

        # Ping stats
        total_pings = c.execute("SELECT COUNT(*) FROM ping_logs").fetchone()[0]
        online_pings = c.execute("SELECT COUNT(*) FROM ping_logs WHERE status = 1").fetchone()[0]

        # Metrics stats
        total_metrics = c.execute("SELECT COUNT(*) FROM metrics_logs").fetchone()[0]

        # Anomaly stats
        total_anomalies = c.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]
        unacknowledged = c.execute("SELECT COUNT(*) FROM anomalies WHERE acknowledged = 0").fetchone()[0]
        high_severity = c.execute("SELECT COUNT(*) FROM anomalies WHERE severity = 'high'").fetchone()[0]

        conn.close()

        return jsonify({
            "devices": {
                "total": total_devices
            },
            "ping_logs": {
                "total": total_pings,
                "online": online_pings,
                "offline": total_pings - online_pings,
                "uptime_percentage": round((online_pings / total_pings * 100) if total_pings > 0 else 0, 2)
            },
            "metrics_logs": {
                "total": total_metrics
            },
            "anomalies": {
                "total": total_anomalies,
                "unacknowledged": unacknowledged,
                "high_severity": high_severity,
                "medium_severity": total_anomalies - high_severity
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def api_health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })


if __name__ == "__main__":
    from datetime import datetime

    init_db()

    # Create anomalies table
    conn = sqlite3.connect("monitor.db")
    c = conn.cursor()
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
    conn.commit()
    conn.close()

    print("🚀 Starting Flask API server with anomaly detection...")
    app.run(host="0.0.0.0", port=5000, debug=True)