#!/usr/bin/env python


import cv2
import numpy as np
import tf
from time import sleep
import cv2.aruco as aruco
import glob
import rospy
#Import bridge to convert open cv frames into ros frames
from cv_bridge import CvBridge

from geometry_msgs.msg import Pose
from sensor_msgs.msg import Image

from geometry_msgs.msg import PointStamped
from visualization_msgs.msg import MarkerArray
from visualization_msgs.msg import Marker

import math


def isRotationMatrix(R) :
    Rt = np.transpose(R)
    shouldBeIdentity = np.dot(Rt, R)
    I = np.identity(3, dtype = R.dtype)
    n = np.linalg.norm(I - shouldBeIdentity)
    return n < 1e-6


def rotationMatrixToEulerAngles(R) :

    assert(isRotationMatrix(R))

    sy = math.sqrt(R[0,0] * R[0,0] +  R[1,0] * R[1,0])

    singular = sy < 1e-6

    if  not singular :
        x = math.atan2(R[2,1] , R[2,2])
        y = math.atan2(-R[2,0], sy)
        z = math.atan2(R[1,0], R[0,0])
    else :
        x = math.atan2(-R[1,2], R[1,1])
        y = math.atan2(-R[2,0], sy)
        z = 0

    return np.array([x, y, z])



cap = cv2.VideoCapture(1)

criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
objp = np.zeros((6*7,3), np.float32)
objp[:,:2] = np.mgrid[0:7,0:6].T.reshape(-1,2)

# Arrays to store object points and image points from all the images.
objpoints = [] # 3d point in real world space
imgpoints = [] # 2d points in image plane.

images = glob.glob('/home/ivliev/catkin_ws/src/test_aruco/script/calib_images/*.jpg')



for fname in images:
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

    # Find the chess board corners
    ret, corners = cv2.findChessboardCorners(gray, (7,6),None)

    # If found, add object points, image points (after refining them)
    if ret == True:
        objpoints.append(objp)

        corners2 = cv2.cornerSubPix(gray,corners,(11,11),(-1,-1),criteria)
        imgpoints.append(corners2)

        # Draw and display the corners
        img = cv2.drawChessboardCorners(img, (7,6), corners2,ret)


ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1],None,None)


while 1:
    #Initializing publisher
    pub_frame = rospy.Publisher("frames", Image, queue_size=10)
    pub_pose = rospy.Publisher("aruco/pose", Pose, queue_size=10)

    rospy.init_node('stream_publisher', anonymous=True)
    rate = rospy.Rate(10)
    # Reads frames from a camera
    ret, frame = cap.read()
    # operations on the frame come here
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_250)
    parameters = aruco.DetectorParameters_create()
    #lists of ids and the corners beloning to each id
    corners, ids, rejectedImgPoints = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)


    font = cv2.FONT_HERSHEY_SIMPLEX #font for displaying text (below)
    if np.all(ids != None):
        for i in range(len(ids)):
            if ids[i][0] == 1 or ids[i][0] == 2 or ids[i][0] == 3:
                rvec, tvec,_ = aruco.estimatePoseSingleMarkers(corners[i], 0.08, mtx, dist)
                dst, jacobian = cv2.Rodrigues(rvec)
                array_angle = rotationMatrixToEulerAngles(dst)
                array_angle_deg = array_angle*180/math.pi

                if(array_angle_deg[2] < 0):
                    array_angle_deg[2] = array_angle_deg[2] +360
                # print array_angle_deg[2]

                h = 0.1
                x0 = tvec[0][0][0] + h * np.sin(array_angle[2]*math.pi/180)
                y0 = tvec[0][0][1] + h * np.cos(array_angle[2]*math.pi/180)

                if ids[i][0] == 1:
                    theta = array_angle_deg[2]
                if ids[i][0] == 2:
                    theta = (array_angle_deg[2] + 240) % 360
                if ids[i][0] == 3:
                    theta = (array_angle_deg[2] + 120) % 360
                print x0, y0, theta

                msg = Pose()
                msg.position.x= tvec[0][0][0]
                msg.position.y= tvec[0][0][1]
                msg.position.z= tvec[0][0][2]

                # msg.orientation.x=pose_quat[0]
                # msg.orientation.y=pose_quat[1]
                # msg.orientation.z=pose_quat[2]
                # msg.orientation.w=pose_quat[3]

                pub_pose.publish(msg);

                #!!!!!!!!!!!
                aruco.drawAxis(frame, mtx, dist, rvec[0], tvec[0], 0.1) #Draw Axis
                aruco.drawDetectedMarkers(frame, corners) #Draw A square around the markers
        #!!!!!!!!!!!


        ###### DRAW ID #####
        cv2.putText(frame, "Id: " + str(ids), (0,64), font, 1, (0,255,0),2,cv2.LINE_AA)
        # print('>>>')
        # print(corners[0][0])
        # print('<<<')

    ##Use the belw comment if you need ti display an image in a window
    cv2.imshow('frame',frame)
    #Give the frames to ros Environment
    bridge= CvBridge()
    #Encoding bgr8: CV_8UC3 color image with blue-green-red color order
    ros_image = bridge.cv2_to_imgmsg(frame, "bgr8")
    pub_frame.publish(ros_image)
    rate.sleep()

    # Wait for Esc key to stop
    k = cv2.waitKey(30) & 0xff
    if k == 27:
        break

# Close the window
cap.release()

# De-allocate any associated memory usage
cv2.destroyAllWindows()
