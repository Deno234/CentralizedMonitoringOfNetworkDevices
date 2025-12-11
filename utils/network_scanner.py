import subprocess
import platform
import re
import socket
from typing import Dict, List, Tuple
import ipaddress
import concurrent.futures  # Added for parallel pinging


def get_local_network():
    """
    Get the local network range (e.g., 192.168.1.0/24)
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        ip_parts = local_ip.split('.')
        network = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
        return network, local_ip
    except Exception as e:
        print(f"Error getting local network: {e}")
        return "192.168.1.0/24", "127.0.0.1"


def get_arp_table_enhanced() -> Dict[str, Dict]:
    """
    Enhanced ARP table parser that returns more information
    Returns: {mac: {'ip': ip, 'interface': interface, 'type': type}}
    """
    system = platform.system().lower()
    cmd = ["arp", "-a"] if system == "windows" else ["arp", "-n"]

    try:
        # Increased timeout slightly for safety
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        lines = result.stdout.splitlines()
    except Exception as e:
        print(f"Error running ARP command: {e}")
        return {}

    table = {}
    current_interface = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if system == "windows" and "Interface:" in line:
            match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
            if match:
                current_interface = match.group(1)
            continue

        if any(keyword in line.lower() for keyword in ['internet', 'address', 'type', 'hwtype', 'flags']):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        ip = parts[0]
        mac = parts[1] if len(parts) > 1 else None

        if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
            continue

        if mac and ("-" in mac or ":" in mac):
            mac_norm = mac.lower().replace("-", ":")
            if mac_norm in ['ff:ff:ff:ff:ff:ff', '00:00:00:00:00:00']:
                continue

            table[mac_norm] = {
                'ip': ip,
                'interface': current_interface,
                'type': parts[2] if len(parts) > 2 else 'dynamic'
            }

    return table


def _ping_single_host(ip: str, timeout: int) -> str:
    """Helper function for threaded pinging"""
    system = platform.system().lower()
    packet_param = "-n" if system == "windows" else "-c"
    timeout_param = "-w" if system == "windows" else "-W"

    # Correct timeout logic: Windows uses ms, Linux uses seconds (usually)
    if system == "windows":
        timeout_val = str(int(timeout * 1000))
    else:
        # Ensure at least 1 second for Linux to avoid '0' error
        timeout_val = str(max(1, int(timeout)))

    try:
        subprocess.run(
            ["ping", packet_param, "1", timeout_param, timeout_val, str(ip)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 1
        )
        return str(ip)
    except Exception:
        return None


def ping_sweep(network: str = None, timeout: int = 1) -> List[str]:
    """
    Perform a PARALLEL ping sweep on the local network.
    """
    if network is None:
        network, _ = get_local_network()

    print(f"Performing parallel ping sweep on {network}...")

    try:
        network_obj = ipaddress.ip_network(network, strict=False)
    except ValueError as e:
        print(f"Invalid network: {e}")
        return []

    responsive_hosts = []

    # Limit to first 254 hosts
    max_hosts = min(254, network_obj.num_addresses - 2)
    hosts_to_scan = list(network_obj.hosts())[:max_hosts]

    # Use ThreadPoolExecutor for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(_ping_single_host, ip, timeout): ip for ip in hosts_to_scan}

        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            if result:
                responsive_hosts.append(result)

    print(f"Ping sweep complete. Found {len(responsive_hosts)} responsive hosts.")
    return responsive_hosts


def discover_devices(perform_sweep: bool = False) -> Dict[str, Dict]:
    """
    Main device discovery function
    """
    if perform_sweep:
        ping_sweep()  # Now fast!

    devices = get_arp_table_enhanced()

    if perform_sweep:
        print(f"Discovered {len(devices)} devices on the network")

    return devices


# For backward compatibility
def get_arp_table() -> Dict[str, str]:
    enhanced = get_arp_table_enhanced()
    return {mac: info['ip'] for mac, info in enhanced.items()}