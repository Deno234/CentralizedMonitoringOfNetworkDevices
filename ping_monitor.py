import json # To work with JSON files
import time # For breaks between checks
from datetime import datetime # To retrieve and format the current time

from utils.ping import ping # For testing device availability
from utils.arp_scan import get_arp_table # For retrieving the ARP table
from utils.local_ip import get_local_ip # For retrieving one's own local IP address

# Defines the interval between device rechecks (every 5 seconds)
CHECK_INTERVAL = 5


# Loads from the 'devices.json' file information about devices, as a list of dictionary objects
def load_devices():
    with open("devices.json", "r", encoding="utf-8") as f:
        return json.load(f)


# Formats and prints the device status with time, name, optional IP address and status (ONLINE/OFFLINE)
def print_status(device_name, status, ip=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = "ONLINE" if status else "OFFLINE"
    ip_info = f" @ {ip}" if ip else ""
    print(f"[{ts}] {device_name}{ip_info} -> {state}")


"""
1. Loads the ARP table
2. For each device from the JSON file:
    2.1. Normalizes the MAC address.
    2.2. If the device is marked as 'self' (local computer), it retrieves the local IP and considers it online.
    2.3. Otherwise, it looks for the MAC in the ARP table.
    2.4. If there is an IP, it pings the device and prints the status.
    2.5. If there is no MAC in the ARP table, it says that it is offline.
    2.6. Pauses for 5 seconds between iterations.
"""
def main():
    devices = load_devices()
    print("Pokrećem ping monitor s MAC identifikacijom...\n")

    while True:
        arp_table = get_arp_table()

        for d in devices:
            mac = d["mac"].lower().replace("-", ":")
            name = d["name"]

            if d.get("self"):
                ip = get_local_ip()
                status = True
                print_status(name, status, ip)
                continue

            if mac in arp_table:
                ip = arp_table[mac]
                reachable = ping(ip)
                print_status(name, reachable, ip)

            else:
                print_status(name, False)

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
