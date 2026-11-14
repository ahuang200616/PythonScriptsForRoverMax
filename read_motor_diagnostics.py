#!/usr/bin/env python3
import time
import serial

def send_at_command(ser, command_string):
    """Constructs a clean RobStride AT packet terminated with a Carriage Return/Line Feed"""
    full_packet = f"AT+{command_string}\r\n"
    print(f"Sending Command: {full_packet.strip()}")
    ser.write(full_packet.encode('ascii'))
    time.sleep(0.08) # Let the internal CH340 translator process the string data
    
    if ser.in_waiting:
        reply = ser.readline().decode('ascii', errors='ignore').strip()
        print(f" -> Response: {reply}")
        return reply
    return None

def control_robstride_motor():
    motor_id = 4
    
    # 💡 CHANGE THIS string to match the exact filename found in Step 1
    # (Common paths: '/dev/ttyACM0', '/dev/ttyUSB0', '/dev/ttyUSB1')
    serial_port = '/dev/ttyUSB0' 
    
    print(f"Opening RobStride Adapter via Virtual Serial Path ({serial_port})...")
    try:
        # RobStride hardware defaults to a native serial baud rate of 921600 bps
        ser = serial.Serial(serial_port, baudrate=921600, timeout=0.2)
        
        # 1. FORCE FAULT RESET & SET OPERATING MODE
        print("Clearing historical fault latches...")
        send_at_command(ser, f"RESET={motor_id}")
        
        print("Setting target control parameters to Position Mode (Mode 1)...")
        send_at_command(ser, f"MODE={motor_id},1")
        
        # 2. DEFINE STIFFNESS CONTROLS (Kp and Kd)
        send_at_command(ser, f"KP={motor_id},80.0")
        send_at_command(ser, f"KD={motor_id},1.5")
        
        # 3. ENERGIZE THE INVERTER COILS
        print("\nEnabling motor output driver power stage...")
        send_at_command(ser, f"ENABLE={motor_id}")
        time.sleep(0.3) # Essential gap to let the absolute encoder initialize
        
        # 4. SEND REPEATED MOVEMENT TARGET PARAMETERS
        target_angle = 1.57  # Target position: +1.57 radians (approx 90 degrees)
        print(f"\nMoving motor shaft to coordinate target: {target_angle} rad...")
        
        for _ in range(15):
            send_at_command(ser, f"POS={motor_id},{target_angle:.2f}")
            time.sleep(0.1) # Safe 10Hz transmission loop to isolate EMI noise
            
        print("\nMovement tracking sequence finished successfully.")
        
    except Exception as e:
        print(f"[ERROR] Serial connection failed: {e}")
        print("💡 Quick Fix: If you see a permission error, run: sudo usermod -aG dialout $USER (then reboot).")
    finally:
        # 5. SAFE POWER DOWN
        print("\nSafely disabling motor current output loops...")
        try:
            send_at_command(ser, f"DISABLE={motor_id}")
            ser.close()
        except NameError:
            pass
        print("Closed safely.")

if __name__ == "__main__":
    control_robstride_motor()

