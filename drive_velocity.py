#!/usr/bin/env python3
import time
import usb.core
import can
import struct

def float_to_bytes(value):
    """Encodes a standard Python float into 4 bytes (Little-Endian IEEE 754)"""
    return list(struct.pack("<f", value))

def drive_motor_velocity():
    motor_id = 4
    master_id = 0x00
    print("Connecting to Candlelight USB interface using native gs_usb backend...")
    
    try:
        # Connect directly into the active device index
        bus = can.Bus(interface="gs_usb", channel=0, bitrate=1000000)
        print("[SUCCESS] Communication link established cleanly.")
        
        # 29-bit Extended ID mappings: Mode | Master ID | Motor ID
        reset_fault_id = (5 << 24) | (master_id << 16) | motor_id
        write_id       = (7 << 24) | (master_id << 16) | motor_id
        enable_id      = (3 << 24) | (master_id << 16) | motor_id
        disable_id     = (4 << 24) | (master_id << 16) | motor_id

        # ----------------------------------------------------
        # PHASE 1: FORCE FAULT RESET
        # ----------------------------------------------------
        print("Sending explicit fault-clear reset command...")
        bus.send(can.Message(arbitration_id=reset_fault_id, data=[0x00]*8, is_extended_id=True))
        time.sleep(0.2)  # Give the internal state machine time to clear logs

        # ----------------------------------------------------
        # PHASE 2: CHOOSE OPERATING MODE (VELOCITY MODE)
        # ----------------------------------------------------
        print("Configuring internal motor registers to Velocity Mode...")
        mode_payload = [0x05, 0x20, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00]
        bus.send(can.Message(arbitration_id=write_id, data=mode_payload, is_extended_id=True))
        time.sleep(0.1)

        # ----------------------------------------------------
        # PHASE 3: DEFINE MAXIMUM CURRENT/TORQUE LIMIT
        # ----------------------------------------------------
        print("Setting current safety thresholds (3.0A)...")
        current_payload = [0x07, 0x20] + float_to_bytes(3.0) + [0x00, 0x00]
        bus.send(can.Message(arbitration_id=write_id, data=current_payload, is_extended_id=True))
        time.sleep(0.05)

        # ----------------------------------------------------
        # PHASE 4: ENERGIZE THE INVERTER DRIVER
        # ----------------------------------------------------
        print("Enabling motor power stage...")
        bus.send(can.Message(arbitration_id=enable_id, data=[0x00]*8, is_extended_id=True))
        time.sleep(0.3)

        # ----------------------------------------------------
        # PHASE 5: SEND REPEATED SPEED TARGETS
        # ----------------------------------------------------
        target_speed = 2.0  # Increased target to ensure it breaks static friction
        print(f"Streaming continuous speed target: {target_speed} rad/s...")
        speed_payload = [0x13, 0x20] + float_to_bytes(target_speed) + [0x00, 0x00]
        
        # Stream the target speed at 10Hz for 2 seconds
        for i in range(20):
            bus.send(can.Message(arbitration_id=write_id, data=speed_payload, is_extended_id=True))
            time.sleep(0.1)
            
        print("Velocity testing sequence completed.")

    except Exception as e:
        print(f"[ERROR] Transaction failed: {e}")
    finally:
        # ----------------------------------------------------
        # PHASE 6: SAFE SHUTDOWN
        # ----------------------------------------------------
        print("Safely disabling motor torque loops...")
        try:
            bus.send(can.Message(arbitration_id=disable_id, data=[0x00]*8, is_extended_id=True))
            time.sleep(0.05)
            bus.shutdown()
        except Exception:
            pass
        print("Session closed safely.")

if __name__ == "__main__":
    drive_motor_velocity()

