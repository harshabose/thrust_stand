from typing import Protocol, Optional, Dict, Callable, Any, Coroutine
from datetime import datetime
from dataclasses import dataclass

@dataclass
class Config:
    target_thrust: float
    selected_motors: list[int]  # Changed to list for multiple motor selection
    max_pwm: int
    min_pwm: int
    pwm_step: int
    mixin_pwm_step: int
    mixin_thrust_percent: int

    run_for: int  # seconds
    use_method: str
    pwm_write_frequency: int  # microseconds

    mavlink_addr: str
    mavlink_baudrate: int
    mavlink_read_frequency: int

    arduino_port: str
    arduino_baudrate: int
    arduino_read_frequency: int

    logfile_path: str
    csv_path: str
    print_status_interval: int #seconds

@dataclass
class LoadCellReading:
    thrust_readings: Dict[str, int]
    total_thrust: int
    timestamp: datetime

def MOTOR_STR(motor_num: int) -> str:
    """Represents motor number to string (e.g., 1 -> 'MOTOR-1')"""
    return f'MOTOR-{motor_num}'

def MOTOR_NUM(motor_str: str) -> int:
    """Extract motor number from motor string (e.g., 'MOTOR-1' -> 1)"""
    return int(motor_str.split('-')[1])

MIN_PWM: int = 1100
MAX_PWM: int = 1800
THRUST_THRESHOLD: int = 30

@dataclass
class MotorState:
    """State of a single motor"""
    pwm: int = 0  # Current PWM value
    active: bool = False  # Is motor active?
    last_update: Optional[datetime] = None

    def update(self, pwm_value: int):
        """Update motor _state"""
        self.pwm = int(pwm_value)
        self.active = pwm_value > 1000  # Consider active if above minimum
        self.last_update = datetime.now()

@dataclass
class BatteryState:
    current_voltage: float = 0.0
    current_amp: float = 0.0
    power: float = 0.0

    last_update: Optional[datetime] = None

    def update(self, voltage: float, amp: float):
        self.current_voltage = voltage
        self.current_amp = amp
        self.power = voltage * amp
        self.last_update = datetime.now()

class PWMConnection(Protocol):
    def get_motor_state(self, _motor_num: int) -> Optional[MotorState]: ...
    def get_all_motor_states(self) -> Dict[str, MotorState]: ...
    def set_motor_pwm(self, _motor_num: int, pwm_value: int) -> None: ...
    def set_all_motors_pwm(self, pwm_value: int) -> None: ...
    def stop_all_motors(self) -> None: ...


class LoadConnection(Protocol):
    async def get_current_readings(self) -> LoadCellReading: ...
    def tare(self) -> bool: ...
    def register_state_callback(self, callback: Callable[[LoadCellReading], Coroutine[Any, Any, None]]) -> None:
        ...