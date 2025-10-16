# -*- coding: utf-8 -*-
import csv
import os
import state
import time
import can
import threading
import queue
from collections import deque
from datetime import datetime, date
import RPi.GPIO as GPIO

# -------------------- GPIO --------------------
GPIO.setmode(GPIO.BCM)

# -------------------- Config --------------------
BASE_DIR = "/home/orbit/VCU-PT-PRO-2.0/vcu_project/utils"
log_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)

DATA_HEADERS = [
    "Timestamp",
    "CurrentRPM", "RotaryCurrentRPM", "rotary_feedbackRPM",
    "CurrentDirection", "FeedbackRPM_Left", "FeedbackRPM_Right",
    "LeftBtn", "RightBtn", "Seafty_switch", "DirectionBtn", "temp_sesnor_1","temp_sesnor_2","temp_sesnor_3", 
    #"state.power", "state.total_energy", "trip_runtime",
    "Mode",
    # ----- BMS 1 -----
    "BMS1_BatteryVoltage", "BMS1_Current", "BMS1_SOH",
    "BMS1_Cycles", "BMS1_Capacity", "BMS1_MOSFET_Temperature",
    # ----- BMS 2 -----
    "BMS2_BatteryVoltage", "BMS2_Current", "BMS2_SOH",
    "BMS2_Cycles", "BMS2_Capacity", "BMS2_MOsSFET_Temperature"
]

data_queue = queue.Queue()

# ---------------- Averaging Config ----------------
SAMPLE_RATE_HZ = 100
LOG_RATE_HZ = 50
SAMPLES_PER_LOG = 5  # Number of samples to average

# ---------------- Buffers ----------------
numeric_fields = [
    "current_rpm", "rotary_current_rpm", "rotary_feedbackRPM",
    "feedbackRPM_Left", "feedbackRPM_Right"
]
buffers = {field: deque(maxlen=SAMPLES_PER_LOG) for field in numeric_fields}

# ---------------- BMS Setup ----------------
BMS_IDS = ["0746D608", "0746CD62"] # cf11e04
battery_data = {bms_id: {"decoded": {}} for bms_id in BMS_IDS}


# ---------------- CAN Decode Functions ----------------
def decode_mux1(data):
    # Little-endian decoding
    battery_voltage_raw = (data[2] << 8) | data[1]
    battery_current_raw = (data[3] << 8) | data[4]

    # Signed conversion
    '''if battery_current_raw >= 0x8000:
        battery_current_raw -= 0x10000'''

    # Scaling (adjust as per DBC or observed)
    battery_voltage = battery_voltage_raw * 0.1     # volts
    battery_current = (battery_current_raw -65535) * 0.01    # amps

    return {
        "Battery_Voltage": battery_voltage,
        "Battery_Current": battery_current,
        "Battery_Temperature": data[5],
        "Load_Status": data[6],
        "Not_used1": data[7],
    }

def decode_mux2(data):
    return {
        "SOH": data[1],
        "Cycles": (data[3] << 8) | data[4],
        "Battery_Capacity": (data[5] << 8) | data[6],
    }

def decode_mux7(data):
    return {
        "Ambient_Sensor": data[1],
        "MOSFET_Temperature": data[2],
    }

def parse_frame(bms_id, mux, data):
    decoded = {}
    if mux == 1:
        decoded = decode_mux1(data)
    elif mux == 2:
        decoded = decode_mux2(data)
    elif mux == 7:
        decoded = decode_mux7(data)
    if decoded:
        battery_data[bms_id]["decoded"].update(decoded)

# ---------------- BMS Listener Thread ----------------
def bms_listener_thread():
    try:
        bus = can.interface.Bus(channel="can0", interface="socketcan")
        print("[BMS] Listening on CAN0 ...")
        while True:
            msg = bus.recv()
            if msg:
                hex_id = f"{msg.arbitration_id:08X}"
                #print(hex_id)
                if hex_id in BMS_IDS:
                    #print(msg)
                    mux = msg.data[0]
                    #if mux == 1:
                        #print(msg)
                    parse_frame(hex_id, mux, list(msg.data))
    except Exception as e:
        print(f"[BMS] Listener Error: {e}")

# ---------------- CSV Writer Thread ----------------
def _writer_thread(q, headers):
    current_day, f, writer = None, None, None
    flush_counter = 0
    while True:
        try:
            row = q.get()
            if row is None:
                break

            today = date.today()
            if today != current_day:
                if f:
                    f.close()
                filename = os.path.join(log_dir, f"{today}_data.csv")
                f = open(filename, "a", newline="")
                writer = csv.writer(f)
                if os.stat(filename).st_size == 0:
                    writer.writerow(headers)
                current_day = today

            writer.writerow(row)
            flush_counter += 1
            if flush_counter >= 10:
                f.flush()
                flush_counter = 0

        except Exception as e:
            print(f"[Logger] Error writing row: {e}")

# Start threads
threading.Thread(target=_writer_thread, args=(data_queue, DATA_HEADERS), daemon=True).start()
threading.Thread(target=bms_listener_thread, daemon=True).start()

# ---------------- Utils ----------------
def safe_val(val):
    return val if val is not None else 0


# ---------------- Public API ----------------
def log_data(state):
    """Collect samples and log row with averaged motor data and live BMS."""
    # ---------------- Motor Buffers ----------------
    buffers["current_rpm"].append(safe_val(getattr(state, "current_rpm", 0)))
    buffers["rotary_current_rpm"].append(safe_val(getattr(state, "rotary_current_rpm", 0)))
    buffers["rotary_feedbackRPM"].append(safe_val(getattr(state, "device_5_rpm", 0)))
    buffers["feedbackRPM_Left"].append(safe_val(getattr(state, "device_6_rpm", 0)))
    buffers["feedbackRPM_Right"].append(safe_val(getattr(state, "device_4_rpm", 0)))

    # Wait until buffers fill
    if len(buffers["current_rpm"]) < SAMPLES_PER_LOG:
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    # ----- BMS data -----
    b1 = battery_data["0746D608"]["decoded"]
    b2 = battery_data["0746CD62"]["decoded"]#0746CE3E

    row = [
        ts,
        sum(buffers["current_rpm"]) / len(buffers["current_rpm"]),
        sum(buffers["rotary_current_rpm"]) / len(buffers["rotary_current_rpm"]),
        sum(buffers["rotary_feedbackRPM"]) / len(buffers["rotary_feedbackRPM"]),
        getattr(state, "current_direction", 0),
        sum(buffers["feedbackRPM_Left"]) / len(buffers["feedbackRPM_Left"]),
        sum(buffers["feedbackRPM_Right"]) / len(buffers["feedbackRPM_Right"]),
        GPIO.input(getattr(state, "LEFT_BTN_PIN", 0)),
        GPIO.input(getattr(state, "RIGHT_BTN_PIN", 0)),
        GPIO.input(getattr(state, "MODE_SWITCH_PIN", 0)),
        GPIO.input(getattr(state, "DIRECTION_BTN_PIN", 0)),

        # Temperature sensors
        state.temp_sesnor_1,
        state.temp_sesnor_2,
        state.temp_sesnor_3,
        #state.power,             # W
        #state.total_energy,     # Wh
        #state.trip_runtime,  

        #GPIO.input(getattr(state, "ROTARY_SWITCH_PIN", 0)),
        getattr(state, "mode", 0),

        # BMS1
        b1.get("Battery_Voltage", 0),
        b1.get("Battery_Current", 0),
        b1.get("SOH", 0),
        b1.get("Cycles", 0),
        b1.get("Battery_Capacity", 0),
        b1.get("MOSFET_Temperature", 0),

        # BMS2
        b2.get("Battery_Voltage", 0),
        b2.get("Battery_Current", 0),
        b2.get("SOH", 0),
        b2.get("Cycles", 0),
        b2.get("Battery_Capacity", 0),
        b2.get("MOSFET_Temperature", 0),
        
    ]
    print(b1.get("Battery_Current", 0))  # ? Will now print updated values
    print(b2.get("Battery_Current", 0))
    data_queue.put(row)

    # Clear buffers
    for field in buffers:
        buffers[field].clear()

def stop_logger():
    data_queue.put(None)
    print("[Logger] Stopped.")
