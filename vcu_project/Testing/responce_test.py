# -*- coding: utf-8 -*-
import can
import csv
import time
from datetime import datetime

# -------------------- Config --------------------
CAN_INTERFACE = "can0"
BITRATE = 500000
MOTOR_IDS = [4, 5, 6]   # Controller IDs
MAX_RPM = 1000
TEST_RPM = 500
SEND_INTERVAL_SEC = 1
TEST_DURATION_SEC = 120   # Total test time (seconds)

# -------------------- Helper Functions --------------------
def motor_arbitration_id(motor_id):
    """Generate arbitration ID same as working logic."""
    return 0x0CF10000 | (motor_id << 8) | 0x1E

def build_can_data(rpm):
    """Build CAN payload using your working logic."""
    rpm = max(0, min(rpm, MAX_RPM))
    return [
        rpm & 0xFF,          # Low byte
        (rpm >> 8) & 0xFF,   # High byte
        0x01,                # Enable
        0x01,                # Forward
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

# -------------------- Main Test --------------------
def main():
    bus = can.interface.Bus(channel=CAN_INTERFACE, bustype="socketcan")

    csv_file = open("controller_response_log.csv", mode="w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow([
        "timestamp", "direction", "motor_id", "message_id", "hex_data",
        "rpm", "current(A)", "voltage(V)", "error_code", "elapsed_ms"
    ])

    print("?? Starting controller response rate test... Press Ctrl+C to stop.")
    start_time = time.time()

    try:
        while time.time() - start_time < TEST_DURATION_SEC:
            for motor_id in MOTOR_IDS:
                arb_id = motor_arbitration_id(motor_id)
                data = build_can_data(TEST_RPM)
                msg = can.Message(arbitration_id=arb_id, data=data, is_extended_id=True)

                send_time = time.time()
                bus.send(msg)
                csv_writer.writerow([
                    datetime.now().isoformat(), "TX", motor_id,
                    hex(arb_id), " ".join(f"{b:02X}" for b in data),
                    "", "", "", "", 0
                ])
                print(f"TX ? Motor {motor_id}: ID={hex(arb_id)} Data={' '.join(f'{b:02X}' for b in data)}")

                # Wait for feedback frame (0x0CF11E0406)
                resp = bus.recv(timeout=0.5)
                if resp and 0x0CF11E04 <= resp.arbitration_id <= 0x0CF11E06:
                    recv_time = time.time()
                    elapsed = (recv_time - send_time) * 1000
                    device_id, rpm, current, voltage, error_code = decode_motor_response(resp.arbitration_id, resp.data)

                    csv_writer.writerow([
                        datetime.now().isoformat(), "RX", device_id,
                        hex(resp.arbitration_id), " ".join(f"{b:02X}" for b in resp.data),
                        rpm, current, voltage, error_code, f"{elapsed:.2f}"
                    ])
                    print(f"RX ? Motor {device_id}: rpm={rpm} cur={current:.1f} V={voltage:.1f} err={error_code} | {elapsed:.2f} ms")
                else:
                    print(f"?? Motor {motor_id}: No response within 500 ms")

                time.sleep(SEND_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("? Test interrupted manually.")

    finally:
        csv_file.close()
        print("? Log saved as controller_response_log.csv")

# -------------------- Run --------------------
if __name__ == "__main__":
    main()
