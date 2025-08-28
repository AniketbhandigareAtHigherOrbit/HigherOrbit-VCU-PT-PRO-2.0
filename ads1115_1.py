import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import time
# Initialize the I2C interface
i2c = busio.I2C(board.SCL, board.SDA)
print(i2c)
# Create an ADS1115 object
ads = ADS.ADS1115(i2c)
print(ads)
# Define the analog input channel
channel_1 = AnalogIn(ads, ADS.P0)
channel_2 = AnalogIn(ads, ADS.P1)
channel_3 = AnalogIn(ads, ADS.P2)
channel_4 = AnalogIn(ads, ADS.P3)

# Loop to read the analog input continuously
while True:
    '''
    print("Analog Value 1: ", channel_1.value)
    print("Analog Value 2: ", channel_2.value)
    print("Analog Value 3: ", channel_3.value)
    print("Analog Value 4: ", channel_4.value)
    time.sleep(0.9)s
    #print("Analog Value: ", channel.value, "Voltage: ", channel.voltage)
'''
