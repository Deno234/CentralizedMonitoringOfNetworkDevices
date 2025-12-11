import platform  # For recognizing OS
import subprocess  # For executing system commands
import math

"""
Ping function is defined that receives an IP address as a string and a timeout in milliseconds (default value 1000 ms).
The function returns a bool value depending on the success of the ping.
"""


def ping(ip: str, timeout: int = 1000) -> bool:
    system = platform.system().lower()

    # On windows, the -n parameter is used for the number of ping packets, while on other OSes (Linux, macOS) -c is used.
    packet_param = "-n" if system == "windows" else "-c"

    # The ping timeout parameter is set
    timeout_param = "-w" if system == "windows" else "-W"

    """
    Fix for timeout calculation:
    Windows takes milliseconds directly.
    Linux takes seconds.
    We must avoid passing '0' to Linux if timeout < 1000ms.
    """
    if system == "windows":
        # Windows expects milliseconds
        timeout_str = str(int(timeout))
    else:
        # Linux expects seconds. Use ceil to ensure 500ms becomes 1s, not 0s.
        # Or simply ensure min 1.
        timeout_seconds = math.ceil(timeout / 1000.0)
        timeout_str = str(int(timeout_seconds))

    """
    The ping command is executed with the parameter for the number of packets.
    """
    try:
        # Adding a slightly longer subprocess timeout than the ping timeout to let ping finish naturally
        proc_timeout = (timeout / 1000.0) + 1.0

        result = subprocess.run(
            ["ping", packet_param, "1", timeout_param, timeout_str, ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=proc_timeout
        )
        return result.returncode == 0
    except Exception:
        return False