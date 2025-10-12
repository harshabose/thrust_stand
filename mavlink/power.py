from typing import List, Callable, Optional

from config import BatteryState
from mavlink.mavlink import MavlinkConnection

MAV_MSG_ID_BATTERY_STATUS: int = 147
MAV_MSG_ID_BATTERY_STATUS_STR: str = 'BATTERY_STATUS'

class PowerConnection:
    def __init__(self, connection: MavlinkConnection):
        self.__connection: MavlinkConnection = connection

        # Callbacks for _state changes
        self.__state: BatteryState = BatteryState()
        self.__state_callbacks: List[Callable[[BatteryState], None]] = []

        self.__connection.request_data_stream(MAV_MSG_ID_BATTERY_STATUS)
        self.__connection.register_message_handler(
            MAV_MSG_ID_BATTERY_STATUS_STR, self.__handle_battery_status
        )

    def __handle_battery_status(self, msg):
        """Process BATTERY_STATUS message"""

        # Extract voltage from cells array
        # voltages[0] contains the overall battery voltage in millivolts
        # or individual cell voltage if cells are measured separately
        if msg.voltages is None or len(msg.voltages) == 0:
            voltage_mv = 0
        else:
            voltage_mv = msg.voltages[0] if msg.voltages[0] != 65535 else 0
        voltage_v = voltage_mv / 1000.0  # Convert mV to V

        # Extract current in centiamps (cA), convert to amps
        # -1 indicates autopilot does not measure current
        current_ca = msg.current_battery if msg.current_battery != -1 else 0
        current_a = current_ca / 100.0  # Convert cA to A

        # Only update if values changed significantly (0.01V or 0.01A threshold)
        if (abs(self.__state.current_voltage - voltage_v) > 0.01 or
                abs(self.__state.current_amp - current_a) > 0.01):
            old_voltage = self.__state.current_voltage
            old_current = self.__state.current_amp

            # Update state
            self.__state.update(voltage_v, current_a)

            # Trigger callbacks
            self._notify_state_change(self.__state)

            # Debug print (optional, comment out in production)
            print(f"Battery: {old_voltage:.2f}V → {voltage_v:.2f}V, "
                  f"{old_current:.2f}A → {current_a:.2f}A, "
                  f"Power: {self.__state.power:.2f}W")


    def _notify_state_change(self, _state: BatteryState):
        """Notify all registered callbacks of _state change"""
        for callback in self.__state_callbacks:
            try:
                callback(_state)
            except Exception as e:
                print(f"Error in callback: {e}")

    def register_state_callback(self, callback: Callable[[BatteryState], None]):
        """
        Register a callback to be called when motor _state changes

        Args:
            callback: Function that takes (_motor_num: int, _state: MotorState)
        """
        self.__state_callbacks.append(callback)

    def get_battery_status(self) -> BatteryState:
        if not self.__state:
            return BatteryState()

        return BatteryState(
            current_voltage=self.__state.current_voltage,
            current_amp=self.__state.current_amp,
            power=self.__state.power,
            last_update=self.__state.last_update,
        )