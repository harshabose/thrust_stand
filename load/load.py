import asyncio
import serial
from typing import Optional, Dict, List, Callable, Coroutine, Any
from config import LoadCellReading, MOTOR_STR
from datetime import datetime
from scipy import signal
from numpy import ndarray
import re

class LoadConnection:
    def __init__(self, port: str, baudrate: int = 9600):
        """
        Initialize the thrust stand serial monitor.

        Args:
            port: Serial port name (e.g., '/dev/ttyUSB0')
            baudrate: Baudrate for serial communication (default: 9600)
        """
        self.__port = port
        self.__baudrate = baudrate
        self.__serial_conn: Optional[serial.Serial] = None
        self.__running = False
        self.__read_frequency: int = 0

        # Store current readings
        self.__motor_values: Dict[str, int] = {MOTOR_STR(i): 0 for i in range(1, 7)}
        self.__total_value = 0
        self.__last_update: Optional[datetime] = None
        self.__lp_filter: List[Optional[ndarray]] = [None] * 6
        self.__lp_filter_state: List[Optional[ndarray]] = [None] * 6

        self.__state_callbacks: List[Callable[[LoadCellReading], Coroutine[Any, Any, None]]] = []

    async def connect(self, read_frequency: int, timeout: float = 0.1) -> bool:
        """Establish serial connection"""
        try:
            self.__serial_conn = serial.Serial(
                self.__port,
                self.__baudrate,
                timeout=timeout
            )

            self.__lp_filter = [(signal.butter(N=2, Wn=0.5, btype='lowpass', fs=1_000_000 / read_frequency, output='sos'))] * 6

            self.__read_frequency = read_frequency
            print(f"Connected to {self.__port} at {self.__baudrate} baud\n")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Close serial connection"""
        if self.__serial_conn and self.__serial_conn.is_open:
            self.__serial_conn.close()
            print("\nSerial connection closed")

    def tare(self):
        """
        Send tare command to serial device.
        Sends 't' character through serial port.
        """
        if not self.__serial_conn or not self.__serial_conn.is_open:
            print("Error: Not connected to serial port")
            return False

        try:
            self.__serial_conn.write(b't')
            print("Tare command sent")
            return True
        except Exception as e:
            print(f"Error sending tare command: {e}")
            return False

    async def parse_line(self, line: str) -> bool:
        """
        Parse a line of serial output and update internal state.

        Args:
            line: String containing motor data

        Returns:
            True if parsing successful, False otherwise
        """
        line = line.strip()
        if not line:
            return False

        # Parse motor values using regex
        pattern = r'MOTOR-(\d+):\s*(\d+)'
        matches = re.findall(pattern, line)

        if not matches:
            return False

        total: int = 0
        # old_total: int = self.__total_value

        # Update motor values
        for motor_num, value in matches:
            # if self.__lp_filter[int(motor_num) - 1] is not None:
            #     if self.__lp_filter_state[int(motor_num) - 1] is None:
            #         self.__lp_filter_state[int(motor_num) - 1] = signal.sosfilt_zi(self.__lp_filter[int(motor_num) - 1]) * int(value)
            #     else:
            #         filtered, state = signal.sosfilt(self.__lp_filter[int(motor_num) - 1], [int(value)], zi=self.__lp_filter_state[int(motor_num) - 1])
            #         self.__lp_filter_state[int(motor_num) - 1] = state
            #         value = str(int(filtered[0]))
            self.__motor_values[MOTOR_STR(motor_num)] = int(value)
            total += int(value)

        self.__total_value = total

        # # Parse total
        # total_match = re.search(r'TOTO?AL:\s*(\d+)', line)
        # if total_match:
        #     self.__total_value = int(total_match.group(1))

        self.__last_update = datetime.now()

        await self.__notify_state_change(await self.get_current_readings())
        return True

    async def get_current_readings(self) -> LoadCellReading:
        """Get current motor readings"""
        return LoadCellReading(
            thrust_readings=self.__motor_values.copy(),
            total_thrust=self.__total_value,
            timestamp=self.__last_update,
        )

    async def start_monitoring(self, display_mode: str = 'continuous'):
        """
        Start monitoring serial data.

        Args:
            display_mode: 'continuous' (scrolling) or 'update' (in-place update)
        """
        if not self.__serial_conn or not self.__serial_conn.is_open:
            raise RuntimeError("Not connected. Call connect() first.")

        self.__running = True
        print("Monitoring started... (Press Ctrl+C to stop)\n")

        if display_mode == 'continuous':
            await self._monitor_continuous()
        elif display_mode == 'update':
            await self._monitor_update()
        elif display_mode == 'silent':
            await self._monitor_silent()
        else:
            raise ValueError(f"Invalid display_mode: {display_mode}")

    async def _monitor_continuous(self):
        """Monitor with scrolling output - reads only latest data"""
        read_interval = self.__read_frequency / 1_000_000

        while self.__running:
            try:
                if self.__serial_conn.in_waiting > 0:
                    # Discard all but the last line
                    lines = []
                    while self.__serial_conn.in_waiting > 0:
                        line = self.__serial_conn.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            lines.append(line)

                    # Process only the most recent line
                    if lines:
                        latest_line = lines[-1]
                        print(latest_line)
                        await self.parse_line(latest_line)

                await asyncio.sleep(read_interval)

            except Exception as e:
                print(f"Error reading serial: {e}")
                await asyncio.sleep(0.1)

    async def _monitor_update(self):
        """Monitor with in-place updating display - reads only latest data"""
        read_interval = self.__read_frequency / 1_000_000

        while self.__running:
            try:
                if self.__serial_conn.in_waiting > 0:
                    # Discard all but the last complete line
                    lines = []
                    while self.__serial_conn.in_waiting > 0:
                        line = self.__serial_conn.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            lines.append(line)

                    # Process only the most recent line
                    if lines and await self.parse_line(lines[-1]):
                        print("\033[2J\033[H", end='')
                        print("=== Thrust Stand Readings ===\n")

                        for motor, value in sorted(self.__motor_values.items()):
                            print(f"{motor}: {value:5d} g")

                        print(f"\nTOTAL:   {self.__total_value:5d} g")

                        if self.__last_update:
                            print(f"\nLast update: {self.__last_update.strftime('%H:%M:%S.%f')[:-3]}")

                        print("\nPress Ctrl+C to stop")

                await asyncio.sleep(read_interval)

            except Exception as e:
                print(f"Error reading serial: {e}")
                await asyncio.sleep(0.1)

    async def _monitor_silent(self):
        """Monitor without output - reads only latest data"""
        read_interval = self.__read_frequency / 1_000_000

        while self.__running:
            try:
                if self.__serial_conn.in_waiting > 0:
                    # Discard all but the last line
                    lines = []
                    while self.__serial_conn.in_waiting > 0:
                        line = self.__serial_conn.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            lines.append(line)

                    # Process only the most recent line
                    if lines:
                        latest_line = lines[-1]
                        await self.parse_line(latest_line)

                await asyncio.sleep(read_interval)

            except Exception as e:
                print(f"Error reading serial: {e}")
                await asyncio.sleep(0.1)

    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.__running = False

    async def __notify_state_change(self, reading: LoadCellReading):
        for callback in self.__state_callbacks:
            try:
                await callback(reading)
            except Exception as e:
                print(f"Error in callback: {e}")


    def register_state_callback(self, callback: Callable[[LoadCellReading], Coroutine[Any, Any, None]]) -> None:
        self.__state_callbacks.append(callback)


async def main():
    monitor = LoadConnection(port='/dev/cu.usbmodem11301', baudrate=9600)

    if not await monitor.connect(read_frequency=100_000):
        print("Failed to connect!")
        return

    try:
        # Tare on startup
        await asyncio.sleep(5)
        print("Sending tare command...")
        monitor.tare()
        await asyncio.sleep(0.5)

        await monitor.start_monitoring(display_mode='update')

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        monitor.stop_monitoring()
        monitor.disconnect()

if __name__ == "__main__":
    # Run the main monitor
    asyncio.run(main())