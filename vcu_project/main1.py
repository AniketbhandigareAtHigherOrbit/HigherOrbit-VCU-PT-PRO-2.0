import threading
import time
import random

# -------------------- THREAD FUNCTIONS --------------------

def control_loop():
    """Simulates precise machine control loop."""
    while True:
        print("[CONTROL] Running control step...")
        time.sleep(0.05)  # 50 ms cycle (20 Hz)


def logging_loop():
    """Simulates logging CAN/sensor data."""
    while True:
        data = random.randint(0, 100)
        print(f"[LOGGING] Logged data: {data}")
        time.sleep(0.5)  # Log every 500 ms


def safety_loop():
    """Simulates safety monitoring (emergency stop check)."""
    while True:
        print("[SAFETY] Safety check OK")
        time.sleep(1)  # Safety check every 1 sec


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
    while True:
        time.sleep(5)


if __name__ == "__main__":
    main()
