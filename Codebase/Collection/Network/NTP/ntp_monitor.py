import subprocess
import time

'''
This is run on the child pi to measure immediate time offsets between the Pis
example: 

python3 ntp_monitor.py

example output:
1735328254.123456 System time : 0.000372 seconds fast
1735328255.123911 System time : 0.000401 seconds fast
'''

def get_offset():
    out = subprocess.check_output(["chronyc", "tracking"]).decode()
    for line in out.splitlines():
        if "System time" in line:
            return line.strip()
    return "N/A"

while True:
    print(time.time(), get_offset())
    time.sleep(1)