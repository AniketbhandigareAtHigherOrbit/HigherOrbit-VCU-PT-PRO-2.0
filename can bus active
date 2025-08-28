import os
import time

def check_can0():
    result = os.popen("ip link show can0").read()
    if "DOWN" in result:
        print("can0 is DOWN. Restarting...")
        os.system("sudo ip link set can0 down")
        os.system("sudo ip link set can0 type can bitrate 500000 restart-ms 100")
        os.system("sudo ip link set can0 up")
    else:
        print("can0 is UP.")

while True:
    check_can0()
    time.sleep(60)
