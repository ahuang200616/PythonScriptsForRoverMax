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

def build_position_payload(target_pos, kp=80.0, kd=1.2):
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
    print("Locating Candlelight USB hardware...")
    dev = usb.core.find(idVendor=0x1D50, idProduct=0x606F)
    
    if dev is None:
        print("[ERROR] USB adapter not found. Verify physical port placement via 'lsusb'.")
        return
        
    try:
        bus = can.Bus(
            interface="gs_usb", channel=dev.product,
            bus=dev.bus, address=dev.address, bitrate=1000000
        )
        print("[SUCCESS] Communication link established.")
        
        # Extended 29-bit ID mappings (Mode shifted to bits 24-28, Motor ID in bits 0-7)
        control_id = (1 << 24) | motor_id
        enable_id  = (3 << 24) | motor_id
        disable_id = (4 << 24) | motor_id
        write_id   = (7 << 24) | motor_id

        # ----------------------------------------------------
        # PHASE 1: CHOOSE OPERATING MODE (POSITION MODE)
        # ----------------------------------------------------
        # Mode 7 Parameter Write to register 0x2005 (Operating Mode)
        # Data Byte Layout: [Index_Low, Index_High, Value_Byte_0, Value_Byte_1...]
        # 0x01 = Position Mode
        print("Configuring internal motor registers to Position Mode...")
        mode_payload = [0x05, 0x20, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
        bus.send(can.Message(arbitration_id=write_id, data=mode_payload, is_extended_id=True))
        time.sleep(0.3)  # Allow memory write execution gap

        # ----------------------------------------------------
        # PHASE 2: ACTIVATE POWER STAGE
        # ----------------------------------------------------
        print("Waking up motor driver output inverter stages...")
        bus.send(can.Message(arbitration_id=enable_id, data=[0x00]*8, is_extended_id=True))
        time.sleep(0.3)  # Allow high-voltage bus capacitor charging gap
        
        # ----------------------------------------------------
        # PHASE 3: POSITIONING COMMAND LOOPS
        # ----------------------------------------------------
        target_angle = 1.57  # Go to ~90 degrees
        payload = build_position_payload(target_pos=target_angle, kp=80.0, kd=1.2)
        
        print(f"Streaming position coordinates to target: {target_angle} rad (~90°)...")
        # Sending a tight burst of frames to ensure the tracking loop engages cleanly
        for i in range(20):
            bus.send(can.Message(arbitration_id=control_id, data=payload, is_extended_id=True))
            time.sleep(0.1) # Safe 10Hz transmission loop
            
        print("Trajectory stream finished successfully.")
        
    except Exception as e:
        print(f"[ERROR] Transaction failed: {e}")
    finally:
        # ----------------------------------------------------
        # PHASE 4: SAFE TORQUE DROP
        # ----------------------------------------------------
        print("Safely disabling motor current output loops...")
        try:
            bus.send(can.Message(arbitration_id=disable_id, data=[0x00]*8, is_extended_id=True))
            time.sleep(0.05)
            bus.shutdown()
        except Exception:
            pass
        print("Session closed safely.")

if __name__ == "__main__":
    drive_motor()

