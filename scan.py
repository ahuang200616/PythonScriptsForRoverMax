#!/usr/bin/env python3
import can
import robstride

# Setup the standard python-can bus configuration
with can.Bus(interface='socketcan', channel='can0', bitrate=1000000) as bus:
    rs_client = robstride.Client(bus)
    
    print("Pinging IDs to identify the motor...")
    
    # Common default factory IDs to check first to save time, or expand range(1, 128)
    common_ids = [1, 127] 
    
    for motor_id in common_ids:
        try:
            # Attempting to read a standard parameter (like run mode) acts as a ping
            response = rs_client.read(motor_id, 'run_mode')
            **print(f"Success! Motor identified at ID: {motor_id}")**
            break
        except Exception:
            # If it times out or doesn't respond, move to the next ID
            continue
    else:
        print("Could not identify motor on common IDs. Check wiring/baudrate.")

