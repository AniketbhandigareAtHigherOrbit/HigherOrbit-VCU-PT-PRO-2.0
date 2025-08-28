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
    if message.arbitration_id == 0x12314002:
        print(f"trying on: {message.arbitration_id}")
        max_voltage = int.from_bytes(data[0:2], 'big')
        max_cells = data[2]
        min_voltage = int.from_bytes(data[3:5], 'big')
        min_cells = data[5]

        print("   Manually Decoded Max/Min Cell Voltage Data")
        print(f"    - Max Voltage      : {max_voltage} mV")
        print(f"    - Cells @ Max Volt : {max_cells}")
        print(f"    - Min Voltage      : {min_voltage} mV")
        print(f"    - Cells @ Min Volt : {min_cells}")
        
    elif message.arbitration_id in [0x12304001, 0x12304002]:
        data = message.data
        battery_voltage = int.from_bytes(data[0:2], 'big') * 0.1
        current_raw = int.from_bytes(data[4:6], 'big')
        current = (current_raw - 30000) * 0.1
        soc = int.from_bytes(data[6:8], 'big') * 0.1

        print("  ?? Manually Decoded SOC Data:")
        print(f"    - Battery Voltage: {battery_voltage:.1f} V")
        print(f"    - Current        : {current:.1f} A")
        print(f"    - SOC            : {soc:.1f} %")
        
    else:
        pass
        #print("   Unknown response ID, cannot manually decode")

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
