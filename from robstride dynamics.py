from robstride_dynamics import RobstrideBus

# Make sure this matches your CHANNEL ("can1" or "can0")
print("Scanning bus...")
print(RobstrideBus.scan_channel("can1")) 

