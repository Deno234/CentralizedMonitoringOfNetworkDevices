import json
import time
from datetime import datetime
import sys

# Ensure these match your actual folder structure (e.g., utils folder)
from utils.ping import ping
from utils.network_scanner import get_arp_table_enhanced, discover_devices
from utils.local_ip import get_local_ip
from utils.api_client import send_ping

# Interval between device checks (seconds)
CHECK_INTERVAL = 5

# Perform full network sweep every N iterations (to discover new devices)
SWEEP_EVERY_N_ITERATIONS = 12  # Every 60 seconds if CHECK_INTERVAL = 5

iteration_count = 0


def load_devices():
    """Load devices from JSON configuration file"""
    try:
        with open("devices.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Error: devices.json not found!")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing devices.json: {e}")
        sys.exit(1)


def print_status(device_name, status, ip=None, mac=None):
    """Print formatted device status"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = "🟢 ONLINE " if status else "🔴 OFFLINE"
    ip_info = f" @ {ip}" if ip else ""
    mac_info = f" [{mac}]" if mac else ""
    print(f"[{ts}] {state} - {device_name}{ip_info}{mac_info}")


def send_device_status(mac, name, status, ip=None, latency=None):
    """Send device status to API and handle errors"""
    success = send_ping(
        mac=mac,
        name=name,
        status=1 if status else 0,
        ip=ip,
        latency=latency
    )

    if not success:
        print(f"  ⚠️  Warning: Failed to send status for {name} to API")

    return success


def main():
    """Main monitoring loop"""
    global iteration_count

    devices = load_devices()

    print("=" * 70)
    print("📡 NETWORK PING MONITOR WITH MAC IDENTIFICATION")
    print("=" * 70)
    print(f"Monitoring {len(devices)} devices")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print(f"Full network sweep: every {SWEEP_EVERY_N_ITERATIONS * CHECK_INTERVAL} seconds")
    print("=" * 70)
    print()

    # Display configured devices
    print("Configured devices:")
    for d in devices:
        is_self = " (THIS DEVICE)" if d.get("self") else ""
        print(f"  • {d['name']} - {d['mac']}{is_self}")
    print()

    while True:
        try:
            # Perform full sweep periodically to discover new devices
            perform_sweep = (iteration_count % SWEEP_EVERY_N_ITERATIONS == 0)

            iteration_count += 1

            if perform_sweep:
                print(f"🔍 Performing full network sweep (Scan #{iteration_count})...")

            # --- FIXED LOGIC HERE ---
            # We now call discover_devices which handles the sweep if perform_sweep is True
            arp_table = discover_devices(perform_sweep=perform_sweep)
            # ------------------------

            if not arp_table and not perform_sweep:
                print("⚠️  Warning: ARP table is empty. Network scanning may not be working.")

            if not perform_sweep:
                print(f"\n--- Scan #{iteration_count} ({datetime.now().strftime('%H:%M:%S')}) ---")

            print(f"Devices in ARP table: {len(arp_table)}")

            devices_checked = 0
            devices_online = 0

            for d in devices:
                devices_checked += 1

                # Normalize MAC address (handle both formats)
                mac = d["mac"].lower().replace("-", ":")
                name = d["name"]

                # Handle "self" device (the machine running this script)
                if d.get("self"):
                    ip = get_local_ip()
                    status = True
                    print_status(name, status, ip, mac)
                    send_device_status(mac, name, status, ip, None)
                    devices_online += 1
                    continue

                # Check if device is in ARP table
                if mac in arp_table:
                    device_info = arp_table[mac]
                    ip = device_info['ip']

                    # Ping the device to verify it's actually reachable
                    # Using 1000ms timeout
                    reachable = ping(ip, timeout=1000)

                    print_status(name, reachable, ip, mac)
                    send_device_status(mac, name, reachable, ip, None)

                    if reachable:
                        devices_online += 1
                else:
                    # Device not in ARP table - definitely offline
                    print_status(name, False, None, mac)
                    send_device_status(mac, name, False, None, None)

            # Summary
            devices_offline = devices_checked - devices_online
            print(f"\n📊 Summary: {devices_online} online, {devices_offline} offline (of {devices_checked} total)")

            # Show unknown devices in ARP table (not in our config)
            configured_macs = {d["mac"].lower().replace("-", ":") for d in devices}
            unknown_devices = [
                (mac, info['ip'])
                for mac, info in arp_table.items()
                if mac not in configured_macs
            ]

            if unknown_devices:
                print(f"\n🔍 Unknown devices in network ({len(unknown_devices)}):")
                for mac, ip in unknown_devices[:5]:  # Show first 5
                    print(f"  • {mac} @ {ip}")
                if len(unknown_devices) > 5:
                    print(f"  ... and {len(unknown_devices) - 5} more")

            print()

        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
            break
        except Exception as e:
            print(f"\n❌ Error during monitoring: {e}")
            import traceback
            traceback.print_exc()
            print("Continuing in 5 seconds...")

        # Wait before next check
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)