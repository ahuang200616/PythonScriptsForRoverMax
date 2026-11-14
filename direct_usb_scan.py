#!/usr/bin/env python3
import time
import usb.core
import usb.util

def run_direct_usb():
    vendor_id = 0x1d50
    product_id = 0x606f
    
    print(f"Searching for hardware ID {hex(vendor_id)}:{hex(product_id)} via raw USB endpoints...")
    dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
    
    if dev is None:
        print("[ERROR] Device not found physically on the USB ports. Run 'lsusb' again.")
        return

    print("Found device! Detaching any conflicting internal structures...")
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except Exception:
        pass

    try:
        dev.set_configuration()
        print("[SUCCESS] Connected to USB hardware endpoints. Sending broadcast ping...")
        
        # gs_usb candlelight protocol packet framing structure:
        # echo_id (4 bytes) | can_id (4 bytes) | can_dlc (4 bytes) | flags (4 bytes)
        broadcast_packet = b'\x00\x00\x00\x00\x00\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00'
        
        # Write payload out to Bulk Output Endpoint (0x01)
        dev.write(0x01, broadcast_packet, timeout=200)
        time.sleep(0.1)
        
        # Read incoming data back from Bulk Input Endpoint (0x81)
        print("Listening for incoming motor responses...")
        try:
            response = dev.read(0x81, 64, timeout=1500)
            if response:
                print(f"\n🎉 [SUCCESS] Motor responded over raw USB endpoint layer!")
                print(f" -> Raw Response Array (Hex): {[hex(b) for b in response]}")
                
                # In gs_usb framing, bytes 4-7 hold the responding CAN ID header
                if len(response) >= 8:
                    resp_can_id = response[4] | (response[5] << 8) | (response[6] << 16) | (response[7] << 24)
                    print(f" -> Decoded Responding Arbitration ID: {hex(resp_can_id)}")
            else:
                print("\n[TIMEOUT] Connected to adapter, but data frame buffer remained empty.")
        except usb.core.USBError as e:
            if e.errno == 110: # Timeout error code
                print("\n[TIMEOUT] No response from motor. Check 24V-48V power lines.")
            else:
                raise e
            
    except Exception as e:
        print(f"[ERROR] USB transaction error: {e}")

if __name__ == "__main__":
    run_direct_usb()

