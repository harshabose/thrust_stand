from typing import Optional, Dict, Callable, Any, List
from collections import defaultdict
from pymavlink import mavutil
from datetime import datetime
from asyncio import Task, sleep, create_task

def singleton(cls):
    """
    A decorator to make a class a Singleton.
    """
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance

@singleton
class MavlinkConnection:
    def __init__(self, addr: str, baudrate: int):
        self.master: Optional[mavutil.mavfile] = None
        self.__addr = addr
        self.__baudrate: int = baudrate
        self.__read_frequency: int = 0

        self.__connected = False
        self.__running = False
        self.__message_loop_task: Optional[Task] = None

        self.__last_heartbeat: Optional[datetime] = None
        self.__message_handlers: Dict[str, List[Callable]] = defaultdict(list)

    def connect(self, read_frequency: int = 1000000) -> bool:
        try:
            print(f"Connecting to {self.__addr}...")
            self.master = mavutil.mavlink_connection(
                device=self.__addr,
                baud=self.__baudrate
            )

            print("Waiting for heartbeat...")
            self.master.wait_heartbeat()
            print("Received heartbeat. Continuing...")

            self.__connected = True
            self.__last_heartbeat = datetime.now()

            print(f"Connected to system {self.master.target_system}, "
                  f"component {self.master.target_component}")

            # Request data streams
            self.__read_frequency = read_frequency

            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self.__connected = False
            return False

    def request_data_stream(self, msg_id: int, microseconds: int = 1_000_000):
        if not self.master:
            return

        message = self.master.mav.command_long_encode(
            self.master.target_system,  # Target system ID
            self.master.target_component,  # Target component ID
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,  # ID of command to send
            0,  # Confirmation
            msg_id,  # param1: Message ID to be streamed
            microseconds,  # param2: Interval in microseconds
            0,  # param3 (unused)
            0,  # param4 (unused)
            0,  # param5 (unused)
            0,  # param5 (unused)
            0  # param6 (unused)
        )

        self.master.mav.send(message)

    def register_message_handler(self, msg_type: str,  callback: Callable[[Any], None]):
        self.__message_handlers[msg_type].append(callback)

    def _handle_heartbeat(self, msg):
        """Process heartbeat message"""
        self.__last_heartbeat = datetime.now()

    async def start_monitoring(self):
        """Start the async message monitoring loop"""
        if not self.is_connected() or not self.master:
            raise RuntimeError("Not connected. Call connect() first.")

        if self.__running:
            print("Monitoring already running")
            return

        self.__running = True
        self.__message_loop_task = create_task(self._message_loop())
        print("Motor monitoring started")

    async def stop_monitoring(self):
        """Stop the async message monitoring loop"""
        self.__running = False

        if self.__message_loop_task:
            await self.__message_loop_task
            self.__message_loop_task = None

        print("Motor monitoring stopped")

    async def _message_loop(self):
        """Main async loop to read and process MAVLink messages"""
        while self.__running:
            try:
                # Non-blocking read
                msg = self.master.recv_match(blocking=False)

                if msg:
                    msg_type = msg.get_type()

                    # Handle different message types
                    if msg_type == 'HEARTBEAT':
                        self._handle_heartbeat(msg)

                    if msg_type in self.__message_handlers:
                        for handler in self.__message_handlers[msg_type]:
                            try:
                                handler(msg)
                            except Exception as e:
                                print(f"Handler error for {msg_type}: {e}")

                # Small sleep to prevent CPU spinning
                await sleep(0.01)  # 100Hz loop

            except Exception as e:
                print(f"Error in message loop: {e}")
                await sleep(0.1)

    def disconnect(self):
        """Close MAVLink connection"""
        self.__connected = False
        self.__running = False

        if self.master:
            self.master.close()
            print("Disconnected from MAVLink")

    def get_connection_status(self) -> Dict:
        """Get detailed connection status"""
        return {
            'connected': self.__connected,
            'last_heartbeat': self.__last_heartbeat,
            'target_system': self.master.target_system if self.master else None,
            'target_component': self.master.target_component if self.master else None,
        }

    def is_connected(self) -> bool:
        """Check if connected to MAVLink"""
        return self.__connected

    def is_running(self) -> bool:
        return self.__running