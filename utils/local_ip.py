import socket # Allows working with network interfaces and protocols

# This function returns the local IP address of the device
def get_local_ip():
    # A new socket is created that uses IPv4 addressing (AF_INET) and UDP protocol (SOCK_DGRAM)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        """
        The socket 'connects' to IP address 8.8.8.8 (Google DNS server) on port 80, although no actual connection is established.
        It is only important that the socket determines its own IP address that it would use for that connection.
        """
        s.connect(("8.8.8.8", 80))

        # It retrieves the IP address of the local device (used by the socket for that imaginary connection), which gives the actual local IP address.
        ip = s.getsockname()[0]

    except Exception:
        # If an error occurs (e.g. no network connection), the local IP address of the loopback interface 127.0.0.1 is returned.
        ip = "127.0.0.1"

    finally:
        # The socket is closed and resources are released.
        s.close()

    return ip

