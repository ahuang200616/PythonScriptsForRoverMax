import serial
import time
import struct

ADAPTER_PORT = '/dev/ttyCH341USB0'
MOTOR_ID = 1  # Standard factory default for MIT mode (Try 1 first, then 127 if needed)

def configure_adapter():
    print(f"[*] Initializing hardware adapter on {ADAPTER_PORT}...")
    try:
        ser = serial.Serial(ADAPTER_PORT, baudrate=921600, timeout=0.1)
        ser.write(b"AT+MODE=1\r\n")  # Transparent binary streaming
        time.sleep(0.05)
        ser.write(b"AT+CAN_BAUD=1000000\r\n")  # 1 Mbps motor speed
        time.sleep(0.05)
        ser.close()
        print("✅ Adapter configured successfully.")
    except Exception as e:
        print(f"❌ Failed to reach adapter: {e}")

def run_mit_loop():
    configure_adapter()
    
    print(f"\n[*] Connecting raw serial-to-MIT pipeline...")
    try:
        ser = serial.Serial(ADAPTER_PORT, baudrate=921600, timeout=0.5)
        ser.reset_input_buffer()
        
        # --- PHASE 1: SET ZERO POSITION ---
        # Standard Robstride/CubeMars MIT Zero frame format: Data = [0xFF]*7 + [0xFE]
        print(f"[*] Setting absolute Zero on Motor ID {MOTOR_ID}...")
        
        # Custom serial adapter wrapper layout: [SOF (2B)] [CAN_ID (4B)] [DLC (1B)] [DATA (8B)] [EOF (2B)]
        sof_header = b'\xAA\x55'
        arbitration_id = struct.pack('>I', MOTOR_ID)  # 11-bit Standard ID mapping
        dlc = b'\x08'
        zero_payload = b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFE'
        eof_footer = b'\x55\xAA'
        
        zero_packet = sof_header + arbitration_id + dlc + zero_payload + eof_footer
        ser.write(zero_packet)
        ser.flush()
        time.sleep(0.1)
        print("✅ Zero position command transmitted.")

        # --- PHASE 2: ENABLE MOTOR TORQUE ---
        print(f"[*] Sending MIT Enable command to ID {MOTOR_ID}...")
        enable_payload = b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFC'
        enable_packet = sof_header + arbitration_id + dlc + enable_payload + eof_footer
        ser.write(enable_packet)
        ser.flush()
        time.sleep(0.1)

        # --- PHASE 3: TELEMETRY POLLING LOOP ---
        print("\n[*] Starting 10Hz telemetry stream. Press Ctrl+C to stop...")
        # Null command data structure holds current position with zero stiffness (Kp=0, Kd=0)
        idle_control_payload = b'\x00\x00\x00\x00\x00\x00\x00\x00'
        poll_packet = sof_header + arbitration_id + dlc + idle_control_payload + eof_footer
        
        while True:
            ser.write(poll_packet)
            ser.flush()
            
            # Read feedback packet from motor
            response = ser.read(30)
            if response and len(response) >= 15:
                print(f"🔥 Feedback Received! Raw Hex: {response.hex().upper()[:34]}")
            else:
                print("Awaiting bus frame data...")
                
            time.sleep(0.1) # 10Hz control cycle

    except KeyboardInterrupt:
        print("\n[*] Exit flag detected. Disabling motor torque safely...")
        disable_payload = b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFD'
        disable_packet = sof_header + arbitration_id + dlc + disable_payload + eof_footer
        if 'ser' in locals() and ser.is_open:
            ser.write(disable_packet)
            ser.flush()
            ser.close()
        print("✅ Motor safe. Pipeline disconnected.")
    except Exception as e:
        print(f"❌ Runtime exception: {e}")

if __name__ == "__main__":
    run_mit_loop()

