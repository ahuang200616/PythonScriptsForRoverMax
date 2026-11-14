import serial
import time
import struct

ADAPTER_PORT = '/dev/ttyCH341USB0'
BAUD_RATES = ["1000000", "500000", "250000"]
TARGET_IDS = [1, 127]

def configure_adapter(ser, baud):
    ser.write(b"AT+MODE=1\r\n")
    time.sleep(0.05)
    ser.write(f"AT+CAN_BAUD={baud}\r\n".encode())
    time.sleep(0.05)
    ser.reset_input_buffer()

def run_scan():
    print("[*] Starting multi-baud CANopen and MIT cross-protocol scan...")
    try:
        ser = serial.Serial(ADAPTER_PORT, baudrate=921600, timeout=0.2)
        
        for baud in BAUD_RATES:
            print(f"\n==========================================")
            print(f"[*] Testing Bus Speed: {int(baud)//1000} kbps")
            print(f"==========================================")
            configure_adapter(ser, baud)
            
            # --- STRATEGY A: CANopen Network Reset Broadcast ---
            # Standard CANopen NMT frame: ID=0, Data=[0x01, 0x00] (Operational Mode command)
            print("[*] Sending CANopen Global Operational Mode Broadcast...")
            sof = b'\xAA\x55'
            eof = b'\x55\xAA'
            canopen_packet = sof + struct.pack('>I', 0) + b'\x02' + b'\x01\x00\x00\x00\x00\x00\x00\x00' + eof
            ser.write(canopen_packet)
            ser.flush()
            time.sleep(0.05)
            
            for motor_id in TARGET_IDS:
                # --- STRATEGY B: MIT Mode Probe ---
                print(f"  [-] Polling Motor ID {motor_id} via standard MIT protocol...")
                mit_packet = sof + struct.pack('>I', motor_id) + b'\x08' + b'\x00'*8 + eof
                ser.write(mit_packet)
                ser.flush()
                time.sleep(0.05)
                
                # --- STRATEGY C: CANopen SDO Node Guarding Read ---
                print(f"  [-] Polling Motor ID {motor_id} via CANopen Node Guarding (0x700 structure)...")
                guard_packet = sof + struct.pack('>I', 0x700 + motor_id) + b'\x00' + b'\x00'*8 + eof
                ser.write(guard_packet)
                ser.flush()
                time.sleep(0.05)
                
                # Check for any hardware responses in the serial buffer
                response = ser.read(40)
                if response and len(response) >= 15:
                    print(f"\n🔥 SUCCESS! Motor responded at {int(baud)//1000} kbps!")
                    print(f"Raw received bytes: {response.hex().upper()}")
                    ser.close()
                    return
                    
        print("\n[!] Scan finished. No frames received at any standard baud rate configuration.")
        ser.close()
        
    except Exception as e:
        print(f"❌ Scanner failed: {e}")

if __name__ == "__main__":
    run_scan()

