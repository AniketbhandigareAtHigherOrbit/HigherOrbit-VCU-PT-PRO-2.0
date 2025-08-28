# Mode manager logic
# mode_manager.py
import time
import RPi.GPIO as GPIO
#from control.on_road import run_on_road_mode
#from control.off_road import run_off_road_mode

# GPIO pin for mode select switch
MODE_SWITCH_PIN = 17  # Example GPIO pin number

# Mode definitions
MODE_ON_ROAD = 0
MODE_OFF_ROAD = 1

def setup_gpio():
    """Setup GPIO mode input."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(MODE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def get_current_mode():
    """
    Read the mode from the switch.
    Returns:
        MODE_ON_ROAD or MODE_OFF_ROAD
    """
    # Assuming switch ON = OFF-ROAD, OFF = ON-ROAD (you can invert logic as needed)
    if GPIO.input(MODE_SWITCH_PIN) == GPIO.LOW:		
        return MODE_OFF_ROAD 
    else:
        return MODE_ON_ROAD
	
def main():
    setup_gpio()

    try:
        while True:
            mode = get_current_mode()

            if mode == MODE_ON_ROAD:
                print("Mode: ON-ROAD ? Disabling rotary motors.")
                #run_on_road_mode()
            
            elif mode == MODE_OFF_ROAD:
                print("Mode: OFF-ROAD ? Activating off-road logic.")
                #run_off_road_mode()

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
