# -*- coding: utf-8 -*-
import time
import threading
import RPi.GPIO as GPIO
#import utils.logger   # <-- your new logging module
from utils import logger
from utils import machine_stats
import can
import state


from canbus.can_reader import setup_can_bus
from canbus.can_bus_active import check_can0
from control.motor_manager import MotorManager, BMSManager
#from utils.update_sheet import update_sheet
from control.on_road import on_road_mode_step
from display.lcd_display import LCDDisplay
from control.motor_manager import manual_decode
#from control.motor_manager import MotorManager

# -------------------- LCD SETUP --------------------

lcd = LCDDisplay()
lcd.start()
lcd.add_task(lcd.display_orbit_pt_pro)
time.sleep(1.0)
# from control.off_road import off_road_mode_step

bus = can.interface.Bus(channel="can0", bustype="socketcan")
motor_manager = MotorManager(bus)
bms_manager = BMSManager(bus)
# Pass it to on_road
on_road_mode_step(motor_manager)

# -------------------- CONSTANTS --------------------
MODE_ON_ROAD = 1
MODE_OFF_ROAD = 0
MODE_SWITCH_PIN = 20

# -------------------- GPIO SETUP -------------------
def init_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([state.LEFT_BTN_PIN, state.RIGHT_BTN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(state.MODE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(state.DIRECTION_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(state.ROTARY_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(state.SAFETY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    print("[INFO] GPIO initialized.")

def get_current_mode():
    """Read the mode from the switch."""
    return MODE_OFF_ROAD if GPIO.input(MODE_SWITCH_PIN) == GPIO.HIGH else MODE_ON_ROAD

def print_battery_state():
    """Print current state values (for testing)."""
    print("------ Battery State ------")
    print(f"Battery Voltage     : {state.battery_voltage}")
    print(f"Current             : {state.current}")
    print(f"SOC (%)             : {state.soc}")
    print(f"Max Voltage         : {state.max_voltage}")
    print(f"Min Voltage         : {state.min_voltage}")
    print(f"Max Voltage Cell    : {state.max_cells}")
    print(f"Min Voltage Cell    : {state.min_cells}")
    print(f"Max Temp            : {state.max_temp}")
    print(f"Min Temp            : {state.min_temp}")
    print(f"Max Temp Cell       : {state.max_temp_cell}")
    print(f"Min Temp Cell       : {state.min_temp_cell}")
    print(f"Charge/Dis Status   : {state.charge_dis_status}")
    print(f"Charge MOS Status   : {state.charge_mos_status}")
    print(f"Discharge MOS Status: {state.dis_mos_status}")
    print(f"BMS Life (%)        : {state.bms_life}")
    print(f"Residual Capacity   : {state.residual_capacity}")
    
    print("---------------------------\n")
    # New computed fields
    print(f"Power (W)           : {state.power:.2f}")
    print(f"Total Power-1 (W)   : {state.total_power_1:.2f}")
    print(f"Total Energy (Wh)   : {state.total_energy:.4f}")
    print("---------------------------\n")
    print(f"Last_trip_power (W)      : {state.Last_trip_power:.2f}")
    print(f"Last_trip_total_energy   : {state.Last_trip_total_energy:.2f}")
    print(f"Last_trip_trip_runtime   : {state.Last_trip_trip_runtime:.4f}")
    print("---------------------------\n")
    
    print(f"device_4_rpm  : {state.device_4_rpm}")
    print(f"device_4_current: {state.device_4_current}")
    print(f"device_4_voltage        : {state.device_4_voltage}")
    print(f"device_4_error   : {state.device_4_error}")

    print(f"device_5_rpm  : {state.device_5_rpm}")
    print(f"device_5current: {state.device_5_current}")
    print(f"device_5_voltage        : {state.device_5_voltage}")
    print(f"device_5_error   : {state.device_5_error}")
    
    print(f"device_6_rpm  : {state.device_6_rpm}")
    print(f"device_6_current: {state.device_6_current}")
    print(f"device_6_voltage        : {state.device_6_voltage}")
    print(f"device_6_error   : {state.device_6_error}")
# -------------------- THREAD FUNCTIONS -------------
def machine_control_loop(bus):
    """Thread 1: Handles machine control (on-road / off-road)."""
    last_mode = 1
    last_lcd_update = 0

    while True:
        mode = get_current_mode()

        if mode != MODE_ON_ROAD:
            if last_mode != 1:   # only call once on change
                #lcd.add_task(lcd.display_on_road_mode)
                last_mode = 1

            on_road_mode_step(motor_manager)

            now = time.time()
            if now - last_lcd_update >= 1.0:
                #lcd.add_task(lcd.Real_time_data, state.current_rpm, state.rotary_current_rpm)
                last_lcd_update = now
                #print("[INFO] LCD updated (real-time data).")

        else:
            if last_mode != 0:
                #lcd.add_task(lcd.seafty_lever_Active)
                last_mode = 0         
            #print("[INFO] Machine OFF (mode switch).")

        # Control loop timing (20 Hz = 50 ms)
        time.sleep(0.05)

def logging_loop():
    """Thread 2: Handles periodic logging (3 readings/sec)."""
    log_interval = 1 / 10  # 3 readings per second => 0.333 sec
    while True:
        start_time = time.time()

        # Log latest state + GPIO
        logger.log_data(state, GPIO)

        # Sleep the remaining time to maintain fixed interval
        elapsed = time.time() - start_time
        sleep_time = max(0, log_interval - elapsed)
        time.sleep(sleep_time)

# -------------------- THREAD FUNCTIONS -------------
def can_reader_loop(bus, bms_manager):
    """Thread 3: Reads BMS data, decodes, updates state, prints battery info."""
    log_interval = 1 / 50  # 3 readings per second
    print("[INFO] can_reader_loop started")

    while True:
        start_time = time.time()
        try:
            # Send polling request to BMS
            bms_manager._send_request()

            # Receive and decode BMS response
            decoded = bms_manager._receive_response()
            # Print updated state
            #print_battery_state()

        except Exception as e:
            print(f"[ERROR] BMS loop: {e}")

        # Maintain loop timing
        elapsed = time.time() - start_time
        sleep_time = max(0, log_interval - elapsed)
        time.sleep(sleep_time)
          
def start_threads(bus):
    """Launches all threads."""

    # Thread 1 ? Machine control
    t1 = threading.Thread(target=machine_control_loop, args=(bus,), daemon=True)

    # Thread 2 ? Logging
    t2 = threading.Thread(target=logging_loop, daemon=True)

    # Thread 3 ? Safety (optional)
    t3 = threading.Thread(target=can_reader_loop, args=(bus, bms_manager), daemon=True)

    #t4 = threading.Thread(target=lcd_display_loop, daemon=True)
    # Start threads
    t1.start()
    t2.start()
    t3.start()
    #t4.start()
    print("[INFO] Threads started: Machine Control + Logging")

    machine_stats.start_energy_monitor(interval=1.0, delay=10)
    print("[INFO] Energy monitor scheduled (starts after 10s)")

    # Keep main thread alive (control loop blocks)
    t1.join()
    # logging thread runs in background, no join
    
from display.lcd_display_th import LCDManager
lcd_manager = LCDManager()
            
def main():
    bus = setup_can_bus()
    '''if not bus:
        check_can0()
        return'''
    lcd_manager.start()
    init_gpio()
    start_threads(bus)
    

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Program stopped by user (Ctrl+C). Cleaning up...")
        GPIO.cleanup()
