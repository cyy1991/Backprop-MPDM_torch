#!/usr/bin/python3
import rospy
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Path
from Utils.Utils import quaternion_to_euler
import numpy as np


class RobotStateSub:
    def __init__(self, topic_pose="/odom", topic_speed="/cmd_vel", topic_path="/move_base/GlobalPlanner/plan"):
        # robot = [x, y, yaw, speed_x, speed_y, speed_yaw]
        self.pose = [0, 0, 0]
        self.speed = [0, 0, 0]
        self.robot = np.zeros(6)
        self.robot[:3] = None, None, None
        self.path = None
        self.goal = np.zeros(3)
        self.goal[:] = None, None, None
        self.sub_path = rospy.Subscriber(
            topic_path, Path, self.callback_path, queue_size=1)
        self.sub_pose = rospy.Subscriber(
            topic_pose, PoseStamped, self.callback_pose, queue_size=1)
        self.sub_speed = rospy.Subscriber(
            topic_speed, Twist, self.callback_twist, queue_size=1)

    def callback_path(self, msg):
        self.path= []
        for p in msg.poses:
            _, _, yaw = quaternion_to_euler(
            p.pose.orientation.x,
            p.pose.orientation.y,
            p.pose.orientation.z,
            p.pose.orientation.w)
            point = [p.pose.position.x, p.pose.position.y, yaw]
            self.path.append(point)
        self.path = np.array(self.path)

        # self.goal = self.path

        # TODO: extract goal

    def callback_pose(self, msg):
        _, _, yaw = quaternion_to_euler(
            msg.pose.orientation.x,
            msg.pose.orientation.y,
            msg.pose.orientation.z,
            msg.pose.orientation.w)
        x = msg.pose.position.x
        y = msg.pose.position.y
        self.pose[:] = x, y, yaw
        self.robot[:3] = self.pose[:]

    def callback_twist(self, msg):
        x = msg.linear.x
        y = msg.linear.y
        yaw = msg.angular.z
        self.speed[:] = x, y, yaw
        self.robot[3:] = self.speed[:]

    def get_robot_state(self):
        if np.isnan(self.robot)[0] or np.isnan(self.robot)[1] or np.isnan(self.robot)[2] or self.path is None:
            return None, None
        return self.robot.copy(), self.path.copy()