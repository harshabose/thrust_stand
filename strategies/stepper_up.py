import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from config import PWMConnection, LoadConnection, Config, LoadCellReading, MOTOR_STR, MIN_PWM, MAX_PWM, THRUST_THRESHOLD
from csv import writer as csv_writer


@dataclass
class StepperState:
    """Current state of the stepper algorithm"""
    total_target_thrust: float
    selected_motors: List[int]
    max_pwm_value: int          #microseconds
    min_pwm_value: int          #microseconds
    pwm_step: int               #microseconds
    run_for: int                #seconds
    pwm_write_frequency: int    #microseconds

    mixin_pwm_step:int = 50
    mixin_thrust_percent:int = 80
    total_current_thrust: float = 0
    total_adjustment_count: int = 0
    running: bool = False

    test_start_time: Optional[datetime] = None
    last_adjustment_time: Optional[datetime] = None

    last_loads_read_timestamp: Optional[datetime] = None
    last_pwm_read_timestamp: Optional[datetime] = None

    print_status_interval: int = 5

@dataclass
class MotorTarget:
    """Individual motor thrust target and state"""
    motor_num: int
    target_thrust: float
    current_pwm: int
    last_adjustment_time: Optional[datetime] = None
    current_thrust: float = 0.0
    adjustments_count: int = 0

class StepperUp:
    def __init__(self, config: Config, pwm_connection: PWMConnection, load_connection: LoadConnection):
        self.__pwm_connection: PWMConnection = pwm_connection
        self.__load_connection: LoadConnection = load_connection
        self.__log_file: Optional[object] = None
        self.__csv_writer: Optional[csv_writer] = None

        self._current_state: StepperState = StepperState(
            total_target_thrust=config.target_thrust,
            selected_motors=config.selected_motors,
            max_pwm_value=config.max_pwm,
            min_pwm_value=config.min_pwm,
            mixin_pwm_step=config.mixin_pwm_step,
            mixin_thrust_percent=config.mixin_thrust_percent,
            pwm_step=config.pwm_step,
            run_for=config.run_for,
            pwm_write_frequency=config.pwm_write_frequency,
            print_status_interval=config.print_status_interval,
        )

        num_motors = len(config.selected_motors)
        thrust_per_motor = config.target_thrust / num_motors

        self.__motor_targets: Dict[str, MotorTarget] = {}
        for motor_num in config.selected_motors:
            print("creating motor target with ", MOTOR_STR(motor_num))
            self.__motor_targets[MOTOR_STR(motor_num)] = MotorTarget(
                motor_num=motor_num,
                target_thrust=thrust_per_motor,
                current_pwm=config.min_pwm,
            )

        if config.logfile_path:
            self.__log_file = config.logfile_path
        if config.csv_path:
            self.__csv_writer = csv_writer(config.csv_path)


    async def _update_thrust_readings(self):
        """Update current thrust readings from load cells"""

        readings: LoadCellReading = await self.__load_connection.get_current_readings()

        self._current_state.total_current_thrust = readings.total_thrust
        self._current_state.last_loads_read_timestamp = readings.timestamp

        individual_readings: Dict[str, int] = readings.thrust_readings

        for motor_str, thrust in individual_readings.items():
            if motor_str in self.__motor_targets:
                self.__motor_targets[motor_str].current_thrust = thrust

    def _update_pwm_readings(self):
        """Update current pwm readings from motors"""

        individual_readings = self.__pwm_connection.get_all_motor_states()
        self._current_state.last_pwm_read_timestamp = datetime.now()

        for motor_str, reading in individual_readings.items():
            if motor_str in self.__motor_targets:
                self.__motor_targets[motor_str].current_pwm = reading.pwm

    def _should_update_pwm(self, motor_target: MotorTarget) -> Tuple[bool, int]:
        """Determine if motor PWM should be increased"""

        # Check if below target
        error = motor_target.target_thrust - motor_target.current_thrust

        # Only increase if the error is significant (more than 5% of target)
        threshold = THRUST_THRESHOLD

        if error > threshold:
            # Calculate thrust percentage
            mixin_threshold = motor_target.target_thrust * (self._current_state.mixin_thrust_percent / 100.0)
            
            # Use mixin_pwm_step if below threshold, otherwise regular pwm_step
            if motor_target.current_thrust < mixin_threshold:
                step = self._current_state.mixin_pwm_step
            else:
                step = self._current_state.pwm_step
            
            # Check PWM limits
            if motor_target.current_pwm < self._current_state.max_pwm_value:
                return True, step

        return False, 0

    def _adjust_motor_pwm(self, motor_str: str, adjustment: int):
        """Increase PWM for a specific motor"""
        target = self.__motor_targets[motor_str]

        # Calculate new PWM
        new_pwm = target.current_pwm + adjustment

        # Enforce max limit
        if new_pwm > self._current_state.max_pwm_value:
            new_pwm = self._current_state.max_pwm_value
        elif new_pwm < self._current_state.min_pwm_value:
            new_pwm = self._current_state.min_pwm_value

        # Send command to flight controller
        try:
            self.__pwm_connection.set_motor_pwm(target.motor_num, new_pwm)
            target.adjustments_count += 1
            target.current_pwm = new_pwm
            target.last_adjustment_time = datetime.now()
            self._current_state.total_adjustment_count += 1

            print(f"{motor_str}: PWM {target.current_pwm - self._current_state.pwm_step} → {new_pwm} µs "
                  f"(Thrust: {target.current_thrust:.1f}/{target.target_thrust:.1f}g)")

        except Exception as e:
            print(f"Error adjusting motor {motor_str}: {e}")

    def _print_status(self):
        """Print current status"""
        elapsed = (datetime.now() - self._current_state.test_start_time).total_seconds() if self._current_state.test_start_time else 0

        print("\n" + "=" * 60)
        print(f"Elapsed: {elapsed:.1f}s / {self._current_state.run_for}s")
        print(f"Total Adjustments: {self._current_state.total_adjustment_count}")
        print("-" * 60)

        total_thrust_actual = 0
        total_thrust_target = 0

        for motor_num, motor_target in self.__motor_targets.items():
            error = motor_target.target_thrust - motor_target.current_thrust

            print(f"Motor {motor_num}: "
                  f"PWM={motor_target.current_pwm:4d}µs | "
                  f"Thrust={motor_target.current_thrust:6.1f}g/{motor_target.target_thrust:6.1f}g | "
                  f"Error={error:+6.1f}g | "
                  f"Adj={motor_target.adjustments_count}")

            total_thrust_actual += motor_target.current_thrust
            total_thrust_target += motor_target.target_thrust

        print("-" * 60)
        print(f"TOTAL: {total_thrust_actual:.1f}g / {total_thrust_target:.1f}g")
        print("=" * 60)

    async def run(self):
        """Main control loop"""
        self._current_state.running = True
        self._current_state.test_start_time = datetime.now()

        # Start logging
        # self.start_logging()

        # Write frequency in seconds
        write_interval = self._current_state.pwm_write_frequency / 1_000_000

        print("\n" + "=" * 60)
        print("STEPPER STRATEGY STARTED")
        print("=" * 60)
        print(f"Target total thrust: {self._current_state.total_target_thrust}g")
        print(f"Target per motor: {self._current_state.total_target_thrust / len(self._current_state.selected_motors):.1f}g")
        print(f"Selected motors: {self._current_state.selected_motors}")
        print(f"PWM step: {self._current_state.pwm_step}µs")
        print(f"PWM range: {self._current_state.min_pwm_value}-{self._current_state.max_pwm_value}µs")
        print(f"Write frequency: {write_interval * 1000:.1f}ms")
        print(f"Duration: {self._current_state.run_for}s")
        print("=" * 60 + "\n")

        # Initialize all motors to minimum PWM
        print("Initializing motors to minimum PWM...")
        for motor_str, motor_target in self.__motor_targets.items():
            self.__pwm_connection.set_motor_pwm(motor_target.motor_num, self._current_state.min_pwm_value)
        await asyncio.sleep(1)

        last_adjustment_time = datetime.now()
        last_status_print = datetime.now()

        try:
            while self._current_state.running:
                elapsed = (datetime.now() - self._current_state.test_start_time).total_seconds()

                # Check if test duration reached
                if elapsed >= self._current_state.run_for:
                    print("\nTest duration reached. Stopping...")
                    break

                # Update thrust readings from load cells
                await self._update_thrust_readings()

                # Update pwm readings from motors
                # self._update_pwm_readings()

                # Log current state
                # self.log_state()

                # Check if it's time to adjust PWM
                time_since_adjustment = (datetime.now() - last_adjustment_time).total_seconds()

                if time_since_adjustment >= write_interval:
                    # Check each motor and adjust if needed
                    for motor_num, target in self.__motor_targets.items():
                        should_update, adjustment = self._should_update_pwm(target)
                        if should_update:
                            self._adjust_motor_pwm(motor_num, adjustment)

                    last_adjustment_time = datetime.now()

                # Print status every 5 seconds
                if (datetime.now() - last_status_print).total_seconds() >= 5.0:
                    self._print_status()
                    last_status_print = datetime.now()

                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.05)

        except KeyboardInterrupt:
            print("\n\nTest interrupted by user!")

        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown"""
        print("\n" + "=" * 60)
        print("SHUTTING DOWN")
        print("=" * 60)

        # Print final status
        self._print_status()

        # Stop all motors
        print("\nStopping all motors...")
        for motor_str, motor_target in self.__motor_targets.items():
            self.__pwm_connection.set_motor_pwm(motor_target.motor_num, self._current_state.min_pwm_value)

        await asyncio.sleep(0.5)

        # Stop logging
        # self.stop_logging()

        # Print summary
        elapsed = (datetime.now() - self._current_state.test_start_time).total_seconds() if self._current_state.test_start_time else 0
        print(f"\nTest Summary:")
        print(f"  Duration: {elapsed:.1f}s")
        print(f"  Total PWM adjustments: {self._current_state.total_adjustment_count}")
        print(f"  Adjustments per motor:")
        for motor_str in sorted(self.__motor_targets.keys()):
            print(f"    {motor_str}: {self.__motor_targets[motor_str].adjustments_count}")

        print("\n" + "=" * 60)
        self._current_state.running = False


async def main():
    from mavlink import PWMConnection, MavlinkConnection
    from load import LoadConnection, AverageLoadConnection

    # Configuration
    config = Config(
        target_thrust=18000.0,  # 2kg total
        selected_motors=[1, 4, 6],  # Use motors 1,4
        pwm_step=2,  # 10µs per step
        max_pwm=MAX_PWM,
        min_pwm=MIN_PWM,
        run_for=2400,  # 60 seconds
        use_method="stepper",
        pwm_write_frequency=1_000_000,  # 500 milliseconds in microseconds
        mavlink_addr='/dev/cu.usbserial-0001',
        mavlink_baudrate=57600,
        mavlink_read_frequency=100_000,  # 100ms
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
        strategy = StepperUp(config, pwm, AverageLoadConnection(load, 10))
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