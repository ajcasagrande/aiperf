#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Simple vs Detailed State Models

This compares minimal state models vs detailed ones and shows when each is appropriate.
"""

import asyncio
import logging
from enum import Enum

# =============================================================================
# MINIMAL STATE MODEL (Often Better!)
# =============================================================================


class SimpleStates(Enum):
    """Minimal state model - just the essentials."""

    STOPPED = (
        "stopped"  # Service is not running (includes created, initialized, stopped)
    )
    RUNNING = "running"  # Service is actively running
    ERROR = "error"  # Something went wrong


class SimpleService:
    """Service with minimal state model."""

    def __init__(self, service_id: str):
        self.service_id = service_id
        self.logger = logging.getLogger(service_id)
        self._state = SimpleStates.STOPPED

    async def start(self) -> None:
        """Start the service - simple and clear."""
        if self._state == SimpleStates.RUNNING:
            return

        if self._state == SimpleStates.ERROR:
            raise RuntimeError("Cannot start from error state")

        try:
            # Do all the work in one method
            await self._initialize_and_start()
            self._state = SimpleStates.RUNNING
            self.logger.info("Service started")
        except Exception as e:
            self._state = SimpleStates.ERROR
            self.logger.error(f"Failed to start: {e}")
            raise

    async def stop(self) -> None:
        """Stop the service - simple and clear."""
        if self._state == SimpleStates.STOPPED:
            return

        try:
            await self._shutdown()
            self._state = SimpleStates.STOPPED
            self.logger.info("Service stopped")
        except Exception as e:
            self._state = SimpleStates.ERROR
            self.logger.error(f"Failed to stop: {e}")
            raise

    async def _initialize_and_start(self):
        """All initialization and startup in one place."""
        await asyncio.sleep(0.1)  # Simulate initialization
        await asyncio.sleep(0.1)  # Simulate startup

    async def _shutdown(self):
        """All shutdown logic in one place."""
        await asyncio.sleep(0.1)  # Simulate shutdown

    @property
    def state(self) -> SimpleStates:
        return self._state


# =============================================================================
# DETAILED STATE MODEL (What we had before)
# =============================================================================


class DetailedStates(Enum):
    """Detailed state model with intermediate states."""

    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class DetailedService:
    """Service with detailed state model."""

    def __init__(self, service_id: str):
        self.service_id = service_id
        self.logger = logging.getLogger(service_id)
        self._state = DetailedStates.CREATED

    async def initialize(self) -> None:
        if self._state != DetailedStates.CREATED:
            raise ValueError(f"Cannot initialize from {self._state}")

        self._state = DetailedStates.INITIALIZING
        try:
            await self._do_initialize()
            self._state = DetailedStates.INITIALIZED
        except Exception:
            self._state = DetailedStates.ERROR
            raise

    async def start(self) -> None:
        if self._state != DetailedStates.INITIALIZED:
            raise ValueError(f"Cannot start from {self._state}")

        self._state = DetailedStates.STARTING
        try:
            await self._do_start()
            self._state = DetailedStates.RUNNING
        except Exception:
            self._state = DetailedStates.ERROR
            raise

    async def stop(self) -> None:
        if self._state != DetailedStates.RUNNING:
            return

        self._state = DetailedStates.STOPPING
        try:
            await self._do_stop()
            self._state = DetailedStates.STOPPED
        except Exception:
            self._state = DetailedStates.ERROR
            raise

    async def _do_initialize(self):
        await asyncio.sleep(0.1)

    async def _do_start(self):
        await asyncio.sleep(0.1)

    async def _do_stop(self):
        await asyncio.sleep(0.1)

    @property
    def state(self) -> DetailedStates:
        return self._state


# =============================================================================
# REAL WORLD EXAMPLES
# =============================================================================


class HTTPServerStates(Enum):
    """Real HTTP servers often use simple states."""

    STOPPED = "stopped"  # Not listening
    RUNNING = "running"  # Accepting connections
    ERROR = "error"  # Failed to bind/listen


class DatabaseStates(Enum):
    """Databases often need more detailed states."""

    OFFLINE = "offline"
    STARTING = "starting"  # Needed! Recovery can take minutes
    ONLINE = "online"
    STOPPING = "stopping"  # Needed! Checkpoint writes take time
    CRASHED = "crashed"


class ProcessStates(Enum):
    """Unix processes use very simple states."""

    RUNNING = "running"  # R
    SLEEPING = "sleeping"  # S
    STOPPED = "stopped"  # T
    ZOMBIE = "zombie"  # Z


# =============================================================================
# WHEN TO USE WHICH MODEL
# =============================================================================

"""
USE SIMPLE STATES WHEN:
✅ State transitions are fast (< 1 second)
✅ You don't need to show progress to users
✅ Intermediate states don't provide actionable information
✅ You want to keep the API simple
✅ Debugging intermediate states isn't important
✅ You're building a library/framework where simplicity matters

EXAMPLES:
- HTTP servers (start/stop is instant)
- Simple workers/processors
- File handlers
- Caches
- Most microservices

USE DETAILED STATES WHEN:
✅ State transitions take significant time (> 5 seconds)
✅ Users need progress feedback
✅ Different actions are valid in intermediate states
✅ You need fine-grained observability
✅ Debugging transition problems is important
✅ External systems need to know the exact phase

EXAMPLES:
- Database servers (startup/shutdown takes time)
- ML model loading (can take minutes)
- Large data processing jobs
- System services with complex initialization
- Distributed systems coordination
"""


# =============================================================================
# HYBRID APPROACH (Often Best!)
# =============================================================================


class SmartStates(Enum):
    """Hybrid: Simple public API, detailed internal tracking."""

    # Public states (simple)
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"

    # Internal states (detailed) - not exposed in public API
    _INITIALIZING = "_initializing"
    _STARTING = "_starting"
    _STOPPING = "_stopping"


class SmartService:
    """Best of both worlds: Simple API, detailed internal tracking."""

    def __init__(self, service_id: str):
        self.service_id = service_id
        self.logger = logging.getLogger(service_id)
        self._detailed_state = SmartStates.STOPPED

    async def start(self) -> None:
        """Simple public API."""
        if self.state == SmartStates.RUNNING:
            return

        try:
            # Internal detailed tracking
            self._detailed_state = SmartStates._INITIALIZING
            self.logger.debug("Initializing...")
            await self._initialize()

            self._detailed_state = SmartStates._STARTING
            self.logger.debug("Starting...")
            await self._start()

            self._detailed_state = SmartStates.RUNNING
            self.logger.info("Service started")

        except Exception as e:
            self._detailed_state = SmartStates.ERROR
            self.logger.error(f"Failed to start: {e}")
            raise

    async def stop(self) -> None:
        """Simple public API."""
        if self.state == SmartStates.STOPPED:
            return

        try:
            self._detailed_state = SmartStates._STOPPING
            self.logger.debug("Stopping...")
            await self._shutdown()

            self._detailed_state = SmartStates.STOPPED
            self.logger.info("Service stopped")

        except Exception:
            self._detailed_state = SmartStates.ERROR
            raise

    @property
    def state(self) -> SmartStates:
        """Public API only shows simple states."""
        if self._detailed_state.value.startswith("_"):
            # Map internal states to public ones
            if self._detailed_state in (
                SmartStates._INITIALIZING,
                SmartStates._STARTING,
            ):
                return SmartStates.STOPPED  # "Not running yet"
            elif self._detailed_state == SmartStates._STOPPING:
                return SmartStates.RUNNING  # "Still running until fully stopped"
        return self._detailed_state

    @property
    def detailed_state(self) -> SmartStates:
        """Internal API for debugging/monitoring."""
        return self._detailed_state

    async def _initialize(self):
        await asyncio.sleep(0.1)

    async def _start(self):
        await asyncio.sleep(0.1)

    async def _shutdown(self):
        await asyncio.sleep(0.1)


# =============================================================================
# RECOMMENDATION FOR AIPERF
# =============================================================================

"""
FOR AIPERF SERVICES, I RECOMMEND THE HYBRID APPROACH:

✅ SIMPLE PUBLIC API:
   - STOPPED (not running, includes created/initialized)
   - RUNNING (actively running)
   - Error (something failed)

✅ DETAILED INTERNAL TRACKING:
   - Log the detailed phases internally
   - Expose detailed_state property for debugging
   - Use detailed states for timeout detection
   - Use detailed states for cancellation points

✅ BENEFITS:
   - Simple for service implementers
   - Simple for service consumers
   - Rich debugging information when needed
   - Progress tracking for long operations
   - Easy to add more internal states later

This gives you the best of both worlds!
"""


async def demo():
    """Demonstrate the different approaches."""

    print("=== Simple Service ===")
    simple = SimpleService("simple")
    print(f"Initial: {simple.state}")
    await simple.start()
    print(f"After start: {simple.state}")
    await simple.stop()
    print(f"After stop: {simple.state}")

    print("\n=== Smart Service (Hybrid) ===")
    smart = SmartService("smart")
    print(f"Public state: {smart.state}")
    print(f"Detailed state: {smart.detailed_state}")
    await smart.start()
    print(f"Public state: {smart.state}")
    print(f"Detailed state: {smart.detailed_state}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo())
