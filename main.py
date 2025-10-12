import asyncio

from config import Config, MIN_PWM, MAX_PWM
from gui import DEPSInterface, GUIConfig
from controller import DEPSController, async_tk_mainloop


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
        mavlink_addr='udpin:10.106.216.178:14550',
        mavlink_baudrate=115200,
        mavlink_read_frequency=1_000_000,
        arduino_port='/dev/cu.usbmodem11301',
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