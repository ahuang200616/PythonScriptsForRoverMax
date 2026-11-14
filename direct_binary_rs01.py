import serial
import time
import struct
import sys

ADAPTER_PORT = '/dev/ttyCH341USB0'
MOTOR_ID = 127  # Try 127 first (factory private default), then change to 1 if testing MIT firmware.

def run_hardware_bridge():
    print(f"[*] Step 1: Connecting to physical serial port on {ADAPTER_PORT}...")
    try:
        ser = serial.Serial(ADAPTER_PORT, baudrate=921600, timeout=1.5)
    except Exception as e:
        print(f"❌ Failed to open port: {e}")
        sys.exit(1)
        
    print("[*] Step 2: Sending hardware firmware configuration handshakes...")
    # Clean up lingering adapter memory states
    ser.write(b"AT+MODE=0\r\n")
    time.sleep(0.05)
    
    # Transition the controller into binary streaming mode
    ser.write(b"AT+MODE=1\r\n")  
    time.sleep(0.05)
    
    # Synchronize the internal CAN clock speed to 1 Mbps
    ser.write(b"AT+CAN_BAUD=1000000\r\n")  
    time.sleep(0.05)
    
    # Clear out confirmation text echoes from the buffer
    ser.reset_input_buffer()
    print("✅ Adapter firmware initialization complete.")

    # --- PACKET CONSTRUCTION ---
    # The Robstride adapter wraps binary serial traffic using an explicit framing standard:
    # [SOF: 2 Bytes] [Arbitration ID: 4 Bytes] [DLC: 1 Byte] [Payload: 8 Bytes] [EOF: 2 Bytes]
    sof_header = b'\xAA\x55'
    eof_footer = b'\x55\xAA'
    
    # Base private communication packet query for ID 127 mapping: 0x0000FD7F
    # For a general motor query, the arbitration ID format matches: 0x0000FD00 + Motor ID
    arb_id = 0x0000FD00 | MOTOR_ID
    arbitration_bytes = struct.pack('>I', arb_id) # Packs into 4 big-endian bytes
    
    dlc_byte = b'\x08' # Explicit data payload length specification
    data_payload = b'\x00' * 8 # Clear command polling bytes
    
    # Assemble the full raw byte packet stream
    tx_packet = sof_header + arbitration_bytes + dlc_byte + data_payload + eof_footer
    
    print(f"[*] Step 3: Transmitting raw binary packet bytes: {tx_packet.hex().upper()}")
    ser.write(tx_packet)
    ser.flush()

    # --- TELEMETRY CAPTURE ---
    print("[*] Step 4: Awaiting physical telemetry response back from motor transceiver...")
    # The motor returns a matching 17-byte structural payload wrapper
    rx_bytes = ser.read(30)
    
    if rx_bytes:
        print(f"\n🔥 SUCCESS! Captured active hardware data feedback packet!")
        print(f"Raw Hex Stream: {rx_bytes.hex().upper()}")
        
        # Parse the message structure if it contains the valid start of frame header
        if b'\xAA\x55' in rx_bytes:
            start_idx = rx_bytes.find(b'\xAA\x55')
            extracted_data = rx_bytes[start_idx+7 : start_idx+15]
            print(f"Extracted Motor Telemetry Hex Payload: {[hex(b) for b in extracted_data]}")
    else:
        print("\n❌ Timeout: Physical bus line remain silent.")
        print("👉 Diagnostic: Double check that your independent 24V-48V external motor power supply is active.")
        print("👉 Alignment: Ensure that a common ground wire bridges the Negative (-) rail of the supply to the adapter GND terminal.")

    ser.close()
    print("[*] Pipeline safely released.")

if __name__ == "__main__":
    run_hardware_bridge()

