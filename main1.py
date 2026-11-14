#!/usr/bin/env python3
import signal
import sys
import time
from robstride_driver import RobStrideMotor


def print_telemetry(telem):
    if telem is None:
        return
    print(
        f"Telemetry -> "
        f"Pos: {telem['pos_deg']:+6.1f} deg | "
        f"Vel: {telem['vel_rad']:+5.2f} rad/s | "
        f"Torque: {telem['torque_nm']:+5.2f} Nm | "
        f"Temp: {telem['temp_c']:4.1f} C | "
        f"Fault: {telem['fault_str']}"
    )


def main():
    def handle_signal(signum, frame):
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGHUP, handle_signal)

    print("Connecting to Motor 127 via gs_usb...")
    try:
        with RobStrideMotor(motor_id=127, max_torque_nm=3.0, default_speed_rad=1.5) as motor:
            print_telemetry(motor.last_telemetry)

            print("\nReady! Available Commands:")
            print(f"  - <deg>            -> Move to angle at current speed ({motor.default_speed_rad:.2f} rad/s)")
            print("  - <deg> <rad/s>    -> Move to angle at custom speed (e.g., 90 0.5)")
            print(f"  - v <rad/s>        -> Set default travel speed (0.05 to {motor.hw_max_speed_rad} rad/s)")
            print(f"  - t <Nm>           -> Set max torque limit (0.1 to {motor.hw_max_torque_nm} Nm)")
            print("  - q                -> Disable motor and exit\n")

            while True:
                user_in = input("Command [<deg> | <deg> <rad/s> | v <rad/s> | t <Nm> | q]: ").strip().lower()
                if user_in in ("q", "quit", "exit"):
                    break
                if not user_in:
                    continue

                if user_in.startswith("t"):
                    val_str = user_in[1:].replace("=", "").strip()
                    try:
                        telem = motor.set_max_torque(float(val_str))
                        print(f"Max torque limit set to {motor.max_torque_nm:.2f} Nm")
                        print_telemetry(telem)
                    except ValueError:
                        print("Invalid torque command. Example: t 4.5")
                    continue

                if user_in.startswith("v"):
                    val_str = user_in[1:].replace("=", "").strip()
                    try:
                        motor.set_default_speed(float(val_str))
                        print(f"Default travel speed set to {motor.default_speed_rad:.2f} rad/s")
                    except ValueError:
                        print("Invalid velocity command. Example: v 1.0")
                    continue

                parts = user_in.replace(",", " ").split()
                try:
                    target_deg = float(parts)
                    custom_vel = float(parts) if len(parts) >= 2 else None
                except ValueError:
                    print("Invalid input. Enter '<deg>', '<deg> <rad/s>', 'v <rad/s>', 't <Nm>', or 'q'.")
                    continue

                if not (-720.0 <= target_deg <= 720.0):
                    print("Angle out of safe range (-720 deg to +720 deg).")
                    continue

                last_print_time = [0.0]

                def throttled_callback(telem):
                    now = time.time()
                    if (now - last_print_time) >= 0.25:
                        print_telemetry(telem)
                        last_print_time = now

                final_telem = motor.move_to(target_deg, speed_rad=custom_vel, callback=throttled_callback)
                print_telemetry(final_telem)
                print("")

    except (KeyboardInterrupt, EOFError, SystemExit):
        print("\nInterrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")

    print("Motor disabled and USB adapter closed cleanly.")


if __name__ == "__main__":
    main()
