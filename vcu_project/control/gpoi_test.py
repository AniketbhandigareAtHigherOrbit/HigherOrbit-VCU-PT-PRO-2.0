import RPi.GPIO as GPIO
import time

# Use BCM numbering
GPIO.setmode(GPIO.BCM)

# Pins to test
pins = [22, 27, 17]

# Setup pins as input with internal pull-down resistors
GPIO.setup(pins, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

print("Reading GPIO 22 and GPIO 27... Press Ctrl+C to stop.")

try:
    while True:
        states = {pin: GPIO.input(pin) for pin in pins}
        print(f"GPIO 22: {states[22]}   GPIO 27: {states[27]}   GPIO 17: {states[17]}")
        time.sleep(0)
except KeyboardInterrupt:
    print("\nStopped by user.")
finally:
    GPIO.cleanup()
