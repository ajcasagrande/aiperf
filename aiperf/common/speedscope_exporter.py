# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Memory-efficient Python profiler with Speedscope export capability.

This module provides real-time execution profiling using Python's sys.setprofile()
with memory-bounded capture and efficient export to Speedscope format.

Features:
- Configurable memory limits and event buffer sizes
- Smart sampling for long-running processes
- Circular buffers to prevent memory explosion
- Lightweight data structures during capture

Usage:
    # Memory-efficient profiling with limits
    with SpeedscopeProfiler(max_events=100000) as profiler:
        # your code here
        pass

    profiler.export("profile.json")
"""

import sys
import threading
import time
from collections import deque
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from types import FrameType
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field


class ProfilingError(Exception):
    """Base exception for profiling operations."""


class ProfileNotStartedError(ProfilingError):
    """Raised when trying to stop profiling that hasn't started."""


class ProfileAlreadyStartedError(ProfilingError):
    """Raised when trying to start profiling that's already active."""


class MemoryLimitExceededError(ProfilingError):
    """Raised when profiling memory limits are exceeded."""


class TimeUnit(Enum):
    """Time units supported by Speedscope."""

    NANOSECONDS = "nanoseconds"
    MICROSECONDS = "microseconds"
    MILLISECONDS = "milliseconds"
    SECONDS = "seconds"


class SamplingStrategy(Enum):
    """Sampling strategies for memory management."""

    NONE = "none"
    ADAPTIVE = "adaptive"  # Start full, then sample as buffer fills
    FIXED = "fixed"  # Sample every N events


class FilterLevel(Enum):
    """Levels of builtin filtering."""

    NONE = "none"  # No filtering - capture everything
    BASIC = "basic"  # Filter common builtins (len, isinstance, etc.)
    AGGRESSIVE = "aggressive"  # Filter all builtins and standard library


class Frame(BaseModel):
    """Function frame information."""

    model_config = ConfigDict(frozen=True, slots=True)

    name: str
    file: str | None = None
    line: int | None = Field(None, ge=1)


class Event(BaseModel):
    """Speedscope profiling event."""

    model_config = ConfigDict(frozen=True, slots=True)

    type: Literal["O", "C"]
    frame: int = Field(ge=0)
    at: int = Field(ge=0)


class Profile(BaseModel):
    """Single thread profile data."""

    model_config = ConfigDict(frozen=True)

    type: Literal["evented"] = "evented"
    name: str
    unit: str
    startValue: int = Field(ge=0)
    endValue: int = Field(ge=0)
    events: list[Event] = Field(default_factory=list)


class SpeedscopeData(BaseModel):
    """Complete Speedscope export format."""

    model_config = ConfigDict(frozen=True)

    schema_url: str = Field(
        default="https://www.speedscope.app/file-format-schema.json", alias="$schema"
    )
    version: str = "0.0.1"
    shared: dict[str, list[Frame]] = Field(default_factory=lambda: {"frames": []})
    profiles: list[Profile] = Field(default_factory=list)


class CompactEvent(NamedTuple):
    """Lightweight event representation for memory efficiency."""

    event_type: int  # 0=call, 1=return
    frame_id: int
    timestamp: float
    thread_id: int


class SpeedscopeProfiler:
    """
    Memory-efficient real-time Python profiler with Speedscope export.

    Uses circular buffers, sampling, and memory limits to prevent excessive
    memory consumption during long-running profiling sessions.
    """

    # Common builtin functions that are rarely interesting for profiling
    _BASIC_FILTERED_FUNCTIONS = {
        "len",
        "isinstance",
        "hasattr",
        "getattr",
        "setattr",
        "delattr",
        "iter",
        "next",
        "min",
        "max",
        "sum",
        "abs",
        "round",
        "pow",
        "bool",
        "int",
        "float",
        "str",
        "list",
        "dict",
        "set",
        "tuple",
        "repr",
        "hash",
        "id",
        "type",
        "callable",
        "ord",
        "chr",
        "enumerate",
        "range",
        "zip",
        "map",
        "filter",
        "any",
        "all",
        "sorted",
        "reversed",
        "divmod",
        "bin",
        "oct",
        "hex",
    }

    # Common builtin methods that are rarely interesting
    _BASIC_FILTERED_METHODS = {
        "append",
        "extend",
        "insert",
        "remove",
        "pop",
        "clear",
        "index",
        "count",
        "get",
        "setdefault",
        "update",
        "keys",
        "values",
        "items",
        "copy",
        "add",
        "discard",
        "union",
        "intersection",
        "difference",
        "upper",
        "lower",
        "strip",
        "split",
        "join",
        "replace",
        "find",
        "startswith",
        "endswith",
        "format",
        "encode",
        "decode",
    }

    # Standard library modules to filter at aggressive level
    _STDLIB_MODULES = {
        "sys",
        "os",
        "re",
        "json",
        "time",
        "datetime",
        "collections",
        "itertools",
        "functools",
        "operator",
        "copy",
        "pickle",
        "urllib",
        "http",
        "email",
        "html",
        "xml",
        "csv",
        "configparser",
        "logging",
        "threading",
        "multiprocessing",
        "subprocess",
        "socket",
        "ssl",
        "hashlib",
        "hmac",
        "base64",
        "zlib",
        "sqlite3",
        "uuid",
        "random",
        "math",
        "statistics",
        "decimal",
        "fractions",
        "pathlib",
        "glob",
        "shutil",
        "tempfile",
        "typing",
        "inspect",
        "traceback",
        "warnings",
        "weakref",
    }

    def __init__(
        self,
        unit: TimeUnit = TimeUnit.MICROSECONDS,
        max_events: int = 10_000_000,
        max_frames: int = 500_000,
        sampling_strategy: SamplingStrategy = SamplingStrategy.ADAPTIVE,
        memory_warning_mb: int = 750,
        memory_limit_mb: int = 1000,
        filter_level: FilterLevel = FilterLevel.BASIC,
    ) -> None:
        self._unit = unit
        self._conversion_factor = self._get_conversion_factor()
        self._max_events = max_events
        self._max_frames = max_frames
        self._sampling_strategy = sampling_strategy
        self._memory_warning_mb = memory_warning_mb
        self._memory_limit_mb = memory_limit_mb
        self._filter_level = filter_level

        # Profiling state
        self._start_time = 0.0
        self._profiling = False
        self._events_captured = 0
        self._sample_rate = 1
        self._sample_counter = 0

        # Memory-efficient event storage using circular buffer
        self._events = deque(maxlen=max_events)

        # Thread stacks with size limits
        self._thread_stacks: dict[int, deque] = {}
        self._max_stack_depth = 100

        # Frame management with limits
        self._frame_cache: dict[str, int] = {}
        self._frames: list[Frame] = []

        # Memory monitoring
        self._last_memory_check = 0.0
        self._memory_warnings_sent = 0

        # Thread safety
        self._lock = threading.Lock()

    def _should_filter_frame(self, name: str, filename: str) -> bool:
        """Determine if a frame should be filtered based on filter level."""
        if self._filter_level == FilterLevel.NONE:
            return False

        # Always filter internal Python machinery
        if filename in ("<built-in>", "<frozen>", "<string>"):
            return True

        # Basic filtering: common builtins and methods
        if self._filter_level == FilterLevel.BASIC:
            # Filter common builtin functions
            if name in self._BASIC_FILTERED_FUNCTIONS:
                return True

            # Filter common builtin methods
            if name in self._BASIC_FILTERED_METHODS:
                return True

            # Filter very internal Python calls
            if name.startswith("_") and not name.startswith("__"):
                # Keep dunder methods but filter single underscore
                return True

        # Aggressive filtering: all builtins and stdlib
        elif self._filter_level == FilterLevel.AGGRESSIVE:
            # Filter all builtins
            if filename == "<built-in>":
                return True

            # Filter standard library modules
            if filename and any(
                stdlib_mod in filename for stdlib_mod in self._STDLIB_MODULES
            ):
                return True

            # Filter site-packages (third-party libraries)
            if "site-packages" in filename:
                return True

            # Filter anything that looks like internal Python
            if filename and any(
                internal in filename
                for internal in [
                    "<frozen",
                    "/lib/python",
                    "\\lib\\python",
                    "/_internal/",
                    "\\_internal\\",
                ]
            ):
                return True

            # Filter private methods and functions
            if name.startswith("_"):
                return True

        return False

    def _get_conversion_factor(self) -> float:
        """Get time conversion factor from seconds to target unit."""
        return {
            TimeUnit.NANOSECONDS: 1e9,
            TimeUnit.MICROSECONDS: 1e6,
            TimeUnit.MILLISECONDS: 1e3,
            TimeUnit.SECONDS: 1.0,
        }[self._unit]

    def _convert_time(self, timestamp: float) -> int:
        """Convert timestamp to target unit relative to profile start."""
        return int((timestamp - self._start_time) * self._conversion_factor)

    def _check_memory_usage(self) -> None:
        """Monitor memory usage and apply limits."""
        current_time = time.perf_counter()

        # Check every 10 seconds to reduce overhead and noise
        if current_time - self._last_memory_check < 10.0:
            return

        self._last_memory_check = current_time

        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            if memory_mb > self._memory_limit_mb:
                raise MemoryLimitExceededError(
                    f"Memory usage {memory_mb:.1f}MB exceeds limit {self._memory_limit_mb}MB"
                )

            # Only warn when approaching limit (90% of limit) and limit warnings
            warning_threshold = self._memory_limit_mb * 0.9
            if memory_mb > warning_threshold and self._memory_warnings_sent < 2:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Profiler memory usage: {memory_mb:.1f}MB (approaching limit: {self._memory_limit_mb}MB)"
                )
                self._memory_warnings_sent += 1

        except ImportError:
            # psutil not available, skip memory monitoring
            pass

    def _should_sample_event(self) -> bool:
        """Determine if current event should be sampled."""
        if self._sampling_strategy == SamplingStrategy.NONE:
            return True

        self._sample_counter += 1

        if self._sampling_strategy == SamplingStrategy.ADAPTIVE:
            # Adaptive sampling: increase sample rate as buffer fills
            buffer_usage = len(self._events) / self._max_events
            if buffer_usage > 0.8:
                self._sample_rate = max(10, int(buffer_usage * 100))
            elif buffer_usage > 0.5:
                self._sample_rate = max(5, int(buffer_usage * 50))
            else:
                self._sample_rate = 1

        return self._sample_counter % self._sample_rate == 0

    def _get_frame_id(self, name: str, filename: str, lineno: int) -> int | None:
        """Get or create frame ID, respecting memory limits."""
        if len(self._frames) >= self._max_frames:
            # Frame limit reached, return None to skip this event
            return None

        key = f"{filename}:{lineno}:{name}"

        if key not in self._frame_cache:
            # Clean filename for memory efficiency
            clean_filename = (
                filename if filename != "<unknown>" and len(filename) < 200 else None
            )

            frame = Frame(
                name=name[:100],  # Truncate long names
                file=clean_filename,
                line=lineno if lineno > 0 else None,
            )
            frame_id = len(self._frames)
            self._frame_cache[key] = frame_id
            self._frames.append(frame)
            return frame_id

        return self._frame_cache[key]

    def _profile_callback(self, frame: FrameType, event: str, arg: Any) -> None:
        """Memory-efficient profile callback."""
        if not self._profiling or event not in ("call", "return"):
            return

        # Skip if sampling says so
        if not self._should_sample_event():
            return

        timestamp = time.perf_counter()
        thread_id = threading.get_ident()

        try:
            # Periodic memory checks
            if self._events_captured % 10000 == 0:
                self._check_memory_usage()

            name = frame.f_code.co_name
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno

            # Skip filtered frames to reduce noise and memory usage
            if self._should_filter_frame(name, filename):
                return

            with self._lock:
                # Initialize thread stack with size limit
                if thread_id not in self._thread_stacks:
                    self._thread_stacks[thread_id] = deque(maxlen=self._max_stack_depth)

                stack = self._thread_stacks[thread_id]

                if event == "call":
                    frame_id = self._get_frame_id(name, filename, lineno)
                    if frame_id is not None:
                        # Store lightweight event
                        compact_event = CompactEvent(0, frame_id, timestamp, thread_id)
                        self._events.append(compact_event)
                        stack.append(frame_id)
                        self._events_captured += 1

                elif event == "return" and stack:
                    frame_id = stack.pop()
                    compact_event = CompactEvent(1, frame_id, timestamp, thread_id)
                    self._events.append(compact_event)
                    self._events_captured += 1

        except Exception:
            # Don't let profiling errors crash the application
            pass

    def start(self) -> None:
        """Start memory-efficient profiling."""
        if self._profiling:
            raise ProfileAlreadyStartedError("Profiling is already active")

        # Reset state
        self._start_time = time.perf_counter()
        self._profiling = True
        self._events_captured = 0
        self._sample_rate = 1
        self._sample_counter = 0
        self._memory_warnings_sent = 0

        sys.setprofile(self._profile_callback)

    def stop(self) -> SpeedscopeData:
        """Stop profiling and return Speedscope data."""
        if not self._profiling:
            raise ProfileNotStartedError("Profiling is not active")

        self._profiling = False
        sys.setprofile(None)

        if not self._events:
            raise ProfilingError("No profiling data captured")

        return self._build_speedscope_data()

    def _build_speedscope_data(self) -> SpeedscopeData:
        """Build Speedscope data efficiently from captured events."""
        # Group events by thread with memory-efficient processing
        events_by_thread: dict[int, list[CompactEvent]] = {}

        for event in self._events:
            thread_id = event.thread_id
            if thread_id not in events_by_thread:
                events_by_thread[thread_id] = []
            events_by_thread[thread_id].append(event)

        profiles = []

        # Process each thread efficiently
        for thread_id, thread_events in events_by_thread.items():
            if not thread_events:
                continue

            speedscope_events = self._create_speedscope_events(thread_events)
            if not speedscope_events:
                continue

            profile = Profile(
                name=f"Thread {thread_id}",
                unit=self._unit.value,
                startValue=min(e.at for e in speedscope_events),
                endValue=max(e.at for e in speedscope_events),
                events=speedscope_events,
            )
            profiles.append(profile)

        # Create combined profile for multiple threads (memory permitting)
        if len(profiles) > 1 and len(self._events) < self._max_events // 2:
            all_events = []
            for thread_events in events_by_thread.values():
                all_events.extend(self._create_speedscope_events(thread_events))

            if all_events:
                all_events.sort(key=lambda e: e.at)
                combined_profile = Profile(
                    name="All Threads",
                    unit=self._unit.value,
                    startValue=min(e.at for e in all_events),
                    endValue=max(e.at for e in all_events),
                    events=all_events,
                )
                profiles.insert(0, combined_profile)

        return SpeedscopeData(shared={"frames": self._frames}, profiles=profiles)

    def _create_speedscope_events(
        self, thread_events: list[CompactEvent]
    ) -> list[Event]:
        """Convert compact events to Speedscope events efficiently."""
        events = []
        call_stack = []

        for event in thread_events:
            timestamp = self._convert_time(event.timestamp)

            if event.event_type == 0:  # call
                events.append(Event(type="O", frame=event.frame_id, at=timestamp))
                call_stack.append(event.frame_id)
            elif event.event_type == 1:  # return
                if call_stack and call_stack[-1] == event.frame_id:
                    call_stack.pop()
                    events.append(Event(type="C", frame=event.frame_id, at=timestamp))

        # Close remaining open calls
        final_time = self._convert_time(time.perf_counter())
        while call_stack:
            frame_id = call_stack.pop()
            events.append(Event(type="C", frame=frame_id, at=final_time))

        return events

    def save(self, data: SpeedscopeData, path: str | Path) -> None:
        """Save Speedscope data to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with path.open("w", encoding="utf-8") as f:
                f.write(data.model_dump_json(by_alias=True, indent=2))
        except Exception as e:
            raise ProfilingError(f"Failed to save profile: {e}") from e

    def export(self, path: str | Path, name: str = "Python Profile") -> None:
        """Stop profiling and export to file."""
        data = self.stop()

        # Update profile names
        updated_profiles = []
        for profile in data.profiles:
            if profile.name.startswith("Thread"):
                thread_part = profile.name.split(" ", 1)[1]
                updated_profiles.append(
                    profile.model_copy(update={"name": f"{name} ({thread_part})"})
                )
            elif profile.name == "All Threads":
                updated_profiles.append(
                    profile.model_copy(update={"name": f"{name} (All Threads)"})
                )
            else:
                updated_profiles.append(profile)

        data = data.model_copy(update={"profiles": updated_profiles})
        self.save(data, path)

    def get_memory_stats(self) -> dict[str, Any]:
        """Get current memory usage statistics."""
        return {
            "events_captured": self._events_captured,
            "events_buffered": len(self._events),
            "max_events": self._max_events,
            "frames_cached": len(self._frames),
            "max_frames": self._max_frames,
            "sample_rate": self._sample_rate,
            "threads_tracked": len(self._thread_stacks),
            "buffer_usage_pct": len(self._events) / self._max_events * 100,
        }

    def __enter__(self) -> "SpeedscopeProfiler":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if self._profiling:
            self._cached_data = self.stop()

    @property
    def data(self) -> SpeedscopeData | None:
        """Get the cached profiling data after context manager exit."""
        return getattr(self, "_cached_data", None)

    def export_cached(self, path: str | Path, name: str = "Python Profile") -> None:
        """Export cached data to file (for use after context manager)."""
        data = self.data
        if not data:
            raise ProfilingError("No cached profiling data available")

        # Update profile names
        updated_profiles = []
        for profile in data.profiles:
            if profile.name.startswith("Thread"):
                thread_part = profile.name.split(" ", 1)[1]
                updated_profiles.append(
                    profile.model_copy(update={"name": f"{name} ({thread_part})"})
                )
            elif profile.name == "All Threads":
                updated_profiles.append(
                    profile.model_copy(update={"name": f"{name} (All Threads)"})
                )
            else:
                updated_profiles.append(profile)

        data = data.model_copy(update={"profiles": updated_profiles})
        self.save(data, path)


@contextmanager
def profile(
    path: str | Path | None = None,
    name: str = "Python Profile",
    unit: TimeUnit = TimeUnit.MICROSECONDS,
    max_events: int = 100_000,
    memory_limit_mb: int = 200,
    filter_level: FilterLevel = FilterLevel.BASIC,
):
    """
    Memory-efficient context manager for quick profiling.

    Args:
        path: Optional file path to save profile
        name: Profile name
        unit: Time unit for measurements
        max_events: Maximum events to capture
        memory_limit_mb: Memory limit in MB
        filter_level: Level of builtin filtering (NONE, BASIC, AGGRESSIVE)
    """
    profiler = SpeedscopeProfiler(
        unit=unit,
        max_events=max_events,
        memory_limit_mb=memory_limit_mb,
        filter_level=filter_level,
    )

    try:
        profiler.start()
        yield profiler

        if path is not None:
            profiler.export(path, name)

    finally:
        if profiler._profiling:
            profiler._profiling = False
            sys.setprofile(None)
