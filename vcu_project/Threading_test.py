import threading
import time
import random

# -------------------- THREAD FUNCTIONS --------------------

def control_loop():
    data2=0
    """Simulates precise machine control loop."""
    while True:
        data2=data2+1
        #data2 = random.randint(0, 100)
        print("[CONTROL] Running control step...", data2)
        time.sleep(0.001) # 50 ms cycle (20 Hz)


def logging_loop():
    data=0
    """Simulates logging CAN/sensor data."""
    while True:
        data=data+1
        #data = random.randint(0, 100)
        print(f"[LOGGING] Logged data: {data}")
        time.sleep(0.001)  # Log every 500 ms


def safety_loop():
    data1=0
    """Simulates safety monitoring (emergency stop check)."""
    while True:
        data1=data1+1
        #data1 = random.randint(0, 100)
        print("[SAFETY] Safety check OK", data1)
        time.sleep(0.001)  # Safety check every 1 sec

# -------------------- MAIN --------------------
def main():
    # Create threads
    t1 = threading.Thread(target=control_loop, daemon=True)
    t2 = threading.Thread(target=logging_loop, daemon=True)
    t3 = threading.Thread(target=safety_loop, daemon=True)

    # Start threads
    t1.start()
    t2.start()
    t3.start()

    # Keep main alive
    data4=0
    while True:
        data4=data4+1
        #data1 = random.randint(0, 100)
        print("[main] Main loop check OK", data4)
        time.sleep(0.001)  # Safety check every 1 sec
        print("")


if __name__ == "__main__":
    main()
