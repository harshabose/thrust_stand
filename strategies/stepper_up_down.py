from config import Config, MIN_PWM, MAX_PWM, THRUST_THRESHOLD
from strategies import StepperUp, MotorTarget
from math import fabs
from typing import Tuple
import asyncio

class StepperUpDown(StepperUp):
    def _should_update_pwm(self, motor_target: MotorTarget) -> Tuple[bool, int]:
        # Check error from required
        error = motor_target.target_thrust - motor_target.current_thrust

        # Only update if the error is significant (more than 1% of target)
        threshold = THRUST_THRESHOLD

        if fabs(error) > threshold:
            if error > 0 and motor_target.current_pwm < self._current_state.max_pwm_value:
                return True, self._current_state.pwm_step
            elif error < 0 and motor_target.current_pwm > self._current_state.min_pwm_value:
                return True, -self._current_state.pwm_step

        return False, 0


async def main():
    from mavlink import PWMConnection, MavlinkConnection, PowerConnection
    from load import LoadConnection, AverageLoadConnection

    # Configuration
    config = Config(
        target_thrust=36_000.0,  # 2kg total
        selected_motors=[1, 2, 3, 4, 5, 6],  # Use motors 1,4
        pwm_step=2,  # 10µs per step
        max_pwm=MAX_PWM,
        min_pwm=MIN_PWM,
        run_for=600,  # 60 seconds
        use_method="stepper",
        pwm_write_frequency=1_000_000,  # 500 milliseconds in microseconds
        mavlink_addr='/dev/cu.usbserial-0001',
        mavlink_baudrate=57600,
        mavlink_read_frequency=1_000_000,  # 100ms
        arduino_port='/dev/cu.usbmodem1301',
        arduino_baudrate=9600,
        arduino_read_frequency=100_000,  # 500ms
        csv_path="",
        logfile_path="",
        print_status_interval=1
    )

    mavlink = MavlinkConnection(
        addr=config.mavlink_addr,
        baudrate=config.mavlink_baudrate,
    )

    # Initialize connections
    pwm = PWMConnection(
        connection=mavlink,
        num_motors=6,
        read_frequency=config.mavlink_read_frequency,
    )

    power = PowerConnection(
        connection=mavlink
    )

    load = LoadConnection(
        port=config.arduino_port,
        baudrate=config.arduino_baudrate,
    )

    # Connect
    if not mavlink.connect(read_frequency=config.mavlink_read_frequency):
        print("Failed to connect to MAVLink!")
        return

    if not await load.connect(read_frequency=config.arduino_read_frequency):
        print("Failed to connect to load monitor!")
        return

    print("sleeping for 5 seconds...")
    await asyncio.sleep(5)
    try:
        # Tare load cells
        print("Taring load cells...")
        load.tare()
        await asyncio.sleep(2)

        # Start monitoring
        await mavlink.start_monitoring()
        asyncio.create_task(load.start_monitoring(display_mode='continuous'))

        # Create and run the strategy
        strategy = StepperUpDown(config, pwm, AverageLoadConnection(load, 10))
        await strategy.run()
    finally:
        # Cleanup
        await mavlink.stop_monitoring()
        pwm.stop_all_motors()
        mavlink.disconnect()

        load.stop_monitoring()
        load.disconnect()

if __name__ == "__main__":
    asyncio.run(main())