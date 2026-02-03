"""
Android Agent - No Root Required
Works around Android/Termux permission restrictions with the help of ADB
"""

import time
import requests
import sys
import uuid
import os
from datetime import datetime
import re
import subprocess
# ==================== CONFIGURATION ====================
SERVER_IP = "192.168.1.11"
SERVER_PORT = 5000
API_URL = f"http://{SERVER_IP}:{SERVER_PORT}/api/metrics"
INTERVAL = 10  # seconds
# ======================================================


def get_mac_address():
    """Get MAC address"""
#    mac_int = uuid.getnode()
#    mac = ':'.join(f"{(mac_int >> ele) & 0xff:02x}"
#                   for ele in range(40, -1, -8))

    mac = 'de:e4:e2:5a:d9:8d'
    return mac.lower()


def get_local_ip():
    """Get local IP address"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return None



def get_memory_usage():
    """Get memory usage without psutil"""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            mem_total = 0
            mem_available = 0

            for line in lines:
                if line.startswith('MemTotal:'):
                    mem_total = int(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    mem_available = int(line.split()[1])

            if mem_total > 0:
                mem_used = mem_total - mem_available
                return (mem_used / mem_total) * 100
    except:
        pass

    return 0.0


def get_disk_usage():
    """Get disk usage using df command"""
    try:
        import subprocess
        result = subprocess.run(['df', '/data'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 5:
                # Parse percentage (remove % sign)
                return float(parts[4].rstrip('%'))
    except:
        pass

    return 0.0





def get_cpu_usage():
    try:
        cmd = "adb shell top -n 1 -b | head -n 10"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        for line in result.stdout.split('\n'):
            l = line.lower()
            if '%cpu' in l and 'idle' in l:
                parts = l.split()

                total_cpu = None
                idle_val = None

                # nađi npr. '800%cpu'
                for p in parts:
                    if '%cpu' in p:
                        num = p.replace('%cpu', '').strip()
                        if num.endswith('%'):
                            num = num[:-1]
                        total_cpu = float(num)
                        break

                # nađi npr. '679%idle'
                for p in parts:
                    if 'idle' in p:
                        num = p.replace('%idle', '').strip()
                        if num.endswith('%'):
                            num = num[:-1]
                        idle_val = float(num)
                        break

                if total_cpu is None or idle_val is None:
                    return 0.0

                cores = max(1.0, total_cpu / 100.0)
                usage = (total_cpu - idle_val) / cores
                return round(usage, 2)

        return 0.0
    except Exception:
        return 0.0

def get_network_stats():
    try:
        # Poziva se samo sekcija sa statistikama sučelja radi brzine
        result = subprocess.run(
            ['adb', 'shell', 'dumpsys', 'netstats'],
            capture_output=True, text=True, timeout=5
        )

        output = result.stdout

        # Tražim se "mIfaceStatsMap"
        # Format u logu: ifaceName rxBytes rxPackets txBytes txPackets
        # Primjer: wlan0 3105779908 2501003 199790974 716499

        stats = {}
        # Regex koji traži ime sučelja i brojeve bajtova nakon njega
        pattern = r"(\w+)\s+(\d+)\s+\d+\s+(\d+)\s+\d+"

        matches = re.findall(pattern, output)

        total_rx = 0
        total_tx = 0

        for iface, rx, tx in matches:
            if iface in ['wlan0', 'rmnet0', 'rmnet1', 'rmnet2']:
                total_rx += int(rx)
                total_tx += int(tx)

        return total_tx, total_rx  # Vraća ukupne bajtove
    except Exception as e:
        print(f"Greška pri čitanju mreže: {e}")
        return 0, 0


class MetricsCollector:
    """Metrics collector without psutil dependency"""

    def __init__(self):
        self.last_net_sent = None
        self.last_net_recv = None
        self.last_check_time = None

    def collect_metrics(self):
        """Collect system metrics"""
        cpu = get_cpu_usage()
        ram = get_memory_usage()
        disk = get_disk_usage()

        # Network rate calculation
        current_time = time.time()
        net_sent, net_recv = get_network_stats()

        if self.last_net_sent is None or self.last_check_time is None:
            net_sent_rate = 0
            net_recv_rate = 0
        else:
            time_diff = current_time - self.last_check_time
            if time_diff > 0:
                net_sent_rate = (net_sent - self.last_net_sent) / time_diff
                net_recv_rate = (net_recv - self.last_net_recv) / time_diff
            else:
                net_sent_rate = 0
                net_recv_rate = 0

        self.last_net_sent = net_sent
        self.last_net_recv = net_recv
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
        r = requests.post(API_URL, json=payload, timeout=5)
        return r.status_code == 200
    except Exception as e:
        return False


def test_connection():
    """Test connection to server"""
    health_url = f"http://{SERVER_IP}:{SERVER_PORT}/api/health"
    try:
        r = requests.get(health_url, timeout=5)
        return r.status_code == 200
    except:
        return False


def main():
    """Main agent loop"""
    mac = get_mac_address()
    ip = get_local_ip()
    name = "Smartphone Denis"

    # Check for diagnostic mode
    diagnostic = len(sys.argv) > 1 and sys.argv[1] == '--test'

    print("=" * 60)
    print("📱 ANDROID AGENT (NO ROOT)")
    print("=" * 60)
    print(f"Device:      {name}")
    print(f"MAC:         {mac}")
    print(f"IP:          {ip}")
    print(f"Server:      {SERVER_IP}:{SERVER_PORT}")
    print("=" * 60)

    if diagnostic:
        print("\n🔍 DIAGNOSTIC MODE")
        print("Testing all metric collection methods...\n")

        print("CPU Usage:")
        cpu = get_cpu_usage()
        print(f"  Result: {cpu:.1f}%\n")

        print("Memory Usage:")
        ram = get_memory_usage()
        print(f"  Result: {ram:.1f}%\n")

        print("Disk Usage:")
        disk = get_disk_usage()
        print(f"  Result: {disk:.1f}%\n")

        print("Network Stats:")
        sent, recv = get_network_stats()
        print(f"  Sent: {sent:,} bytes")
        print(f"  Recv: {recv:,} bytes\n")

        print("Waiting 5 seconds to test rate calculation...")
        time.sleep(5)
        sent2, recv2 = get_network_stats()
        time_diff = 5.0
        sent_rate = (sent2 - sent) / time_diff
        recv_rate = (recv2 - recv) / time_diff
        print(f"  Upload rate: {sent_rate:.1f} B/s")
        print(f"  Download rate: {recv_rate:.1f} B/s\n")

        sys.exit(0)

    print("\n🔍 Testing connection...")
    if not test_connection():
        print("❌ Cannot connect to server!")
        print(f"   Check SERVER_IP: {SERVER_IP}")
        print("\n💡 Run with --test flag to diagnose metrics:")
        print("   python agent_android_noroot.py --test")
        sys.exit(1)

    print("✅ Connected!\n")
    print("💡 Tip: Run 'python agent_android_noroot.py --test' to diagnose issues\n")

    collector = MetricsCollector()
    iteration = 0

    while True:
        try:
            iteration += 1
            cpu, ram, disk, net_sent_rate, net_recv_rate = collector.collect_metrics()
            ok = send_metrics(mac, name, ip, cpu, ram, disk, net_sent_rate, net_recv_rate)

            timestamp = datetime.now().strftime("%H:%M:%S")
            status = "✅" if ok else "❌"

            def fmt(b):
                if b < 1024: return f"{b:.0f}B/s"
                elif b < 1024*1024: return f"{b/1024:.1f}KB/s"
                else: return f"{b/(1024*1024):.1f}MB/s"

            print(f"[{timestamp}] #{iteration:03d} | "
                  f"CPU:{cpu:4.0f}% | RAM:{ram:4.0f}% | "
                  f"↑{fmt(net_sent_rate):>8} ↓{fmt(net_recv_rate):>8} {status}")

        except KeyboardInterrupt:
            print("\n\n⏹️ Stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)