import requests

API_BASE = "http://localhost:5000"

def api_get(path):
    try:
        url = f"{API_BASE}{path}"
        r = requests.get(url, timeout=3)
        return r.json()
    except Exception:
        return None
