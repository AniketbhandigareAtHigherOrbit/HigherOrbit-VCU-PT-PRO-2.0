import RPi.GPIO as GPIO
import spidev
import time
from copy import deepcopy

# ---------- PIN CONFIG ----------
RST_PIN = 17  # Reset
CS_PIN  = 27  # Chip Select

# ---------- GPIO SETUP ----------
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()
GPIO.setup(RST_PIN, GPIO.OUT)
GPIO.setup(CS_PIN, GPIO.OUT)

# ---------- SPI SETUP ----------
spi = spidev.SpiDev()
spi.open(0, 1)      # SPI0, CE0
spi.max_speed_hz = 1800000
#spi.cshigh = True    # Inverted CS

# ---------- LCD FUNCTIONS ----------
def lcd_reset():
    GPIO.output(RST_PIN, GPIO.LOW)
    time.sleep(0.05)
    GPIO.output(RST_PIN, GPIO.HIGH)
    time.sleep(0.05)

def lcd_send(rs, rw, byte):
    b1 = 0b11111000 | ((rw & 0x01)<<2) | ((rs & 0x01)<<1)
    high = byte & 0xF0
    low  = (byte & 0x0F) << 4
    GPIO.output(CS_PIN, GPIO.LOW)
    spi.xfer2([b1, high, low])
    GPIO.output(CS_PIN, GPIO.HIGH)
    time.sleep(0.001)

def lcd_command(cmd):
    lcd_send(0, 0, cmd)

def lcd_data(dat):
    lcd_send(1, 0, dat)

# ---------- INITIALIZE LCD ----------
def lcd_init():
    lcd_reset()
    lcd_command(0x30)  # basic instruction set
    lcd_command(0x30)
    lcd_command(0x0C)  # display on
    lcd_command(0x34)  # extended instruction set
    lcd_command(0x34)
    lcd_command(0x36)  # graphics on

# ---------- GRAPHIC FRAMEBUFFER ----------
WIDTH = 128
HEIGHT = 64
fbuff = [[0]*(WIDTH//8) for _ in range(HEIGHT)]
disp_fbuff = None

def lcd_clear():
    global fbuff
    fbuff = [[0]*(WIDTH//8) for _ in range(HEIGHT)]

def plot(x, y, set=True):
    if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
        return
    if set:
        fbuff[y][x//8] |= 1 << (7-(x%8))
    else:
        fbuff[y][x//8] &= ~(1 << (7-(x%8)))

def line(x1, y1, x2, y2, set=True):
    dx = abs(x2-x1)
    dy = abs(y2-y1)
    sx = 1 if x1<x2 else -1
    sy = 1 if y1<y2 else -1
    err = dx - dy
    while True:
        plot(x1, y1, set)
        if x1==x2 and y1==y2:
            break
        e2 = 2*err
        if e2 > -dy:
            err -= dy
            x1 += sx
        if e2 < dx:
            err += dx
            y1 += sy

def rect(x1, y1, x2, y2, set=True):
    line(x1, y1, x2, y1, set)
    line(x2, y1, x2, y2, set)
    line(x2, y2, x1, y2, set)
    line(x1, y2, x1, y1, set)

# ---------- REDRAW FRAMEBUFFER ----------
def _send_line(row, dx1, dx2):
    lcd_command(0x80 + (row % 32))  # set row
    lcd_command(0x80 + (dx1//16) + (8 if row>=32 else 0))  # set col
    for b in fbuff[row][dx1//8:(dx2//8)+1]:
        lcd_data(b)

def lcd_redraw():
    global disp_fbuff
    for row in range(HEIGHT):
        _send_line(row, 0, WIDTH-1)
    disp_fbuff = deepcopy(fbuff)

# ---------- EXAMPLE: DISPLAY "HELLO WORLD" ----------
# ---------- EXAMPLE: DISPLAY "HELLO WORLD" WITH SCALING ----------
def put_text(s, x, y, scale=1):
    # Simple 5x7 font, A-Z only
    font = {
        'H':[0x7F,0x08,0x08,0x08,0x7F],
        'E':[0x7F,0x49,0x49,0x49,0x41],
        'L':[0x7F,0x40,0x40,0x40,0x40],
        'O':[0x3E,0x41,0x41,0x41,0x3E],
        'W':[0x3F,0x40,0x38,0x40,0x3F],
        'R':[0x7F,0x09,0x19,0x29,0x46],
        'D':[0x7F,0x41,0x41,0x22,0x1C],
        ' ': [0,0,0,0,0]
    }
    for c in s.upper():
        if c in font:
            char = font[c]
            for col in range(5):
                for row in range(8):
                    pixel_on = (char[col] >> row) & 0x01
                    # Scale pixels
                    for sx in range(scale):
                        for sy in range(scale):
                            plot(x + col*scale + sx, y + row*scale + sy, pixel_on)
            x += 5*scale + scale  # space between chars


# ---------- MAIN ----------
if __name__=="__main__":
    lcd_init()
    lcd_clear()
    put_text("HELLO", x=0, y=0, scale=1)

    # Medium text
    put_text("WORLD", x=0, y=16, scale=2)

    # Large text
    put_text("HI", x=0, y=40, scale=3)
    #put_text("HELLO", 0, 0)
    #put_text("WORLD", 0, 16)
    lcd_redraw()
    print("Displayed HELLO WORLD")
