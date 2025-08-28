# config.py

### === General Settings === ###
PROJECT_NAME = "VCU for Electric Farming Vehicle"
VERSION = "1.0"
DEBUG_MODE = True

### === ADS1115 Settings === ###
ADC_CHANNEL = 0  # Using A0 (ADS.P0)
ADC_VOLTAGE_THRESHOLD = 3.0  # Minimum voltage before warning

### === CAN Bus Settings === ###
CAN_CHANNEL = "can0"
CAN_BUSTYPE = "socketcan"
CAN_TIMEOUT = 1.0  # seconds

### === Traction Control Settings === ###
MAX_SAFE_SPEED = 50  # km/h
MIN_SAFE_VOLTAGE = 3.0  # volts

### === Logging Settings === ###
LOG_LEVEL = "INFO"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

### === Mode Manager Settings === ###
DEFAULT_MODE = "on_farm"
AVAILABLE_MODES = ["on_road", "on_farm", "puddling"]

### === Watchdog === ###
WATCHDOG_INTERVAL = 5  # seconds


