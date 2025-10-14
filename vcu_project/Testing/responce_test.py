
# -*- coding: utf-8 -*-
"""
controller_response_threads.py

TX thread sends FWD then waits for FWD feedback, then sends REV and waits for REV feedback.
RX thread continuously listens and notifies TX when expected feedback is seen.
Logs TX and RX events + measured TX->RX latency to CSV.
"""

import can
import csv
import time
import threading
from datetime import datetime

# ---------------- CONFIG ----------------
MOTOR_IDS = [4, 5, 6]        # motors to test
MAX_RPM = 1000
TEST_RPM = 500
TEST_DURATION = 320           # total test time in seconds
LOG_FILE = "controller_response_latency_threads_1.csv"
CAN_CHANNEL = "can0"
CAN_BUSTYPE = "socketcan"
TX_TIMEOUT = 5.0             # seconds to wait for feedback before considering timeout
TX_SLEEP_BETWEEN = 0.1       # small delay between motor commands in TX loop
# ----------------------------------------

# ----- Helpers: CAN IDs / payload / decode -----
def motor_tx_id(motor_id):
    """TX Command ID: 0x0CF10000 + (DeviceID << 8) + 0x1E"""
    return 0x0CF10000 | (motor_id << 8) | 0x1E

def motor_rx_id(motor_id):
    """RX Feedback ID: 0x0CF11F00 + DeviceID"""
    return 0x0CF11F00 | motor_id

def build_can_data(rpm, direction):
    """Build TX CAN frame data. direction: 'FWD' or 'REV'"""
    rpm = max(0, min(rpm, MAX_RPM))
    enable = 0x01
    dir_byte = 0x01 if direction == "FWD" else 0x02
    return bytes([
        rpm & 0xFF, (rpm >> 8) & 0xFF,
        enable, dir_byte,
        0x00, 0x00, 0x00, 0x00
    ])

def decode_feedback(msg_id, data_bytes):
    """Decode controller feedback frame (Message 2 spec). Returns dict."""
    # Expecting data_bytes as bytes-like of length >= 6
    device_id = msg_id - 0x0CF11F00
    # safety: ensure len
    db = bytes(data_bytes)
    if len(db) < 6:
        return None

    rpm = (db[1] << 8) | db[0]
    controller_temp = db[2] - 40
    motor_temp = db[3] - 30

    status_byte = db[4]
    # feedback bits are at BIT3 .. BIT4? per spec earlier: feedback encoded at bits 3 (and maybe 4)
    # Using (status >> 3) & 0x03 like before
    feedback_bits = (status_byte >> 3) & 0x03
    feedback_dir = {0: "STOP", 1: "FWD", 2: "REV"}.get(feedback_bits, "UNK")

    # command bits are bits 1..0
    command_bits = status_byte & 0x03
    command_dir = {0: "STOP", 1: "FWD", 2: "REV"}.get(command_bits, "UNK")

    switch_byte = db[5]
    forward_sw = bool((switch_byte >> 5) & 0x01)
    reverse_sw = bool((switch_byte >> 4) & 0x01)
    brake_sw = bool((switch_byte >> 3) & 0x01)
    hall_a = bool(switch_byte & 0x01)
    hall_b = bool((switch_byte >> 1) & 0x01)
    hall_c = bool((switch_byte >> 2) & 0x01)

    return {
        "device_id": device_id,
        "rpm": rpm,
        "controller_temp": controller_temp,
        "motor_temp": motor_temp,
        "feedback_dir": feedback_dir,
        "command_dir": command_dir,
        "forward_sw": forward_sw,
        "reverse_sw": reverse_sw,
        "brake_sw": brake_sw,
        "hall_a": hall_a,
        "hall_b": hall_b,
        "hall_c": hall_c,
        "raw_hex": " ".join(f"{b:02X}" for b in db)
    }

# ----- Shared state between threads -----
# For each motor we keep:
# expected_dir[motor_id] = "FWD" or "REV" or None
# event_map[motor_id] = threading.Event set by RX when expected feedback seen
# tx_times[motor_id] = last send timestamp (float)
# rx_info_map[motor_id] = dict of last rx decode (populated by RX)
expected_dir = {m: None for m in MOTOR_IDS}
event_map = {m: threading.Event() for m in MOTOR_IDS}
tx_times = {m: None for m in MOTOR_IDS}
rx_info_map = {m: None for m in MOTOR_IDS}

# Lock for CSV writing and shared maps
map_lock = threading.Lock()
csv_lock = threading.Lock()

# ----- CSV header writer (create file) -----
with open(LOG_FILE, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow([
        "timestamp", "event_type", "motor_id", "command_dir", "feedback_dir",
        "command_rpm", "feedback_rpm", "response_delay_s",
        "controller_temp", "motor_temp",
        "tx_arb_id", "tx_data_hex", "rx_arb_id", "rx_data_hex", "note"
    ])
    

# ----- RX thread -----
def rx_thread_func(bus, stop_event):
    """
    Continuously read CAN frames. Decode known feedback frames.
    If feedback matches expected direction for that motor, store rx_info_map and set event.
    Always log received frames.
    """
    print("RX thread started")
    while not stop_event.is_set():
        try:
            msg = bus.recv(timeout=0.2)
        except Exception as e:
            print("RX bus.recv error:", e)
            msg = None

        if msg is None:
            continue

        arb = msg.arbitration_id
        raw_hex = " ".join(f"{b:02X}" for b in msg.data)
        tstamp = datetime.now().isoformat()

        # Log all RX messages
        with csv_lock:
            with open(LOG_FILE, "a", newline="") as fh:
                w = csv.writer(fh)
                w.writerow([tstamp, "RX_RAW", "", "", "",
                            "", "", "", "", "", "", "", f"0x{arb:X}", raw_hex, "raw"])

        # If this is a feedback frame of interest:
        # feedback IDs are 0x0CF11F00..0x0CF11FFF with device id in low byte
        if (arb & 0x0FFFFFF0) >> 4 == (0x0CF11F00 >> 4):  # tolerant mask
            # We prefer exact match:
            dev = arb - 0x0CF11F00
            if dev in MOTOR_IDS:
                info = decode_feedback(arb, msg.data)
                if info is None:
                    continue

                # Log decoded feedback
                with csv_lock:
                    with open(LOG_FILE, "a", newline="") as fh:
                        w = csv.writer(fh)
                        w.writerow([
                            tstamp, "RX_DECODE", info["device_id"], "", info["feedback_dir"],
                            "", info["rpm"], "", info["controller_temp"], info["motor_temp"],
                            "", "", f"0x{arb:X}", info["raw_hex"], ""
                        ])

                # If TX thread is expecting a certain direction for this motor, check & notify
                with map_lock:
                    expected = expected_dir.get(info["device_id"])
                if expected is not None and info["feedback_dir"] == expected:
                    # store rx info and set event
                    with map_lock:
                        rx_info_map[info["device_id"]] = {
                            "timestamp": tstamp,
                            "feedback_dir": info["feedback_dir"],
                            "rpm": info["rpm"],
                            "controller_temp": info["controller_temp"],
                            "motor_temp": info["motor_temp"],
                            "rx_arb_id": arb,
                            "rx_data_hex": info["raw_hex"]
                        }
                        # signal waiting TX thread
                        event_map[info["device_id"]].set()

    print("RX thread stopped")
    

# ----- TX thread -----
def tx_thread_func(bus, stop_event):
    """
    For each motor, send FWD command and wait for FWD feedback (or timeout),
    then send REV and wait for REV feedback. Repeat until stop_event or TEST_DURATION expires.
    """
    print("TX thread started")
    start_time = time.time()
    directions = ["FWD", "REV"]

    while not stop_event.is_set() and (time.time() - start_time) < TEST_DURATION:
        for motor in MOTOR_IDS:
            for direction in directions:
                if stop_event.is_set():
                    break

                # prepare and send command
                arb_id = motor_tx_id(motor)
                data = build_can_data(TEST_RPM, direction)
                tx_time = time.time()
                try:
                    bus.send(can.Message(arbitration_id=arb_id, data=data, is_extended_id=True))
                except Exception as e:
                    print(f"TX send error (motor {motor}): {e}")

                # record expected direction and tx_time
                with map_lock:
                    expected_dir[motor] = direction
                    tx_times[motor] = tx_time
                    # clear previous rx info and clear event
                    rx_info_map[motor] = None
                    event_map[motor].clear()

                tx_hex = " ".join(f"{b:02X}" for b in data)
                print(f"[TX] {datetime.now().isoformat()} Motor {motor} dir={direction} rpm={TEST_RPM} id=0x{arb_id:X} data={tx_hex}")

                # log the TX
                with csv_lock:
                    with open(LOG_FILE, "a", newline="") as fh:
                        w = csv.writer(fh)
                        w.writerow([
                            datetime.now().isoformat(), "TX", motor, direction, "",
                            TEST_RPM, "", "", "", "",
                            f"0x{arb_id:X}", tx_hex, "", "", ""
                        ])

                # wait for event set by RX thread (matching feedback) or timeout
                signaled = event_map[motor].wait(timeout=TX_TIMEOUT)

                # Gather rx data if available
                with map_lock:
                    rx = rx_info_map.get(motor)
                    # clear expected_dir after handling
                    expected_dir[motor] = None

                if signaled and rx is not None:
                    response_delay = None
                    if tx_times.get(motor) is not None:
                        response_delay = time.time() - tx_times[motor]
                    print(f"[MATCH] Motor {motor} expected={direction} got={rx['feedback_dir']} rpm={rx['rpm']} delay={response_delay:.4f}s")
                    # write match line
                    with csv_lock:
                        with open(LOG_FILE, "a", newline="") as fh:
                            w = csv.writer(fh)
                            w.writerow([
                                datetime.now().isoformat(), "MATCH", motor, direction, rx["feedback_dir"],
                                TEST_RPM, rx["rpm"], round(response_delay, 4) if response_delay else "",
                                rx["controller_temp"], rx["motor_temp"],
                                f"0x{arb_id:X}", tx_hex,
                                f"0x{rx['rx_arb_id']:X}", rx["rx_data_hex"], ""
                            ])
                else:
                    # Timeout or no matching feedback
                    print(f"[TIMEOUT] Motor {motor} did not respond with {direction} within {TX_TIMEOUT}s")
                    with csv_lock:
                        with open(LOG_FILE, "a", newline="") as fh:
                            w = csv.writer(fh)
                            w.writerow([
                                datetime.now().isoformat(), "TIMEOUT", motor, direction, "",
                                TEST_RPM, "", "", "", "",
                                f"0x{arb_id:X}", tx_hex, "", "", f"no_feedback_with_{direction}"
                            ])

                # short pause before next send to other motors
                time.sleep(TX_SLEEP_BETWEEN)

    print("TX thread stopped")

# ----- Main -----
def main():
    # open CAN bus
    try:
        bus = can.interface.Bus(channel=CAN_CHANNEL, bustype=CAN_BUSTYPE)
    except Exception as e:
        print("Failed to open CAN bus:", e)
        return

    stop_event = threading.Event()
    rx_thread = threading.Thread(target=rx_thread_func, args=(bus, stop_event), daemon=True)
    tx_thread = threading.Thread(target=tx_thread_func, args=(bus, stop_event), daemon=True)

    # start threads
    rx_thread.start()
    tx_thread.start()

    print(f"Test started for {TEST_DURATION} seconds. Logging to {LOG_FILE}")
    try:
        # wait for duration
        time.sleep(TEST_DURATION)
    except KeyboardInterrupt:
        print("Interrupted by user")

    # signal stop and join
    stop_event.set()
    tx_thread.join(timeout=2.0)
    rx_thread.join(timeout=2.0)

    print("Test finished. CSV:", LOG_FILE)

if __name__ == "__main__":
    main()
