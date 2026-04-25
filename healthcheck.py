import socket
import sys
import os

def check_murmur():
    # Try multiple addresses to be safe
    targets = ['127.0.0.1', 'localhost']
    port = 64738
    
    for host in targets:
        try:
            print(f"DEBUG: Probing Murmur on {host}:{port} via UDP...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5) # Increased timeout
            
            # Mumble UDP Ping packet (12 null bytes)
            ping = b'\x00' * 12
            sock.sendto(ping, (host, port))
            
            data, addr = sock.recvfrom(1024)
            if len(data) > 0:
                print(f"SUCCESS: Received {len(data)} bytes from {addr}")
                return True
        except Exception as e:
            print(f"DEBUG: Failed to probe {host}: {e}")
            
    return False

if __name__ == "__main__":
    if check_murmur():
        print("RESULT: Healthy")
        sys.exit(0)
    else:
        print("RESULT: Unhealthy")
        sys.exit(1)
