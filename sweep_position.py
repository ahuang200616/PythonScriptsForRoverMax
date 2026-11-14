#!/usr/bin/env python3
import time
import usb.core
import can
import struct

def float_to_bytes(value):
    """Encodes a standard Python float into 4 bytes (Little-Endian IEEE 754)"""
    return list(struct.pack("<f", value))

def drive_motor_position():
    motor_id = 4
    master_id = 0x00
    print("Connecting to Candlelight USB interface using native gs_usb backend...")
    
    try:
        # Bypasses local discovery blocks and hooks directly into the active device index
        bus = can.Bus(
            interface="gs_usb", 
            channel=0, 
            bitrate=1000000
        )
        print("[SUCCESS] Connected cleanly to your CAN adapter network.")
        
        # 29-bit Extended ID formatting mapping
        write_id = (7 << 24) | (master_id << 16) | motor_id
        enable_id = (3 << 24) | (master_id << 16) | motor_id

        # ----------------------------------------------------
        # PHASE 1: CHOOSE OPERATING MODE (POSITION MODE)
        # ----------------------------------------------------
        print("Configuring internal motor registers to Position Mode...")
        mode_payload = [0x05, 0x20, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00]
        bus.send(can.Message(arbitration_id=write_id, data=mode_payload, is_extended_id=True))
        time.sleep(0.1)

        # ----------------------------------------------------
        # PHASE 2: DEFINE COIL CONTROL STIFFNESS (Kp and Kd)
        # ----------------------------------------------------
        print("Writing position loop stiffness gains (Kp=100.0)...")
        kp_payload = [0x15, 0x20] + float_to_bytes(100.0) + [0x00, 0x00]
        bus.send(can.Message(arbitration_id=write_id, data=kp_payload, is_extended_id=True))
        time.sleep(0.05)

        print("Writing damping parameters (Kd=1.5)...")
        kd_payload = [0x16, 0x20] + float_to_bytes(1.5) + [0x00, 0x00]
        bus.send(can.Message(arbitration_id=write_id, data=kd_payload, is_extended_id=True))
        time.sleep(0.05)

        # ----------------------------------------------------
        # PHASE 3: WRITE VELOCITY LIMITS (Crucial for motion)
        # ----------------------------------------------------
        # Register 0x2017: Maximum Velocity Limit (float)
        # We set this to 2.0 rad/s so the motor can spin smoothly
        print("Writing maximum running speed limit (2.0 rad/s)...")
        vel_limit_payload = [0x17, 0x20] + float_to_bytes(2.0) + [0x00, 0x00]
        bus.send(can.Message(arbitration_id=write_id, data=vel_limit_payload, is_extended_id=True))
        time.sleep(0.05)

        # ----------------------------------------------------
        # PHASE 4: ENERGIZE THE INVERTER DRIVER
        # ----------------------------------------------------
        print("Enabling motor power stage...")
        bus.send(can.Message(arbitration_id=enable_id, data=[0x00]*8, is_extended_id=True))
        time.sleep(0.2)

        # ----------------------------------------------------
        # PHASE 5: COMMAND THE TARGET PROFILE DISTANCE
        # ----------------------------------------------------
        target_pos = 1.57  # Target angle: +1.57 radians (approx 90 degrees)
        print(f"Streaming movement target payload: {target_pos} rad...")
        pos_payload = [0x14, 0x20] + float_to_bytes(target_pos) + [0x00, 0x00]
        
        # Keep stream sequence open for 2 seconds to give the actuator time to complete the move
        for i in range(20):
            bus.send(can.Message(arbitration_id=write_id, data=pos_payload, is_extended_id=True))
            time.sleep(0.1)
            
        print("Movement profile sequence completed.")

    except Exception as e:
        print(f"[ERROR] Transaction failed: {e}")
    finally:
        # ----------------------------------------------------
        # PHASE 6: SAFE SHUTDOWN
        # ----------------------------------------------------
        print("Safely disabling motor torque loops...")
        try:
            disable_id = (4 << 24) | (master_id << 16) | motor_id
            bus.send(can.Message(arbitration_id=disable_id, data=[0x00]*8, is_extended_id=True))
            time.sleep(0.05)
            bus.shutdown()
        except Exception:
            pass
        print("Session closed safely.")

if __name__ == "__main__":
    drive_motor_position()

