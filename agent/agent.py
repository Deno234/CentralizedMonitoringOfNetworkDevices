import time
import psutil
import requests
from utils import get_mac_address

API_URL = "http://localhost:5000/api/metrics"
INTERVAL = 5  # seconds


def collect_metrics():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent

    net = psutil.net_io_counters()
    net_sent = net.bytes_sent
    net_recv = net.bytes_recv

    return cpu, ram, disk, net_sent, net_recv


def send_metrics(mac, name, ip, cpu, ram, disk, net_sent, net_recv):
    payload = {
        "mac": mac,
        "name": name,
        "ip": ip,
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "net_sent": net_sent,
        "net_recv": net_recv
    }

    try:
        r = requests.post(API_URL, json=payload, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_local_ip():
    import socket
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except:
        return None


def main():
    mac = get_mac_address()
    name = f"Device-{mac[-5:]}"
    ip = get_local_ip()

    print(f"Starting AGENT for MAC={mac}, IP={ip}")

    while True:
        cpu, ram, disk, net_sent, net_recv = collect_metrics()

        ok = send_metrics(
            mac, name, ip, cpu, ram, disk, net_sent, net_recv
        )

        print(
            f"[AGENT] CPU={cpu}% RAM={ram}% Disk={disk}% NetSent={net_sent} NetRecv={net_recv} -> {'OK' if ok else 'FAIL'}"
        )

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
