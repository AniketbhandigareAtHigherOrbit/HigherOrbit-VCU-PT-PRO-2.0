import spidev
import time
import RPi.GPIO as GPIO

# --- Pin config ---
RST_PIN = 12  # Reset pin (change if needed)

# --- Init GPIO ---
GPIO.setmode(GPIO.BCM)
GPIO.setup(RST_PIN, GPIO.OUT)

# --- Reset sequence ---
GPIO.output(RST_PIN, GPIO.LOW)
time.sleep(0.1)
GPIO.output(RST_PIN, GPIO.HIGH)
time.sleep(0.1)

# --- SPI setup ---
spi = spidev.SpiDev()
spi.open(0, 1)  # /dev/spidev0.1
spi.max_speed_hz = 500000
spi.mode = 0

# ST7920 constants
CMD = 0xF8
DATA = 0xFA

def send_cmd(cmd):
    """Send command to ST7920."""
    spi.xfer2([CMD, cmd & 0xF0, (cmd << 4) & 0xF0])
    time.sleep(0.001)

def send_data(data):
    """Send data to ST7920."""
    spi.xfer2([DATA, data & 0xF0, (data << 4) & 0xF0])
    time.sleep(0.001)

def init_display():
    send_cmd(0x30)  # Basic instruction set
    time.sleep(0.01)
    send_cmd(0x0C)  # Display ON, cursor OFF
    time.sleep(0.01)
    send_cmd(0x01)  # Clear display
    time.sleep(0.02)
    send_cmd(0x06)  # Entry mode set

def set_ddram_addr(addr):
    send_cmd(0x80 | addr)

def write_text(text):
    for ch in text:
        send_data(ord(ch))

# --- Run test ---
init_display()
set_ddram_addr(0x00)  # First line
write_text("Hello World!")
time.sleep(2.1)
set_ddram_addr(0xB9)  # Second line
write_text("ST7920 OK")

print("Text written to display")
