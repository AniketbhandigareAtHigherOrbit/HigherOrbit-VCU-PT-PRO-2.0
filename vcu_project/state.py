
# state.py ? shared global state for all modules
import threading
import RPi.GPIO as GPIO
state_lock = threading.Lock()

SEND_CAN_ID = 0x12300140
# Current drive data
current_rpm = 0 
rotary_current_rpm = 0 
current_direction = 0x01 # 0x01 = forward, 0x02 = reverse

TURN_RPM=300
MAX_RPM_ON_ROAD = 1500
LONG_PRESS_RPM_ON_ROAD = 300

MAX_RPM_OFF_ROAD = 1500
ROTARY_MAX_RPM = 1000
LONG_PRESS_RPM_OFF_ROAD = 300

LONG_PRESS_TIME = 0.02     # seconds to consider as long press
DOUBLE_PRESS_GAP = 0.20    # max time between taps for double press
SEND_PERIOD = 0.1          # periodic CAN refresh (10 Hz)

RPM_SLEW_RATE = 150
# Twirl pattern (both motors)
STEP_TIMES = [2.50, 8.50, 2.50]
L_STEPS = [(300, 300), (300, 100), (300, 300)]
R_STEPS = [(300, 300), (100, 300), (300, 300)]

#STEP_TIMES = [3.0, 8, 0.2, 0.2, 0.2]
#L_STEPS = [(300, 300), (300, 100), (0, 0), (0, 0), (0, 0)]
#R_STEPS = [(300, 300), (100, 300), (0, 0), (0, 0), (0, 0)]

SINGLE_RIGHT_LOW =100
SINGLE_LEFT_LOW =100

# Motor feedback
feedbackRPM_Left = 0
feedbackRPM_Right = 0

# ---------- GPIO ----------
LEFT_BTN_PIN = 26
RIGHT_BTN_PIN = 22
MODE_SWITCH_PIN = 20
DIRECTION_BTN_PIN = 21
ROTARY_SWITCH_PIN = 16
SAFETY_PIN = 16

GPIO.setmode(GPIO.BCM)
GPIO.setup([LEFT_BTN_PIN, RIGHT_BTN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(MODE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(DIRECTION_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(ROTARY_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(SAFETY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Mode tracking
MODE_IDLE = 0
MODE_SINGLE_LEFT = 1
MODE_SINGLE_RIGHT = 2
MODE_TWIRL_LEFT = 3
MODE_TWIRL_RIGHT = 4
mode = MODE_IDLE

# Feedback assist
RE_ALIGN_RPM_REDUCTION = 100   # how much to trim the faster motor
FEEDBACK_TOLERANCE = 50        # acceptable RPM difference before correcting
LOW_RPM_FEEDBACK_OFF = 300     # <--- ignore feedback below

# Button states
direction_btn_last_state = False  # Was LOW
#current_direction = 0x01  # 0x01 = forward, 0x02 = reverse
last_direction_toggle = 0.0
DIRECTION_DEBOUNCE = 0.3  # seconds

left_pressed = False
right_pressed = False
left_press_start = 0.0
right_press_start = 0.0
left_last_rise = 0.0
right_last_rise = 0.0

last_left_rpm = 0
last_right_rpm = 0

twirl_step = 0
twirl_step_start = 0.0
last_send_time = 0.0
feedbackRPM_Left = 0
feedbackRPM_Right = 0

# Safety
is_safe_stop = False

# Stopwatch globals
hours = 0
mins = 0
secs = 0

# Optional: store start time
stopwatch_start = 0

# Latest CAN device data
device_4_rpm = None
device_4_current = None
device_4_voltage = None
device_4_error = None

device_5_rpm = None
device_5_current = None
device_5_voltage = None
device_5_error = None

device_6_rpm = None
device_6_current = None
device_6_voltage = None
device_6_error = None

#----------------------------------------------------------
#Battery data 
# Variables for real-time usage
'''battery_voltage = None
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

decoded_full = None'''

max_voltage = None
max_cells = None
min_voltage = None
min_cells = None

battery_voltage = None
current = None
soc = None

max_temp = None
max_temp_cell = None
min_temp = None
min_temp_cell = None
 
charge_dis_status = None
charge_mos_status = None
dis_mos_status = None
bms_life = None
residual_capacity = None


#------------------------------------
total_power_1 = 0.0     # Wh

# Computed values for current trip
power = 0.0             # W
total_energy = 0.0      # Wh
trip_runtime = 0.0      # hours (accumulated time machine was running)

# Persistent last trip values
Last_trip_power = 0.0
Last_trip_total_energy = 0.0  # Wh
Last_trip_trip_runtime = 0.0  # hours
