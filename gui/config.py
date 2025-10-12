from typing import List
from dataclasses import dataclass

@dataclass
class GUIConfig:
    """Configuration for GUI appearance and behavior"""
    window_title: str = "DEPS Interface"
    bg_color: str = "black"
    fg_color: str = "white"
    fullscreen: bool = True
    plot_update_interval_ms: int = 500
    timer_update_interval_ms: int = 1000
    max_motors: int = 6

@dataclass
class TestParameters:
    """Parameters for a test run"""
    target_thrust: float = 0.0
    test_duration: int = 0
    max_pwm: int = 0
    selected_motors: List[int] = None

    def __post_init__(self):
        if self.selected_motors is None:
            self.selected_motors = []