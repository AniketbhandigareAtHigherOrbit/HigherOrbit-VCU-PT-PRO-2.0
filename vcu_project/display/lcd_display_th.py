import time
import threading
from RPLCD.i2c import CharLCD
import state
import RPi.GPIO as GPIO

class LCDManager:
    def __init__(self, address=0x27, port=1, cols=16, rows=4, page_time=5, request_pin=18):
        # --- LCD setup ---
        self.lcd = CharLCD(
            i2c_expander='PCF8574',
            address=address,
            port=port,
            cols=cols,
            rows=rows,
            dotsize=8
        )

        self.running = False
        self.page_index = 0
        self.pages = [self.page_main, self.page_main_2]
        self.thread = None
        self.page_time = page_time

    def clear(self):
        self.lcd.clear()

    def show_message(self, line, text):
        if 0 <= line <= 3:
            self.lcd.cursor_pos = (line, 0)
            self.lcd.write_string(text.ljust(16))

    # --- Splash Screen ---
    def display_orbit_pt_pro(self):
        self.clear()
        self.show_message(0, "****************")
        self.show_message(1, "* ORBIT PT PRO *")
        self.show_message(2, "*     2.0      *")
        self.show_message(3, "****************")

    # --- Pages ---
    def page_main(self):
        self.show_message(0, f"L:{state.device_6_rpm:4} c:{state.device_6_current:4}")
        self.show_message(1, f"R:{state.device_4_rpm:4} C:{state.device_4_current:3}")
        self.show_message(2, f"Rot:{state.device_5_rpm:4} C:{state.device_5_current:3}")
        self.show_message(3, f"T:{state.device_6_current + state.device_4_current + state.device_5_current:4.1f} SOC:{state.soc:3}")

    def page_main_2(self):
        self.show_message(0, f"Power:{state.power:6.1f}")
        self.show_message(1, f"TotEng:{state.total_energy:6.1f}")
        self.show_message(2, f"Rot:{state.device_5_rpm:4} C:{state.device_5_current:3}")
        self.show_message(3, f"T:{state.hours:02}:{state.mins:02}:{state.secs:02}")

    def page_error(self):
        self.show_message(0, "**** ERROR *****")
        self.show_message(1, f"LEFT :{state.device_6_error:02}")
        self.show_message(2, f"RIGHT:{state.device_4_error:02}")
        self.show_message(3, f"ROTRY:{state.device_5_error:02}")

    def on_request(self, channel):
        """Called when the request button is pressed."""
        # Example: temporarily show extra page for 5 seconds
        if self.running:
            self.clear()
            self.show_message(0, "****************")
            self.show_message(1, "* ORBIT PT PRO *")
            self.show_message(2, "*  2.0 Pressed *")
            self.show_message(3, "****************")
            # Optionally wait before returning to normal pages
            time.sleep(5)
    # --- Thread loop ---
    def run(self):
        self.running = True

        # --- Splash screen for 5 seconds with live refresh ---
        '''splash_duration = 5
        splash_start = time.time()
        while time.time() - splash_start < splash_duration:'''
        self.display_orbit_pt_pro()  # redraw splash every 0.2s
        time.sleep(5)

        # --- Page cycling loop ---
        page_index = 0
        page_time = 10
        last_page_change = time.time()

        while self.running:
            # Update stopwatch
            elapsed = int(time.time() - state.stopwatch_start)
            state.hours, rem = divmod(elapsed, 3600)
            state.mins, state.secs = divmod(rem, 60)

            # Show error if any device has an error
            if (state.device_4_error != 0 or 
                state.device_5_error != 0 or 
                state.device_6_error != 0):
                self.page_error()

            else:
                # Display current page
                self.pages[page_index % len(self.pages)]()

                # Switch page if time elapsed
                if time.time() - last_page_change >= page_time:
                    page_index += 1
                    last_page_change = time.time()

            # Refresh frequently to show live variables
            time.sleep(0.2)

    def start(self):
        if not self.thread:
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
            self.thread = None
