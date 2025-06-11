#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import time
from enum import Enum, auto


class RequestTimerKind(Enum):
    """Timestamp kinds for request handling stages."""

    # TODO: how should this handle streaming vs non-streaming requests?

    REQUEST_START = auto()  # Start of request handling
    REQUEST_END = auto()  # End of request handling
    SEND_START = auto()  # Start of sending request bytes
    SEND_END = auto()  # End of sending request bytes
    RECV_START = auto()  # Start of receiving response bytes
    RECV_CHUNK = auto()  # Start of receiving response chunk
    RECV_END = auto()  # End of receiving response bytes


class RequestTimers:
    """Records timestamps for different stages of request handling."""

    def __init__(self):
        """Initialize timer with zeroed timestamps."""
        self.timestamps: dict[RequestTimerKind, int] = {}
        self.chunk_timestamps: list[int] = []

    def reset(self) -> None:
        """Reset all timestamp values to zero. Must be called before re-using the timer."""
        self.timestamps = {}
        self.chunk_timestamps = []

    @property
    def chunk_count(self) -> int:
        """Get the number of chunks captured."""
        return len(self.chunk_timestamps)

    def append_chunk_timestamp(self, timestamp_ns: int) -> None:
        """Append a timestamp for a chunk.

        Args:
            timestamp_ns: The timestamp in nanoseconds.
        """
        self.chunk_timestamps.append(timestamp_ns)

    def capture_chunk_timestamp(self) -> int:
        """Capture a timestamp for a chunk and return it."""
        self.append_chunk_timestamp(time.perf_counter_ns())
        return self.chunk_timestamps[-1]

    def timestamp(self, kind: RequestTimerKind) -> int:
        """Get the timestamp, in nanoseconds, for a kind.

        Args:
            kind: The timestamp kind.

        Returns:
            The timestamp in nanoseconds.
        """
        return self.timestamps[kind]

    def chunk_timestamp(self, index: int) -> int:
        """Get the timestamp of a chunk in nanoseconds."""
        if index < 0 or index >= len(self.chunk_timestamps):
            raise ValueError(f"Invalid chunk index: {index}")
        return self.chunk_timestamps[index]

    def capture_timestamp(self, kind: RequestTimerKind) -> int:
        """Set a timestamp to the current time, in nanoseconds.

        Args:
            kind: The timestamp kind.

        Returns:
            The timestamp in nanoseconds.
        """
        ts = time.perf_counter_ns()
        self.timestamps[kind] = ts
        return ts

    def duration(self, start: RequestTimerKind, end: RequestTimerKind) -> int | None:
        """Return the duration between start timestamp and end timestamp in nanoseconds.

        Args:
            start: The start timestamp kind.
            end: The end timestamp kind.

        Returns:
            Duration in nanoseconds, or None if the duration could not be calculated.
        """
        start_ts = self.timestamps[start]
        end_ts = self.timestamps[end]

        # If the start or end timestamp is 0 then can't calculate the
        # duration, so return max to indicate error.
        if start_ts == 0 or end_ts == 0:
            return None

        return end_ts - start_ts
