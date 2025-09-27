# stress_test_motor_manager.py
import can
import time
import logging
import argparse
from motor_manager import MotorManager

def run_test(wheel_hz, rotary_hz, duration=5):
    print(f"\n?? Testing at wheel_hz={wheel_hz}, rotary_hz={rotary_hz}")
    bus = can.interface.Bus(channel="can0", interface="socketcan")
    mm = MotorManager(bus, wheel_hz=wheel_hz, rotary_hz=rotary_hz)

    try:
        mm.set_wheels(500, 500, 0x01)
        mm.set_rotary(300, 0x01)
        time.sleep(duration)
        mm.stop_all()
        time.sleep(1)
    finally:
        mm.shutdown()
        bus.shutdown()   # ? closes socket, removes warning


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep", action="store_true",
                        help="Run sweep test at multiple Hz values")
    parser.add_argument("--wheel_hz", type=int, default=20,
                        help="Wheel update rate Hz")
    parser.add_argument("--rotary_hz", type=int, default=20,
                        help="Rotary update rate Hz")
    parser.add_argument("--duration", type=int, default=5,
                        help="Duration per test in seconds")
    args = parser.parse_args()

    if args.sweep:
        # Sweep test from 10 Hz up to 200 Hz
        for hz in [10, 20, 50, 100, 150, 200, 300, 400]:
            run_test(hz, hz, args.duration)
            print("? Completed", hz, "Hz test")
            time.sleep(2)
    else:
        run_test(args.wheel_hz, args.rotary_hz, args.duration)

if __name__ == "__main__":
    main()
