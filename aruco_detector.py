#!/usr/bin/env python3
"""Detect ArUco markers and issue bounded search/approach commands when armed."""

import time

import cv2
from cv2 import aruco
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Int32, Int32MultiArray

# Standard 4 bit by 4 bit
DICTIONARY = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
PARAMETERS = aruco.DetectorParameters_create()

# Subject to change
ALLOWED_IDS = (1, 3, 7)
 
def find_markers(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = aruco.detectMarkers(gray, DICTIONARY, parameters=PARAMETERS)
    if ids is None:
        return {}
    return {int(marker_id): points[0] for marker_id, points in zip(ids.flatten(), corners)}


def detect_ids(frame):
    return sorted(find_markers(frame))



"""
tracking_command(points,frame_width)

Upon the detection of a valid frame containing a valid aruco id, the tracking_command
method is called. 

Approach after centering; keep commands above the MAX open-loop duty cutoff.

@param points t

@return Twist() with 'command' reference

@throws none
"""


def tracking_command(points, frame_width):
    print('Hi')
    xs = points[:, 0]
    center_error = (float(xs.mean()) - frame_width / 2) / (frame_width / 2)
    marker_width = float(xs.max() - xs.min())

    # Twist constructor body need not have any args; okay.
    command = Twist()

    if (command.angular.z != 0.0 | command.linear.x != 0.0):
        command.angular.z = 0.0
        command.linear.x = 0.0

    # Should not allow excessive centre errors.

    # Should stop at the 'dead zone' ~ approx. 100 < dist < 120 
    
    try:
        if (center_error > 0.2):
            print("[DEBUG] Centre marker slightly off. Adjusting course slightly")
            command.angular.z = -1.2
        elif (center_error < 0.2):
            print("[DEBUG] Centre marker slightly off. Adjusting course slightly")
            command.angular.z = 1.2
        else:
            if (marker_width >= 120):
                print("[DEBUG] marker width exceeded 120 px, reversing.")
                command.linear.x = -0.32
            elif (marker_width < 100):
                print("[DEBUG] marker width below 100 px, approaching.")
                command.linear.x = 0.32
            else:
                command.linear.x = 0.0
            return command
    except Exception as e:
        print("Unable to correctly adjust rover. Perhaps modify the constraints above?")
        print(e)
        return command

class ArucoDetector(Node):
    def __init__(self):
        super().__init__('aruco_detector')
        self.bridge = CvBridge()
        self.last_frame_time = 0.0
        self.last_enable_time = 0.0
        self.last_ids = None
        self.target_id = 1
        self.confirmed_frames = 0
        self.armed = False
        self.publisher = self.create_publisher(Int32MultiArray, '/aruco/detected_ids', 10)
        self.command_publisher = self.create_publisher(Twist, '/aruco/cmd_vel', 1)
        self.create_subscription(Bool, '/aruco/enable', self.on_enable, 1)
        self.create_subscription(Int32, '/aruco/target_id', self.on_target, 1)
        self.subscription = self.create_subscription(
            Image, '/camera/camera/color/image_raw', self.on_image,
            qos_profile_sensor_data)
        self.get_logger().info('ArUco 4x4 recognition ready; tracking requires WebUI Start')

    def on_enable(self, message):
        self.armed = message.data
        if message.data:
            self.last_enable_time = time.monotonic()
        else:
            self.confirmed_frames = 0
            self.command_publisher.publish(Twist())

    def on_target(self, message):
        if message.data in ALLOWED_IDS:
            self.target_id = message.data
            self.confirmed_frames = 0

    def on_image(self, message):
        now = time.monotonic()
        if now - self.last_frame_time < 0.1:
            return
        self.last_frame_time = now
        try:
            frame = self.bridge.imgmsg_to_cv2(message, desired_encoding='bgr8')
            # The MAX camera is mounted inverted; steering uses upright image coordinates.
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            found = find_markers(frame)
        except Exception as error:
            self.get_logger().warning(f'Could not process camera frame: {error}')
            return

        ids = sorted(found)
        self.publisher.publish(Int32MultiArray(data=ids))
        
        if ids != self.last_ids:
            self.get_logger().info(f'ArUco IDs: {ids if ids else "none"}')
            self.last_ids = ids

        if not self.armed or now - self.last_enable_time > 0.7:
            self.armed = False
            self.confirmed_frames = 0
            return

        
        command = Twist()
    
        if self.target_id in found:
            self.confirmed_frames += 1
            if self.confirmed_frames >= 2:
                try:
                   print('[Debug] Frame found')
                   command = tracking_command(found[self.target_id], frame.shape[1]) 
                except Exception as e:
                    print("[Debug] Exception occured when calling tracking_command")
                finally:
                    time.sleep(0.2)
        else:
            self.confirmed_frames = 0
            command.angular.z = 1.2
    
        self.command_publisher.publish(command)


def main():
    rclpy.init()
    node = ArucoDetector()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        print("[Debug] One of two exceptions occured: 1) KeyboardInterrupt || ExternalShutdownException")
    finally:
        node.command_publisher.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
