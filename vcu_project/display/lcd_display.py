# lcd_display.py
import threading
import time
from RPLCD.i2c import CharLCD
import state

state.stopwatch_start = time.time()

def update_stopwatch():
    """Update global stopwatch variables in state.py."""
    elapsed = int(time.time() - state.stopwatch_start)
    state.hours, rem = divmod(elapsed, 3600)
    state.mins, state.secs = divmod(rem, 60)

class LCDDisplay(threading.Thread):
    def __init__(self, address=0x27, port=1, cols=16, rows=4):
        super().__init__(daemon=True)
        self.lcd = CharLCD(
            i2c_expander='PCF8574',
            address=address,
            port=port,
            cols=cols,
            rows=rows,
            dotsize=8
        )
        self.running = True
        self.queue = []
        self.lock = threading.Lock()
        self.start_time = time.time() 
           
    def run(self):
        while self.running:
            if self.queue:
                with self.lock:
                    func, args, kwargs = self.queue.pop(0)
                func(*args, **kwargs)
            time.sleep(0.1)

    def stop(self):
        self.running = False
        self.clear()

    def add_task(self, func, *args, **kwargs):
        with self.lock:
            self.queue.append((func, args, kwargs))

    # ---------- LCD Operations ----------
    def blink_display(self, delay=0.5, times=2):
        for _ in range(times):
            self.lcd.display_enabled = False
            time.sleep(delay)
            self.lcd.display_enabled = True
            time.sleep(delay)

    def clear(self):
        self.lcd.clear()

    def show_message(self, line, text):
        if line < 0 or line > 3:
            raise ValueError("LCD line must be between 0 and 3")
        self.lcd.cursor_pos = (line, 0)
        self.lcd.write_string(text.ljust(16))

    def show_status(self, mode, direction, rpm_left, rpm_right, rpm_rotary):
        self.clear()
        self.show_message(0, f"Mode:{mode[:10]}")
        self.show_message(1, f"Dir:{direction}")
        self.show_message(2, f"L:{rpm_left:4} R:{rpm_right:4}")
        self.show_message(3, f"Rotary:{rpm_rotary:4}")

    # ---------- Predefined Screens ----------
    def orbit_pt_pro(self, times=2):
        self.clear()
        for _ in range(times):
            self.show_message(0, "****************")
            self.show_message(1, "* ORBIT PT PRO *")
            self.show_message(2, "*     2.0      *")
            self.show_message(3, "****************")
            #self.blink_display()

    def display_on_road_mode(self, times=2):
        self.clear()
        for _ in range(times):
            self.show_message(0, "****************")
            self.show_message(1, "* ON ROAD MODE *")
            self.show_message(2, "*   ACTIVATED  *")
            self.show_message(3, "****************")
            #self.blink_display()

    def display_off_road_mode(self, times=2):
        self.clear()
        for _ in range(times):
            self.show_message(0, "****************")
            self.show_message(1, "* OFF ROAD MODE*")
            self.show_message(2, "*   ACTIVATED  *")
            self.show_message(3, "****************")
            #self.blink_display()

    def display_back_rotary_off(self, times=2):
        self.clear()
        for _ in range(times):
            self.show_message(0, "****************")
            self.show_message(1, "* BACK ROTARY  *")
            self.show_message(2, "* INACTIVATED  *")
            self.show_message(3, "****************")
            #self.blink_display()

    def display_back_rotary_on(self, times=2):
        self.clear()
        for _ in range(times):
            self.show_message(0, "****************")
            self.show_message(1, "* BACK ROTARY  *")
            self.show_message(2, "*  ACTIVATED   *")
            self.show_message(3, "****************")
            self.blink_display()
            
    def seafty_lever_Active(self, times=2):
        #self.clear()
        #for _ in range(times): #Safety leaver
        self.show_message(0, "****************")
        self.show_message(1, "* SAFETY LEVER*")
        self.show_message(2, "*  ACTIVATED   *")
        self.show_message(3, "****************")
            #self.blink_display()

    def display_orbit_pt_pro(self):
        self.clear()
        self.show_message(0, "****************")
        self.show_message(1, "* ORBIT PT PRO *")
        self.show_message(2, "*     2.0      *")
        self.show_message(3, "****************")

    def Real_time_data(self, current_rpm_1, rotary_current_rpm_1):
        # Elapsed time since start

        update_stopwatch()
        # Just update live values, no clear
        self.show_message(0, f"W-   {current_rpm_1:4}")
        self.show_message(1, f"RPM- {rotary_current_rpm_1:4}")
        self.show_message(2, f"T-{state.hours:02}:{state.mins:02}:{state.secs:02}")

