
# control/on_road_mode.py
# -*- coding: utf-8 -*-

import time
import can
import RPi.GPIO as GPIO
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from canbus.can_utils import can_bus_correction
import subprocess

# ---------- CONSTANTS ----------

MAX_RPM = 1500
ROTARY_MAX_RPM = 1200
LONG_PRESS_RPM = base_rpm

LONG_PRESS_TIME = 0.2      # seconds to consider as long press
DOUBLE_PRESS_GAP = 0.40    # max time between taps for double press
SEND_PERIOD = 0.02          # periodic CAN refresh (10 Hz)

# Twirl pattern (both motors)
STEP_TIMES = [3.0, 8, 0.2, 0.2, 0.2]
L_STEPS = [(300, 300), (300, 100), (0, 0), (0, 0), (0, 0)]
R_STEPS = [(300, 300), (100, 300), (0, 0), (0, 0), (0, 0)]

# Feedback assist
RE_ALIGN_RPM_REDUCTION = 100   # how much to trim the faster motor
FEEDBACK_TOLERANCE = 50        # acceptable RPM difference before correcting
LOW_RPM_FEEDBACK_OFF = 300     # <--- ignore feedback below this RPM

# ---------- GPIO ----------
LEFT_BTN_PIN = 26
RIGHT_BTN_PIN = 22
MODE_SWITCH_PIN = 20
DIRECTION_BTN_PIN = 21
ROTARY_SWITCH_PIN = 16
SAFETY_PIN = 16

GPIO.setmode(GPIO.BCM)
GPIO.setup([LEFT_BTN_PIN, RIGHT_BTN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(MODE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(DIRECTION_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(ROTARY_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(SAFETY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# ---------- CAN ----------
bus = can.interface.Bus(channel='can0', interface='socketcan')

# ---------- STATE ----------
MODE_IDLE = 0
MODE_SINGLE_LEFT = 1
MODE_SINGLE_RIGHT = 2
MODE_TWIRL_LEFT = 3
MODE_TWIRL_RIGHT = 4

mode = MODE_IDLE

direction_btn_last_state = False  # Was LOW
current_direction = 0x01  # 0x01 = forward, 0x02 = reverse
last_direction_toggle = 0.0
DIRECTION_DEBOUNCE = 0.3  # seconds

left_pressed = False
right_pressed = False
left_press_start = 0.0
right_press_start = 0.0
left_last_rise = 0.0
right_last_rise = 0.0

twirl_step = 0
twirl_step_start = 0.0

last_send_time = 0.0

feedbackRPM_Left = 0
feedbackRPM_Right = 0


# ---------- ADS1115 ----------
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
throttle_channel = AnalogIn(ads, ADS.P0)  # Assuming throttle on A0
rotary_throttle_channel = AnalogIn(ads, ADS.P1)

# ---------- CAN Reset ----------
import os, time, can, subprocess

def reset_can_interface():
    """
    Reset CAN interface and return a new bus object.
    """
    try:
        print("?? Resetting can0 with bitrate 250000...")
        subprocess.run(["sudo", "ip", "link", "set", "can0", "down"], check=False)

        # small pause before setting up again
        time.sleep(0.3)

        result = subprocess.run(
            ["sudo", "ip", "link", "set", "can0", "up", "type", "can", "bitrate", "250000"],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"? Failed to bring can0 up: {result.stderr.strip()}")
            return None

        # give kernel a moment before binding
        time.sleep(0.5)

        print("? can0 reset successful, reconnecting bus...")
        new_bus = can.interface.Bus(channel="can0", bustype="socketcan")
        return new_bus

    except Exception as e:
        print(f"? CAN reset error: {e}")
        return None

# ---------- Safe Send (TX spacing) ----------
_last_send_tick = 0.0
def safe_send(msg, min_interval=0.005):
    """
    Send CAN frame with minimal spacing to avoid 'No buffer space available' (Err 105).
    """
    global _last_send_tick, bus
    now = time.time()
    gap = now - _last_send_tick
    if gap < min_interval:
        time.sleep(min_interval - gap)

    try:
        bus.send(msg, timeout=0.01)
    except can.CanError as e:
        if "No buffer space available" in str(e):
            reset_can_interface()
        else:
            print(f"Motor send failed: {e}")
        raise
    _last_send_tick = time.time()

# ---------- Feedback ----------
def read_feedback():
    global feedbackRPM_Left, feedbackRPM_Right
    try:
        msg = bus.recv(timeout=0.0)
        if msg is None:
            return
        recvId = msg.arbitration_id
        buf = msg.data
        if (recvId & 0xFF) == 0x05:
            feedbackRPM_Left = buf[0] | (buf[1] << 8)
            #print("Left feedbackRPM",feedbackRPM_Left) 
        elif (recvId & 0xFF) == 0x06:
            feedbackRPM_Right = buf[0] | (buf[1] << 8)
            #ACAprint("Right feedbackRPM",feedbackRPM_Right) 
    except Exception as e:
        print(f"Feedback read failed: {e}")


# ---------- Helpers ----------
def adc_to_rpm(value):
    rpm = int((value / 36535) * MAX_RPM)
    #print("given RMP",rpm )
    return max(0, min(rpm, MAX_RPM))

def is_twirl_mode_enabled():
    return GPIO.input(MODE_SWITCH_PIN) == GPIO.HIGH

def send_can_message(bus_obj, msg):
    """
    Wrapper to send CAN messages with auto-recovery.
    """
    try:
        safe_send(msg)

    except can.CanError as e:
        if "No buffer space available" in str(e) or "Network is down" in str(e):
            new_bus = reset_can_interface()
            if new_bus:
                bus = new_bus   # swap in the fixed bus
                try:
                    bus.send(msg, timeout=0.01)  # retry once
                except can.CanError as e2:
                    print(f"Retry after reset failed: {e2}")
        else:
            print(f"Motor send failed: {e}")

        return bus_obj
    return bus_obj

def toggle_direction():
    global current_direction
    current_direction = 0x02 if current_direction == 0x01 else 0x01
    print("Direction set to", "REVERSE" if current_direction == 0x02 else "FORWARD")

def build_can_data(rpm, direction):
    rpm = max(0, min(int(rpm), MAX_RPM))
    return [
        rpm & 0xFF,
        (rpm >> 8) & 0xFF,
        0x01,          # enable
        direction,     # 0x01 forward, 0x02 reverse, 0x00 stop
        0x00, 0x00, 0x00, 0x00
    ]

def build_rotary_can_data(rpm, direction):
    rpm = max(0, min(int(rpm), ROTARY_MAX_RPM))
    return [
        rpm & 0xFF,
        (rpm >> 8) & 0xFF,
        0x01,
        direction,
        0x00, 0x00, 0x00, 0x00
    ]

def send_rotary_motor_rpm(rpm, direction):
    """Send one frame to rotary motor (ID=4)."""
    try:
        arbitration_id = 0x0CF10000 | (0x05 << 8) | 0x1E
        msg = can.Message(
            arbitration_id=arbitration_id,
            is_extended_id=True,
            data=build_rotary_can_data(rpm, direction)
        )
        safe_send(msg)
    except can.CanError as e:
        if "No buffer space available" in str(e) or "Network is down" in str(e):
            new_bus = reset_can_interface()
            if new_bus:
                bus = new_bus   # swap in the fixed bus
                try:
                    bus.send(msg, timeout=0.01)  # retry once
                except can.CanError as e2:
                    print(f"Retry after reset failed: {e2}")
        else:
            print(f"Motor send failed: {e}")

def rotary_motor_stop():
    """Hard stop rotary motor."""
    send_rotary_motor_rpm(0, 0x00)

def send_motor_rpm_with_dir(rpm_left, rpm_right, direction):
    """Send one frame to each motor."""
    try:
        id_left = 0x0CF10000 | (0x06 << 8) | 0x1E
        id_right = 0x0CF10000 | (0x04 << 8) | 0x1E
        safe_send(can.Message(arbitration_id=id_left,  is_extended_id=True, data=build_can_data(rpm_left,  direction)))
        safe_send(can.Message(arbitration_id=id_right, is_extended_id=True, data=build_can_data(rpm_right, direction)))
    except can.CanError as e:
        if "No buffer space available" in str(e):
            reset_can_interface()
        else:
            print(f"Motor send failed: {e}")

def safe_stop():
    """Stop both motors once."""
    try:
        send_motor_rpm_with_dir(0, 0, 0x00)
    except Exception:
        pass

# ---------- Twirl ----------
def begin_twirl(left: bool):
    global mode, twirl_step, twirl_step_start
    if not is_twirl_mode_enabled():
        print("Twirl blocked: Mode switch is OFF")
        return
    mode = MODE_TWIRL_LEFT if left else MODE_TWIRL_RIGHT
    twirl_step = 1
    twirl_step_start = time.monotonic()
    print(f"Twirl {'LEFT' if left else 'RIGHT'} started")

def execute_twirl(now):
    global mode, twirl_step, twirl_step_start
    steps = L_STEPS if mode == MODE_TWIRL_LEFT else R_STEPS
    if 1 <= twirl_step <= len(steps):
        rpm_left, rpm_right = steps[twirl_step - 1]
        send_motor_rpm_with_dir(rpm_left, rpm_right, current_direction)
        if now - twirl_step_start > STEP_TIMES[twirl_step - 1]:
            twirl_step += 1
            twirl_step_start = now
    else:
        mode = MODE_IDLE
        twirl_step = 0
        print("Twirl completed")
        safe_stop()

# ---------- Buttons (YOUR ORIGINAL FUNCTION) ----------
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
                #ramp_motor(target_rpm=300)
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
                #ramp_motor(target_rpm=300)
                print("Single RIGHT started")

    if not right_now and right_pressed:
        if mode == MODE_SINGLE_RIGHT:
            safe_stop()
            mode = MODE_IDLE
            print("Single RIGHT stopped")
        right_pressed = False

# ---------- Drive ----------
def periodic_drive(now):
    global last_send_time, base_rpm
    if (now - last_send_time) < SEND_PERIOD:
        return
    last_send_time = now

    try:
        
        throttle_value = throttle_channel.value
        base_rpm = adc_to_rpm(throttle_value)
        # --------- Long press modes (ignore feedback + throttle) ---------
        if mode == MODE_SINGLE_LEFT:
            send_motor_rpm_with_dir(base_rpm, 0, current_direction)
            return
        elif mode == MODE_SINGLE_RIGHT:
            send_motor_rpm_with_dir(0, base_rpm, current_direction)
            return

        # --------- Normal throttle mode (with feedback) ---------
        throttle_value = throttle_channel.value
        base_rpm = adc_to_rpm(throttle_value)

        if base_rpm < 50:  # Dead zone
            safe_stop()
            return

        # Start with equal RPMs (open-loop)
        rpm_left = base_rpm
        rpm_right = base_rpm

        # -------- Feedback correction --------
        if base_rpm >= LOW_RPM_FEEDBACK_OFF:
            diff = feedbackRPM_Left - feedbackRPM_Right
            if abs(diff) > FEEDBACK_TOLERANCE:
                correction = int(0.1 * diff)
                if diff > 0:
                    rpm_left = max(0, rpm_left - correction)
                elif diff < 0:
                    rpm_right = max(0, rpm_right + correction)

        send_motor_rpm_with_dir(rpm_left, rpm_right, current_direction)

    except Exception as e:
        print(f"Throttle/feedback drive failed: {e}")
        safe_stop()

# ---------- Rotary ----------
def rotary_motor_step():
    
    """Runs a single step of rotary motor logic (independent of drive motors)."""
    if GPIO.input(MODE_SWITCH_PIN) == GPIO.LOW:
        rotary_motor_stop()
        return

    if GPIO.input(ROTARY_SWITCH_PIN) == GPIO.LOW:
        rotary_motor_stop()
        return

    try:
        throttle_value = rotary_throttle_channel.value
        throttle_rpm = adc_to_rpm(throttle_value)
        if throttle_rpm > 50:  # Dead zone
            send_rotary_motor_rpm(throttle_rpm, current_direction)
            print("send RPM ", throttle_rpm)
        else:
            rotary_motor_stop()
    except Exception as e:
        print(f"Rotary throttle read failed: {e}")
        rotary_motor_stop()

# ---------- MAIN STEP ----------
def on_road_mode_step():
    """
    Runs a single non-blocking step of On-Road logic.
    This should be called repeatedly from main().
    """
    now = time.monotonic()

    # ---------- DUAL BUTTON SAFETY ----------
    left_b = GPIO.input(LEFT_BTN_PIN) == GPIO.HIGH
    right_b = GPIO.input(RIGHT_BTN_PIN) == GPIO.HIGH

    if left_b and right_b:
        safe_stop()
        global mode
        mode = MODE_IDLE
        return

    # ---------- Direction Button Handling ----------
    global direction_btn_last_state, current_direction
    direction_now = GPIO.input(DIRECTION_BTN_PIN) == GPIO.HIGH
    if direction_now != direction_btn_last_state:   # detect ANY change
        toggle_direction()
    direction_btn_last_state = direction_now

    # ---------- Handle Button Presses ----------
    handle_button_edges(now)

    # ---------- Twirl Mode Execution ----------
    if mode in (MODE_TWIRL_LEFT, MODE_TWIRL_RIGHT):
        execute_twirl(now)
    else:
        periodic_drive(now)
        rotary_motor_step()
        read_feedback()

