#!/usr/bin/env python3
import time
import usb.core
import can

def parse_robstride_feedback(msg):
    """
    Decodes the 29-bit extended MIT Cheetah protocol feedback packet
    """
    if len(msg.data) >= 8:
        # 16-bit unsigned position value
        raw_pos = (msg.data[1] << 8) | msg.data[2]
        # 16-bit unsigned velocity value
        raw_vel = (msg.data[3] << 8) | msg.data[4]
        # Internal temperature integer
        temp = msg.data[6]
        
        print(f"\n📊 [TELEMETRY] Motor ID 4 Update:")
        print(f" -> Raw Position Matrix: {raw_pos}")
        print(f" -> Raw Velocity Matrix: {raw_vel}")
        print(f" -> Temperature Status:  {temp}°C")
        return True
    return False

def execute_motor_session():
    motor_id = 4
    print("Connecting to Motor ID 4 via native gs_usb backend...")
    
    dev = usb.core.find(idVendor=0x1D50, idProduct=0x606F)
    if dev is None:
        print("[ERROR] Cannot find the USB adapter hardware.")
        return
        
    try:
        # Establish the stable driver handle
        bus = can.Bus(
            interface="gs_usb",
            channel=dev.product,
            bus=dev.bus,
            address=dev.address,
            bitrate=1000000
        )
        
        # 1. Enable Motor Command Frame (Command Mode 3)
        # Mode (bits 24-28) = 3 | Motor Target ID (bits 8-15) = 4
        enable_id = (3 << 24) | (motor_id << 8)
        print("Sending Wake/Enable Frame...")
        bus.send(can.Message(arbitration_id=enable_id, data=[0x00]*8, is_extended_id=True))
        time.sleep(0.1)
        
        # 2. Query/Control Frame (Command Mode 2)
        # Keeps the motor safe with zero torque while forcing a state reply
        control_id = (2 << 24) | (motor_id << 8)
        print("Polling telemetry states...")
        bus.send(can.Message(arbitration_id=control_id, data=[0x00]*8, is_extended_id=True))
        
        # 3. Listen for telemetry response
        reply = bus.recv(timeout=1.0)
        if reply:
            parse_robstride_feedback(reply)
            
        # 4. Safely Disable Motor Command Frame (Command Mode 4) before exiting
        # This removes mechanical torque safely so the motor spins freely
        disable_id = (4 << 24) | (motor_id << 8)
        print("\nSending Safe Disable Frame...")
        bus.send(can.Message(arbitration_id=disable_id, data=[0x00]*8, is_extended_id=True))
        
        bus.shutdown()
        print("[FINISHED] Session safely closed down.")
        
    except Exception as e:
        print(f"[ERROR] Session dropped: {e}")

if __name__ == "__main__":
    execute_motor_session()

