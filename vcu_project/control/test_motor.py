# -*- coding: utf-8 -*-
import can
import time

# Settings
MAX_RPM = 1000
TEST_RPM = 500  # Test RPM
motor_ids = [4, 5, 6]  # Motor IDs to test
SEND_INTERVAL = 2  # seconds between each motor test

# Function to generate arbitration ID
def motor_arbitration_id(motor_id):
    return 0x0CF10000 | (motor_id << 8) | 0x1E

# Build CAN data as per Arduino buildCanData()
def build_can_data(rpm):
    rpm = max(0, min(rpm, MAX_RPM))
    return [
        rpm & 0xFF,          # Low byte
        (rpm >> 8) & 0xFF,   # High byte
        0x01,                # Enable
        0x01,                # Forward
        0x00, 0x00, 0x00, 0x00
    ]

def main():
    bus = can.interface.Bus(channel='can0', bustype='socketcan')

    try:
        print("Starting one-by-one motor test for IDs:", motor_ids)
        while True:
            for motor_id in motor_ids:
                arb_id = motor_arbitration_id(motor_id)
                data = build_can_data(TEST_RPM)
                msg = can.Message(arbitration_id=arb_id,
                                  data=data,
                                  is_extended_id=True)
                try:
                    bus.send(msg)
                    print(f"Sent ? Motor {motor_id} (ID: 0x{arb_id:X}) ? RPM {TEST_RPM}")
                except can.CanError as e:
                    print(f"Error sending to Motor {motor_id}: {e}")

                time.sleep(SEND_INTERVAL)  # Wait before next motor

    except KeyboardInterrupt:
        print("Stopping motor test.")

if __name__ == "__main__":
    main()
