#!/usr/bin/env python3
import time
import usb.core
import can

# Factory boundary constraints for RobStride / CyberGear protocol scaling
P_MIN, P_MAX = -12.5, 12.5
V_MIN, V_MAX = -30.0, 30.0
KP_MIN, KP_MAX = 0.0, 500.0
KD_MIN, KD_MAX = 0.0, 5.0
T_MIN, T_MAX = -12.0, 12.0

def float_to_uint(x, v_min, v_max, bits=16):
    """ Converts a floating point value to a constrained unsigned int block """
    x = max(min(x, v_max), v_min) # Constrain within safety limits
    span = v_max - v_min
    return int((x - v_min) * ((1 << bits) - 1) / span)

def build_position_payload(target_pos, target_vel=0.0, kp=40.0, kd=1.5, torque=0.0):
    """
    Encodes floating point targets into the required 8-byte protocol payload layout
    Byte 0-1: Target Position (16-bit)
    Byte 2-3: Target Velocity (16-bit)
    Byte 4-5: Kp Gain (16-bit)
    Byte 6-7: Kd Gain (16-bit)
    Note: Feed-forward torque is usually appended in specific mode headers or left to 0.
    """
    p_raw = float_to_uint(target_pos, P_MIN, P_MAX)
    v_raw = float_to_uint(target_vel, V_MIN, V_MAX)
    kp_raw = float_to_uint(kp, KP_MIN, KP_MAX)
    kd_raw = float_to_uint(kd, KD_MIN, KD_MAX)
    
    payload = [
        (p_raw >> 8) & 0xFF, p_raw & 0xFF,
        (v_raw >> 8) & 0xFF, v_raw & 0xFF,
        (kp_raw >> 8) & 0xFF, kp_raw & 0xFF,
        (kd_raw >> 8) & 0xFF, kd_raw & 0xFF
    ]
    return payload

def run_position_control():
    motor_id = 4
    
    # Locate physical openmoko adapter
    dev = usb.core.find(idVendor=0x1D50, idProduct=0x606F)
    if dev is None:
        print("[ERROR] Cannot find the USB adapter hardware.")
        return
        
    try:
        bus = can.Bus(
            interface="gs_usb",
            channel=dev.product,
            bus=dev.bus,
            address=dev.address,
            bitrate=1000000
        )
        
        # 1. Wake up the Motor (Command Mode 3)
        enable_id = (3 << 24) | (motor_id << 8)
        print(f"Enabling Motor ID {motor_id}...")
        bus.send(can.Message(arbitration_id=enable_id, data=[0x00]*8, is_extended_id=True))
        time.sleep(0.2)
        
        # 2. Build tracking payload
        # Target: +1.57 radians (~90 degrees)
        # Kp=30.0 (Stiffness stiffness), Kd=1.0 (Damping to stop oscillation)
        target_angle = 1.57 
        control_payload = build_position_payload(target_pos=target_angle, kp=30.0, kd=1.0)
        
        # Command Mode 1 = Motor Control/Drive Mode
        control_id = (1 << 24) | (motor_id << 8)
        
        print(f"Commanding Motor to position: {target_angle} rad (~90°)...")
        # Send position commands in a brief loop to keep watchdog alive
        for _ in range(20):
            bus.send(can.Message(arbitration_id=control_id, data=control_payload, is_extended_id=True))
            time.sleep(0.05)
            
        print("Target position reached.")
        
    except KeyboardInterrupt:
        print("\nExecution interrupted by user.")
    except Exception as e:
        print(f"[ERROR] Run failed: {e}")
    finally:
        # 3. CRUCIAL SAFETY: Always cut inverter power before closing script
        disable_id = (4 << 24) | (motor_id << 8)
        print("Disabling motor power stage safely...")
        try:
            bus.send(can.Message(arbitration_id=disable_id, data=[0x00]*8, is_extended_id=True))
            bus.shutdown()
        except NameError:
            pass
        print("Session closed.")

if __name__ == "__main__":
    run_position_control()

