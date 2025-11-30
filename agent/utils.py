import uuid

def get_mac_address():
    mac_int = uuid.getnode()
    mac = ':'.join(f"{(mac_int >> ele) & 0xff:02x}"
                   for ele in range(40, -1, -8))
    return mac.lower()
