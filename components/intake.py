
from networktables import NetworkTable
from wpilib import CANTalon, PowerDistributionPanel

from components import shooter

import csv, time

import logging
from _collections import deque

class States:
    no_ball = 0
    backdriving = 11
    backdriving_slow = 12
    up_to_speed = 10
    intaking_free = 1
    intaking_contact = 2
    pinning = 4
    pinned = 5
    fire = 6

class Intake:
    intake_motor = CANTalon
    shooter = shooter.Shooter

    max_speed = 9000.0

    def __init__(self):
        self._speed = 0.0
        self.state = States.no_ball
        self.current_deque = deque([0.0] * 3, 3)  # Used to average currents over last n readings
        self.log_queue = []
        self.velocity_queue = []
        self.intake_time = 0.0
        self.previous_velocity = 0.0
        self.shoot_time = None
        self.sd = NetworkTable.getTable('SmartDashboard')
        self.contact_time = time.time()

    def intake(self):
        """ Spin the intake at the maximum speed to suck balls in """
        self.speed_mode()
        pass

    def backdrive(self):
        """ Backdrive the intake """
        self.speed_mode()
        pass

    def backdrive_slow(self):
        """ Backdrive the intake at 0.5 speed """
        self.speed_mode()
        pass

    def backdrive_pin(self):
        """ Used when pinning the ball """
        self.speed_mode()
        pass

    def stop(self):
        """ Stop the intake """
        self.speed_mode()
        pass

    def jam(self):
        """ Jam the ball in the intake """
        self.position_mode()
        self.intake_motor.set(-1000)

    def speed_mode(self):
        self.intake_motor.changeControlMode(CANTalon.ControlMode.Speed)
        self.intake_motor.setPID(0.0, 0.0, 0.0, 1023.0/Intake.max_speed)

    def position_mode(self):
        self.intake_motor.changeControlMode(CANTalon.ControlMode.Position)
        self.intake_motor.setPID(1.0, 0.0, 0.0)
        self.intake_motor.setPosition(0.0)

    def shooting(self):
        if self.state == States.fire:
            return True
        return False

    def stop(self):
        self.state = States.no_ball

    def toggle(self):
        if self.state != States.no_ball and self.state != States.pinned:
            self.state = States.no_ball
            self.log_current()
        else:
            self.state = States.intaking_free

    def backdrive(self):
        self.state = States.backdriving

    def backdrive_slow(self):
        self.state = States.backdriving_slow

    def fire(self):
        self.state = States.fire

    def log_current(self):
        csv_file = open("/tmp/current_log.csv", "a")
        csv_file.write(str(self.log_queue).strip('[]').replace(' ', '')+"\n")
        csv_file.close()
        csv_file = open("/tmp/velocity_log.csv", "a")
        csv_file.write(str(self.velocity_queue).strip('[]').replace(' ', '')+"\n")
        csv_file.close()
        self.log_queue = []
        self.velocity_queue = []

    def on_enable(self):
        self.stop()

    def execute(self):
        # add next reading on right, will automatically pop on left
        maxlen = self.current_deque.maxlen
        prev_current_avg = sum(self.current_deque)/maxlen
        self.current_deque.append(self.intake_motor.getOutputCurrent())
        self.current_avg = sum(self.current_deque) / maxlen
        current_rate = self.current_avg - prev_current_avg#self.current_deque[maxlen-1]-self.current_deque[maxlen-2]
        self.velocity = self.intake_motor.get()
        self.acceleration = self.velocity - self.previous_velocity

        self.sd.putDouble("intake_current_rate", self.current_rate)
        self.sd.putDouble("intake_current_avg", self.current_avg)
        self.sd.putDouble("intake_closed_loop_error", self.intake_motor.getClosedLoopError())
        self.sd.putDouble("intake_acceleration", self.acceleration)
        self.sd.putDouble("intake_velocity", self.velocity)


        if self.state != States.no_ball and self.state != States.pinned:
            self.log_queue.append(self.current_deque[maxlen-1])
            self.velocity_queue.append(self.intake_motor.get())

        if self.state == States.backdriving:
            self.intake_motor.changeControlMode(CANTalon.ControlMode.Speed)
            self._speed = -1.0

        if self.state == States.no_ball:
            self._speed = 0.0

        if self.state == States.intaking_free:
            self.intake_motor.changeControlMode(CANTalon.ControlMode.Speed)
            self.intake_motor.setPID(0.0, 0.0, 0.0, 1023.0/Intake.max_speed)
            self.shooter.change_state(shooter.States.off)
            if self._speed == 0.7 and self.intake_motor.getClosedLoopError() < Intake.max_speed*0.05:
                self.state = States.up_to_speed
            self._speed = 0.7

        if self.state == States.up_to_speed:
            if self.intake_motor.getClosedLoopError() > Intake.max_speed*0.1 and acceleration < 0.0 and current_rate > 0.0:
                self.contact_time = time.time()
                self.state = States.intaking_contact

        if self.state == States.intaking_contact:
            self.shooter.change_state(shooter.States.backdriving)
            if time.time() - self.contact_time > 0.3:#acceleration > 0.0:#self.intake_motor.getClosedLoopError() < Intake.max_speed*0.1:
                self.state = States.pinning

        if self.state == States.pinning:
            self._speed = -0.3
            self.shooter.change_state(shooter.States.backdriving)
            if velocity < 0.0 and acceleration > 0.0:
                self.state = States.pinned
                self.intake_motor.changeControlMode(CANTalon.ControlMode.Position)
                self.intake_motor.setPID(1.0, 0.0, 0.0)
                self.intake_motor.setPosition(0.0)
                self.intake_motor.set(-1000)

        if self.state == States.pinned:
            self.shooter.change_state(shooter.States.off)
            self._speed = 0.0
            if self.log_queue:
                self.log_current()

        if self.state == States.backdriving_slow:
            self._speed = -0.5
            self.state = States.no_ball

        if self.state == States.fire:
            self.intake_motor.changeControlMode(CANTalon.ControlMode.Speed)
            self.intake_motor.setPID(0.0, 0.0, 0.0, 1023.0/Intake.max_speed)
            if abs(self.shooter.shooter_motor.getClosedLoopError())<= 0.02*(self.shooter.max_speed) and self.shooter._speed != 0.0:
                self._speed = 1.0
                if not self.shoot_time:
                    self.shoot_time = time.time()
            if self.shoot_time and time.time() - self.shoot_time > 1.0:
                self.state = States.no_ball
                self.shooter.stop()
                self.shoot_time = None

        if self.state != States.pinned:
            self.intake_motor.set(self._speed*Intake.max_speed)

        self.previous_velocity = velocity
