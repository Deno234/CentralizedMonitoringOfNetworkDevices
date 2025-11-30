import requests

API_URL = "http://localhost:5000"   # ili IP servera

def send_ping(mac, name, status, ip=None, latency=None):
    payload = {
        "mac": mac,
        "name": name,
        "status": status,
        "ip": ip,
        "latency": latency
    }
    try:
        r = requests.post(f"{API_URL}/api/ping", json=payload, timeout=2)
        return r.status_code == 200
    except Exception:
        return False
