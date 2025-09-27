
# can_managers.py
import threading
import time
import can
import subprocess
import csv
import os
import json
from datetime import datetime

import state  # your state module (must exist)

# -------------------- Config --------------------
UPDATE_RATE_HZ = 5
TIMEOUT_SEC = 0.5  # If no update within 200ms -> send 0 rm
ROTARY_MAX_RPM = 1500
WHEEL_MAX_RPM = 1500

CSV_FILE = "battery_data.csv"
DBC_PATH = "Inverted_Protocol_DBC_File.dbc"
SEND_CAN_ID = 0x12300140
RESPONSE_TIMEOUT = 0.5  # seconds

# Fields we want to collect before saving (non-exhaustive, extend if needed)
# -------------------- BMS Decode --------------------

# --------------- Utility: CAN bus setup (small helper) --------------
def setup_can_bus(channel="can0"):
    try:
        bus = can.interface.Bus(channel=channel, bustype="socketcan")
        print("[CAN] Interface initialized:", channel)
        return bus
    except Exception as e:
        print("[CAN] Could not initialize CAN bus:", e)
        return None

def manual_decode(message):
    """
    Decode BMS CAN message into a dictionary containing all battery variables.
    Ensures all state fields exist.
    """
    # Initialize full decoded dictionary


    data = message.data
    msg_id = message.arbitration_id

    # ------------------- Battery core values -------------------
    if msg_id == 0x12314002:
        #print(f"trying on: {message.arbitration_id}")
        state.max_voltage = (int.from_bytes(data[0:2], 'big'))*0.001
        state.max_cells = data[2]
        state.min_voltage = (int.from_bytes(data[3:5], 'big'))*0.001
        state.min_cells = data[5]

        '''print("   Manually Decoded Max/Min Cell Voltage Data")
        print(f"    - Max Voltage      : {max_voltage} mV")
        print(f"    - Cells @ Max Volt : {max_cells}")
        print(f"    - Min Voltage      : {min_voltage} mV")
        print(f"    - Cells @ Min Volt : {min_cells}")'''
    # ------------------- Cell voltages -------------------
    elif msg_id in [0x12304001, 0x12304002]:
        #data = message.data
        state.battery_voltage = int.from_bytes(data[0:2], 'big') * 0.1
        current_raw = int.from_bytes(data[4:6], 'big')
        state.current = (current_raw - 30000) * 0.1
        state.soc = int.from_bytes(data[6:8], 'big') * 0.1

        '''print("  ?? Manually Decoded SOC Data:")
        print(f"    - Battery Voltage: {battery_voltage:.1f} V")
        print(f"    - Current        : {current:.1f} A")
        print(f"    - SOC            : {soc:.1f} %")'''   
        
    elif msg_id in [0x12324001, 0x12324002]:
        state.max_temp = data[0] - 40
        state.max_temp_cell = data[1]
        state.min_temp = data[2] - 40
        state.min_temp_cell = data[3]

    elif message.arbitration_id in [0x12334001, 0x12334002]:
        state.charge_dis_status = data[0]
        state.charge_mos_status = data[1]
        state.dis_mos_status = data[2]
        state.bms_life = data[3]
        state.residual_capacity = int.from_bytes(data[4:8], 'big')
        
    elif 0x0CF11E04 <= msg_id <= 0x0CF11E06:
        device_id = msg_id - 0x0CF11E00
        rpm = (data[1] << 8) | data[0]
        current = (data[3] << 8 | data[2]) / 10
        voltage = (data[5] << 8 | data[4]) / 10
        error_code = (data[7] << 8) | data[6]

        if device_id == 4:
            state.device_4_rpm = rpm
            state.device_4_current = current
            state.device_4_voltage = voltage
            state.device_4_error = error_code
        elif device_id == 5:
            state.device_5_rpm = rpm
            state.device_5_current = current
            state.device_5_voltage = voltage
            state.device_5_error = error_code
        elif device_id == 6:
            state.device_6_rpm = rpm
            state.device_6_current = current
            state.device_6_voltage = voltage
            state.device_6_error = error_code
    # ------------------- Cell temps -------------------      
    
    else:
        pass
        #print("   Unknown response ID, cannot manually decode")
  
    decoded_full=None
    return decoded_full

# --------------- Helpers -----------------
def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def format_can_data(data):
    """Return data as hex string. Accepts bytes or list."""
    if data is None:
        return ""
    try:
        # If Message.data is a bytes-like object, this will work; else convert list->bytes
        return " ".join(f"{b:02X}" for b in bytes(data))
    except Exception:
        # Fallback for weird types
        return str(data)

def clamp_rpm(rpm, max_rpm):
    """Clamp rpm to [0, max_rpm]."""
    try:
        rpm = int(rpm)
    except Exception:
        rpm = 0
    return max(0, min(rpm, int(max_rpm)))

def build_can_data(rpm, direction, max_rpm):
    """Build CAN data frame for wheel or rotary motor (8 bytes)."""
    rpm = clamp_rpm(rpm, max_rpm)
    return bytes([
        rpm & 0xFF,
        (rpm >> 8) & 0xFF,
        0x01, int(direction) & 0xFF,
        0x00, 0x00, 0x00, 0x00
    ])
    
def reset_can_interface():
    """Reset can0 interface safely (uses sudo ip link; requires permissions)."""
    print("[CAN] Resetting can0 ...")
    subprocess.run(["sudo", "ip", "link", "set", "can0", "down"], check=False)
    time.sleep(0.3)
    subprocess.run(
        ["sudo", "ip", "link", "set", "can0", "up", "type", "can", "bitrate", "500000"],
        capture_output=True, text=True)

# ?? Global health flag + timestamp
_can_down = False
_last_reset_time = 0

def safe_send(bus, msg):
    """Send CAN frame safely, recover if buffer full or network down."""
    global _can_down, _last_reset_time
    try:
        bus.send(msg, timeout=0.01)

    except can.CanError as e:
        err = str(e)
        if any(x in err for x in ("No buffer space available", "Network is down")):
            print(f"[CAN] Recoverable error: {err}")
            _can_down = True   # ? mark unhealthy
        else:
            print(f"[CAN] send error: {err}")

    except Exception as e:
        print(f"[CAN] unexpected send error: {e}")


# ?? Separate watchdog (run in its own thread at startup)
def can_watchdog():
    global _can_down, _last_reset_time
    while True:
        if _can_down:
            now = time.time()
            if now - _last_reset_time > 5.0:   # ? reset at most every 5 sec
                print("[CAN] Resetting can0 ...")
                reset_can_interface()
                _last_reset_time = now
                _can_down = False
        time.sleep(1.0)


# --------------- CSV Saving --------------

# -------------------- Motor Manager --------------------
class MotorManager:
    def __init__(self, bus):
        self.bus = bus

        # Desired states
        self.wheel_left = (0, 0)   # (rpm, dir)
        self.wheel_right = (0, 0)
        self.rotary = (0, 0)

        # Last update times
        now = time.time()
        self.last_wheel_update = now
        self.last_rotary_update = now

        # Thread
        self._running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    # ----------- API -----------
    def set_wheels(self, rpm_left, rpm_right, direction):
        self.wheel_left = (rpm_left, direction)
        self.wheel_right = (rpm_right, direction)
        self.last_wheel_update = time.time()

    def set_rotary(self, rpm, direction):
        self.rotary = (rpm, direction)
        self.last_rotary_update = time.time()

    def stop_all(self):
        self.set_wheels(0, 0, 0)
        self.set_rotary(0, 0)

    # ----------- Background thread -----------
    def _loop(self):
        period = 1 / UPDATE_RATE_HZ
        next_time = time.time()

        # CAN IDs (fixed, precomputed)
        id_left = 0x0CF10000 | (0x06 << 8) | 0x1E
        id_right = 0x0CF10000 | (0x04 << 8) | 0x1E
        id_rot = 0x0CF10000 | (0x05 << 8) | 0x1E

        while self._running:
            now = time.time()

            # Wheels (timeout fallback)
            wl = self.wheel_left if now - self.last_wheel_update <= TIMEOUT_SEC else (0, 0)
            wr = self.wheel_right if now - self.last_wheel_update <= TIMEOUT_SEC else (0, 0)

            # Rotary (timeout fallback)
            rot = self.rotary if now - self.last_rotary_update <= TIMEOUT_SEC else (0, 0)

            try:
                # Build messages
                msg_left = can.Message(
                    arbitration_id=id_left, is_extended_id=True,
                    data=build_can_data(*wl, WHEEL_MAX_RPM)
                )
                msg_right = can.Message(
                    arbitration_id=id_right, is_extended_id=True,
                    data=build_can_data(*wr, WHEEL_MAX_RPM)
                )
                msg_rot = can.Message(
                    arbitration_id=id_rot, is_extended_id=True,
                    data=build_can_data(*rot, ROTARY_MAX_RPM)
                )

                # Send
                safe_send(self.bus, msg_left)
                safe_send(self.bus, msg_right)
                safe_send(self.bus, msg_rot)

            except Exception as e:
                print(f"[MotorManager] send failed: {e}")

            # Strict timing
            next_time += period
            sleep_time = next_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # If running late, resync immediately
                next_time = time.time()

    def shutdown(self):
        self._running = False
        self.thread.join()

# -------------------- BMS Manager --------------------
class BMSManager:
    def __init__(self, bus, db=None, poll_interval=0.01):
        """
        db: optionally a cantools DBC DB object (or None)
        poll_interval: seconds between polls (default 0.5)
        """
        self.bus = bus
        self.db = db
        self.poll_interval = poll_interval
        self._running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print("[BMSManager] started")

    def _send_request(self):
        """Send polling request to BMS safely."""
        try:
            # Some BMS expect a particular request payload; default to 8 zeros
            payload = bytes([0x00] * 8)
            msg = can.Message(
                arbitration_id=SEND_CAN_ID,
                data=payload,
                is_extended_id=True
            )
            safe_send(self.bus, msg)
            # don't spam the console too much
            # print("[BMSManager] Request sent to BMS")
        except Exception as e:
            print(f"[BMSManager] send_request error: {e}")

    def _receive_response(self):
        """Receive and decode BMS response. Returns decoded dict (may be partial)."""
        try:
            msg = self.bus.recv(timeout=RESPONSE_TIMEOUT)
            if msg is None:
                # no reply this cycle
                return None

            ts = get_timestamp()
            #print(f"\n{ts} Received: ID=0x{msg.arbitration_id:X}, DLC={msg.dlc} Bytes: {format_can_data(msg.data)}")

            decoded = None
            if self.db:
                try:
                    decoded = self.db.decode_message(msg.arbitration_id, msg.data)
                    print("[BMSManager] Decoded via DBC:", decoded)
                except Exception as e:
                    print("[BMSManager] DBC decode failed:", e)
                    decoded = manual_decode(msg)
            else:
                decoded = manual_decode(msg)

            return decoded
        except Exception as e:
            print("[BMSManager] receive error:", e)
            return None

    def _loop(self):
        """Main BMS polling loop."""
        while self._running:
            try:
                self._send_request()
                time.sleep(0.01)
                decoded = self._receive_response()
                if decoded:
                    # Update state variables safely (use state.lock if available)
                    state.bms_last_update = time.time()
                    state.decoded_full = decoded
            except Exception as e:
                print("[BMSManager] loop error:", e)

            time.sleep(self.poll_interval)

    def shutdown(self):
        self._running = False
        self.thread.join()

# --------------- Simple test runner --------------
if __name__ == "__main__":
    # Quick manual test (requires can0 up and running)
    bus = setup_can_bus()
    if not bus:
        print("Exiting because CAN bus not available.")
        raise SystemExit(1)

    # Try to load DBC if available (optional)
    db = None
    try:
        import cantools
        if os.path.exists(DBC_PATH):
            db = cantools.database.load_file(DBC_PATH)
            print("[DBC] Loaded", DBC_PATH)
        else:
            print("[DBC] Not found; skipping DBC decode")
    except Exception:
        db = None

    motor = MotorManager(bus)   # starts motor thread
    bms = BMSManager(bus, db=db, poll_interval=0.01)

    # Simple print loop to observe state updates
    try:
        time.sleep(0.2)
        '''while True:
            def fmt(x): return str(x) if x is not None else "N/A"
            print("------ Battery State ------")
            print("Voltage:", fmt(getattr(state, "battery_voltage", None)),
                  "Current:", fmt(getattr(state, "current", None)),
                  "SOC:", fmt(getattr(state, "soc", None)))
            print("MaxV:", fmt(getattr(state, "max_voltage", None)),
                  "MinV:", fmt(getattr(state, "min_voltage", None)))
            print("Decoded full:", getattr(state, "decoded_full", None))
            print("Last BMS update:", getattr(state, "bms_last_update", "N/A"))
            print("---------------------------\n")
            time.sleep(0.2)'''
    except KeyboardInterrupt:
        print("Stopping...")
        motor.shutdown()
        bms.shutdown()
