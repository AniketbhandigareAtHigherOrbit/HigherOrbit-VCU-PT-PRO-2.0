# control/on_road_mode.py
# -*- coding: utf-8 -*-

import threading
import state
import time
import can
import RPi.GPIO as GPIO
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
#from canbus.can_utils import can_bus_correction
import subprocess
from control.motor_manager import MotorManager

# Feedback assist
RE_ALIGN_RPM_REDUCTION = 100   # how much to trim the faster motor
FEEDBACK_TOLERANCE = 50        # acceptable RPM difference before correcting
LOW_RPM_FEEDBACK_OFF = 300     # <--- ignore feedback below

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

# ---------- ADS1115 ----------
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
throttle_channel = AnalogIn(ads, ADS.P0)
rotary_throttle_channel = AnalogIn(ads, ADS.P1)

def adc_to_rpm(value):
    """Convert ADC throttle value to RPM (clamped)."""
    rpm = int((value / 36535) * state.MAX_RPM_ON_ROAD)  # use ON_ROAD limit
    return max(0, min(rpm, state.MAX_RPM_ON_ROAD))

def is_twirl_mode_enabled():
    """Check if mode switch is ON (Twirl enabled)."""
    return GPIO.input(state.MODE_SWITCH_PIN) == GPIO.HIGH

def toggle_direction():
    """Safely toggle drive direction."""
    state.current_direction = (
        0x02 if state.current_direction == 0x01 else 0x01
    )
    print(
        "Direction set to",
        "REVERSE" if state.current_direction == 0x02 else "FORWARD"
    )

def begin_twirl(left: bool):
    """Start twirl sequence (LEFT or RIGHT)."""
    # if not is_twirl_mode_enabled():
    #     print("Twirl blocked: Mode switch is OFF")
    #     return
    state.mode = state.MODE_TWIRL_LEFT if left else state.MODE_TWIRL_RIGHT
    state.twirl_step = 1
    state.twirl_step_start = time.monotonic()
    print(f"Twirl {'LEFT' if left else 'RIGHT'} started")

def execute_twirl(now, motor_manager):
    """Run twirl sequence step-by-step."""
    mode = state.mode
    twirl_step = state.twirl_step
    twirl_step_start = state.twirl_step_start
    current_direction = state.current_direction

    steps = state.L_STEPS if mode == state.MODE_TWIRL_LEFT else state.R_STEPS

    if 1 <= twirl_step <= len(steps):
        rpm_left, rpm_right = steps[twirl_step - 1]

        # Apply motor command
        motor_manager.set_wheels(rpm_left, rpm_right, current_direction)

        if now - twirl_step_start > state.STEP_TIMES[twirl_step - 1]:
            state.twirl_step += 1
            state.twirl_step_start = now
    else:
        state.mode = state.MODE_IDLE
        state.twirl_step = 0
        print("Twirl completed")
        safe_stop(motor_manager)
        
def apply_gradient(target, current, slew_rate):
    if target > current + slew_rate:
        return current + slew_rate
    elif target < current - slew_rate:
        return current - slew_rate
    else:
        return target

def periodic_drive(now, motor_manager):
    """Periodic drive loop for wheels updates motor_manager (does NOT send directly)."""

    # Persistent storage of last RPMs
    if not hasattr(state, "last_left_rpm"):
        state.last_left_rpm = 0
    if not hasattr(state, "last_right_rpm"):
        state.last_right_rpm = 0

    RPM_SLEW_RATE = state.RPM_SLEW_RATE  # max RPM change per cycle

    # Ensure timely update
    if (now - state.last_send_time) < state.SEND_PERIOD:
        return
    state.last_send_time = now

    try:
        throttle_value = throttle_channel.value
        base_rpm = adc_to_rpm(throttle_value)

        mode = state.mode
        current_direction = state.current_direction

        # ---------------- Mode Handling ----------------
        if mode == state.MODE_SINGLE_LEFT:
            target_left = base_rpm
            target_right = state.SINGLE_LEFT_LOW  

        elif mode == state.MODE_SINGLE_RIGHT:
            target_left = state.SINGLE_RIGHT_LOW  
            target_right = base_rpm

        else:
            # Dead zone check 
            if base_rpm < 120:  # threshold
                motor_manager.set_wheels(0, 0, current_direction)
                state.current_rpm = 0
                state.last_left_rpm = 0
                state.last_right_rpm = 0
                return

            target_left = target_right = base_rpm
            state.current_rpm = base_rpm

        # ---------------- Gradient Limiter ----------------
        def apply_gradient(target, current, slew_rate):
        
            if target < current and (current - target) > (3 * slew_rate):
                return max(target, current - (3 * slew_rate))  # faster decay
            
            if target > current + slew_rate:
                return current + slew_rate
            elif target < current - slew_rate:
                return current - slew_rate
            else:
                return target

        rpm_left = apply_gradient(target_left, state.last_left_rpm, RPM_SLEW_RATE)
        rpm_right = apply_gradient(target_right, state.last_right_rpm, RPM_SLEW_RATE)

        # Apply motor command
        motor_manager.set_wheels(rpm_left, rpm_right, current_direction)

        # Save for next cycle
        state.last_left_rpm = rpm_left
        state.last_right_rpm = rpm_right

    except Exception as e:
        print(f"Throttle/feedback drive failed: {e}")
        safe_stop(motor_manager)

def handle_button_edges(now, motor_manager):
    """Detect button presses and update mode safely with shared state."""

    # -------- LEFT BUTTON --------
    left_now = GPIO.input(state.LEFT_BTN_PIN) == GPIO.HIGH

    left_pressed = state.left_pressed
    left_press_start = state.left_press_start
    left_last_rise = state.left_last_rise
    mode = state.mode

    if left_now and not left_pressed:  # Rising edge
        if (now - left_last_rise) <= state.DOUBLE_PRESS_GAP:
            begin_twirl(left=True)
        else:
            state.left_press_start = now
        state.left_last_rise = now
        state.left_pressed = True

    if left_now and left_pressed:
        if mode in (state.MODE_IDLE, state.MODE_SINGLE_LEFT, state.MODE_SINGLE_RIGHT):
            if (now - left_press_start) >= state.LONG_PRESS_TIME and mode != state.MODE_SINGLE_LEFT:
                state.mode = state.MODE_SINGLE_LEFT
                print("Single LEFT started")

    if not left_now and left_pressed:  # Release
        if mode == state.MODE_SINGLE_LEFT:
            #safe_stop(motor_manager)
            state.mode = state.MODE_IDLE
            print("Single LEFT stopped")
        state.left_pressed = False

    # -------- RIGHT BUTTON --------
    right_now = GPIO.input(state.RIGHT_BTN_PIN) == GPIO.HIGH

    right_pressed = state.right_pressed
    right_press_start = state.right_press_start
    right_last_rise = state.right_last_rise
    mode = state.mode

    if right_now and not right_pressed:
        if (now - right_last_rise) <= state.DOUBLE_PRESS_GAP:
            begin_twirl(left=False)
        else:
            state.right_press_start = now
        state.right_last_rise = now
        state.right_pressed = True

    if right_now and right_pressed:
        if mode in (state.MODE_IDLE, state.MODE_SINGLE_LEFT, state.MODE_SINGLE_RIGHT):
            if (now - right_press_start) >= state.LONG_PRESS_TIME and mode != state.MODE_SINGLE_RIGHT:
                state.mode = state.MODE_SINGLE_RIGHT
                print("Single RIGHT started")

    if not right_now and right_pressed:  # Release
        if mode == state.MODE_SINGLE_RIGHT:
            #safe_stop(motor_manager)
            state.mode = state.MODE_IDLE
            print("Single RIGHT stopped")
        state.right_pressed = False

def rotary_motor_step(motor_manager):
    """Runs a single step of rotary motor logic (independent of drive motors)."""
 # ?? Protect shared state
        # Stop rotary motor if switch is OFF
    if GPIO.input(state.ROTARY_SWITCH_PIN) == GPIO.LOW:
        rotary_motor_stop(motor_manager)
        state.rotary_current_rpm = 0
        return

    try:
        throttle_value = rotary_throttle_channel.value
        throttle_rpm = adc_to_rpm(throttle_value)
        state.rotary_current_rpm = throttle_rpm
        if throttle_rpm > 80:  # Dead zone filter
            motor_manager.set_rotary(throttle_rpm, state.current_direction)
        else:
            rotary_motor_stop(motor_manager)
            state.rotary_current_rpm = 0

    except Exception as e:
        print(f"Rotary throttle read failed: {e}")
        rotary_motor_stop(motor_manager)

def rotary_motor_stop(motor_manager):
    """Hard stop rotary motor."""
    try:
        motor_manager.set_rotary(0, 0x00)
        state.is_safe_stop = True
    except Exception as e:
        print("Error setting rotary stop:", e)

def run(motor_manager):
    """Run rotary + wheels at fixed RPM (test/demo)."""
    try:
        motor_manager.set_rotary(500, state.current_direction)
        motor_manager.set_wheels(500, 500, state.current_direction)
        state.is_safe_stop = False
    except Exception as e:
        print("Error running motors:", e)


def safe_stop(motor_manager):
    """Gradually stop rotary + wheels using gradient."""

    try:
        RPM_SLEW_RATE = 250  # same as periodic_drive

        def apply_gradient(target, current, slew_rate):
            if target > current + slew_rate:
                return current + slew_rate
            elif target < current - slew_rate:
                return current - slew_rate
            else:
                return target

        # ---- Wheels ----
        rpm_left = apply_gradient(0, state.last_left_rpm, RPM_SLEW_RATE)
        rpm_right = apply_gradient(0, state.last_right_rpm, RPM_SLEW_RATE)
        motor_manager.set_wheels(rpm_left, rpm_right, 0x00)

        # ---- Rotary ----
        rotary_rpm = apply_gradient(0, state.rotary_current_rpm, RPM_SLEW_RATE)
        motor_manager.set_rotary(rotary_rpm, 0x00)

        # Save updated values
        state.last_left_rpm = rpm_left
        state.last_right_rpm = rpm_right
        state.rotary_current_rpm = rotary_rpm
        state.current_rpm = 0
        state.is_safe_stop = True

    except Exception as e:
        print("Error during safe_stop:", e)

def wheel_break_stop(motor_manager):
    """Gradually stop both motors using gradient."""
    try:
        motor_manager.set_wheels_break(rpm_left, rpm_right, 0x00)
        # Save new state
        state.last_left_rpm = rpm_left
        state.last_right_rpm = rpm_right
        state.is_safe_stop = True

    except Exception as e:
        print("Error setting safe_stop:", e)


def wheel_safe_stop(motor_manager):
    """Gradually stop both motors using gradient."""
    try:
        RPM_SLEW_RATE = 250  # same slew rate as periodic_drive

        def apply_gradient(target, current, slew_rate):
            if target > current + slew_rate:
                return current + slew_rate
            elif target < current - slew_rate:
                return current - slew_rate
            else:
                return target

        # Ramp both wheels toward 0
        rpm_left = apply_gradient(0, state.last_left_rpm, RPM_SLEW_RATE)
        rpm_right = apply_gradient(0, state.last_right_rpm, RPM_SLEW_RATE)

        motor_manager.set_wheels(rpm_left, rpm_right, 0x00)

        # Save new state
        state.last_left_rpm = rpm_left
        state.last_right_rpm = rpm_right
        state.is_safe_stop = True

    except Exception as e:
        print("Error setting safe_stop:", e)


def ramp_wheel_rpm(motor_manager, target_rpm, direction, step=50, delay=0.05):
    """
    Smoothly ramp both wheels to the target RPM in the given direction.
    Uses global state.current_rpm and state_lock for thread safety.
    """
    rpm = state.current_rpm

    while rpm != target_rpm:
        if rpm < target_rpm:
            rpm = min(rpm + step, target_rpm)
        else:
            rpm = max(rpm - step, target_rpm)

        print("Ramping wheels to", rpm)
        try:
            motor_manager.set_wheels(rpm, rpm, direction)
        except Exception as e:
            print("Error setting wheels during ramp:", e)
            break

        state.current_rpm = rpm
        time.sleep(delay)

def toggle_direction(motor_manager, desired_rpm=0, step=100, delay=0.05, safety_pause=0.2):
    """
    Smoothly change wheel direction without jerks.
    Runs in a separate thread to avoid blocking the main loop.
    """

    def _toggle():
        # --- Ramp down first ---

        current_dir = state.current_direction
        rpm = state.current_rpm

        print("Ramping down before direction change...")
        ramp_wheel_rpm(motor_manager, 0, current_dir, step=step, delay=delay)
        time.sleep(safety_pause)

        # --- Switch direction ---
        state.current_direction = 0x02 if state.current_direction == 0x01 else 0x01
        new_dir = state.current_direction
        print("Direction set to", "REVERSE" if new_dir == 0x02 else "FORWARD")

        # --- Ramp back up ---
        if desired_rpm > 0:
            print(f"Ramping up to {desired_rpm} rpm in new direction...")
            ramp_wheel_rpm(motor_manager, desired_rpm, new_dir, step=step, delay=delay)

    threading.Thread(target=_toggle, daemon=True).start()

def on_road_mode_step(motor_manager):

    """
    Runs a single non-blocking step of On-Road logic.
    Should be called repeatedly from main().
    """
    now = time.monotonic()

    # ---------- Handle Button Presses ----------
    handle_button_edges(now, motor_manager)

    # ---------- DUAL BUTTON SAFETY ----------
    left_b = GPIO.input(state.LEFT_BTN_PIN) == GPIO.HIGH
    right_b = GPIO.input(state.RIGHT_BTN_PIN) == GPIO.HIGH

    if left_b and right_b:
        safe_stop(motor_manager)
        state.mode = state.MODE_IDLE
        return
                    
    # ---------- Direction Button Handling ----------

    last_dir_btn_state = state.direction_btn_last_state

    # ---------- Read throttle ----------
    try:
        throttle_value = throttle_channel.value
        base_rpm = adc_to_rpm(throttle_value)
    except Exception as e:
        print(f"Throttle read failed: {e}")
        base_rpm = 0

    #state.current_rpm = base_rpm
    current_rpm = base_rpm

    # ---------- Read direction button ----------
    direction_now = GPIO.input(state.DIRECTION_BTN_PIN) == GPIO.HIGH

    # ---------- Detect change ----------
    if direction_now != last_dir_btn_state:
        toggle_direction(
            motor_manager,
            desired_rpm=current_rpm,
            step=70,
            delay=0.03,
            safety_pause=0.3,
        )
    # ---------- Update last state ----------
    state.direction_btn_last_state = direction_now
    # ---------- Twirl Mode Execution ----------
    current_mode = state.mode

    if current_mode in (state.MODE_TWIRL_LEFT, state.MODE_TWIRL_RIGHT):
        execute_twirl(now, motor_manager)
        pass
    else:

        #motor_manager.set_wheels(100, 120, 0x01)

        periodic_drive(now, motor_manager)
        rotary_motor_step(motor_manager)

    # Small loop delay
    time.sleep(0.01)

