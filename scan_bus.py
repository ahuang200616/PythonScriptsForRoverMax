from robstride_dynamics import RobstrideBus
import subprocess


# Make sure this matches your CHANNEL ("can1" or "can0")
print("Scanning bus...")
print(RobstrideBus.scan_channel("can0")) 


        # THE CORE FIX: Automatically flush the Jetson's CAN controller error states 
        # behind the scenes before exiting, preventing the need for manual commands.
print("Flushing Jetson network socket layer dynamically...")
subprocess.run(["sudo", "ip", "link", "set", "can0", "down"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["sudo", "ip", "link", "set", "can0", "up", "type", "can", "bitrate", "1000000"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
