import socket
import sys

def check_murmur():
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        
        # Mumble UDP Ping packet (12 null bytes)
        ping = b'\x00' * 12
        
        # Send to localhost
        sock.sendto(ping, ('127.0.0.1', 64738))
        
        # Wait for response
        data, _ = sock.recvfrom(1024)
        
        if len(data) > 0:
            print(f"Healthy: Received {len(data)} bytes from Murmur")
            return True
    except Exception as e:
        print(f"Unhealthy: {e}")
        
    return False

if __name__ == "__main__":
    if check_murmur():
        sys.exit(0)
    else:
        sys.exit(1)
