
from wpilib.command import Subsystem

from wpilib import CANTalon

from robot_map import RobotMap

import math

class Chassis():
    def __init__(self, robot):

        super().__init__()

        self.robot = robot
        # we want to create four swervemodules here
        # the numbers here need to be replaced with constants from robotmap
        #  A - D
        #  |   |
        #  B - C
        self._modules = [SwerveModule(RobotMap.module_a_move_motor_id,
                                      RobotMap.module_a_rotation_motor_id,
                                      True, False, True),
                         SwerveModule(RobotMap.module_b_move_motor_id,
                                      RobotMap.module_b_rotation_motor_id,
                                      True, True, True),
                         SwerveModule(RobotMap.module_c_move_motor_id,
                                      RobotMap.module_c_rotation_motor_id,
                                      True, True, True),
                         SwerveModule(RobotMap.module_d_move_motor_id,
                                      RobotMap.module_d_rotation_motor_id,
                                      True, False, True)
                         ]

    def drive(self, vX, vY, vZ, throttle):
        if self.robot.field_oriented:
            vX, vY = self.robot.oi.fieldOrient(vX, vY, self.robot.bno055.getHeading())
        motor_vectors = []
        for scaling in RobotMap.motor_vz_scaling:
            motor_vectors.append((vX+vZ*scaling[0], vY+vZ*scaling[1]))
        # convert the vectors to polar coordinates
        polar = []
        max_mag = 1.0
        for motor_vector in motor_vectors:
            #                      direction                                                             magnitude
            polar_vector = [math.atan2(motor_vector[1], motor_vector[0]), math.sqrt(motor_vector[0]**2+motor_vector[1]**2)]
            if abs(polar_vector[1]) > max_mag:
                max_mag= polar_vector[1]
            polar.append(polar_vector)

        for polar_vector in polar:
            polar_vector[1]/= max_mag
            polar_vector[1]*=throttle

        for module, polar_vector in zip(self._modules, polar):
            module.steer(polar_vector[0], polar_vector[1])


class SwerveModule():
    def __init__(self, driveCanTalonId, steerCanTalonId,
                 absoluteEncoder=True, reverseDrive=False,
                 reverseSteer=False):
        # Initialise private motor controllers
        self._drive = CANTalon(driveCanTalonId)
        self.reverse_drive = reverseDrive
        self._steer = CANTalon(steerCanTalonId)
        # Private members to store the setpoints
        self._speed = 0.0
        self._direction = 0.0
        # Always in radians. Right hand rule applies - Z is up!

        # Set up the motor controllers
        # Different depending on whether we are using absolute encoders or not
        if absoluteEncoder:
            self.counts_per_radian = 1024.0/(2.0*math.pi)
            self._steer.setFeedbackDevice(CANTalon.FeedbackDevice.AnalogEncoder)
            self._steer.changeControlMode(CANTalon.ControlMode.Position)
            self._steer.reverseSensor(reverseSteer)
            self._steer.reverseOutput(not reverseSteer)
            # Read the current encoder position
            self._steer.setPID(6.0, 0.0, 0.0) # PID values for abs
            self._direction = 1.0*self._steer.get()/self.counts_per_radian
            import logging
            logging.getLogger("Swerve").info("CAN id: %i Counts: %i Direction: %f"
                                             % (steerCanTalonId, self._steer.get(), self._direction))
        else:
            self._steer.changeControlMode(CANTalon.ControlMode.Position)
            self._steer.setFeedbackDevice(CANTalon.FeedbackDevice.QuadEncoder)
            self._steer.setPID(6.0, 0.0, 0.0) # PID values for rel
            self._steer.setPosition(0.0)
            self.counts_per_radian = 497.0*(40.0/48.0)*4.0/(2.0*math.pi)


    def steer(self, direction, speed = 0):
        # Set the speed and direction of the swerve module
        # Always choose the direction that minimises movement,
        # even if this means reversing the drive motor
        direction = constrain_angle(direction) # rescale to +/-pi
        current_heading = constrain_angle(self._direction)

        delta = min_angular_displacement(current_heading, direction)

        self._direction += delta
        if self.reverse_drive:
            speed=-speed
        if abs(constrain_angle(self._direction)-direction)<math.pi/6.0:
            self._drive.set(speed)
            self._speed = speed
        else:
            self._drive.set(-speed)
            self._speed = -speed
        if speed != 0.0:
            self._steer.set(self._direction*self.counts_per_radian)

    def getSpeed(self):
        return self._speed

    def getDirection(self):
        return self._direction

def constrain_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))

def min_angular_displacement(current, target):
    target = constrain_angle(target)
    opp_target = constrain_angle(target + math.pi)
    current = constrain_angle(current)
    diff = constrain_angle(target-current)
    opp_diff = constrain_angle(opp_target-current)

    if abs(diff) < abs(opp_diff):
        return diff
    return opp_diff


