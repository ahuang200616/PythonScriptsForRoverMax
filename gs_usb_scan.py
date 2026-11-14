#!/usr/bin/env python3
import time
import usb.core
import can

def run_gs_usb_scan():
    print("Searching for OpenMoko Candlelight hardware via user-space drivers...")
    
    # 1. Locate the physical raw hardware ID via pyusb
    dev = usb.core.find(idVendor=0x1D50, idProduct=0x606F)
    
    if dev is None:
        print("[ERROR] Could not find the USB adapter. Ensure it is plugged in via 'lsusb'.")
        return
        
    print(f"[FOUND] Adapter located at Bus {dev.bus} Address {dev.address}.")
    
    try:
        # 2. Let python-can handle the USB control channel initialization natively
        # This sends the required open/start tokens and opens the network pipeline at 1Mbps
        print("Configuring CAN controller registers and opening channel at 1Mbps...")
        bus = can.Bus(
            interface="gs_usb",
            channel=dev.product,
            bus=dev.bus,
            address=dev.address,
            bitrate=1000000
        )
        
        # 3. Broadcast the RobStride identification probe frame
        print("Broadcasting identification frame to the motor bus...")
        msg = can.Message(
            arbitration_id=0x00, 
            data=[0x00] * 8, 
            is_extended_id=False
        )
        bus.send(msg)
        
        # 4. Listen for back-channel telemetry replies
        print("Listening for a motor response (Timeout: 2.5 seconds)...")
        start_time = time.time()
        success = False
        
        while time.time() - start_time < 2.5:
            reply = bus.recv(timeout=0.1)
            if reply is not None:
                success = True
                print(f"\n🎉 [SUCCESS] Motor responded frame detected!")
                print(f" -> Frame Type: {'29-bit Extended' if reply.is_extended_id else '11-bit Standard'}")
                print(f" -> Arbitration ID (Hex): {hex(reply.arbitration_id)}")
                print(f" -> Data Payload Bytes: {[hex(b) for b in reply.data]}")
                break
                
        if not success:
            print("\n[TIMEOUT] The USB channel opened perfectly, but the motor did not reply.")
            print("Troubleshooting Checkpoints:")
            print(" 1. Ensure the motor is powered with external 24V/48V supply voltage.")
            print(" 2. Make sure the physical 120Ω termination resistor switch on the USB adapter is toggled to ON.")
            print(" 3. Try physically swapping the CAN_H and CAN_L wires clamped into the green terminal block.")
            
        bus.shutdown()
        
    except Exception as e:
        print(f"[ERROR] Communication failed: {e}")
        print("💡 Tip: Always execute hardware scripts using: sudo $(which python3) gs_usb_scan.py")

if __name__ == "__main__":
    run_gs_usb_scan()

