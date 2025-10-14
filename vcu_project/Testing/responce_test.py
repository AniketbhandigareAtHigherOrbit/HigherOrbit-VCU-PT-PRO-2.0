
# -*- coding: utf-8 -*-
import can
import csv
import time
import threading
from datetime import datetime

# -------------------- Config --------------------
CAN_INTERFACE = "can0"
BITRATE = 500000
MOTOR_IDS = [4, 5, 6]         # Controller IDs
MAX_RPM = 1000
TEST_RPM = 500
SEND_INTERVAL_SEC = 0.2       # Adjustable send rate
TEST_DURATION_SEC = 120       # Total duration (s)
LOG_FILE = "controller_response_log_tx.csv"

# -------------------- Helper Functions --------------------
def motor_arbitration_id(motor_id):
    """Generate arbitration ID same as working logic."""
    return 0x0CF10000 | (motor_id << 8) | 0x1E

def build_can_data(rpm, direction):
    """Build CAN payload with direction toggle."""
    rpm = max(0, min(rpm, MAX_RPM))
    dir_flag = 0x01 if direction == "FWD" else 0x00
    return [
        rpm & 0xFF,          # Low byte
        (rpm >> 8) & 0xFF,   # High byte
        0x01,                # Enable
        dir_flag,            # Direction byte (0x01=FWD, 0x00=REV)
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
    """Thread to send commands alternately forward and reverse."""
    print("?? TX thread started.")
    direction = "FWD"

    while not stop_event.is_set():
        for motor_id in MOTOR_IDS:
            arb_id = motor_arbitration_id(motor_id)
            data = build_can_data(TEST_RPM, direction)
            msg = can.Message(arbitration_id=arb_id, data=data, is_extended_id=True)

            try:
                bus.send(msg)
                with lock:
                    writer.writerow([
                        datetime.now().isoformat(), "TX", direction, motor_id,
                        hex(arb_id), " ".join(f"{b:02X}" for b in data),
                        "", "", "", "", 0
                    ])
                print(f"[TX] {direction} ? Motor {motor_id} | ID={hex(arb_id)} Data={' '.join(f'{b:02X}' for b in data)}")
            except can.CanError as e:
                print(f"?? CAN send error (Motor {motor_id}): {e}")

        # Toggle direction each cycle
        direction = "REV" if direction == "FWD" else "FWD"
        time.sleep(SEND_INTERVAL_SEC)

    print("?? TX thread stopped.")

def rx_thread(bus, writer, lock, stop_event):
    """Thread to receive and decode feedback from controllers."""
    print("?? RX thread started.")
    while not stop_event.is_set():
        msg = bus.recv(timeout=0.1)
        if msg and 0x0CF11E04 <= msg.arbitration_id <= 0x0CF11E06:
            recv_time = datetime.now()
            device_id, rpm, current, voltage, error_code = decode_motor_response(msg.arbitration_id, msg.data)

            # Optional: infer direction from RPM sign
            direction = "FWD" if rpm >= 0 else "REV"

            with lock:
                writer.writerow([
                    recv_time.isoformat(), "RX", direction, device_id,
                    hex(msg.arbitration_id), " ".join(f"{b:02X}" for b in msg.data),
                    rpm, current, voltage, error_code, ""
                ])
            print(f"[RX] {direction} ? Motor {device_id}: RPM={rpm}  I={current:.1f}A  V={voltage:.1f}V  ERR={error_code}")
    print("?? RX thread stopped.")

# -------------------- Main --------------------
def main():
    bus = can.interface.Bus(channel=CAN_INTERFACE, bustype="socketcan")

    csv_file = open(LOG_FILE, mode="w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow([
        "timestamp", "direction_type", "direction", "motor_id", "message_id",
        "hex_data", "rpm", "current(A)", "voltage(V)", "error_code", "elapsed_ms"
    ])

    lock = threading.Lock()
    stop_event = threading.Event()

    tx = threading.Thread(target=tx_thread, args=(bus, csv_writer, lock, stop_event))
    rx = threading.Thread(target=rx_thread, args=(bus, csv_writer, lock, stop_event))

    print("?? Starting bidirectional controller response test...")
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
