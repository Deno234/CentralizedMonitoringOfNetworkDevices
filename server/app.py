from flask import Flask, request, jsonify
from flask_cors import CORS
from db import (
    init_db,
    get_or_create_device,
    update_device_seen,
    save_ping_log,
    save_metrics_log,
    get_all_devices,
    get_ping_logs,
    get_metrics_logs
)

app = Flask(__name__)
CORS(app)  # omogućava pozive sa Streamlita (port 8501)


@app.route("/api/ping", methods=["POST"])
def api_ping():
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
    return jsonify(get_all_devices())


@app.route("/api/ping_logs", methods=["GET"])
def api_ping_logs():
    return jsonify(get_ping_logs())


@app.route("/api/metrics_logs", methods=["GET"])
def api_metrics_logs():
    return jsonify(get_metrics_logs())


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
