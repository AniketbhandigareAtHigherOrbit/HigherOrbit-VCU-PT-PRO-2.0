#control/on_road_mode.py
# -*- coding: utf-8 -*-

import time
import can
import RPi.GPIO as GPIO

# ---------- CONSTANTS ----------
MAX_RPM = 3000
LONG_PRESS_TIME = 0.2      # seconds to consider as long press
DOUBLE_PRESS_GAP = 0.40    # max time between taps for double press
LONG_PRESS_RPM = 2000
SEND_PERIOD = 0.05         # periodic CAN refresh (20 Hz) to keep controller latched

# ---------------- Constants ----------------

TWIRL_RPM = 500          # For twirl mode rotary motor

# Rotary motor constants
ROTARY_MAX_RPM = 2500
ROTARY_MIN_RPM = 800
ROTARY_ONOFF_PIN = 26   # Change as per wiring
ROTARY_TWIRL_RPM = 100
# Twirl pattern (both motors)
STEP_TIMES = [1.0, 1.2, 1.5, 1.2, 1.0]
L_STEPS = [(2500, 1200), (2200, 1400), (1800, 1800), (1400, 2200), (1200, 2500)]
R_STEPS = [(1200, 2500), (1400, 2200), (1800, 1800), (2200, 1400), (2500, 1200)]

# ---------- GPIO ----------
LEFT_BTN_PIN = 22
RIGHT_BTN_PIN = 27
GPIO.setmode(GPIO.BCM)
GPIO.setup([LEFT_BTN_PIN, RIGHT_BTN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(ROTARY_ONOFF_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# ---------- CAN ----------
bus = can.interface.Bus(channel='can0', interface='socketcan')

# ---------- STATE ----------
MODE_IDLE = 0
MODE_SINGLE_LEFT = 1
MODE_SINGLE_RIGHT = 2
MODE_TWIRL_LEFT = 3
MODE_TWIRL_RIGHT = 4

mode = MODE_IDLE

# per-button timing
left_pressed = False
right_pressed = False
left_press_start = 0.0
right_press_start = 0.0
left_last_rise = 0.0
right_last_rise = 0.0

# twirl state
twirl_step = 0
twirl_step_start = 0.0

# periodic send throttling
last_send_time = 0.0


# ---------- Helpers ----------
def build_can_data(rpm, direction):
    rpm = max(0, min(int(rpm), MAX_RPM))
    return [
        rpm & 0xFF,
        (rpm >> 8) & 0xFF,
        0x01,          # enable
        direction,     # 0x01 forward, 0x00 stop
        0x00, 0x00, 0x00, 0x00
    ]


def send_motor_rpm_with_dir(rpm_left, rpm_right, direction):
    """Send one frame to each main motor."""
    id_left = 0x0CF10000 | (0x06 << 8) | 0x1E
    id_right = 0x0CF10000 | (0x04 << 8) | 0x1E
    bus.send(can.Message(arbitration_id=id_left,  is_extended_id=True, data=build_can_data(rpm_left,  direction)))
    bus.send(can.Message(arbitration_id=id_right, is_extended_id=True, data=build_can_data(rpm_right, direction)))


def send_rotary_motor(rpm_rotary, direction):
    """Send one frame to rotary motor (ID 4)."""
    id_rotary = 0x0CF10000 | (0x05 << 8) | 0x1E  # ID for rotary motor
    bus.send(can.Message(arbitration_id=id_rotary, is_extended_id=True, data=build_can_data(rpm_rotary, direction)))


def safe_stop():
    """Stop all motors."""
    try:
        send_motor_rpm_with_dir(0, 0, 0x00)
        send_rotary_motor(0, 0x00)
    except Exception:
        pass


def begin_twirl(left: bool):
    global mode, twirl_step, twirl_step_start
    mode = MODE_TWIRL_LEFT if left else MODE_TWIRL_RIGHT
    twirl_step = 1
    twirl_step_start = time.monotonic()
    print(f"Twirl {'LEFT' if left else 'RIGHT'} started")


def execute_twirl(now):
    global mode, twirl_step, twirl_step_start
    steps = L_STEPS if mode == MODE_TWIRL_LEFT else R_STEPS
    if 1 <= twirl_step <= len(steps):
        rpm_left, rpm_right = steps[twirl_step - 1]
        send_motor_rpm_with_dir(rpm_left, rpm_right, 0x01)
        if now - twirl_step_start > STEP_TIMES[twirl_step - 1]:
            twirl_step += 1
            twirl_step_start = now
    else:
        mode = MODE_IDLE
        twirl_step = 0
        print("Twirl completed")
        safe_stop()


def handle_button_edges(now):
    """Detect button presses and update mode."""
    global left_pressed, right_pressed
    global left_press_start, right_press_start
    global left_last_rise, right_last_rise
    global mode

    # -------- LEFT BUTTON --------
    left_now = GPIO.input(LEFT_BTN_PIN) == GPIO.HIGH

    if left_now and not left_pressed:  # Rising edge
        if (now - left_last_rise) <= DOUBLE_PRESS_GAP:
            begin_twirl(left=True)
        else:
            left_press_start = now
        left_last_rise = now
        left_pressed = True

    if left_now and left_pressed:
        if mode in (MODE_IDLE, MODE_SINGLE_LEFT, MODE_SINGLE_RIGHT):
            if (now - left_press_start) >= LONG_PRESS_TIME and mode != MODE_SINGLE_LEFT:
                mode = MODE_SINGLE_LEFT
                print("Single LEFT started")

    if not left_now and left_pressed:  # Release
        if mode == MODE_SINGLE_LEFT:
            safe_stop()
            mode = MODE_IDLE
            print("Single LEFT stopped")
        left_pressed = False

    # -------- RIGHT BUTTON --------
    right_now = GPIO.input(RIGHT_BTN_PIN) == GPIO.HIGH

    if right_now and not right_pressed:
        if (now - right_last_rise) <= DOUBLE_PRESS_GAP:
            begin_twirl(left=False)
        else:
            right_press_start = now
        right_last_rise = now
        right_pressed = True

    if right_now and right_pressed:
        if mode in (MODE_IDLE, MODE_SINGLE_LEFT, MODE_SINGLE_RIGHT):
            if (now - right_press_start) >= LONG_PRESS_TIME and mode != MODE_SINGLE_RIGHT:
                mode = MODE_SINGLE_RIGHT
                print("Single RIGHT started")

    if not right_now and right_pressed:
        if mode == MODE_SINGLE_RIGHT:
            safe_stop()
            mode = MODE_IDLE
            print("Single RIGHT stopped")
        right_pressed = False

def periodic_drive(now):
    """Send periodic CAN frames."""
    global last_send_time
    if (now - last_send_time) < SEND_PERIOD:
        returns
    last_send_time = now

    # ---------------- Drive main motors ----------------
    if mode == MODE_SINGLE_LEFT:
        send_motor_rpm_with_dir(LONG_PRESS_RPM, 0, 0x01)
    elif mode == MODE_SINGLE_RIGHT:
        send_motor_rpm_with_dir(0, LONG_PRESS_RPM, 0x01)

    # ---------------- Rotary motor logic ----------------
    rotary_on = GPIO.input(ROTARY_ONOFF_PIN) == GPIO.HIGH
    print("Rotary On:", rotary_on)

    if rotary_on:
        # Check if in twirl mode
        if mode in (MODE_TWIRL_LEFT, MODE_TWIRL_RIGHT):
            # Twirl RPM
            send_rotary_motor(ROTARY_TWIRL_RPM, 0x01)
        else:
            # Normal long press RPM
            send_rotary_motor(ROTARY_MAX_RPM, 0x01)
    else:
        send_rotary_motor(0, 0x00)



# ---------- MAIN STEP ----------
def on_road_mode_step():
    """
    Runs a single non-blocking step of On-Road logic.
    This should be called repeatedly from main()s
    """
    now = time.monotonic()
    handle_button_edges(now)
    if mode in (MODE_TWIRL_LEFT, MODE_TWIRL_RIGHT):
        execute_twirl(now)
    periodic_drive(now)
