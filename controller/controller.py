import asyncio
from tkinter import Tk, TclError
from typing import Optional

from config import Config, MIN_PWM, MAX_PWM, MotorState, BatteryState
from mavlink import PWMConnection, PowerConnection, MavlinkConnection
from load import LoadConnection, AverageLoadConnection
from strategies import StepperUpDown
from gui import DEPSInterface, GUIConfig


class DEPSController:
    """Controller that bridges GUI and hardware backend"""

    def __init__(self, gui: DEPSInterface, config: Config):
        self.__gui = gui
        self.__config = config

        # Hardware connections
        self.__mavlink: Optional[MavlinkConnection] = None
        self.__pwm: Optional[PWMConnection] = None
        self.__power: Optional[PowerConnection] = None
        self.__load: Optional[LoadConnection] = None
        self.__avg_load: Optional[AverageLoadConnection] = None
        self.__strategy: Optional[StepperUpDown] = None

        # State
        self.__hardware_ready: bool = False
        self.__test_running: bool = False

        # Register GUI callbacks
        self.__gui.register_start_callback(self.__on_gui_start)
        self.__gui.register_stop_callback(self.__on_gui_stop)
        self.__gui.register_tare_callback(self.__on_gui_tare)

    async def initialize(self) -> bool:
        """Initialize all hardware connections"""
        try:
            print("Initializing hardware connections...")

            # Create MAVLink connection
            self.__mavlink = MavlinkConnection(
                addr=self.__config.mavlink_addr,
                baudrate=self.__config.mavlink_baudrate
            )

            # Initialize PWM
            self.__pwm = PWMConnection(
                connection=self.__mavlink,
                num_motors=6
            )
            self.__pwm.register_state_callback(self.__on_pwm_update)

            # Initialize Power
            self.__power = PowerConnection(connection=self.__mavlink)
            self.__power.register_state_callback(self.__on_power_update)

            # Initialize Load
            self.__load = LoadConnection(
                port=self.__config.arduino_port,
                baudrate=self.__config.arduino_baudrate
            )

            # Connect to MAVLink
            if not self.__mavlink.connect(read_frequency=self.__config.mavlink_read_frequency):
                print("Failed to connect to MAVLink")
                return False

            # Connect to load cells
            if not await self.__load.connect(read_frequency=self.__config.arduino_read_frequency):
                print("Failed to connect to load cells")
                return False

            print("Waiting for systems to stabilize...")
            await asyncio.sleep(3)

            # Tare load cells
            print("Taring load cells...")
            self.__load.tare()
            await asyncio.sleep(2)

            # Start monitoring
            await self.__mavlink.start_monitoring()
            asyncio.create_task(self.__load.start_monitoring(display_mode='continuous'))

            # Create the averaged load connection
            self.__avg_load = AverageLoadConnection(self.__load, 10)

            self.__hardware_ready = True
            print("Hardware initialized successfully!")
            return True

        except Exception as e:
            print(f"Hardware initialization failed: {e}")
            return False

    def __on_pwm_update(self, motor_num: int, state: MotorState):
        """Callback when motor PWM changes"""
        print("called __on_pwm_update")
        self.__gui.update_pwm(motor_num, state.pwm)

    def __on_power_update(self, state: BatteryState):
        """Callback when the battery state changes"""

        self.__gui.update_voltage(state.current_voltage)
        self.__gui.update_current(state.current_amp)
        self.__gui.update_power(state.power)

    def __on_gui_start(self):
        """Handle START button from GUI"""

        if not self.__hardware_ready:
            print("Hardware not ready!")
            return

        if self.__test_running:
            print("Test already running!")
            return

        # Get parameters from GUI
        params = self.__gui.get_test_parameters()
        if not params:
            return

        # Update hardware config with GUI values
        self.__config.target_thrust = params.target_thrust
        self.__config.selected_motors = params.selected_motors
        self.__config.max_pwm = min(params.max_pwm, MAX_PWM)
        self.__config.run_for = params.test_duration

        # Start test asynchronously
        asyncio.create_task(self.__run_test())

    async def __run_test(self):
        """Execute the test strategy"""
        try:
            self.__test_running = True
            print("Starting test strategy...")

            # Create strategy
            self.__strategy = StepperUpDown(
                self.__config,
                self.__pwm,
                self.__avg_load
            )

            # Run strategy
            await self.__strategy.run()

        except Exception as e:
            print(f"Test error: {e}")

        finally:
            self.__test_running = False
            self.__stop_motors()
            print("Test completed")

    def __on_gui_stop(self):
        """Handle STOP button from GUI"""
        self.__stop_motors()
        self.__test_running = False

    def __on_gui_tare(self):
        """Handle Tare button from GUI"""
        if self.__load:
            self.__load.tare()

    def __stop_motors(self):
        """Emergency stop all motors"""
        if self.__pwm:
            self.__pwm.stop_all_motors()

    async def cleanup(self):
        """Clean up all resources"""
        print("Cleaning up...")

        self.__stop_motors()

        if self.__mavlink:
            await self.__mavlink.stop_monitoring()
            self.__mavlink.disconnect()

        if self.__load:
            self.__load.stop_monitoring()
            self.__load.disconnect()

        print("Cleanup complete")

    def is_hardware_ready(self) -> bool:
        """Check if hardware is initialized"""
        return self.__hardware_ready

    def is_test_running(self) -> bool:
        """Check if test is running"""
        return self.__test_running


async def async_tk_mainloop(root: Tk):
    """Run Tkinter event loop asynchronously"""
    while True:
        try:
            # Process Tkinter events
            root.update()

            # Small delay to prevent CPU spinning
            await asyncio.sleep(0.01)  # 100Hz update rate

        except TclError:
            # The window was closed
            break
        except Exception as e:
            print(f"GUI loop error: {e}")
            break


async def main():
    """Main entry point"""
    # Hardware configuration
    hardware_config = Config(
        target_thrust=18000.0,
        selected_motors=[1, 4, 6],
        pwm_step=2,
        max_pwm=MAX_PWM,
        min_pwm=MIN_PWM,
        run_for=2400,
        use_method="stepper",
        pwm_write_frequency=1_000_000,
        mavlink_addr='/dev/cu.usbserial-0001',
        mavlink_baudrate=57600,
        mavlink_read_frequency=100_000,
        arduino_port='/dev/cu.usbmodem1301',
        arduino_baudrate=9600,
        arduino_read_frequency=100_000,
        csv_path="",
        logfile_path="",
        print_status_interval=1
    )

    # Create GUI
    gui_config = GUIConfig(
        window_title="DEPS Interface",
        fullscreen=True,
        max_motors=6
    )
    gui = DEPSInterface(config=gui_config)

    # Create controller
    controller = DEPSController(gui, hardware_config)

    try:
        # Initialize hardware in the background
        init_task = asyncio.create_task(controller.initialize())

        # Run GUI loop while hardware initializes
        # This allows the GUI to be responsive during initialization
        await asyncio.sleep(2)

        # Wait for hardware to be ready
        await init_task

        if not controller.is_hardware_ready():
            print("Failed to initialize hardware!")
            gui.destroy()
            return

        print("System ready. GUI is now active.")

        # Run GUI mainloop
        await async_tk_mainloop(gui)

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    finally:
        # Cleanup
        await controller.cleanup()

        # Destroy GUI if still exists
        try:
            gui.destroy()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())