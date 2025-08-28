import can
import cantools
import time
import struct

DBC_PATH = 'Inverted_Protocol_DBC_File.dbc'
SEND_CAN_ID = 0x12300140
RESPONSE_TIMEOUT = 9.0  # seconds

# Load DBC globally
try:
    db = cantools.database.load_file(DBC_PATH)
    print(f"DBC file loaded successfully: {DBC_PATH}")
except Exception as e:
    print(f"Failed to load DBC file: {e}")
    db = None

def format_can_data(data):
    return ' '.join(f'{byte:02X}' for byte in data)

def get_timestamp():
    return time.strftime("[%H:%M:%S]")

def send_request(bus):
    msg = can.Message(
        arbitration_id=SEND_CAN_ID,
        data=[0x00] * 8,
        is_extended_id=True
    )
    try:
        bus.send(msg)
        print("Request sent to BMS")
    except can.CanError as e:
        print(f"Error sending request: {e}")

def manual_decode(message):
    data = message.data
    
def manual_decode(msg):
    can_id = msg.arbitration_id
    data = msg.data

    if can_id == 0x12304002:
        soc = data[0]
        voltage_raw = (data[1] << 8) | data[2]
        current_raw = (data[3] << 8) | data[4]
        voltage = voltage_raw / 100.0  # Example: 30000 => 300.00V
        current = (current_raw - 10000) / 10.0  # Example: 965 => -35A
        print(f"?? SOC={soc}%, Voltage={voltage:.2f}V, Current={current:.2f}A")

    elif can_id == 0x12314002:
        max_volt_cell = data[0]
        max_volt = data[1]
        min_volt_cell = data[2]
        min_volt = data[3]
        print(f"?? MaxVoltCell={max_volt_cell}, MaxVolt={max_volt}, MinVoltCell={min_volt_cell}, MinVolt={min_volt}")

    elif can_id == 0x12324002:
        max_temp_cell = data[0]
        max_temp = data[1]
        min_temp_cell = data[2]
        min_temp = data[3]
        print(f"??? MaxTempCell={max_temp_cell}, MaxTemp={max_temp}C, MinTempCell={min_temp_cell}, MinTemp={min_temp}C")

    elif can_id == 0x12334002:
        mos_status = data[1]
        print(f"? MOS Status={mos_status}")

    elif can_id == 0x12344002:
        status_flags = data[0]
        fault_flags = data[1]
        print(f"?? Protection Status: {bin(status_flags)}, Faults: {bin(fault_flags)}")

    elif can_id == 0x12354002:
        index = data[0]
        c1 = data[1]
        c2 = data[3]
        c3 = data[5]
        print(f"?? Cell Block {index}: C1={c1}, C2={c2}, C3={c3}")

    elif can_id == 0x12364002:
        print(f"?? BMS Status Info: {data.hex()}")

    elif can_id == 0x12374002:
        print("??? Balance Info or Reserved Frame (All 0s)")

    elif can_id == 0x520:
        print(f"?? Charger Status (0x520): {data.hex()}")

    elif can_id == 0x521:
        print(f"?? Charger Data (0x521): {data.hex()}")

    else:
        print(f"?? Undecoded ID: {hex(can_id)}, Raw: {data.hex()}")


def receive_response(bus):
    try:
        msg = bus.recv(timeout=RESPONSE_TIMEOUT)
        if msg is None:
            print("No response received.")
            return

        timestamp = get_timestamp()
        print(f"\n{timestamp} Received: ID=0x{msg.arbitration_id:X}, DLC={msg.dlc}",f"  Bytes     : {format_can_data(msg.data)}")
        #print(f"  Bytes     : {format_can_data(msg.data)}")

        if db:
            try:
                decoded = db.decode_message(msg.arbitration_id, msg.data)
                print("   Decoded by DBC:")
                for signal, value in decoded.items():
                    print(f"    - {signal}: {value}")
            except Exception as e:
                #print(f"   Could not decode using DBC: {e}")
                #print("   Trying manual decode...")
                manual_decode(msg)

        else:
            print("DBC decoding skipped (DBC not loaded)")
            


    except Exception as e:
        print(f"Receive error: {e}")

def main():
    try:
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        print("CAN interface initialized.\n")

        while True:
            send_request(bus)
            time.sleep(0.1)
            receive_response(bus)
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"CAN interface error: {e}")

if __name__ == '__main__':
    main()
