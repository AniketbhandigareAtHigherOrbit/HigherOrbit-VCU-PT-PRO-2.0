# safety.py

def safety_checks(state):
    """
    Runs all safety-related checks based on the current system state.
    Args:
        state (dict): Current system status data from sensors, BMS, and user inputs.
    Returns:
        dict: Actions or flags indicating required safety interventions.
    """

    actions = {
        "disable_rotary": False,
        "disconnect_machine": False,
        "throw_error": None,
        "slow_wheel_rpm": False,
        "enable_traction_control": False,
        "switch_off_cooling_fans": False,
        "shutdown_system": False
    }

    # 1. SOC check: Disable rotary if SOC < 5%
    if state.get("soc", 100) < 5:
        actions["disable_rotary"] = True

    # 2. Disconnect if only one battery is connected
    if state.get("battery_count", 2) == 1:
        actions["disconnect_machine"] = True

    # 3. Throw error if battery set-A is connected with set-B
    if state.get("battery_set_a") and state.get("battery_set_b"):
        actions["throw_error"] = "Battery set-A and set-B connected together!"

    # 4. Slow wheel RPM if rotary power is high
    if state.get("rotary_power", 0) > state.get("rotary_power_limit", 1000):
        actions["slow_wheel_rpm"] = True

    # 5. Auto-disable rotary in “On-road” mode
    if state.get("mode") == "on-road":
        actions["disable_rotary"] = True

    # 6. Enable traction control to avoid tyre slippage
    if state.get("wheel_slip_detected", False):
        actions["enable_traction_control"] = True

    # 7. Switch off cooling fans if motor temperature is safe
    if state.get("motor_temp", 0) < state.get("cooling_temp_threshold", 60):
        actions["switch_off_cooling_fans"] = True

    # 8. Water sensors: shut off if submerged beyond limits
    if state.get("water_depth", 0) > state.get("max_water_depth", 0.5):
        actions["shutdown_system"] = True
        actions["throw_error"] = "Water level exceeded safety limit!"

    # 9. Auto shutoff on toppling or accidents
    if state.get("tilt_angle", 0) > state.get("max_tilt_angle", 30):
        actions["shutdown_system"] = True
        actions["throw_error"] = "Topple detected!"

    if state.get("jerk_detected", False):
        actions["shutdown_system"] = True
        actions["throw_error"] = "Severe jerk/impact detected!"

    return actions

