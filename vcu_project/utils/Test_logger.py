# test_logger_state.py
import time
import logger
import state
import RPi.GPIO as GPIO

def main():
    print("=== Testing state logging ===")

    # Init GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([state.LEFT_BTN_PIN, state.RIGHT_BTN_PIN], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(state.MODE_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(state.DIRECTION_BTN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(state.ROTARY_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(state.SAFETY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # Fake some state changes
    state.current_rpm = 1200
    state.rotary_current_rpm = 400
    state.current_direction = 1
    state.feedbackRPM_Left = 1180
    state.feedbackRPM_Right = 1190
    state.is_safe_stop = False
    state.mode = state.MODE_SINGLE_LEFT

    # Log multiple snapshots
    for _ in range(3):
        logger.log_state(state, GPIO)
        time.sleep(0.5)

    print("=== Done. Check logs/ folder for today's *_data.csv ===")

if __name__ == "__main__":
    main()

