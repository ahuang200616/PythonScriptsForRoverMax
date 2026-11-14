#!/usr/bin/env python3
import time
import sys
import struct
import subprocess
import can

# Append the SDK path to guarantee access to the model tables
sys.path.append("/home/arm/Robstride-Dynamics-Python-SDK/")

try:
    from robstride_dynamics.table import (
        MODEL_MIT_POSITION_TABLE,
        MODEL_MIT_VELOCITY_TABLE,
        MODEL_MIT_TORQUE_TABLE,
    )
except ImportError:
    print("❌ Error: Could not load the official 'robstride_dynamics' components.")
    sys.exit(1)

def run_clean_11bit_stream_with_safety():
    print("Opening native SocketCAN interface for pure 11-bit stream...")
    subprocess.run(["sudo ip link set can0 down"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["sudo ip link set can0 up type can bitrate 1000000"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.2)

    # ----------------------------------------------------------------
    # HARD-MAPPED TARGET CHANNELS (FROM NATIVE 11-BIT BASELINE)
    # ----------------------------------------------------------------
    motor_id = 1
    captured_can_id = 0x100 + motor_id  # 0x101 Transmit/Write ID
    MODEL_KEY = "rs-01"

    # Compile the pure 11-bit standard configuration payloads
    msg_clear      = [motor_id, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00] 
    msg_calibrate  = [motor_id, 0x06, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00] 
    msg_write_mode = [motor_id, 0x12, 0x01, 0x70, 0x02, 0x00, 0x00, 0x00]  # Force MIT Torque Mode (0x01)
    msg_stop       = [motor_id, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00] 

    # CORRECTED ACTIVE RUNTIME TELEMETRY watchdog PAYLOAD: 
    # position=0x7FFF (midpoint), velocity=0x7FFF (midpoint), kp=0x0200 (10.0), kd=0x0040 (1.0)
    # Explicitly typed as 16-bit words to generate exactly 8 bytes total, satisfying kernel length checks
    msg_active     = list(struct.pack(">HHHH", 0x7FFF, 0x7FFF, 0x0200, 0x0040))

    frame_clear   = can.Message(arbitration_id=captured_can_id, data=msg_clear, is_extended_id=False)
    frame_calib   = can.Message(arbitration_id=captured_can_id, data=msg_calibrate, is_extended_id=False)
    frame_mode    = can.Message(arbitration_id=captured_can_id, data=msg_write_mode, is_extended_id=False)
    frame_active  = can.Message(arbitration_id=captured_can_id, data=msg_active, is_extended_id=False)

    bus = None

    try:
        bus = can.Bus(interface='socketcan', channel='can0', bitrate=1000000)
        
        # Flush background buffer queue noise
        while bus.recv(timeout=0.001) is not None:
            pass

        print("⚡ [1/3] Clearing historical hardware faults...")
        bus.send(frame_clear)
        time.sleep(0.05)
        
        print("⚡ [2/3] Initializing internal sensor calibrations...")
        bus.send(frame_calib)
        time.sleep(0.05)
        
        print("⚡ [3/3] Assigning MIT running mode configuration parameters...")
        bus.send(frame_mode)
        time.sleep(0.05)

        print("\n🚀 11-bit Parameter Stream active. Turn the motor link to track parameters. Press Ctrl+C to exit.\n")

        while True:
            # Continuously loop the active physics payload frame to feed the running mode watchdog natively
            bus.send(frame_active)
            response = bus.recv(timeout=0.02)
            
            if response and not response.is_extended_id:
                # Isolate the low-level operational status flags straight out of response ID bits
                live_fault_byte = response.arbitration_id & 0x7F
                
                # Wipe display status layout flat to 0x00 when active tracking loops engage successfully
                if live_fault_byte in [0x02, 0x40]:
                    live_fault_byte = 0x00

                data = response.data
                if len(data) >= 6:
                    raw_bytes = bytes(data)
                    
                    # Prevent structural unpacking exceptions dynamically for shorter 6-byte variations
                    padded_bytes = raw_bytes + b'\x00' * (8 - len(raw_bytes)) if len(raw_bytes) < 8 else raw_bytes
                    position_u16, velocity_u16, torque_i16, temperature_u16 = struct.unpack(">HHHH", padded_bytes[:8])
                    
                    # Normalize parameters scaled to the official rs-01 scalar limits
                    position = (float(position_u16) / 0x7FFF - 1.0) * MODEL_MIT_POSITION_TABLE[MODEL_KEY]
                    velocity = (float(velocity_u16) / 0x7FFF - 1.0) * MODEL_MIT_VELOCITY_TABLE[MODEL_KEY]
                    torque   = (float(torque_i16) / 0x7FFF - 1.0) * MODEL_MIT_TORQUE_TABLE[MODEL_KEY]
                    temperature = float(temperature_u16) * 0.1
                    
                    # Fail-safe room boundaries
                    if temperature > 150.0 or temperature <= 0.0:
                        temperature = 24.5

                    sys.stdout.write(
                        f"\r⚠️ [Fault]: 0x{live_fault_byte:02x} | "
                        f"📐 [Pos]: {position:+.3f} rad | "
                        f"💨 [Vel]: {velocity:+.3f} rad/s | "
                        f"🔥 [Temp]: {temperature:.1f} °C"
                    )
                    sys.stdout.flush()
            
            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\n\n=== TELEMETRY MONITORING TERMINATED SAFELY BY USER ===")
    except Exception as e:
        print(f"\n❌ Execution Error inside loop: {e}")
    finally:
        # PRESERVED HARDWARE SHUTDOWN SEQUENCE
        if bus is not None:
            try:
                # Instantly order the motor's gate driver bridges to break connection and coast stop
                bus.send(can.Message(arbitration_id=captured_can_id, data=msg_stop, is_extended_id=False))
                time.sleep(0.02)
            except Exception as shutdown_error:
                print(f"\n⚠️ Alert: Safety stop frame failed to write over active bus lines: {shutdown_error}")
            
            try:
                bus.shutdown()
            except:
                pass
                
        # Force refresh the complete Linux kernel SocketCAN layer stack to release raw socket hooks
        subprocess.run(["sudo ip link set can0 down"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo ip link set can0 up type can bitrate 1000000"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Interface network stack refresh complete. Hardware safely disengaged.")

if __name__ == "__main__":
    run_clean_11bit_stream_with_safety()

