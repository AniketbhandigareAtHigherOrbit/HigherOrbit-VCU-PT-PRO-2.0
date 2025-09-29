import csv
import os
from datetime import datetime, date
import threading
import queue
from collections import deque
import RPi.GPIO as GPIO

# -------------------- GPIO --------------------
GPIO.setmode(GPIO.BCM)   # Or GPIO.BOARD depending on wiring

# -------------------- Config --------------------
BASE_DIR = "/home/orbit/VCU-PT-PRO-2.0/vcu_project/utils"
log_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)

DATA_HEADERS = [
    "Timestamp",
    "CurrentRPM",
    "RotaryCurrentRPM",
    "CurrentDirection",
    "FeedbackRPM_Left",
    "FeedbackRPM_Right",
    "LeftBtn",
    "RightBtn",
    "ModeSwitch",
    "DirectionBtn",
    "RotarySwitch",
    "SafetyPin",
    "IsSafeStop",
    "Mode",
    # Battery / BMS fields
    "BatteryVoltage",
    "Current",
    "SOC",
    "MaxVoltage",
    "MaxCells",
    "MinVoltage",
    "MinCells",
    "MaxTemp",
    "MaxTempCell",
    "MinTemp",
    "MinTempCell",
    "ChargeDisStatus",
    "ChargeMOSStatus",
    "DisMOSStatus",
    "BMSLife",
    "ResidualCapacity"
]

EVENT_HEADERS = ["Timestamp", "EventType", "Details"]

data_queue = queue.Queue()
event_queue = queue.Queue()

active_timers = {}  # duration timers

# ---------------- Averaging Config ----------------
SAMPLE_RATE_HZ = 150
LOG_RATE_HZ = 90
SAMPLES_PER_LOG = 60  # = 20

numeric_fields = [
    "current_rpm", "rotary_current_rpm",
    "feedbackRPM_Left", "feedbackRPM_Right",
    "battery_voltage", "current", "soc"
]
buffers = {field: deque(maxlen=SAMPLES_PER_LOG) for field in numeric_fields}

# ---------------- File Management ----------------
def get_filenames():
    today = date.today().strftime("%Y-%m-%d")
    data_file = os.path.join(log_dir, f"{today}_data.csv")
    event_file = os.path.join(log_dir, f"{today}_events.csv")
    return data_file, event_file

def _writer_thread(q, headers, file_type):
    """Background thread for writing CSV with daily rotation."""
    current_day, f, writer = None, None, None
    while True:
        try:
            row = q.get()
            if row is None:
                break

            today = date.today()
            if today != current_day:
                if f:
                    f.close()
                filename = get_filenames()[0] if file_type == "data" else get_filenames()[1]
                f = open(filename, "a", newline="")
                writer = csv.writer(f)
                if os.stat(filename).st_size == 0:
                    writer.writerow(headers)
                current_day = today

            writer.writerow(row)
            f.flush()
        except Exception as e:
            print(f"[Logger] Error writing {file_type} row: {e}")


# Start writer threads
threading.Thread(target=_writer_thread, args=(data_queue, DATA_HEADERS, "data"), daemon=True).start()
threading.Thread(target=_writer_thread, args=(event_queue, EVENT_HEADERS, "event"), daemon=True).start()


# ---------------- Utils ----------------
def safe_val(val):
    return val if val is not None else 0


# ---------------- Public API ----------------
def log_data(state, GPIO):
    """Collect 300 Hz samples, log averaged row at 15 Hz."""
    # Fill buffers
    buffers["current_rpm"].append(safe_val(state.current_rpm))
    buffers["rotary_current_rpm"].append(safe_val(state.device_5_rpm))
    buffers["feedbackRPM_Left"].append(safe_val(state.device_6_rpm))
    buffers["feedbackRPM_Right"].append(safe_val(state.device_4_rpm))
    buffers["battery_voltage"].append(safe_val(getattr(state, "battery_voltage", 0)))
    buffers["current"].append(safe_val(getattr(state, "current", 0)))
    buffers["soc"].append(safe_val(getattr(state, "soc", 0)))

    # Only log once buffers are full
    if len(buffers["current_rpm"]) < SAMPLES_PER_LOG:
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        ts,
        sum(buffers["current_rpm"]) / len(buffers["current_rpm"]),
        sum(buffers["rotary_current_rpm"]) / len(buffers["rotary_current_rpm"]),
        state.current_direction,
        sum(buffers["feedbackRPM_Left"]) / len(buffers["feedbackRPM_Left"]),
        sum(buffers["feedbackRPM_Right"]) / len(buffers["feedbackRPM_Right"]),
        GPIO.input(state.LEFT_BTN_PIN),
        GPIO.input(state.RIGHT_BTN_PIN),
        GPIO.input(state.MODE_SWITCH_PIN),
        GPIO.input(state.DIRECTION_BTN_PIN),
        GPIO.input(state.ROTARY_SWITCH_PIN),
        GPIO.input(state.SAFETY_PIN),
        state.is_safe_stop,
        state.mode,
        sum(buffers["battery_voltage"]) / len(buffers["battery_voltage"]),
        sum(buffers["current"]) / len(buffers["current"]),
        sum(buffers["soc"]) / len(buffers["soc"]),
        getattr(state, "max_voltage", None),
        getattr(state, "max_cells", None),
        getattr(state, "min_voltage", None),
        getattr(state, "min_cells", None),
        getattr(state, "max_temp", None),
        getattr(state, "max_temp_cell", None),
        getattr(state, "min_temp", None),
        getattr(state, "min_temp_cell", None),
        getattr(state, "charge_dis_status", None),
        getattr(state, "charge_mos_status", None),
        getattr(state, "dis_mos_status", None),
        getattr(state, "bms_life", None),
        getattr(state, "residual_capacity", None)
    ]

    data_queue.put(row)
    #print(ts,"updated in log ")

    # Clear buffers for next cycle
    for field in buffers:
        buffers[field].clear()


def log_event(event_type, details=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_queue.put([ts, event_type, details])


# ---------------- Duration Tracker ----------------
def start_timer(name):
    if name not in active_timers:
        active_timers[name] = datetime.now()
        log_event("Start", f"{name} started")


def stop_timer(name):
    if name in active_timers:
        start_time = active_timers.pop(name)
        duration = (datetime.now() - start_time).total_seconds()
        log_event("Duration", f"{name} lasted {duration:.1f} sec")
        log_event("Stop", f"{name} stopped")
