
# -*- coding: utf-8 -*-
import can
import csv
import time
import threading
from datetime import datetime

# ---------------- CONFIG ----------------
MOTOR_IDS = [4, 5, 6]         # Motor IDs to test
MAX_RPM = 1000
TEST_RPM = 500
TX_FREQUENCY_HZ = 5           # Hz, adjustable
LOG_FILE = "motor_response_log.csv"

# ----------------------------------------
def build_can_data(rpm, direction):
    """Build TX CAN frame data for controller command."""
    rpm = max(0, min(rpm, MAX_RPM))
    enable = 0x01
    dir_byte = 0x01 if direction == "FWD" else 0x02
    return [
        rpm & 0xFF,
        (rpm >> 8) & 0xFF,
        enable,
        dir_byte,
        0x00, 0x00, 0x00, 0x00
    ]


def motor_arbitration_id(motor_id):
    """0x0CF10000 + (MotorID << 8) + 0x1E"""
    return 0x0CF10000 | (motor_id << 8) | 0x1E


def decode_controller_feedback(msg_id, data):
    """Decode feedback frame (0x0CF11F00 + Device ID)."""
    device_id = msg_id - 0x0CF11F00

    rpm = (data[1] << 8) | data[0]
    controller_temp = data[2] - 40
    motor_temp = data[3] - 30

    status_byte = data[4]
    switch_byte = data[5]

    # Decode controller status bits
    feedback_state = (status_byte >> 3) & 0x03
    command_state = status_byte & 0x03
    feedback_dir = {0: "STOP", 1: "FWD", 2: "REV"}.get(feedback_state, "UNK")
    command_dir = {0: "STOP", 1: "FWD", 2: "REV"}.get(command_state, "UNK")

    # Switch signals
    forward_sw = bool((switch_byte >> 5) & 0x01)
    reverse_sw = bool((switch_byte >> 4) & 0x01)
    brake_sw = bool((switch_byte >> 3) & 0x01)
    hall_a = bool(switch_byte & 0x01)
    hall_b = bool((switch_byte >> 1) & 0x01)
    hall_c = bool((switch_byte >> 2) & 0x01)

    return {
        "device_id": device_id,
        "rpm": rpm,
        "controller_temp": controller_temp,
        "motor_temp": motor_temp,
        "feedback_dir": feedback_dir,
        "command_dir": command_dir,
        "forward_sw": forward_sw,
        "reverse_sw": reverse_sw,
        "brake_sw": brake_sw,
        "hall_a": hall_a,
        "hall_b": hall_b,
        "hall_c": hall_c
    }


def tx_thread(bus, stop_event):
    """Thread to transmit motor commands periodically."""
    period = 1.0 / TX_FREQUENCY_HZ
    csv_writer = csv.writer(open(LOG_FILE, "a", newline=""))
    csv_writer.writerow(["Timestamp", "Type", "MotorID", "Dir", "RPM", "ArbID", "CAN Data (HEX)"])

    direction_flag = True  # alternate between forward and reverse
    while not stop_event.is_set():
        direction = "FWD" if direction_flag else "REV"
        for motor_id in MOTOR_IDS:
            arb_id = motor_arbitration_id(motor_id)
            data = build_can_data(TEST_RPM, direction)
            msg = can.Message(arbitration_id=arb_id, data=data, is_extended_id=True)

            try:
                bus.send(msg)
                hex_data = " ".join(f"{b:02X}" for b in data)
                print(f"[TX] ID:0x{arb_id:X} ? Motor {motor_id} {direction} {TEST_RPM}rpm | {hex_data}")
                csv_writer.writerow([datetime.now(), "TX", motor_id, direction, TEST_RPM, f"0x{arb_id:X}", hex_data])
            except can.CanError as e:
                print(f"CAN send error: {e}")

        direction_flag = not direction_flag
        time.sleep(period)



def rx_thread(bus, stop_event):
    """Thread to receive and decode controller feedback."""
    csv_writer = csv.writer(open(LOG_FILE, "a", newline=""))
    while not stop_event.is_set():
        msg = bus.recv(0.1)
        if msg and (msg.arbitration_id & 0x0FFFFF00) == 0x0CF11F00:
            try:
                info = decode_controller_feedback(msg.arbitration_id, msg.data)
                print(f"[RX] Motor {info['device_id']} | {info['rpm']}rpm | Cmd:{info['command_dir']} | "
                      f"Fb:{info['feedback_dir']} | CtrlT:{info['controller_temp']}C | MotT:{info['motor_temp']}C")
                csv_writer.writerow([
                    datetime.now(), "RX", info["device_id"], info["feedback_dir"], info["rpm"],
                    f"0x{msg.arbitration_id:X}",
                    " ".join(f"{b:02X}" for b in msg.data)
                ])
            except Exception as e:
                print(f"RX decode error: {e}")


def main():
    bus = can.interface.Bus(channel='can0', bustype='socketcan')
    stop_event = threading.Event()

    tx = threading.Thread(target=tx_thread, args=(bus, stop_event))
    rx = threading.Thread(target=rx_thread, args=(bus, stop_event))
    tx.start()
    rx.start()

    print(f"--- Motor Response Test Running ---\n"
          f"Motors: {MOTOR_IDS}\nTX Frequency: {TX_FREQUENCY_HZ}Hz\nLogging to: {LOG_FILE}\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        tx.join()
        rx.join()
        print("Test stopped.")


if __name__ == "__main__":
    main()
