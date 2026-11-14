#!/usr/bin/env python3
import time
import can

def parse_standard_feedback(msg):
    """
    Parses standard motor telemetry payload feedback.
    """
    if len(msg.data) >= 7:
        # Reconstruct values from high/low data bytes
        raw_pos = (msg.data[0] << 8) | msg.data[1]
        raw_vel = (msg.data[2] << 8) | msg.data[3]
        raw_trq = (msg.data[4] << 8) | msg.data[5]
        temp = msg.data[6]
        
        print(f"\n🎉 [SUCCESS] Received Telemetry Feedback!")
        print(f" -> Raw Position:    {raw_pos}")
        print(f" -> Raw Velocity:    {raw_vel}")
        print(f" -> Raw Torque/Cur:  {raw_trq}")
        print(f" -> Temperature:     {temp}°C")
        return True
    return False

def run_standard_motor():
    motor_id = 4  # Targeting the ID detected during your original scan
    print(f"Initializing native SocketCAN (can0) for 11-bit Standard Frame on ID {motor_id}...")
    
    try:
        bus = can.interface.Bus(channel='can0', interface='socketcan')
        
        # In standard 11-bit frame variations:
        # Data[0] often specifies the Command type:
        # 0x03 -> Enable, 0x02 -> Control Query, 0x04 -> Disable
        enable_data  = [0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        query_data   = [0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        disable_data = [0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

        # 1. Wake the motor up from standby mode
        print(f"Sending Enable frame to Standard ID {motor_id}...")
        bus.send(can.Message(arbitration_id=motor_id, data=enable_data, is_extended_id=False))
        time.sleep(0.05)

        # 2. Query data
        print("Sending Query state frame...")
        bus.send(can.Message(arbitration_id=motor_id, data=query_data, is_extended_id=False))
        
        # 3. Listen for response
        start_time = time.time()
        timeout = 1.5
        success = False
        
        while time.time() - start_time < timeout:
            reply = bus.recv(timeout=0.1)
            if reply is not None:
                # Catch any response frames from the motor
                if reply.arbitration_id == motor_id or (reply.arbitration_id & 0x7F) == motor_id:
                    success = parse_standard_feedback(reply)
                    if success:
                        break
                        
        if not success:
            print("\n[TIMEOUT] Motor did not answer standard 11-bit poll frames.")
            print("To see raw hex bytes floating on your network, try running this command in a terminal:")
            print("  candump can0")

    finally:
        # Always send safety shutdown frame before closing script
        print("Sending Safety Disable frame...")
        bus.send(can.Message(arbitration_id=motor_id, data=disable_data, is_extended_id=False))
        bus.shutdown()

if __name__ == "__main__":
    run_standard_motor()

