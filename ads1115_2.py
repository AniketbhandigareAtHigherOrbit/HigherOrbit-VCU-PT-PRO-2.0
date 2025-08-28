import time
import board
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# Create I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Create ADS object
ads = ADS1115(i2c, address=0x48)  # Change address if needed

# Create input channel on A0
chan = AnalogIn(ads, ADS1115.P0)

# Read voltage
while True:
    print(f"Voltage on A0: {chan.voltage:.3f} V")
    time.sleep(1)
