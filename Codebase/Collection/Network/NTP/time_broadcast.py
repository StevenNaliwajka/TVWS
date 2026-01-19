#!/usr/bin/env python3
import socket
import time
import sys
'''

PUT ON THE PARENT PI

Command line example
python3 time_broadcast.py 192.176.0.255 5005

where 192.176.0.255 is the last ip address in the subnet chosen, as it is the broadcast address
the 5005 is the port it uses to transfer the data, if left empty it will default to 5005
best to leave empty as the receive script currently expects traffic on the 5005 port
'''

if len(sys.argv) < 2:
    print("Usage: python3 time_broadcast.py <broadcast_ip> [port]")
    print("Example: python3 time_broadcast.py 192.176.0.255 5005")
    sys.exit(1)

BROADCAST_IP = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

addr = (BROADCAST_IP, PORT)

print(f"Broadcasting time to {BROADCAST_IP}:{PORT}")

while True:
    t = time.time()
    sock.sendto(f"{t}".encode(), addr)
    time.sleep(1)