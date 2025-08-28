import spidev
import RPi.GPIO as GPIO
from copy import deepcopy

# GPIO pins
RST_PIN = 25
CS_PIN  = 8  # GPIO8 (CE0)

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(RST_PIN, GPIO.OUT)
GPIO.setup(CS_PIN, GPIO.OUT)

class ST7920:
    def __init__(self):
        # SPI setup
        self.spi = spidev.SpiDev()
        self.spi.open(0, 1)  # SPI0 CE0
        self.spi.max_speed_hz = 1800000
        self.spi.cshigh = False  # normal CS
        
        # Reset display
        GPIO.output(RST_PIN, GPIO.LOW)
        GPIO.output(CS_PIN, GPIO.LOW)
        self.delay(10)
        GPIO.output(RST_PIN, GPIO.HIGH)
        
        # Initialize ST7920
        self.send(0, 0, 0x30)  # basic instruction
        self.send(0, 0, 0x30)
        self.send(0, 0, 0x0C)  # display on
        self.send(0, 0, 0x34)  # enable graphics
        self.send(0, 0, 0x36)  # graphics mode

        self.width = 128
        self.height = 64
        self.clear()
        self.currentlydisplayedfbuff = None
        self.redraw()

        # Example 6x8 font for ASCII 32-127
        self.fontsheet = self.load_font_sheet()

    def delay(self, ms):
        import time
        time.sleep(ms / 1000.0)

    def send(self, rs, rw, cmds):
        if type(cmds) is int:
            cmds = [cmds]
        b1 = 0b11111000 | ((rw&0x01)<<2) | ((rs&0x01)<<1)
        bytes_to_send = []
        for cmd in cmds:
            bytes_to_send.append(cmd & 0xF0)
            bytes_to_send.append((cmd & 0x0F) << 4)
        GPIO.output(CS_PIN, GPIO.LOW)
        self.spi.xfer2([b1] + bytes_to_send)
        GPIO.output(CS_PIN, GPIO.HIGH)

    def clear(self):
        self.fbuff = [[0]*(128//8) for _ in range(64)]

    def plot(self, x, y, set=True):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
        if set:
            self.fbuff[y][x//8] |= 1 << (7-(x%8))
        else:
            self.fbuff[y][x//8] &= ~(1 << (7-(x%8)))

    def line(self, x1, y1, x2, y2, set=True):
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        while True:
            self.plot(x1, y1, set)
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
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

    def fill_rect(self, x1, y1, x2, y2, set=True):
        for y in range(y1, y2+1):
            self.line(x1, y, x2, y, set)

    def _send_line(self, row):
        self.send(0, 0, [0x80 + row%32, 0x80])
        self.send(1, 0, self.fbuff[row])

    def redraw(self):
        for row in range(0, 64):
            self._send_line(row)
        self.currentlydisplayedfbuff = deepcopy(self.fbuff)

    # Load a simple built-in 6x8 font (ASCII 32-127)
    def load_font_sheet(self):
        # Each char is 6x8 pixels. For simplicity, let's define A-Z only
        font = {}
        # Example: define 'H' (ASCII 72)
        font[72] = [
            [1,1,1,1,1,1],
            [0,0,1,0,0,0],
            [0,0,1,0,0,0],
            [0,0,1,0,0,0],
            [1,1,1,1,1,1],
            [0,0,0,0,0,0],
            [0,0,0,0,0,0],
            [0,0,0,0,0,0],
        ]
        # Add other letters as needed
        return (font, 6, 8)

    def put_text_scaled(self, s, x, y, scale=2):
        font, cw, ch = self.fontsheet
        for c in s:
            code = ord(c)
            if code not in font:
                x += cw*scale
                continue
            char = font[code]
            for sy in range(ch):
                for sx in range(cw):
                    if char[sy][sx] == 1:
                        for dy in range(scale):
                            for dx in range(scale):
                                self.plot(x+sx*scale+dx, y+sy*scale+dy, True)
            x += cw * scale

if __name__ == "__main__":
    lcd = ST7920()
    lcd.clear()
    lcd.put_text_scaled("H", 10, 10, scale=5)
    lcd.put_text_scaled("I", 50, 10, scale=5)
    lcd.redraw()
