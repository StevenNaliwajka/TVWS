import socket, time

'''
PUT ON THE CHILD PIs
example command line:
python3 time_receive.py

Opens pi to receive the traffic being sent by the parent pi
will output the time offset including any network delays

example output:

Offset: 0.0047 s
Offset: 0.0019 s
Offset: 0.0061 s
'''

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", 5005))

while True:
    data, _ = sock.recvfrom(1024)
    t_master = float(data.decode())
    t_local = time.time()
    print(f"Offset: {t_local - t_master:.6f} s")