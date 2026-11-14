#!/usr/bin/env python3
import time
import usb.core
import can

P_MIN, P_MAX = -12.5, 12.5
V_MIN, V_MAX = -30.0, 30.0
KP_MIN, KP_MAX = 0.0, 500.0
KD_MIN, KD_MAX = 0.0, 5.0

def float_to_uint(x, v_min, v_max, bits=16):
    x = max(min(x, v_max), v_min)
    span = v_max - v_min
    return int((x - v_min) * ((1 << bits) - 1) / span)

def build_position_payload(target_pos, kp=35.0, kd=0.8):
    p_raw = float_to_uint(target_pos, P_MIN, P_MAX)
    v_raw = float_to_uint(0.0, V_MIN, V_MAX)
    kp_raw = float_to_uint(kp, KP_MIN, KP_MAX)
    kd_raw = float_to_uint(kd, KD_MIN, KD_MAX)
    
    return [
        (p_raw >> 8) & 0xFF, p_raw & 0xFF,
        (v_raw >> 8) & 0xFF, v_raw & 0xFF,
        (kp_raw >> 8) & 0xFF, kp_raw & 0xFF,
        (kd_raw >> 8) & 0xFF, kd_raw & 0xFF
    ]

def drive_motor():
    motor_id = 4
    print("Locating Candlelight USB device...")
    dev = usb.core.find(idVendor=0x1D50, idProduct=0x606F)
    
    if dev is None:
        print("[ERROR] USB adapter not found. Please un-plug and re-insert the USB stick.")
        return
        
    try:
        # Initializing through the working pyusb instance lookup configuration
        bus = can.Bus(
            interface="gs_usb",
            channel=dev.product,
            bus=dev.bus,
            address=dev.address,
            bitrate=1000000
        )
        print("[SUCCESS] Driver active. Sending movement tracking profiles...")
        
        # New bitwise ID layouts (Mode shifted to bits 24-28, Motor ID in bits 0-7)
        zero_id    = (6 << 24) | motor_id
        enable_id  = (3 << 24) | motor_id
        control_id = (1 << 24) | motor_id

        # 1. Reset absolute system zero positioning point
        bus.send(can.Message(arbitration_id=zero_id, data=[0x00]*8, is_extended_id=True))
        time.sleep(0.2)

        # 2. Wake the motor driver inverter smoothly
        bus.send(can.Message(arbitration_id=enable_id, data=[0x00]*8, is_extended_id=True))
        time.sleep(0.2)
        
        # 3. Position tracking target: +1.57 radians (~90 degrees)
        target_angle = 1.57  
        payload = build_position_payload(target_pos=target_angle, kp=90.0, kd=0.8)
        
        # Slower 10Hz transmission loop ensures signal recovery over noisy lines
        print(f"Streaming control sequence to position: {target_angle} rad...")
        for i in range(15):
            bus.send(can.Message(arbitration_id=control_id, data=payload, is_extended_id=True))
            time.sleep(0.1) # 10Hz stream reduces noise-induced buffer errors
            
        print("Target command loop finished successfully.")
        
    except Exception as e:
        print(f"[ERROR] Transaction aborted: {e}")
    finally:
        print("Safely shutting down motor power stage...")
        try:
            disable_id = (4 << 24) | motor_id
            bus.send(can.Message(arbitration_id=disable_id, data=[0x00]*8, is_extended_id=True))
            time.sleep(0.05)
            bus.shutdown()
        except Exception:
            pass
        print("Bus closed cleanly.")

if __name__ == "__main__":
    drive_motor()

