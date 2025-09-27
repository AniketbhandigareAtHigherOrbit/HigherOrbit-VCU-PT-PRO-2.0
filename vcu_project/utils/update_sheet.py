import gspread
from google.oauth2.service_account import Credentials
import time
import state
# Path to JSON credentials
SERVICE_ACCOUNT_FILE = "/home/orbit/VCU-PT-PRO-2.0/vcu_project/vcu-data-sheet-514fbe4de9c7.json"

# Google Sheets scope
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Authenticate
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

# === USE SHEET ID DIRECTLY (not URL) ===
SHEET_ID = "12jXRnZzKICr4MGd61lxa71orj2tjaUUUDm7i-YOgu98"  # paste only the ID, not the full link
sheet = client.open_by_key(SHEET_ID).sheet1

# Quick test: print sheet name
print("Connected to sheet:", sheet.title)

# Example: Append data every 5 sec
counter = 0

def update_sheet():
	
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    row = [
        timestamp,
        state.mode,
        state.current_rpm,
        state.rotary_current_rpm,
        hex(state.current_direction),
        state.MODE_IDLE,
        state.MODE_SINGLE_LEFT,
        state.MODE_SINGLE_RIGHT,
        state.MODE_TWIRL_LEFT,
        state.MODE_TWIRL_RIGHT,
    ]

    sheet.append_row(row)
    print("? Updated:", row)

