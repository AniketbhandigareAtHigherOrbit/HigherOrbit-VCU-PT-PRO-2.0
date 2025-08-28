# -*- coding: utf-8 -*-
import can
import cantools
import time
import csv
import os
from datetime import datetime

CSV_FILE = "battery_data.csv"
DBC_PATH = 'Inverted_Protocol_DBC_File.dbc'
SEND_CAN_ID = 0x12300140
RESPONSE_TIMEOUT = 0.5  # seconds

FIELDNAMES = [
    "id",
    "battery_voltage", "current", "soc",
    "max_voltage", "min_voltage", "max_voltage_cells", "min_voltage_cells",
    "max_temp", "max_temp_cell", "min_temp", "min_temp_cell",
    "charge_dis_status", "charge_mos_status", "dis_mos_status",
    "bms_life", "residual_capacity",
    "No_of_btty_string", "No_of_Tempe", "Charger_status", "Load_status", "Reserved_4_0x12344001", "charge_discharge_cycles", "Reserved_7_0x12344001",
    "frame_number", "monomer_voltages", "reserved_7_0x12354001",
    "frame_number", "monomer_temperatures",
    "cell_balance_states",
    "failure_status",
    "decoded_full",
    "timestamp"
]


# Store combined data for CSV logging
decoded_full = {key: None for key in FIELDNAMES if key != "timestamp"}

# Variables for real-time usage
battery_voltage = None
current = None
soc = None

max_voltage = None
min_voltage = None
max_voltage_cells = None
min_voltage_cells = None

max_temp = None
max_temp_cell = None
min_temp = None
min_temp_cell = None

charge_dis_status = None
charge_mos_status = None
dis_mos_status = None
bms_life = None
residual_capacity = None

# Load DBC file
try:
    db = cantools.database.load_file(DBC_PATH)
    print(f"DBC file loaded successfully: {DBC_PATH}")
except Exception as e:
    print(f"Failed to load DBC file: {e}")
    db = None

def setup_can_bus(channel='can0', bustype='socketcan'):
    try:
        bus = can.interface.Bus(channel=channel, bustype=bustype)
        print(f"CAN interface '{channel}' initialized.")
        return bus
    except Exception as e:
        print(f"CAN interface error: {e}")
        return None

def send_request(bus, can_id):
    msg = can.Message(
        arbitration_id=can_id,
        data=[0x00] * 8,
        is_extended_id=True
    )
    try:
        bus.send(msg)
        print("Request sent to BMS")
    except can.CanError as e:
        print(f"Error sending request: {e}")

def save_to_csv(decoded):
    decoded["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, mode="a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(decoded)

def manual_decode(message):
    global battery_voltage, current, soc
    global max_voltage, min_voltage, max_voltage_cells, min_voltage_cells
    global max_temp, max_temp_cell, min_temp, min_temp_cell
    global charge_dis_status, charge_mos_status, dis_mos_status, bms_life, residual_capacity
    global No_of_btty_string, No_of_Tempe, Charger_status, Load_status, Reserved_4_0x12344001, charge_discharge_cycles, Reserved_7_0x12344001
    global frame_number, monomer_voltages, reserved_7_0x12354001
    global frame_number, monomer_temperatures
    global cell_balance_states
    global failure_status
    global decoded_full

    data = message.data

    if decoded_full["id"] is None:
        decoded_full["id"] = hex(message.arbitration_id)

    if message.arbitration_id in [0x12304001, 0x12304002]:
        battery_voltage = int.from_bytes(data[0:2], 'big') * 0.1
        current_raw = int.from_bytes(data[4:6], 'big')
        current = (current_raw - 30000) * 0.1
        soc = int.from_bytes(data[6:8], 'big') * 0.1

        decoded_full["battery_voltage"] = battery_voltage
        decoded_full["current"] = current
        decoded_full["soc"] = soc

    elif message.arbitration_id in [0x12314001, 0x12314002]:
        max_voltage = int.from_bytes(data[0:2], 'big')
        max_voltage_cells = data[2]
        min_voltage = int.from_bytes(data[3:5], 'big')
        min_voltage_cells = data[5]

        decoded_full["max_voltage"] = max_voltage
        decoded_full["max_voltage_cells"] = max_voltage_cells
        decoded_full["min_voltage"] = min_voltage
        decoded_full["min_voltage_cells"] = min_voltage_cells

    elif message.arbitration_id in [0x12324001, 0x12324002]:
        max_temp = data[0] - 40
        max_temp_cell = data[1]
        min_temp = data[2] - 40
        min_temp_cell = data[3]

        decoded_full["max_temp"] = max_temp
        decoded_full["max_temp_cell"] = max_temp_cell
        decoded_full["min_temp"] = min_temp
        decoded_full["min_temp_cell"] = min_temp_cell

    elif message.arbitration_id in [0x12334001, 0x12334002]:
        charge_dis_status = data[0]
        charge_mos_status = data[1]
        dis_mos_status = data[2]
        bms_life = data[3]
        residual_capacity = int.from_bytes(data[4:8], 'big')

        decoded_full["charge_dis_status"] = charge_dis_status
        decoded_full["charge_mos_status"] = charge_mos_status
        decoded_full["dis_mos_status"] = dis_mos_status
        decoded_full["bms_life"] = bms_life
        decoded_full["residual_capacity"] = residual_capacity
    
    elif message.arbitration_id in [0x12344001, 0x12344002]:
        
        No_of_btty_string = data[0]
        No_of_Tempe = data[1]
        Charger_status = data[2] #(0 disconnect 1 access)
        Load_status = data[3]    #(0 disconnect 1 access)                           
        Reserved_4_0x12344001 = data[4]
        charge_discharge_cycles = int.from_bytes(data[5:7], 'big')
        Reserved_7_0x12344001 = data[7]

        decoded_full["No_of_btty_string"] = No_of_btty_string
        decoded_full["No_of_Tempe"] = No_of_Tempe
        decoded_full["Charger_status"] = Charger_status
        decoded_full["Reserved_4_0x12344001"] = Reserved_4_0x12344001
        decoded_full["charge_discharge_cycles"] = charge_discharge_cycles 
        decoded_full["Reserved_7_0x12344001"] = Reserved_7_0x12344001
        print(No_of_btty_string, No_of_Tempe, Charger_status)
        
#--------------------------------------------------------------------------------------
    elif message.arbitration_id in [0x12354001, 0x12354002]:
        frame_number = data[0]  # Frame number, starts from 0; 0xFF invalid

        # Monomer voltages: Each cell voltage is 2 bytes, in millivolts
        monomer_voltages = []
        for i in range(1, 7, 2):  # Bytes 1–6
            voltage_mv = int.from_bytes(data[i:i+2], 'big')  # Big endian
            monomer_voltages.append(voltage_mv)

        reserved_7_0x12354001 = data[7]

        decoded_full["frame_number"] = frame_number
        decoded_full["monomer_voltages"] = monomer_voltages
        decoded_full["reserved_7_0x12354001"] = reserved_7_0x12354001
        
    elif message.arbitration_id in [0x12344001, 0x12344002]:
        
        No_of_btty_string = data[0]
        No_of_Tempe = data[1]
        Charger_status = data[2] #(0 disconnect 1 access)
        Load_status = data[3]    #(0 disconnect 1 access)                           
        Reserved_4_0x12344001 = data[4]
        charge_discharge_cycles = int.from_bytes(data[5:7], 'big')
        Reserved_7_0x12344001 = data[7]

        decoded_full["No_of_btty_string"] = No_of_btty_string
        decoded_full["No_of_Tempe"] = No_of_Tempe
        decoded_full["Charger_status"] = Charger_status
        decoded_full["Reserved_4_0x12344001"] = Reserved_4_0x12344001
        decoded_full["charge_discharge_cycles"] = charge_discharge_cycles 
        decoded_full["Reserved_7_0x12344001"] = Reserved_7_0x12344001
        
#--------------------------------------------------------------------------------------
    elif message.arbitration_id in [0x12354001, 0x12354002]:
        frame_number = data[0]  # Frame number, starts from 0; 0xFF invalid

        # Monomer voltages: Each cell voltage is 2 bytes, in millivolts
        monomer_voltages = []
        for i in range(1, 7, 2):  # Bytes 1–6
            voltage_mv = int.from_bytes(data[i:i+2], 'big')  # Big endian
            monomer_voltages.append(voltage_mv)

        reserved_7_0x12354001 = data[7]

        decoded_full["frame_number"] = frame_number
        decoded_full["monomer_voltages"] = monomer_voltages
        decoded_full["reserved_7_0x12354001"] = reserved_7_0x12354001


#--------------------------------------------------------------------------------------
    elif message.arbitration_id in [0x12364001, 0x12364001]:
        frame_number = data[0]  # Frame number, starts from 0

        # Monomer temperatures: each 1 byte, with 40°C offset
        monomer_temperatures = []
        for i in range(1, 8):  # Bytes 1–7
            temp_c = data[i] - 40
            monomer_temperatures.append(temp_c)

        decoded_full["frame_number"] = frame_number
        decoded_full["monomer_temperatures"] = monomer_temperatures

#----------------------------------------------------------------------------------------
    elif message.arbitration_id in [0x12374001, 0x12374002]:
        # Combine all 8 bytes into a single 64-bit integer (big-endian)
        balance_bits = int.from_bytes(data, 'big')

        # Extract balance states for cells 1 to 48 (Bit0 = Cell 1)
        cell_balance_states = []
        for cell in range(48):
            state = (balance_bits >> cell) & 0x01  # 0 = Closed, 1 = Open
            cell_balance_states.append(state)

        decoded_full["cell_balance_states"] = cell_balance_states

#-----------------------------------------------------------------------------------------
    elif message.arbitration_id in [0x12384001, 0x12384002]:
        failure_status = {}

        # Byte 0
        failure_status["cell_volt_high_lvl1"] = (data[0] >> 0) & 0x01
        failure_status["cell_volt_high_lvl2"] = (data[0] >> 1) & 0x01
        failure_status["cell_volt_low_lvl1"] = (data[0] >> 2) & 0x01
        failure_status["cell_volt_low_lvl2"] = (data[0] >> 3) & 0x01
        failure_status["sum_volt_high_lvl1"] = (data[0] >> 4) & 0x01
        failure_status["sum_volt_high_lvl2"] = (data[0] >> 5) & 0x01
        failure_status["sum_volt_low_lvl1"]  = (data[0] >> 6) & 0x01
        failure_status["sum_volt_low_lvl2"]  = (data[0] >> 7) & 0x01

        # Byte 1
        failure_status["chg_temp_high_lvl1"]  = (data[1] >> 0) & 0x01
        failure_status["chg_temp_high_lvl2"]  = (data[1] >> 1) & 0x01
        failure_status["chg_temp_low_lvl1"]   = (data[1] >> 2) & 0x01
        failure_status["chg_temp_low_lvl2"]   = (data[1] >> 3) & 0x01
        failure_status["dischg_temp_high_lvl1"] = (data[1] >> 4) & 0x01
        failure_status["dischg_temp_high_lvl2"] = (data[1] >> 5) & 0x01
        failure_status["dischg_temp_low_lvl1"]  = (data[1] >> 6) & 0x01
        failure_status["dischg_temp_low_lvl2"]  = (data[1] >> 7) & 0x01

        # Byte 2
        failure_status["chg_overcurrent_lvl1"]   = (data[2] >> 0) & 0x01
        failure_status["chg_overcurrent_lvl2"]   = (data[2] >> 1) & 0x01
        failure_status["dischg_overcurrent_lvl1"] = (data[2] >> 2) & 0x01
        failure_status["dischg_overcurrent_lvl2"] = (data[2] >> 3) & 0x01
        failure_status["soc_high_lvl1"]          = (data[2] >> 4) & 0x01
        failure_status["soc_high_lvl2"]          = (data[2] >> 5) & 0x01
        failure_status["soc_low_lvl1"]           = (data[2] >> 6) & 0x01
        failure_status["soc_low_lvl2"]           = (data[2] >> 7) & 0x01

        # Byte 3
        failure_status["diff_volt_lvl1"] = (data[3] >> 0) & 0x01
        failure_status["diff_volt_lvl2"] = (data[3] >> 1) & 0x01
        failure_status["diff_temp_lvl1"] = (data[3] >> 2) & 0x01
        failure_status["diff_temp_lvl2"] = (data[3] >> 3) & 0x01
        # Bits 4–7 Reserved

        # Reserved bytes
        failure_status["reserved_4"] = data[4]
        failure_status["reserved_5"] = data[5]
        failure_status["reserved_6"] = data[6]
        failure_status["reserved_7"] = data[7]

        decoded_full["battery_failure_status"] = failure_status
        
        print(battery_voltage, current, soc,max_voltage, min_voltage, max_voltage_cells, min_voltage_cells,max_temp, max_temp_cell,
         min_temp, min_temp_cell,charge_dis_status, charge_mos_status, dis_mos_status,bms_life, 
        residual_capacity,No_of_btty_string, No_of_Tempe, Charger_status, Load_status, Reserved_4_0x12344001, charge_discharge_cycles, Reserved_7_0x12344001,
        frame_number, monomer_voltages, reserved_7_0x12354001,frame_number,cell_balance_states,failure_status,decoded_full)

        

    # Save once all fields are collected
    if all(decoded_full[key] is not None for key in FIELDNAMES if key != "timestamp"):
        save_to_csv(decoded_full)
        print("? Data saved:", decoded_full)
        decoded_full = {key: None for key in FIELDNAMES if key != "timestamp"}  # Reset for next cycle

def receive_response(bus):
    try:
        msg = bus.recv(timeout=RESPONSE_TIMEOUT)
        if msg is None:
            print("No response received.")
            return None

        if db:
            try:
                decoded = db.decode_message(msg.arbitration_id, msg.data)
                print("Decoded by DBC:", decoded)
            except Exception:
                manual_decode(msg)
        else:
            manual_decode(msg)

        return msg

    except Exception as e:
        print(f"Receive error: {e}")
        return None

if __name__ == '__main__':
    bus = setup_can_bus()
    if bus:
        while True:
            #print(f"[Decoded] ID: {decoded_full['id']} Data: {decoded_full}")
            send_request(bus, SEND_CAN_ID)
            time.sleep(0.1)
            receive_response(bus)
            time.sleep(0.5)

