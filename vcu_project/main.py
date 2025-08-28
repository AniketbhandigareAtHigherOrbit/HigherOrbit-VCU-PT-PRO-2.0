SEND_CAN_ID = 0x12300140
import time
import RPi.GPIO as GPIO

#from canbus.can_reader import setup_can_bus
#from canbus.can_bus_active import check_can0
#from control.on_road import on_road_mode_step
#from control.off_road import run_off_road_mode

from display.st7920_driver import ST7920


# Example call
#write_text(["Hello Aniket!", "ST7920 Test OK"])

'''
MODE_ON_ROAD = 1
MODE_OFF_ROAD = 0
MODE_SWITCH_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(MODE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def get_current_mode():
    """Read the mode from the switch."""
    return MODE_OFF_ROAD if GPIO.input(MODE_SWITCH_PIN) == GPIO.HIGH else MODE_ON_ROAD
'''
def main():
    lcd = ST7920()

    '''
    bus = setup_can_bus()
    if not bus:
        check_can0()
        return'''

    while True:
        lcd.clear()
        '''lcd.put_text("AAAAAAAAAAAAAAAAAAAAL", 0, 0, scale=1)
        lcd.put_text("AAAAAAAAAAL", 0, 16, scale=2)
        lcd.put_text("AAAAAAL", 2, 40, scale=3)'''
        lcd.redraw() 
        lcd.demo_text()
        time.sleep(6.05)
        lcd.clear_display()
        #lcd.clear()      
        #Clear framebuffer
        #lcd.redraw()  

        '''
        mode = get_current_mode()

        if mode == MODE_ON_ROAD:
            #print("on road mode ")
            on_road_mode_step()  # Runs one step only
        elif mode == MODE_OFF_ROAD:
            pass
            #print("OFF-ROAD mode")
            #run_off_road_mode(bus)

        time.sleep(0.05)  # Loop runs every 50ms'''
    lcd.clear()
if __name__ == "__main__":
    main()
