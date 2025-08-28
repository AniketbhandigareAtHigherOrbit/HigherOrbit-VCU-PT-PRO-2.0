import can
import cantools

# Load the DBC file
db = cantools.database.load_file('Inverted_Protocol_DBC_File.dbc')

# Set up CAN bus (SPI interface, MCP2515)
can_interface = 'can0'
bus = can.interface.Bus(channel=can_interface, bustype='socketcan')

print("Listening for CAN messages...")

try:
    while True:
        message = bus.recv()  # Receive CAN message
        if message is not None:
            try:
                decoded_msg = db.decode_message(message.arbitration_id, message.data)
                print(f"ID: {hex(message.arbitration_id)}, Decoded Data: {decoded_msg}")
            except Exception as e:
                print(f"ID: {hex(message.arbitration_id)}, Raw Data: {message.data.hex()} (Undecodable: {e})")
except KeyboardInterrupt:
    print("Stopped by user.")
