import csv
import os
from datetime import datetime, date
import threading
import queue

# -------------------- Config --------------------
# Absolute path to logs folder inside your project
BASE_DIR = "/home/orbit/VCU-PT-PRO-2.0/vcu_project/utils"
log_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)

# CSV Headers
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
    # --- Battery / BMS fields ---
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

# Queues for thread-safe logging
data_queue = queue.Queue()
event_queue = queue.Queue()

# Timer storage for durations
active_timers = {}  # {name: start_time}


# ---------------- File Management ---------------- #
def get_filenames():
    """Return today's log file paths (absolute path)."""
    today = date.today().strftime("%Y-%m-%d")
    data_file = os.path.join(log_dir, f"{today}_data.csv")
    event_file = os.path.join(log_dir, f"{today}_events.csv")
    return data_file, event_file


# ---------------- CSV Writer Worker ---------------- #
def _writer_thread(q, headers, file_type):
    """Thread that writes queued rows to CSV with daily rotation."""
    current_day = None
    f = None
    writer = None

    while True:
        try:
            row = q.get()
            if row is None:  # sentinel to stop thread
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


# Start background threads
threading.Thread(target=_writer_thread, args=(data_queue, DATA_HEADERS, "data"), daemon=True).start()
threading.Thread(target=_writer_thread, args=(event_queue, EVENT_HEADERS, "event"), daemon=True).start()


# ---------------- Public API ---------------- #
def log_data(state, GPIO):
    """Log latest live state and GPIO inputs to data CSV."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        ts,
        state.current_rpm,
        state.rotary_current_rpm,
        state.current_direction,
        state.device_6_current,
        state.device_4_current,
        GPIO.input(state.LEFT_BTN_PIN),
        GPIO.input(state.RIGHT_BTN_PIN),
        GPIO.input(state.MODE_SWITCH_PIN),
        GPIO.input(state.DIRECTION_BTN_PIN),
        GPIO.input(state.ROTARY_SWITCH_PIN),
        GPIO.input(state.SAFETY_PIN),
        state.is_safe_stop,
        state.mode,
        getattr(state, "battery_voltage", None),
        getattr(state, "current", None),
        getattr(state, "soc", None),
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


def log_event(event_type, details=""):
    """Log discrete events to events CSV."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_queue.put([ts, event_type, details])


# ---------------- Duration Tracker ---------------- #
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
