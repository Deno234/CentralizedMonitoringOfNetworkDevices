import time
import psutil
import requests
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_package.utils import get_mac_address

API_URL = "http://localhost:5000/api/metrics"
INTERVAL = 5  # seconds


def get_local_ip():
    """Get local IP address"""
    import socket
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except:
        return None


class MetricsCollector:
    """
    Metrics collector that properly tracks network traffic rate
    """

    def __init__(self):
        self.last_net_io = None
        self.last_check_time = None

    def collect_metrics(self):
        """
        Collect system metrics

        Returns:
            tuple: (cpu, ram, disk, net_sent_rate, net_recv_rate)
        """
        # CPU and RAM are instantaneous values
        cpu = psutil.cpu_percent(interval=1)  # 1 second sample
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent

        # Network: Calculate rate of change (bytes per second)
        current_time = time.time()
        current_net_io = psutil.net_io_counters()

        if self.last_net_io is None or self.last_check_time is None:
            # First run - no previous data to compare
            net_sent_rate = 0
            net_recv_rate = 0
        else:
            # Calculate time elapsed
            time_diff = current_time - self.last_check_time

            if time_diff > 0:
                # Calculate bytes per second
                net_sent_rate = (current_net_io.bytes_sent - self.last_net_io.bytes_sent) / time_diff
                net_recv_rate = (current_net_io.bytes_recv - self.last_net_io.bytes_recv) / time_diff
            else:
                net_sent_rate = 0
                net_recv_rate = 0

        # Update for next iteration
        self.last_net_io = current_net_io
        self.last_check_time = current_time

        return cpu, ram, disk, net_sent_rate, net_recv_rate


def send_metrics(mac, name, ip, cpu, ram, disk, net_sent, net_recv):
    """Send metrics to API"""
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
    except Exception as e:
        print(f"    Error sending metrics: {e}")
        return False


def main():
    """Main agent loop"""
    # Get device info
    mac = get_mac_address()
    ip = get_local_ip()

    # Try to get hostname for more descriptive name
    try:
        import socket
        hostname = socket.gethostname()
        name = f"{hostname}"
    except:
        name = f"Device-{mac[-8:]}"

    print("=" * 70)
    print("📊 SYSTEM METRICS AGENT")
    print("=" * 70)
    print(f"Device Name: {name}")
    print(f"MAC Address: {mac}")
    print(f"IP Address:  {ip}")
    print(f"API URL:     {API_URL}")
    print(f"Interval:    {INTERVAL} seconds")
    print("=" * 70)
    print()

    # Initialize metrics collector
    collector = MetricsCollector()

    iteration = 0

    while True:
        try:
            iteration += 1

            # Collect metrics
            cpu, ram, disk, net_sent_rate, net_recv_rate = collector.collect_metrics()

            # Send to API
            ok = send_metrics(mac, name, ip, cpu, ram, disk, net_sent_rate, net_recv_rate)

            # Format output
            timestamp = datetime.now().strftime("%H:%M:%S")
            status = "✅ OK" if ok else "❌ FAIL"

            # Convert network rates to human-readable format
            def format_bytes(bytes_val):
                """Format bytes to KB/s or MB/s"""
                if bytes_val < 1024:
                    return f"{bytes_val:.1f} B/s"
                elif bytes_val < 1024 * 1024:
                    return f"{bytes_val / 1024:.1f} KB/s"
                else:
                    return f"{bytes_val / (1024 * 1024):.2f} MB/s"

            print(f"[{timestamp}] #{iteration:04d} | "
                  f"CPU: {cpu:5.1f}% | "
                  f"RAM: {ram:5.1f}% | "
                  f"Disk: {disk:5.1f}% | "
                  f"↑{format_bytes(net_sent_rate):>12} | "
                  f"↓{format_bytes(net_recv_rate):>12} | "
                  f"{status}")

        except KeyboardInterrupt:
            print("\n\n⏹️  Agent stopped by user")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

        # Wait before next collection
        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)