import asyncio
from typing import Optional, Dict, List, Callable
from config import MotorState, MIN_PWM, MOTOR_STR

from mavlink import MavlinkConnection

MAV_MSG_ID_SERVO_OUTPUT_RAW: int = 36
MAV_MSG_ID_ACTUATOR_OUTPUT_STATUS_STR: str = 'ACTUATOR_OUTPUT_STATUS'
MAV_MSG_ID_SERVO_OUTPUT_RAW_STR: str = 'SERVO_OUTPUT_RAW'

class PWMConnection:
    def __init__(self, connection: MavlinkConnection, num_motors: int = 6, read_frequency: int = 1_000_000):
        self.__connection: MavlinkConnection = connection
        self.__num_motors = num_motors

        # Motor states (0-indexed internally, but exposed as 1-indexed)
        self.__motor_states: List[MotorState] = [MotorState() for _ in range(num_motors)]

        # Callbacks for _state changes
        self.__state_callbacks: List[Callable[[int, MotorState], None]] = []

        self.__connection.request_data_stream(MAV_MSG_ID_SERVO_OUTPUT_RAW, read_frequency)
        self.__connection.register_message_handler(
            MAV_MSG_ID_ACTUATOR_OUTPUT_STATUS_STR, self.__handle_actuator_output_status
        )
        self.__connection.register_message_handler(
            MAV_MSG_ID_SERVO_OUTPUT_RAW_STR, self.__handle_servo_output_raw
        )

    def __handle_actuator_output_status(self, msg):
        """Process ACTUATOR_OUTPUT_STATUS message (modern)"""
        # Update motor states
        for i in range(min(self.__num_motors, len(msg.actuator))):
            pwm_value = msg.actuator[i]

            # Only update if value changed significantly
            if abs(self.__motor_states[i].pwm - pwm_value) > 1:
                old_pwm = self.__motor_states[i].pwm
                self.__motor_states[i].update(pwm_value)

                # Trigger callbacks
                self.__notify_state_change(i + 1, self.__motor_states[i])

                # Debug print (optional, comment out in production)
                print(f"Motor {i+1}: {old_pwm} → {int(pwm_value)} µs")

    def __handle_servo_output_raw(self, msg):
        """Process SERVO_OUTPUT_RAW message (legacy fallback)"""
        if msg.port != 0:  # Only process MAIN outputs (port 0)
            return

        # Map servo fields to motors
        servo_fields = [
            msg.servo1_raw, msg.servo2_raw, msg.servo3_raw,
            msg.servo4_raw, msg.servo5_raw, msg.servo6_raw
        ]

        for i in range(min(self.__num_motors, len(servo_fields))):
            pwm_value = servo_fields[i]

            # Only update if value changed
            if abs(self.__motor_states[i].pwm - pwm_value) > 1:
                self.__motor_states[i].update(pwm_value)
                self.__notify_state_change(i + 1, self.__motor_states[i])

    def __notify_state_change(self, _motor_num: int, _state: MotorState):
        """Notify all registered callbacks of _state change"""
        for callback in self.__state_callbacks:
            try:
                callback(_motor_num, _state)
            except Exception as e:
                print(f"Error in callback: {e}")

    # Public API methods

    def register_state_callback(self, callback: Callable[[int, MotorState], None]):
        """
        Register a callback to be called when motor _state changes

        Args:
            callback: Function that takes (_motor_num: int, _state: MotorState)
        """
        print("registered pwm callback")
        self.__state_callbacks.append(callback)

    def get_motor_state(self, _motor_num: int) -> Optional[MotorState]:
        """
        Get current _state of a specific motor

        Args:
            _motor_num: Motor number (1-6)

        Returns:
            MotorState or None if invalid motor number
        """
        if 1 <= _motor_num <= self.__num_motors:
            return self.__motor_states[_motor_num - 1]
        return None

    def get_all_motor_states(self) -> Dict[str, MotorState]:
        """
        Get states of all motors

        Returns:
            Dict mapping motor number (1-6) to MotorState
        """
        return {
            MOTOR_STR(i + 1): _state
            for i, _state in enumerate(self.__motor_states)
        }

    def get_motor_pwm(self, _motor_num: int) -> Optional[int]:
        """Get current PWM value for a motor"""
        _state = self.get_motor_state(_motor_num)
        return _state.pwm if _state else None

    def is_motor_active(self, _motor_num: int) -> bool:
        """Check if motor is currently active"""
        _state = self.get_motor_state(_motor_num)
        return _state.active if _state else False

    def set_motor_pwm(self, _motor_num: int, pwm_value: int):
        """
        Send command to set motor PWM

        Args:
            _motor_num: Motor number (1-MAX)
            pwm_value: PWM in microseconds (MIN_PWM-MAX_PWM)
        """

        # if not (MIN_PWM <= pwm_value <= MAX_PWM):
        #     raise ValueError(f"Invalid PWM value: {pwm_value}. Must be between {MIN_PWM} and {MAX_PWM}.")

        if not self.__connection.master:
            raise RuntimeError("Not connected")

        if not (1 <= _motor_num <= self.__num_motors):
            raise ValueError(f"Invalid motor number: {_motor_num}")

        self.__connection.master.set_servo(_motor_num, pwm_value)

        # message = self.__master.mav.command_long_encode(
        #     self.__master.target_system,  # Target system (usually 1)
        #     self.__master.target_component,  # Target component (usually 1)
        #     mavutil.mavlink.MAV_CMD_DO_SET_SERVO,  # The command ID
        #     1,  # Confirmation
        #     _motor_num,  # param1: Servo number
        #     pwm_value,  # param2: PWM value in microseconds
        #     0, 0, 0, 0, 0  # param3-7: Not used
        # )
        #
        # self.__master.mav.send(message)

    def set_all_motors_pwm(self, pwm_value: int):
        """Set all motors to the same PWM value"""
        for _motor_num in range(1, self.__num_motors + 1):
            self.set_motor_pwm(_motor_num, pwm_value)

    def stop_all_motors(self):
        """Emergency stop - set all motors to minimum PWM"""
        self.set_all_motors_pwm(MIN_PWM)


# Usage example
async def main():
    connection = MavlinkConnection(addr="/dev/cu.usbserial-0001", baudrate=57600)

    # Create MAVLink instance
    mav = PWMConnection(connection=connection, num_motors=6)

    # Connect
    if not connection.connect():
        print("Failed to connect!")
        return

    try:
        # Start monitoring
        await connection.start_monitoring()

        print("Monitoring motor PWMs... (Press Ctrl+C to stop)\n")

        # Continuously print motor PWMs
        while True:
            # print("trying to get state...")
            states = mav.get_all_motor_states()

            # Format: Motor 1: 1000µs | Motor 2: 1000µs | ...
            pwm_line = " | ".join([
                f"M{motor_num}: {state.pwm}µs"
                for motor_num, state in states.items()
            ])
            print("\033[2J\033[H", end='')
            print(f"\n{pwm_line}", end='', flush=True)

            await asyncio.sleep(0.1)  # Update every 100ms

    except KeyboardInterrupt:
        print("\n\nInterrupted!")

    finally:
        # Cleanup
        print("Shutting down...")
        await connection.stop_monitoring()
        connection.disconnect()


async def main2():
    connection = MavlinkConnection(addr="udpin:10.106.216.178:14550", baudrate=115200)

    # Create MAVLink instance
    mav = PWMConnection(connection=connection, num_motors=6)

    # Define callback for _state changes
    def on_motor_state_change(_motor_num: int, _state: MotorState):
        print(f"Motor {_motor_num}: {_state.pwm} µs ({'ACTIVE' if _state.active else 'IDLE'})")

    # Register callback
    mav.register_state_callback(on_motor_state_change)

    # Connect
    if not connection.connect():
        print("Failed to connect!")
        return

    try:
        # Start monitoring
        await connection.start_monitoring()

        # Let it run for a bit to see initial states
        await asyncio.sleep(2)

        # Print all motor states
        print("\n=== Current Motor States ===")
        states = mav.get_all_motor_states()

        for _motor_num, _state in states.items():
            print(f"Motor {_motor_num}: {_state.pwm} µs (Active: {_state.active})")

        # Example: Ramp up motor 1
        print("\n=== Ramping up Motor 1 ===")
        for pwm in range(MIN_PWM, 1300, 50):
            print("stepping into ", pwm)
            mav.set_motor_pwm(1, pwm)
            # mav.set_motor_pwm(4, pwm)
            await asyncio.sleep(5)

        # Stop motor
        print("\n=== Stopping Motor 1 ===")
        mav.set_motor_pwm(1, MIN_PWM)
        # mav.set_motor_pwm(4, MIN_PWM)

        # Keep monitoring for a bit
        await asyncio.sleep(2)

    except KeyboardInterrupt:
        print("\nInterrupted!")

    finally:
        # Cleanup
        print("\n=== Shutting down ===")
        mav.stop_all_motors()
        await connection.stop_monitoring()
        connection.disconnect()

if __name__ == "__main__":
    asyncio.run(main())