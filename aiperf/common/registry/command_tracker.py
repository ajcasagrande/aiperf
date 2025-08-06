# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time
import weakref
from collections import defaultdict
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from pydantic import BaseModel, Field

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import (
    CaseInsensitiveStrEnum,
    CommandResponseStatus,
    CommandType,
)
from aiperf.common.hooks import background_task
from aiperf.common.messages import CommandResponse
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.models import ErrorDetails


class CommandState(CaseInsensitiveStrEnum):
    """States that a command can be in during its lifecycle."""

    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class CommandTrackingInfo(BaseModel):
    """Information about a tracked command."""

    command_id: str = Field(description="Unique command identifier")
    command_type: CommandType = Field(description="Type of command")
    target_service_ids: set[str] = Field(
        default_factory=set, description="Target service IDs for this command"
    )
    state: CommandState = Field(
        default=CommandState.PENDING, description="Current command state"
    )
    created_at: float = Field(
        default_factory=time.time, description="Timestamp when command was created"
    )
    sent_at: float | None = Field(
        default=None, description="Timestamp when command was sent"
    )
    timeout_at: float | None = Field(
        default=None, description="Timestamp when command will timeout"
    )
    responses_received: dict[str, CommandResponse] = Field(
        default_factory=dict, description="Responses received from services"
    )
    pending_service_ids: set[str] = Field(
        default_factory=set, description="Service IDs still pending responses"
    )
    error_details: ErrorDetails | None = Field(
        default=None, description="Error details if command failed"
    )


class CommandExecutionResult(BaseModel):
    """Result of command execution."""

    command_id: str = Field(description="Command identifier")
    success: bool = Field(description="Whether command executed successfully")
    responses: list[CommandResponse] = Field(
        default_factory=list, description="All responses received"
    )
    error_details: ErrorDetails | None = Field(
        default=None, description="Error details if execution failed"
    )
    execution_time: float = Field(
        default=0.0, description="Total execution time in seconds"
    )
    response_count: int = Field(default=0, description="Number of responses received")


class CommandTrackerStats(BaseModel):
    """Statistics about the command tracker state."""

    total_commands: int = Field(
        default=0, description="Total number of tracked commands"
    )
    active_commands: int = Field(
        default=0, description="Number of currently active commands"
    )
    completed_commands: int = Field(
        default=0, description="Number of completed commands"
    )
    failed_commands: int = Field(default=0, description="Number of failed commands")
    timeout_commands: int = Field(default=0, description="Number of timed out commands")
    commands_by_type: dict[CommandType, int] = Field(
        default_factory=dict, description="Command counts by type"
    )
    commands_by_state: dict[CommandState, int] = Field(
        default_factory=dict, description="Command counts by state"
    )
    average_response_time: float = Field(
        default=0.0, description="Average response time in seconds"
    )
    last_updated: float = Field(
        default_factory=time.time, description="Timestamp of last stats update"
    )


class CommandTracker(AIPerfLifecycleMixin):
    """Thread-safe command tracker with atomic operations and automatic cleanup."""

    def __init__(
        self,
        default_timeout: float = 30.0,
        cleanup_interval: float = 300.0,
        max_completed_history: int = 1000,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._logger = AIPerfLogger(self.__class__.__name__)

        self._default_timeout = default_timeout
        self._cleanup_interval = cleanup_interval
        self._max_completed_history = max_completed_history

        self._active_commands: dict[str, CommandTrackingInfo] = {}
        self._completed_commands: dict[str, CommandTrackingInfo] = {}
        self._command_futures: dict[str, asyncio.Future[CommandExecutionResult]] = {}
        self._multi_response_futures: dict[
            str, dict[str, asyncio.Future[CommandResponse]]
        ] = {}

        self._global_lock = asyncio.RLock()
        self._command_locks: dict[str, asyncio.Lock] = {}
        self._lock_cleanup_refs: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )

        self._completion_callbacks: list[tuple[weakref.ReferenceType, Callable]] = []
        self._timeout_callbacks: list[tuple[weakref.ReferenceType, Callable]] = []

        self._processed_command_ids: dict[str, float] = {}
        self._stats = CommandTrackerStats()
        self._stats_dirty = True

    @asynccontextmanager
    async def _command_lock(self, command_id: str) -> AsyncGenerator[None, None]:
        """Get or create a per-command lock with automatic cleanup."""
        async with self._global_lock:
            if command_id not in self._command_locks:
                lock = asyncio.Lock()
                self._command_locks[command_id] = lock
                self._lock_cleanup_refs[command_id] = lock

        lock = self._command_locks[command_id]
        async with lock:
            yield

        async with self._global_lock:
            if (
                command_id in self._command_locks
                and command_id not in self._active_commands
            ):
                del self._command_locks[command_id]

    async def start_tracking_command(
        self,
        command_id: str,
        command_type: CommandType,
        target_service_ids: set[str] | None = None,
        timeout: float | None = None,
    ) -> bool:
        """Start tracking a command with specified targets."""
        async with self._command_lock(command_id), self._global_lock:
            if command_id in self._active_commands:
                return False

            timeout_value = timeout or self._default_timeout
            target_ids = target_service_ids or set()

            tracking_info = CommandTrackingInfo(
                command_id=command_id,
                command_type=command_type,
                target_service_ids=target_ids.copy(),
                pending_service_ids=target_ids.copy(),
                timeout_at=time.time() + timeout_value,
            )

            self._active_commands[command_id] = tracking_info

            if target_ids:
                self._multi_response_futures[command_id] = {
                    service_id: asyncio.Future[CommandResponse]()
                    for service_id in target_ids
                }
            else:
                self._command_futures[command_id] = asyncio.Future[
                    CommandExecutionResult
                ]()

            self._stats_dirty = True
            return True

    async def mark_command_sent(self, command_id: str) -> bool:
        """Mark a command as sent."""
        async with self._command_lock(command_id), self._global_lock:
            tracking_info = self._active_commands.get(command_id)
            if tracking_info is None:
                return False

            tracking_info.sent_at = time.time()
            tracking_info.state = CommandState.SENT
            self._stats_dirty = True
            return True

    async def record_response(
        self,
        command_id: str,
        service_id: str,
        response: CommandResponse,
    ) -> bool:
        """Record a response for a command from a specific service."""
        async with self._command_lock(command_id), self._global_lock:
            tracking_info = self._active_commands.get(command_id)
            if tracking_info is None:
                return False

            if service_id not in tracking_info.target_service_ids:
                self._logger.warning(
                    "Received response from unexpected service %s for command %s",
                    service_id,
                    command_id,
                )
                return False

            tracking_info.responses_received[service_id] = response
            tracking_info.pending_service_ids.discard(service_id)

            if service_id in self._multi_response_futures.get(command_id, {}):
                future = self._multi_response_futures[command_id][service_id]
                if not future.done():
                    future.set_result(response)

            if response.status == CommandResponseStatus.ACKNOWLEDGED:
                tracking_info.state = CommandState.ACKNOWLEDGED
            elif response.status == CommandResponseStatus.FAILURE:
                tracking_info.state = CommandState.FAILED
                if hasattr(response, "error"):
                    tracking_info.error_details = response.error

            if not tracking_info.pending_service_ids:
                await self._complete_command(command_id, tracking_info)

            self._stats_dirty = True
            return True

    async def record_single_response(
        self,
        command_id: str,
        response: CommandResponse,
    ) -> bool:
        """Record a response for a single-target command."""
        async with self._command_lock(command_id), self._global_lock:
            tracking_info = self._active_commands.get(command_id)
            if tracking_info is None:
                return False

            tracking_info.responses_received[response.service_id] = response

            if response.status == CommandResponseStatus.SUCCESS:
                tracking_info.state = CommandState.COMPLETED
            elif response.status == CommandResponseStatus.FAILURE:
                tracking_info.state = CommandState.FAILED
                if hasattr(response, "error"):
                    tracking_info.error_details = response.error

            await self._complete_command(command_id, tracking_info)
            self._stats_dirty = True
            return True

    async def cancel_command(self, command_id: str) -> bool:
        """Cancel a command and clean up resources."""
        async with self._command_lock(command_id), self._global_lock:
            tracking_info = self._active_commands.get(command_id)
            if tracking_info is None:
                return False

            tracking_info.state = CommandState.CANCELLED
            await self._complete_command(command_id, tracking_info)
            self._stats_dirty = True
            return True

    async def wait_for_command_completion(
        self,
        command_id: str,
        timeout: float | None = None,
    ) -> CommandExecutionResult | None:
        """Wait for a command to complete and return the result."""
        async with self._global_lock:
            if command_id in self._command_futures:
                future = self._command_futures[command_id]
            elif command_id in self._multi_response_futures:
                future = self._create_multi_response_future(command_id)
            else:
                return None

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            await self._handle_command_timeout(command_id)
            return None

    async def wait_for_all_responses(
        self,
        command_id: str,
        timeout: float | None = None,
    ) -> list[CommandResponse]:
        """Wait for all responses to a multi-target command."""
        async with self._global_lock:
            multi_futures = self._multi_response_futures.get(command_id)
            if not multi_futures:
                return []

            futures = list(multi_futures.values())

        try:
            responses = await asyncio.wait_for(
                asyncio.gather(*futures, return_exceptions=True),
                timeout=timeout,
            )
            return [r for r in responses if isinstance(r, CommandResponse)]
        except asyncio.TimeoutError:
            await self._handle_command_timeout(command_id)
            return []

    async def get_command_info(self, command_id: str) -> CommandTrackingInfo | None:
        """Get tracking information for a command."""
        async with self._global_lock:
            info = self._active_commands.get(command_id)
            if info is None:
                info = self._completed_commands.get(command_id)
            return info.model_copy() if info else None

    async def get_active_commands(self) -> list[CommandTrackingInfo]:
        """Get all currently active commands."""
        async with self._global_lock:
            return [info.model_copy() for info in self._active_commands.values()]

    async def is_command_processed(self, command_id: str) -> bool:
        """Check if a command has already been processed."""
        async with self._global_lock:
            return command_id in self._processed_command_ids

    async def mark_command_processed(self, command_id: str) -> None:
        """Mark a command as processed to prevent duplicates."""
        async with self._global_lock:
            self._processed_command_ids[command_id] = time.time()

    async def get_tracker_stats(
        self, force_update: bool = False
    ) -> CommandTrackerStats:
        """Get current tracker statistics."""
        if force_update or self._stats_dirty:
            await self._update_stats()

        return self._stats.model_copy()

    async def add_completion_callback(
        self,
        callback: Callable[[str, CommandExecutionResult], Any],
        weak_ref: bool = True,
    ) -> None:
        """Add a callback for command completion events."""
        async with self._global_lock:
            if weak_ref:
                ref = weakref.ref(callback)
                self._completion_callbacks.append((ref, None))
            else:
                self._completion_callbacks.append((None, callback))

    async def add_timeout_callback(
        self,
        callback: Callable[[str, CommandTrackingInfo], Any],
        weak_ref: bool = True,
    ) -> None:
        """Add a callback for command timeout events."""
        async with self._global_lock:
            if weak_ref:
                ref = weakref.ref(callback)
                self._timeout_callbacks.append((ref, None))
            else:
                self._timeout_callbacks.append((None, callback))

    async def _complete_command(
        self,
        command_id: str,
        tracking_info: CommandTrackingInfo,
    ) -> None:
        """Move a command from active to completed state."""
        del self._active_commands[command_id]

        if tracking_info.state in (CommandState.PENDING, CommandState.SENT):
            tracking_info.state = CommandState.COMPLETED

        self._completed_commands[command_id] = tracking_info

        if len(self._completed_commands) > self._max_completed_history:
            oldest_commands = sorted(
                self._completed_commands.items(), key=lambda x: x[1].created_at
            )[: len(self._completed_commands) - self._max_completed_history]

            for old_command_id, _ in oldest_commands:
                del self._completed_commands[old_command_id]

        execution_result = CommandExecutionResult(
            command_id=command_id,
            success=tracking_info.state == CommandState.COMPLETED,
            responses=list(tracking_info.responses_received.values()),
            error_details=tracking_info.error_details,
            execution_time=(
                time.time() - tracking_info.created_at
                if tracking_info.created_at
                else 0.0
            ),
            response_count=len(tracking_info.responses_received),
        )

        if command_id in self._command_futures:
            future = self._command_futures.pop(command_id)
            if not future.done():
                future.set_result(execution_result)

        if command_id in self._multi_response_futures:
            for future in self._multi_response_futures[command_id].values():
                if not future.done():
                    future.cancel()
            del self._multi_response_futures[command_id]

        await self._notify_completion_callbacks(command_id, execution_result)

    async def _create_multi_response_future(
        self,
        command_id: str,
    ) -> asyncio.Future[CommandExecutionResult]:
        """Create a future that completes when all responses are received."""

        async def wait_for_all():
            multi_futures = self._multi_response_futures.get(command_id, {})
            if not multi_futures:
                return CommandExecutionResult(
                    command_id=command_id,
                    success=False,
                    execution_time=0.0,
                    response_count=0,
                )

            responses = await asyncio.gather(
                *multi_futures.values(),
                return_exceptions=True,
            )

            valid_responses = [r for r in responses if isinstance(r, CommandResponse)]
            success = all(
                r.status != CommandResponseStatus.FAILURE for r in valid_responses
            )

            tracking_info = self._active_commands.get(command_id)

            return CommandExecutionResult(
                command_id=command_id,
                success=success,
                responses=valid_responses,
                execution_time=(
                    time.time() - tracking_info.created_at
                    if tracking_info and tracking_info.created_at
                    else 0.0
                ),
                response_count=len(valid_responses),
            )

        return asyncio.create_task(wait_for_all())

    async def _handle_command_timeout(self, command_id: str) -> None:
        """Handle command timeout by updating state and notifying callbacks."""
        async with self._command_lock(command_id), self._global_lock:
            tracking_info = self._active_commands.get(command_id)
            if tracking_info is None:
                return

            tracking_info.state = CommandState.TIMEOUT
            tracking_info.error_details = ErrorDetails(
                type=CommandState.TIMEOUT,
                message=f"Command {command_id} timed out",
            )

            await self._complete_command(command_id, tracking_info)
            await self._notify_timeout_callbacks(command_id, tracking_info)

    @background_task(interval=lambda self: self._cleanup_interval)
    async def _cleanup_expired_data(self) -> None:
        """Clean up expired processed command IDs and timed out commands."""
        current_time = time.time()
        cutoff_time = current_time - self._cleanup_interval

        async with self._global_lock:
            expired_processed_ids = [
                cmd_id
                for cmd_id, timestamp in self._processed_command_ids.items()
                if timestamp < cutoff_time
            ]

            for cmd_id in expired_processed_ids:
                del self._processed_command_ids[cmd_id]

            timed_out_commands = []
            for command_id, tracking_info in list(self._active_commands.items()):
                if tracking_info.timeout_at and current_time > tracking_info.timeout_at:
                    timed_out_commands.append(command_id)

            for command_id in timed_out_commands:
                await self._handle_command_timeout(command_id)

    async def _update_stats(self) -> None:
        """Update tracker statistics."""
        async with self._global_lock:
            commands_by_type = defaultdict(int)
            commands_by_state = defaultdict(int)
            total_response_time = 0.0
            response_count = 0

            all_commands = {**self._active_commands, **self._completed_commands}

            for tracking_info in all_commands.values():
                commands_by_type[tracking_info.command_type] += 1
                commands_by_state[tracking_info.state] += 1

                if tracking_info.sent_at and tracking_info.responses_received:
                    for response in tracking_info.responses_received.values():
                        if hasattr(response, "timestamp") and response.timestamp:
                            response_time = response.timestamp - tracking_info.sent_at
                            total_response_time += response_time
                            response_count += 1

            self._stats = CommandTrackerStats(
                total_commands=len(all_commands),
                active_commands=len(self._active_commands),
                completed_commands=len(
                    [
                        info
                        for info in all_commands.values()
                        if info.state == CommandState.COMPLETED
                    ]
                ),
                failed_commands=len(
                    [
                        info
                        for info in all_commands.values()
                        if info.state == CommandState.FAILED
                    ]
                ),
                timeout_commands=len(
                    [
                        info
                        for info in all_commands.values()
                        if info.state == CommandState.TIMEOUT
                    ]
                ),
                commands_by_type=dict(commands_by_type),
                commands_by_state=dict(commands_by_state),
                average_response_time=(
                    total_response_time / response_count if response_count > 0 else 0.0
                ),
                last_updated=time.time(),
            )
            self._stats_dirty = False

    async def _notify_completion_callbacks(
        self,
        command_id: str,
        result: CommandExecutionResult,
    ) -> None:
        """Notify registered callbacks of command completion."""
        cleanup_refs = []

        for weak_ref, strong_ref in self._completion_callbacks:
            callback = None
            if weak_ref is not None:
                callback = weak_ref()
                if callback is None:
                    cleanup_refs.append((weak_ref, strong_ref))
                    continue
            else:
                callback = strong_ref

            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(command_id, result)
                else:
                    callback(command_id, result)
            except Exception as e:
                self._logger.exception(
                    "Completion callback failed for command %s: %s",
                    command_id,
                    e,
                )

        for ref_tuple in cleanup_refs:
            self._completion_callbacks.remove(ref_tuple)

    async def _notify_timeout_callbacks(
        self,
        command_id: str,
        tracking_info: CommandTrackingInfo,
    ) -> None:
        """Notify registered callbacks of command timeout."""
        cleanup_refs = []

        for weak_ref, strong_ref in self._timeout_callbacks:
            callback = None
            if weak_ref is not None:
                callback = weak_ref()
                if callback is None:
                    cleanup_refs.append((weak_ref, strong_ref))
                    continue
            else:
                callback = strong_ref

            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(command_id, tracking_info)
                else:
                    callback(command_id, tracking_info)
            except Exception as e:
                self._logger.exception(
                    "Timeout callback failed for command %s: %s",
                    command_id,
                    e,
                )

        for ref_tuple in cleanup_refs:
            self._timeout_callbacks.remove(ref_tuple)
