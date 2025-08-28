import time
import can
import RPi.GPIO as GPIO

# ---------- CONSTANTS ----------
STEP_TIMES = [1.0, 1.2, 1.5, 1.2, 1.0]
L_STEPS = [(2500, 1200), (2200, 1400), (1800, 1800), (1400, 2200), (1200, 2500)]
R_STEPS = [(1200, 2500), (1400, 2200), (1800, 1800), (2200, 1400), (2500, 1200)]
MAX_RPM = 3000

# ---------- GPIO ----------
LEFT_BTN_PIN = 22
RIGHT_BTN_PIN = 27
GPIO.setmode(GPIO.BCM)
GPIO.setup([LEFT_BTN_PIN, RIGHT_BTN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# ---------- TWIRL STATE ----------
twirl_active = False
twirl_direction_left = True
twirl_step = 0
twirl_step_start = 0

# ---------- CAN SETUP ----------
bus = can.interface.Bus(channel='can0', interface='socketcan')

def build_can_data(rpm, direction):
    rpm = max(0, min(rpm, MAX_RPM))
    return [
        rpm & 0xFF,
        (rpm >> 8) & 0xFF,
        0x01,
        direction,
        0x00, 0x00, 0x00, 0x00
    ]

def send_motor_rpm_with_dir(rpm_left, rpm_right, direction):
    data_left = build_can_data(rpm_left, direction)
    data_right = build_can_data(rpm_right, direction)

    id_left = 0x0CF10000 | (0x06 << 8) | 0x1E
    id_right = 0x0CF10000 | (0x04 << 8) | 0x1E

    bus.send(can.Message(arbitration_id=id_left, is_extended_id=True, data=data_left))
    time.sleep(0.1)
    bus.send(can.Message(arbitration_id=id_right, is_extended_id=True, data=data_right))
    time.sleep(0.1)

    print(f"SENT Left: {rpm_left} RPM, Right: {rpm_right} RPM")

def execute_twirl():
    global twirl_step, twirl_active, twirl_step_start
    now = time.monotonic()
    steps = L_STEPS if twirl_direction_left else R_STEPS

    if 1 <= twirl_step <= 5:
        rpm_left, rpm_right = steps[twirl_step - 1]
        send_motor_rpm_with_dir(rpm_left, rpm_right, 0x01)
        if now - twirl_step_start > STEP_TIMES[twirl_step - 1]:
            twirl_step += 1
            twirl_step_start = now
    else:
        twirl_step = 0
        twirl_active = False
        print(f"[TWIRL {'LEFT' if twirl_direction_left else 'RIGHT'}] Completed")

# ---------- MAIN LOOP ----------
try:
    print("Waiting for GPIO 22 (left twirl) or GPIO 27 (right twirl)...")
    while True:
        if not twirl_active:
            if GPIO.input(LEFT_BTN_PIN) == GPIO.HIGH:  # 3.3V = pressed
                twirl_direction_left = True
                twirl_active = True
                twirl_step = 1
                twirl_step_start = time.monotonic()
                print("Left twirl started!")
            elif GPIO.input(RIGHT_BTN_PIN) == GPIO.HIGH:
                twirl_direction_left = False
                twirl_active = True
                twirl_step = 1
                twirl_step_start = time.monotonic()
                print("Right twirl started!")
        else:
            execute_twirl()

except KeyboardInterrupt:
    print("Stopped by user.")
finally:
    GPIO.cleanup()
