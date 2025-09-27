import time
import threading
import json
import os
import state  # your state.py file

# ------------------------
# JSON file for last trip
# ------------------------
LAST_TRIP_FILE = "/home/orbit/VCU-PT-PRO-2.0/vcu_project/utils/logs/last_trip.json"
LAST_TRIP_DIR = os.path.dirname(LAST_TRIP_FILE)
SAVE_INTERVAL = 60  # seconds

# Internal time tracking
_last_time = time.time()


# ------------------------
# Power and energy calculations
# ------------------------
def compute_power():
    """Compute instantaneous pack power (W)."""
    if state.battery_voltage is not None and state.current is not None:
        state.power = state.battery_voltage * state.current  # W
    else:
        state.power = 0.0


def update_energy(dt=None):
    """
    Integrate total energy (Wh) and trip runtime (hours).
    dt = time difference in seconds, if None uses internal timer
    """
    global _last_time
    now = time.time()
    
    if dt is None:
        dt = now - _last_time
    
    dt_hours = dt / 3600.0
    _last_time = now

    # Update energy
    if state.power is not None:
        state.total_energy += state.power * dt_hours

    # Update runtime if machine is running (current != 0)
    if state.current is not None and abs(state.current) > 0.01:
        state.trip_runtime += dt_hours


def _timer_task(interval=0.2):
    """Background loop that updates power & energy at given interval (default 5 Hz)."""
    compute_power()
    update_energy(interval)
    threading.Timer(interval, _timer_task, [interval]).start()


# ------------------------
# JSON save/load functions
# ------------------------
def _save_last_trip():
    """Save last trip to JSON file continuously."""
    while True:
        try:
            # Ensure folder exists
            if not os.path.exists(LAST_TRIP_DIR):
                os.makedirs(LAST_TRIP_DIR)

            data = {
                "Last_trip_total_energy": state.total_energy,
                "Last_trip_trip_runtime": state.trip_runtime,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            }

            with open(LAST_TRIP_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[ERROR] Saving last trip failed: {e}")

        time.sleep(SAVE_INTERVAL)

def load_last_trip():
    """Load last trip data from JSON file at startup."""
    if not os.path.exists(LAST_TRIP_FILE):
        return
    try:
        with open(LAST_TRIP_FILE, "r") as f:
            data = json.load(f)
            state.Last_trip_total_energy = data.get("Last_trip_total_energy", 0.0)
            state.Last_trip_trip_runtime = data.get("Last_trip_trip_runtime", 0.0)
            # Optionally reset Last_trip_power
            state.Last_trip_power = 0.0
        print(f"[INFO] Last trip loaded: "
              f"Energy={state.Last_trip_total_energy:.4f} Wh, "
              f"Runtime={state.Last_trip_trip_runtime:.2f} h")
    except Exception as e:
        print(f"[ERROR] Loading last trip failed: {e}")


# ------------------------
# Start energy monitor
# ------------------------
def start_energy_monitor(interval=0.2, delay=10):
    """
    Start background monitor after a delay.
    interval = update interval in seconds (0.2s = 5 Hz)
    delay = wait before starting calculations
    """
    global _last_time
    _last_time = time.time()

    def delayed_start():
        print(f"[INFO] Energy monitor started after {delay}s delay")
        _timer_task(interval)

        # Start JSON save loop in a background daemon thread
        save_thread = threading.Thread(target=_save_last_trip, daemon=True)
        save_thread.start()

    threading.Timer(delay, delayed_start).start()
