from typing import Optional, List, Callable, Tuple

from tkinter import Tk, IntVar, StringVar, Label, Button, Entry, Checkbutton, messagebox

from gui.config import GUIConfig, TestParameters
from gui.plot_manager import PlotManager

class DEPSInterface(Tk):
    def __init__(self, config: Optional[GUIConfig] = None):
        super().__init__()

        self.__config = config or GUIConfig()

        # Window configuration
        self.title(self.__config.window_title)
        self.configure(bg=self.__config.bg_color)
        self.resizable(True, True)
        self.attributes('-fullscreen', self.__config.fullscreen)
        self.bind('<Escape>', self.__exit_fullscreen)

        # State variables
        self.__motor_checkboxes: List[IntVar] = [IntVar() for _ in range(self.__config.max_motors)]
        self.__all_motors_checkbox: IntVar = IntVar()

        # Input variables
        self.__thrust_input: StringVar = StringVar()
        self.__time_input: StringVar = StringVar()
        self.__pwm_input: StringVar = StringVar()

        # Output variables
        self.__voltage_output: StringVar = StringVar(value="0.0 V")
        self.__current_output: StringVar = StringVar(value="0.0 A")
        self.__power_output: StringVar = StringVar(value="0.0 W")
        self.__time_elapsed_output: StringVar = StringVar(value="00:00")
        self.__pwm_output: List[int] = list(0 for _ in range(self.__config.max_motors))

        # Timer state
        self.__is_running: bool = False
        self.__target_time_s: int = 0
        self.__current_time_s: int = 0
        self.__timer_id: Optional[str] = None
        self.__plot_update_id: Optional[str] = None

        # Callbacks
        self.__on_start_callback: Optional[Callable[[], None]] = None
        self.__on_stop_callback: Optional[Callable[[], None]] = None
        self.__on_tare_callback: Optional[Callable[[], None]] = None

        # Components
        self.__plot_manager = PlotManager(self, self.__config)

        # Build UI
        self.__create_widgets()

    def __create_widgets(self):
        """Create all GUI widgets"""
        # Title
        Label(
            self,
            text="DEPS Interface",
            font=("Helvetica", 24, "bold"),
            bg=self.__config.bg_color,
            fg=self.__config.fg_color,
            padx=20,
            pady=10
        ).place(relx=0.15, rely=0.01, anchor='nw')

        # Motor Selection
        Label(
            self,
            text="Motor Selection",
            font=("Verdana", 15, "bold"),
            bg=self.__config.bg_color,
            fg=self.__config.fg_color,
            padx=10,
            pady=10
        ).place(relx=0.01, rely=0.10, anchor='nw')

        # All motors checkboxes
        Checkbutton(
            self,
            text="ALL",
            variable=self.__all_motors_checkbox,
            onvalue=1,
            offvalue=0,
            bg=self.__config.bg_color,
            fg=self.__config.fg_color,
            font=("Verdana", 12),
            command=self.__on_all_motors_changed
        ).place(relx=0.05, rely=0.20, anchor='nw')

        # Individual motor checkboxes
        for i in range(self.__config.max_motors):
            Checkbutton(
                self,
                text=f"Motor {i + 1}",
                variable=self.__motor_checkboxes[i],
                onvalue=1,
                offvalue=0,
                bg=self.__config.bg_color,
                fg=self.__config.fg_color,
                font=("Verdana", 12)
            ).place(relx=0.05, rely=0.23 + (i * 0.03), anchor='nw')

        # Input labels
        labels = [
            ("Thrust (g)", 0.01, 0.43),
            ("Time (s)", 0.12, 0.43),
            ("PWM Max", 0.23, 0.43),
            ("Volt", 0.01, 0.54),
            ("Amp", 0.12, 0.54),
            ("Power", 0.23, 0.54),
            ("Time Elapsed", 0.01, 0.65)
        ]

        for text, x, y in labels:
            Label(
                self,
                text=text,
                font=("Verdana", 15),
                bg=self.__config.bg_color,
                fg=self.__config.fg_color,
                padx=10,
                pady=10
            ).place(relx=x, rely=y, anchor='nw')

        # Input entries
        Entry(
            self,
            textvariable=self.__thrust_input,
            font=("Arial", 16),
            width=6,
            bg="white",
            fg="black"
        ).place(relx=0.02, rely=0.49, anchor='nw')

        Entry(
            self,
            textvariable=self.__time_input,
            font=("Arial", 16),
            width=6,
            bg="white",
            fg="black"
        ).place(relx=0.13, rely=0.49, anchor='nw')

        Entry(
            self,
            textvariable=self.__pwm_input,
            font=("Arial", 16),
            width=6,
            bg="white",
            fg="black"
        ).place(relx=0.24, rely=0.49, anchor='nw')

        # Output displays
        Label(
            self,
            textvariable=self.__voltage_output,
            font=("Arial", 16, "bold"),
            width=8,
            bg="white",
            fg="green",
            anchor='center'
        ).place(relx=0.02, rely=0.6, anchor='nw')

        Label(
            self,
            textvariable=self.__current_output,
            font=("Arial", 16, "bold"),
            width=8,
            bg="white",
            fg="green",
            anchor='center'
        ).place(relx=0.13, rely=0.6, anchor='nw')

        Label(
            self,
            textvariable=self.__power_output,
            font=("Arial", 16, "bold"),
            width=8,
            bg="white",
            fg="green",
            anchor='center'
        ).place(relx=0.24, rely=0.6, anchor='nw')

        Label(
            self,
            textvariable=self.__time_elapsed_output,
            font=("Arial", 16, "bold"),
            width=10,
            bg="white",
            fg="green",
            anchor='center'
        ).place(relx=0.02, rely=0.72, anchor='nw')

        # Buttons
        Button(
            self,
            text="START",
            command=self.__handle_start,
            font=("Verdana", 16),
            highlightbackground="green",
            fg="green",
            padx=20,
            pady=10,
            width=4,
            height=1
        ).place(relx=0.07, rely=0.9, anchor='center')

        Button(
            self,
            text="STOP",
            command=self.__handle_stop,
            font=("Verdana", 16),
            highlightbackground="red",
            fg="red",
            padx=20,
            pady=10,
            width=4,
            height=1
        ).place(relx=0.25, rely=0.9, anchor='center')

        Button(
            self,
            text="Tare",
            command=self.__handle_tare,
            font=("Verdana", 16),
            highlightbackground="grey",
            fg="black",
            padx=20,
            pady=2,
            width=4,
            height=1
        ).place(relx=0.2, rely=0.68, anchor='nw')

        Button(
            self,
            text="Reset",
            command=self.__handle_reset,
            font=("Verdana", 16),
            highlightbackground="grey",
            fg="black",
            padx=20,
            pady=3,
            width=4,
            height=1
        ).place(relx=0.2, rely=0.75, anchor='nw')

    def __validate_and_get_parameters(self) -> Optional[TestParameters]:
        """Validate user inputs and return test parameters"""
        try:
            thrust = float(self.__thrust_input.get())
            time = int(self.__time_input.get())
            pwm = int(self.__pwm_input.get())

            if time <= 0:
                raise ValueError("Time must be positive.")
            if pwm <= 0:
                raise ValueError("PWM must be positive.")

            selected = [i + 1 for i, var in enumerate(self.__motor_checkboxes) if var.get() == 1]
            if not selected:
                messagebox.showerror("Input Error", "Please select at least one motor.")
                return None

            return TestParameters(
                target_thrust=thrust,
                test_duration=time,
                max_pwm=pwm,
                selected_motors=selected
            )

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input: {e}")
            return None

    def __exit_fullscreen(self, event=None):
        """Exit fullscreen mode"""
        self.attributes('-fullscreen', False)

    def __on_all_motors_changed(self):
        """Handle ALL motors checkbox toggle"""
        if self.__all_motors_checkbox.get() == 1:
            for checkbox in self.__motor_checkboxes:
                checkbox.set(1)

    def __handle_start(self):
        """Handle START button press"""
        # Validate inputs
        params = self.__validate_and_get_parameters()
        if not params:
            return

        # Confirm with user
        response = messagebox.askyesno("Confirmation", "Are you sure you want to start the test?")
        if not response:
            return

        # Start test
        self.__target_time_s = params.test_duration
        self.__current_time_s = 0
        self.__is_running = True

        # Clear plots
        self.__plot_manager.clear()

        # Start timers
        self.__start_countdown_timer()
        self.__start_plot_updates()

        # Notify callback
        if self.__on_start_callback:
            self.__on_start_callback()

    def __handle_stop(self):
        """Handle STOP button press"""
        self.__stop_test(interrupted=True)

        # Notify callback
        if self.__on_stop_callback:
            self.__on_stop_callback()

    def __handle_tare(self):
        """Handle Tare button press"""
        if self.__on_tare_callback:
            self.__on_tare_callback()
            messagebox.showinfo("Tare", "Load cells tared successfully!")

    def __handle_reset(self):
        """Handle Reset button press"""
        if self.__is_running:
            messagebox.showwarning("Test Running", "Cannot reset while test is running. Press STOP first.")
            return

        self.__current_time_s = 0
        self.__time_elapsed_output.set("00:00")
        self.__plot_manager.clear()
        messagebox.showinfo("Reset", "Time elapsed and plot data have been reset.")

    def __start_countdown_timer(self):
        """Start the countdown timer"""
        self.__countdown_timer()

    def __countdown_timer(self):
        """Update countdown timer"""
        if not self.__is_running:
            return

        self.__current_time_s += 1
        minutes = self.__current_time_s // 60
        seconds = self.__current_time_s % 60
        self.__time_elapsed_output.set(f"{minutes:02d}:{seconds:02d}")

        # Check if target time reached
        if 0 < self.__target_time_s <= self.__current_time_s:
            self.__stop_test(interrupted=False)
            return

        self.__timer_id = self.after(self.__config.timer_update_interval_ms, self.__countdown_timer)

    def __start_plot_updates(self):
        """Start plot update loop"""
        self.__update_plots()

    def __update_plots(self):
        """Update plots with new data"""
        if not self.__is_running:
            return

        # # Get data from the provider
        # if self.__data_provider:
        #     power, voltage, current, motor_pwms = self.__data_provider()
        # else:
        #     power, voltage, current, motor_pwms = 0.0, 0.0, 0.0, tuple(0.0 for _ in range(self.__config.max_motors))
        #
        # # Update displays
        # self.update_power(power)
        # self.update_voltage(voltage)
        # self.update_current(current)

        # Get visible motors
        visible_motors = [i + 1 for i, var in enumerate(self.__motor_checkboxes) if var.get() == 1]

        # Update plots
        self.__plot_manager.update(self.__get_power(), self.__pwm_output, visible_motors)

        # Schedule next update
        self.__plot_update_id = self.after(self.__config.plot_update_interval_ms, self.__update_plots)

    def __stop_test(self, interrupted: bool):
        """Stop the test"""
        self.__is_running = False

        # Cancel timers
        if self.__timer_id:
            self.after_cancel(self.__timer_id)
            self.__timer_id = None

        if self.__plot_update_id:
            self.after_cancel(self.__plot_update_id)
            self.__plot_update_id = None

        # Show message
        if interrupted:
            messagebox.showinfo("Test Interrupted", "The test was stopped by user.")
        else:
            messagebox.showinfo("Test Complete", "The test completed successfully!")

    def __get_power(self) -> float:
        power_str: str = self.__power_output.get()
        return float(power_str.replace(" W", "").strip())

    # Public API

    def register_start_callback(self, callback: Callable[[], None]):
        """Register callback for START button"""
        self.__on_start_callback = callback

    def register_stop_callback(self, callback: Callable[[], None]):
        """Register callback for the STOP button"""
        self.__on_stop_callback = callback

    def register_tare_callback(self, callback: Callable[[], None]):
        """Register callback for the Tare button"""
        self.__on_tare_callback = callback

    def update_voltage(self, voltage: float):
        """Update voltage display"""
        self.__voltage_output.set(f"{voltage:.1f} V")

    def update_current(self, current: float):
        """Update current display"""
        self.__current_output.set(f"{current:.2f} A")

    def update_power(self, power: float):
        """Update power display"""
        self.__power_output.set(f"{power:.1f} W")

    def update_pwm(self, motor_num: int, pwm: int):
        self.__pwm_output[motor_num - 1] = pwm

    def get_test_parameters(self) -> Optional[TestParameters]:
        """Get current test parameters from GUI inputs"""
        return self.__validate_and_get_parameters()

    def is_test_running(self) -> bool:
        """Check if the test is currently running"""
        return self.__is_running