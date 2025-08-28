# st7920_driver.py
import RPi.GPIO as GPIO
import spidev
import time
from copy import deepcopy

class ST7920:
    WIDTH = 128
    HEIGHT = 64

    #def __init__(self, rst_pin=17, cs_pin=27, spi_bus=0, spi_dev=1):
    def __init__(self, rst_pin=17, cs_pin=8, spi_bus=0, spi_dev=0):
        
        self.RST_PIN = rst_pin
        self.CS_PIN  = cs_pin

        # GPIO setup
        if not GPIO.getmode():      # Check if mode is already set
            GPIO.setmode(GPIO.BCM)  # or GPIO.BOARD
        GPIO.setwarnings(False)
        GPIO.setup(self.RST_PIN, GPIO.OUT)
        GPIO.setup(self.CS_PIN, GPIO.OUT)

        # SPI setup
        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_dev)
        self.spi.max_speed_hz = 1800000

        # Framebuffer
        self.fbuff = [[0]*(self.WIDTH//8) for _ in range(self.HEIGHT)]
        self.disp_fbuff = None

        self.init_display()

    # ---------- LOW LEVEL LCD FUNCTIONS ----------
    def reset(self):
        GPIO.output(self.RST_PIN, GPIO.LOW)
        time.sleep(0.05)
        GPIO.output(self.RST_PIN, GPIO.HIGH)
        time.sleep(0.05)

    def send(self, rs, rw, byte):
        b1 = 0b11111000 | ((rw & 0x01)<<2) | ((rs & 0x01)<<1)
        high = byte & 0xF0
        low  = (byte & 0x0F) << 4
        GPIO.output(self.CS_PIN, GPIO.LOW)
        self.spi.xfer2([b1, high, low])
        GPIO.output(self.CS_PIN, GPIO.HIGH)
        time.sleep(0.001)

    def command(self, cmd):
        self.send(0, 0, cmd)

    def data(self, dat):
        self.send(1, 0, dat)

    # ---------- INIT / CLEAR ----------
    def init_display(self):
        self.reset()
        self.command(0x30)
        self.command(0x30)
        self.command(0x0C)
        self.command(0x34)
        self.command(0x34)
        self.command(0x36)

    def clear(self):
        self.fbuff = [[0]*(self.WIDTH//8) for _ in range(self.HEIGHT)]
        
    def clear_display(self):
        self.clear()
        self.redraw()
        
    # ---------- GRAPHICS ----------
    def plot(self, x, y, set=True):
        if x < 0 or x >= self.WIDTH or y < 0 or y >= self.HEIGHT:
            return
        if set:
            self.fbuff[y][x//8] |= 1 << (7-(x%8))
        else:
            self.fbuff[y][x//8] &= ~(1 << (7-(x%8)))

    def line(self, x1, y1, x2, y2, set=True):
        dx = abs(x2-x1)
        dy = abs(y2-y1)
        sx = 1 if x1<x2 else -1
        sy = 1 if y1<y2 else -1
        err = dx - dy
        while True:
            self.plot(x1, y1, set)
            if x1==x2 and y1==y2:
                break
            e2 = 2*err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

    def rect(self, x1, y1, x2, y2, set=True):
        self.line(x1, y1, x2, y1, set)
        self.line(x2, y1, x2, y2, set)
        self.line(x2, y2, x1, y2, set)
        self.line(x1, y2, x1, y1, set)

    # ---------- REDRAW ----------
    def _send_line(self, row, dx1, dx2):
        self.command(0x80 + (row % 32))
        self.command(0x80 + (dx1//16) + (8 if row>=32 else 0))
        for b in self.fbuff[row][dx1//8:(dx2//8)+1]:
            self.data(b)


    def redraw(self):
        for row in range(self.HEIGHT):
            self._send_line(row, 0, self.WIDTH-1)
        self.disp_fbuff = deepcopy(self.fbuff)

    # ---------- TEXT ----------
    def put_text(self, s, x, y, scale=1):
        font = {
            'A':[0x7E,0x09,0x09,0x09,0x7E],
            'N':[0x7F,0x02,0x04,0x08,0x7F],
            'I':[0x00,0x41,0x7F,0x41,0x00],
            'K':[0x7F,0x08,0x14,0x22,0x41],
            'H':[0x7F,0x08,0x08,0x08,0x7F],
            'E':[0x7F,0x49,0x49,0x49,0x41],
            'L':[0x7F,0x40,0x40,0x40,0x40],
            'O':[0x3E,0x41,0x41,0x41,0x3E],
            'W':[0x3F,0x40,0x38,0x40,0x3F],
            'R':[0x7F,0x09,0x19,0x29,0x46],
            'D':[0x7F,0x41,0x41,0x22,0x1C],
            'T':[0x01,0x01,0x7F,0x01,0x01],
            'T':[0x01,0x01,0x7F,0x01,0x01],
            ' ': [0,0,0,0,0]
        }
        for c in s.upper():
            if c in font:
                char = font[c]
                for col in range(5):
                    for row in range(8):
                        pixel_on = (char[col] >> row) & 0x01
                        for sx in range(scale):
                            for sy in range(scale):
                                self.plot(x + col*scale + sx, y + row*scale + sy, pixel_on)
                x += 5*scale + scale  # space between chars

    # ---------- HELLO WORLD EXAMPLE ----------
    def demo_text(self):
        self.clear()
        self.put_text("AAAAAAAAAAAAAAAAAAAAL", 0, 0, scale=1)
        self.put_text("AAAAAAAAAAL", 0, 16, scale=2)
        self.put_text("AAAAAAL", 2, 40, scale=3)
        self.redraw()
