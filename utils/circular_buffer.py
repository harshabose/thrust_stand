from typing import TypeVar, Generic, List
import asyncio
from collections import deque

T = TypeVar('T')


class CircularBuffer(Generic[T]):
    def __init__(self, size: int):
        if size <= 0:
            raise ValueError("Buffer size must be positive")

        self._size = size
        self._buffer: deque[T] = deque(maxlen=size)
        self._lock = asyncio.Lock()
        self._closed = False

    async def push(self, value: T) -> None:
        """
        Push a value to the buffer. If the buffer is full,
        the oldest value is automatically removed.
        """
        if self._closed:
            raise RuntimeError("Cannot push to a closed buffer")

        async with self._lock:
            self._buffer.append(value)  # deque with max-len automatically removes oldest

    async def pop(self) -> T:
        """
        Pop the oldest value from the buffer.
        Raises IndexError if the buffer is empty.
        """
        if self._closed:
            raise RuntimeError("Cannot pop from a closed buffer")

        async with self._lock:
            if not self._buffer:
                raise IndexError("Cannot pop from empty buffer")
            return self._buffer.popleft()

    async def flush(self) -> List[T]:
        """
        Return all values in the buffer and clear it.
        Returns values in order from oldest to newest.
        """
        if self._closed:
            raise RuntimeError("Cannot flush a closed buffer")

        async with self._lock:
            values = list(self._buffer)
            self._buffer.clear()
            return values

    async def close(self) -> None:
        """
        Close the buffer and prevent further operations.
        """
        async with self._lock:
            self._closed = True
            self._buffer.clear()

    def is_closed(self) -> bool:
        """Check if the buffer is closed."""
        return self._closed

    def __len__(self) -> int:
        """Get the current number of items in the buffer."""
        return len(self._buffer)

    @property
    def size(self) -> int:
        """Get maximum buffer size."""
        return self._size