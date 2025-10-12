from typing import List, Callable, Coroutine, Any
from datetime import datetime

from config import LoadCellReading, LoadConnection
from load import LoadConnection as lc
from utils import CircularBuffer
import asyncio

class AverageLoadConnection:
    def __init__(self, connection: LoadConnection, size: int):
        self.__connection: LoadConnection = connection
        self.__connection.register_state_callback(self.__callback)

        self.__circular_buffer: CircularBuffer[LoadCellReading] = CircularBuffer(size)

    async def __callback(self, reading: LoadCellReading) -> None:
        await self.__circular_buffer.push(reading)

    async def get_current_readings(self) -> LoadCellReading:
        values: List[LoadCellReading] = await self.__circular_buffer.flush()

        if not values:
            return LoadCellReading(
                thrust_readings={},
                total_thrust=0,
                timestamp=datetime.now()
            )

        avg_total_thrust = sum(v.total_thrust for v in values) // len(values)

        all_keys = set()
        for reading in values:
            all_keys.update(reading.thrust_readings.keys())

        avg_thrust_readings = {}
        for key in all_keys:
            key_values = [
                reading.thrust_readings[key]
                for reading in values
                if key in reading.thrust_readings
            ]
            avg_thrust_readings[key] = sum(key_values) // len(key_values)

        # Use the most recent timestamp or current time
        latest_timestamp = max(v.timestamp for v in values)

        return LoadCellReading(
            thrust_readings=avg_thrust_readings,
            total_thrust=avg_total_thrust,
            timestamp=latest_timestamp
        )


    def tare(self) -> bool:
        return self.__connection.tare()

    def register_state_callback(self, callback: Callable[[LoadCellReading], Coroutine[Any, Any, None]]) -> None:
        self.__connection.register_state_callback(callback)


async def main():
    # Create the underlying connection
    base_monitor = lc(port='/dev/cu.usbmodem11301', baudrate=9600)

    # Wrap it with averaging (buffer size of 10 readings)
    monitor = AverageLoadConnection(connection=base_monitor, size=10)

    if not await base_monitor.connect(read_frequency=100_000):
        print("Failed to connect!")
        return

    try:
        # Tare on startup
        await asyncio.sleep(5)
        print("Sending tare command...")
        monitor.tare()
        await asyncio.sleep(0.5)

        # Start monitoring in background
        asyncio.create_task(base_monitor.start_monitoring(display_mode='silent'))  # or 'quiet' mode

        # Periodically get averaged readings
        print("\nGetting averaged readings every 2 seconds...")
        for i in range(100):  # Get 10 averaged readings
            await asyncio.sleep(2)

            # Get the averaged reading (flushes the buffer)
            avg_reading = await monitor.get_current_readings()

            print(f"\n--- Averaged Reading #{i + 1} ---")
            print(f"Total Thrust: {avg_reading.total_thrust}")
            print(f"Individual Readings: {avg_reading.thrust_readings}")
            print(f"Timestamp: {avg_reading.timestamp}")

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        base_monitor.stop_monitoring()
        base_monitor.disconnect()
        # await monitor._AverageLoadConnection__circular_buffer.close()


if __name__ == "__main__":
    asyncio.run(main())