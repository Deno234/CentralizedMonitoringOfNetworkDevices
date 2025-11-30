import subprocess # For executing system commands
import platform # For recognizing OS

def get_arp_table():
    """
    Reliably parses ARP table into dictionary  {mac: ip}
    Works on Windows, Linux and macOS operating systems.
    """
    system = platform.system().lower() # Retrieves OS name

    # Correct OS-dependent command for retrieving ARP table
    cmd = ["arp", "-a"] if system == "windows" else ["arp", "-n"]

    # Executes the command and retrieves the output in text format
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Splits command output into lines for easier parsing
    lines = result.stdout.splitlines()

    # Initializing an empty dictionary
    table = {}


    for line in lines:
        # The loop goes through each line of output, removes spaces and converts the text to lowercase
        line = line.strip().lower()

        # Skips blank lines and lines containing header characters like 'interface' or 'type'
        if not line or "interface" in line or "type" in line:
            continue

        # Splits the line into parts (assuming that the first part must be IP, the second MAC) and skips lines that do not have at least those two parts
        parts = line.split()
        if len(parts) < 2:
            continue

        ip = parts[0]
        mac = parts[1]



        """
        1. Checks if the MAC address is in the correct format (separated by dashes or colons).
        2. Normalizes the MAC address by using colons as a separator.
        3. Adds a MAC:IP pair to the dictionary.
        """
        if "-" in mac or ":" in mac:
            mac_norm = mac.replace("-", ":")
            table[mac_norm] = ip

    return table
