import platform # For recognizing OS
import subprocess # For executing system commands

"""
Ping function is defined that receives an IP address as a string and a timeout in milliseconds (default value 1000 ms).
The function returns a bool value depending on the success of the ping.
"""
def ping(ip: str, timeout: int = 1000) -> bool:

    # On windows, the -n parameter is used for the number of ping packets, while on other OSes (Linux, macOS) -c is used.
    packet_param = "-n" if platform.system().lower() == "windows" else "-c"

    # The ping timeout parameter is set
    timeout_param = "-w" if platform.system().lower() == "windows" else "-W"

    """
    The ping command is executed with the parameter for the number of packets, timeout (converted to seconds) and IP address.
    stdout and stderr are redirected to DEVNULL so that the printed output is not seen on the screen.
    The function returns True if the return code of the subprocess is 0 (which means the ping succeeded), otherwise False.
    """
    try:
        result = subprocess.run(
            ["ping", packet_param, "1", timeout_param, str(int(timeout/1000)), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except Exception:
        return False
