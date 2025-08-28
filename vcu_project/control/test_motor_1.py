import can
import time

# ---------- CONFIG ----------
MAX_RPM = 3000
TEST_RPM = 1500
CONTROLLER_ID = 5  # target controller ID

# ---------- CAN SETUP ----------
bus = can.interface.Bus(channel='can0', bustype='socketcan')

def build_can_data(rpm):
    rpm = max(0, min(rpm, MAX_RPM))
    data = [
        rpm & 0xFF,
        (rpm >> 8) & 0xFF,
        0x01,  # enable
        0x01,  # forward
        0x00, 0x00, 0x00, 0x00
    ]
    return data

def send_motor_rpm(rpm):
    arbitration_id = 0x0CF10000 | (CONTROLLER_ID << 8) | 0x1E
    msg = can.Message(arbitration_id=arbitration_id,
                      data=build_can_data(rpm),
                      is_extended_id=True)
    try:
        bus.send(msg)
        print(f"SENT ? ID=0x{arbitration_id:X}, RPM={rpm}, Data={msg.data}")
    except can.CanError:
        print("CAN send failed")

# ---------- MAIN TEST ----------
try:
    while True:
        send_motor_rpm(TEST_RPM)
        time.sleep(1)  # send every 1 sec

except KeyboardInterrupt:
    print("Test stopped")
