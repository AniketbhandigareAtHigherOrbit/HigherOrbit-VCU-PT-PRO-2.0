# -*- coding: utf-8 -*-
import can
import csv
import time
import threading
from datetime import datetime

# -------------------- Config --------------------
CAN_INTERFACE = "can0"
BITRATE = 500000
MOTOR_IDS = [4, 5, 6]
MAX_RPM = 1000
TEST_RPM = 500
SEND_INTERVAL_SEC = 0.05
TEST_DURATION_SEC = 120  # Total test time (seconds)
LOG_FILE = "controller_response_log_0_05.csv"

# -------------------- Helper Functions --------------------
def motor_arbitration_id(motor_id):
    """Generate arbitration ID same as working logic."""
    return 0x0CF10000 | (motor_id << 8) | 0x1E

def build_can_data(rpm):
    """Build CAN payload using your working logic."""
    rpm = max(0, min(rpm, MAX_RPM))
    return [
        rpm & 0xFF,
        (rpm >> 8) & 0xFF,
        0x01,  # Enable
        0x01,  # Forward
        0x00, 0x00, 0x00, 0x00
    ]

def decode_motor_response(msg_id, data):
    """Decode feedback frame (0x0CF11E0406)."""
    device_id = msg_id - 0x0CF11E00
    rpm = (data[1] << 8) | data[0]
    current = ((data[3] << 8) | data[2]) / 10
    voltage = ((data[5] << 8) | data[4]) / 10
    error_code = (data[7] << 8) | data[6]
    return device_id, rpm, current, voltage, error_code

# -------------------- Thread Functions --------------------
def tx_thread(bus, writer, lock, stop_event):
    """Thread for sending motor commands periodically."""
    print("?? TX thread started.")
    while not stop_event.is_set():
        for motor_id in MOTOR_IDS:
            arb_id = motor_arbitration_id(motor_id)
            data = build_can_data(TEST_RPM)
            msg = can.Message(arbitration_id=arb_id, data=data, is_extended_id=True)

            try:
                bus.send(msg)
                with lock:
                    writer.writerow([
                        datetime.now().isoformat(), "TX", motor_id,
                        hex(arb_id), " ".join(f"{b:02X}" for b in data),
                        "", "", "", "", 0
                    ])
                print(f"[TX] Motor {motor_id} ? ID={hex(arb_id)} Data={' '.join(f'{b:02X}' for b in data)}")
            except can.CanError as e:
                print(f"?? CAN send error for Motor {motor_id}: {e}")

        time.sleep(SEND_INTERVAL_SEC)
    print("?? TX thread stopped.")

def rx_thread(bus, writer, lock, stop_event):
    """Thread for receiving and decoding motor responses."""
    print("?? RX thread started.")
    while not stop_event.is_set():
        msg = bus.recv(timeout=0.1)
        if msg and 0x0CF11E04 <= msg.arbitration_id <= 0x0CF11E06:
            recv_time = datetime.now()
            device_id, rpm, current, voltage, error_code = decode_motor_response(msg.arbitration_id, msg.data)
            with lock:
                writer.writerow([
                    recv_time.isoformat(), "RX", device_id,
                    hex(msg.arbitration_id), " ".join(f"{b:02X}" for b in msg.data),
                    rpm, current, voltage, error_code, ""
                ])
            print(f"[RX] Motor {device_id} ? RPM={rpm} I={current:.1f} V={voltage:.1f} ERR={error_code}")
    print("?? RX thread stopped.")


# -------------------- Main --------------------
def main():
    bus = can.interface.Bus(channel=CAN_INTERFACE, bustype="socketcan")

    csv_file = open(LOG_FILE, mode="w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow([
        "timestamp", "direction", "motor_id", "message_id", "hex_data",
        "rpm", "current(A)", "voltage(V)", "error_code", "elapsed_ms"
    ])

    lock = threading.Lock()
    stop_event = threading.Event()

    tx = threading.Thread(target=tx_thread, args=(bus, csv_writer, lock, stop_event))
    rx = threading.Thread(target=rx_thread, args=(bus, csv_writer, lock, stop_event))

    print("?? Starting controller response test...")
    tx.start()
    rx.start()

    start_time = time.time()
    try:
        while time.time() - start_time < TEST_DURATION_SEC:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n?? Interrupted by user.")
    finally:
        stop_event.set()
        tx.join()
        rx.join()
        csv_file.close()
        print(f"? Log saved as {LOG_FILE}")

# -------------------- Run --------------------
if __name__ == "__main__":
    main()
