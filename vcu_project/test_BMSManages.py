import time
import threading
import state
import can
from control.motor_manager import MotorManager, BMSManager
#from can_setup import setup_can_bus # <- your CAN setup

def print_battery_state():
    """Print current state values (for testing)."""
    print("------ Battery State ------")
    print(f"Battery Voltage     : {state.battery_voltage}")
    print(f"Current             : {state.current}")
    print(f"SOC (%)             : {state.soc}")
    print(f"Max Voltage         : {state.max_voltage}")
    print(f"Min Voltage         : {state.min_voltage}")
    print(f"Max Voltage Cell    : {state.max_voltage_cells}")
    print(f"Min Voltage Cell    : {state.min_voltage_cells}")
    print(f"Max Temp            : {state.max_temp}")
    print(f"Max Temp Cell       : {state.max_temp_cell}")
    print(f"Min Temp            : {state.min_temp}")
    print(f"Min Temp Cell       : {state.min_temp_cell}")
    print(f"Charge/Dis Status   : {state.charge_dis_status}")
    print(f"Charge MOS Status   : {state.charge_mos_status}")
    print(f"Discharge MOS Status: {state.dis_mos_status}")
    print(f"BMS Life (%)        : {state.bms_life}")
    print(f"Residual Capacity   : {state.residual_capacity}")
    print(f"Decoded Full Frame  : {state.decoded_full}")
    print("---------------------------\n")


def main():
    bus = can.interface.Bus(channel="can0", bustype="socketcan")

    # Start BMS manager in background
    bms = BMSManager(bus)

    # Run test loop
    try:
        while True:
            print_battery_state()
            time.sleep(1)  # print every second
    except KeyboardInterrupt:
        print("Exiting test...")


if __name__ == "__main__":
    main()
