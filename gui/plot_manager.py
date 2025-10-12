from typing import List, Tuple

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from tkinter import Tk, NW

from gui.config import GUIConfig

class PlotManager:
    """Manages matplotlib plots embedded in tkinter"""
    def __init__(self, master: Tk, config: GUIConfig):
        self.__master = master
        self.__config = config

        # Plot data storage
        self.__time_data: List[float] = []
        self.__power_data: List[float] = []
        self.__motor_pwm_data: List[List[int]] = [[] for _ in range(config.max_motors)]

        # Create figures
        self.__power_fig: Figure
        self.__power_ax: Axes
        self.__pwm_fig: Figure
        self.__pwm_ax: Axes

        self.__create_plots()

    def __create_plots(self):
        """Initialize matplotlib figures and axes"""
        # Power plot
        self.__power_fig, self.__power_ax = plt.subplots(figsize=(4, 1.4))
        self.__configure_plot(
            self.__power_fig,
            self.__power_ax,
            "Time (s)",
            "Power (W)",
            "Power vs Time"
        )
        self.__power_line, = self.__power_ax.plot(
            [], [],
            color='lime',
            marker='o',
            markersize=0.75,
            linewidth=0.75
        )
        self.__power_ax.set_ylim(0, 500)

        # PWM plot
        self.__pwm_fig, self.__pwm_ax = plt.subplots(figsize=(4, 1.4))
        self.__configure_plot(
            self.__pwm_fig,
            self.__pwm_ax,
            "Time (s)",
            "PWM",
            "PWM vs Time"
        )

        # Create lines for each motor
        colors = ['red', 'white', 'grey', 'blue', 'pink', 'orange']
        self.__pwm_lines = []
        for i in range(self.__config.max_motors):
            line, = self.__pwm_ax.plot(
                [], [],
                color=colors[i],
                marker='o',
                markersize=0.5,
                linewidth=0.5,
                label=f'M{i + 1}'
            )
            self.__pwm_lines.append(line)

        self.__pwm_ax.set_ylim(0, 2000)
        self.__pwm_ax.legend(
            loc='upper left',
            fontsize=4,
            facecolor='black',
            edgecolor='black',
            labelcolor='white'
        )

        # Embed in tkinter
        self.__power_canvas = FigureCanvasTkAgg(self.__power_fig, master=self.__master)
        self.__power_canvas_widget = self.__power_canvas.get_tk_widget()
        self.__power_canvas_widget.place(relx=0.380, rely=0.01, width=800, height=400, anchor=NW)

        self.__pwm_canvas = FigureCanvasTkAgg(self.__pwm_fig, master=self.__master)
        self.__pwm_canvas_widget = self.__pwm_canvas.get_tk_widget()
        self.__pwm_canvas_widget.place(relx=0.380, rely=0.5, width=800, height=400, anchor=NW)

    def update(self, power: float, motor_pwms: List[int], visible_motors: List[int]):
        """Update plots with new data"""
        # Calculate time increment
        current_time = self.__time_data[-1] + 0.5 if self.__time_data else 0.0

        # Append new data
        self.__time_data.append(current_time)
        self.__power_data.append(power)

        for i, pwm in enumerate(motor_pwms):
            if i < len(self.__motor_pwm_data):
                self.__motor_pwm_data[i].append(pwm)

        # Update power plot
        self.__power_line.set_data(self.__time_data, self.__power_data)
        self.__power_ax.set_xlim(self.__time_data[0], self.__time_data[-1] if self.__time_data else 10)
        self.__power_ax.relim()
        self.__power_ax.autoscale_view(True, True, True)

        max_power = max(self.__power_data) if self.__power_data else 0
        self.__power_ax.set_title(f"Power vs Time (Max: {max_power:.1f} W)", color='white', fontsize=5)

        # Update PWM plot
        for i, line in enumerate(self.__pwm_lines):
            if (i + 1) in visible_motors:
                line.set_data(self.__time_data, self.__motor_pwm_data[i])
            else:
                line.set_data([], [])

        self.__pwm_ax.set_xlim(self.__time_data[0], self.__time_data[-1] if self.__time_data else 10)
        self.__pwm_ax.relim()
        self.__pwm_ax.autoscale_view(True, True, True)

        # Update PWM title with max values
        max_values = [f"M{i + 1}: {max(data):.0f}" if data else f"M{i + 1}: 0"
                      for i, data in enumerate(self.__motor_pwm_data)]
        self.__pwm_ax.set_title(", ".join(max_values), color='white', fontsize=5)

        # Redraw
        self.__power_canvas.draw_idle()
        self.__pwm_canvas.draw_idle()

    def __configure_plot(self, fig: Figure, ax: Axes, x_label: str, y_label: str, title: str):
        """Configure plot appearance"""
        fig.tight_layout(pad=0.3)
        fig.set_facecolor('black')
        ax.set_facecolor('black')
        ax.tick_params(axis='x', colors='white', labelsize=5)
        ax.tick_params(axis='y', colors='white', labelsize=5)
        ax.spines['left'].set_color('white')
        ax.spines['bottom'].set_color('white')
        ax.spines['right'].set_color('black')
        ax.spines['top'].set_color('black')
        ax.set_xlabel(x_label, color='white', fontsize=5)
        ax.set_ylabel(y_label, color='white', fontsize=5)
        ax.set_title(title, color='white', fontsize=5)

    def clear(self):
        """Clear all plot data"""
        self.__time_data.clear()
        self.__power_data.clear()
        for data in self.__motor_pwm_data:
            data.clear()