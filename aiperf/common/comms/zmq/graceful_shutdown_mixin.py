# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Graceful Shutdown Mixin for ZMQ clients to prevent message dropping during shutdown.

This mixin ensures that:
1. ZMQ operations are shutdown-aware
2. No new operations start during shutdown
3. Proper cancellation handling for graceful shutdown
"""

import asyncio
from typing import Any


class GracefulShutdownMixin:
    """
    Simplified mixin to handle graceful shutdown of ZMQ operations.

    Prevents operations from starting during shutdown and provides
    shutdown-aware ZMQ operation wrappers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Shutdown coordination
        self._shutdown_initiated = asyncio.Event()
        self._shutdown_grace_period = 5.0  # seconds

    async def _graceful_zmq_recv(
        self, socket, timeout: float = None, multipart: bool = False
    ) -> Any:
        """
        Gracefully receive from a ZMQ socket with shutdown awareness.

        Args:
            socket: The ZMQ socket to receive from
            timeout: Optional timeout for the receive operation
            multipart: Whether to receive multipart messages

        Returns:
            The received message
        """
        # Check if shutdown is initiated before starting operation
        if self._shutdown_initiated.is_set():
            raise asyncio.CancelledError("Shutdown in progress")

        try:
            if multipart:
                if timeout:
                    result = await asyncio.wait_for(
                        socket.recv_multipart(), timeout=timeout
                    )
                else:
                    result = await socket.recv_multipart()
            elif hasattr(socket, "recv_string"):
                if timeout:
                    result = await asyncio.wait_for(
                        socket.recv_string(), timeout=timeout
                    )
                else:
                    result = await socket.recv_string()
            else:
                if timeout:
                    result = await asyncio.wait_for(socket.recv(), timeout=timeout)
                else:
                    result = await socket.recv()

            return result

        except asyncio.CancelledError:
            # Check if this is due to shutdown
            if self._shutdown_initiated.is_set():
                self.debug("ZMQ recv cancelled due to graceful shutdown")
            raise

    async def _graceful_zmq_send(self, socket, message, timeout: float = None) -> None:
        """
        Gracefully send to a ZMQ socket with shutdown awareness.

        Args:
            socket: The ZMQ socket to send to
            message: The message to send
            timeout: Optional timeout for the send operation
        """
        # Check if shutdown is initiated before starting operation
        if self._shutdown_initiated.is_set():
            raise asyncio.CancelledError("Shutdown in progress")

        try:
            if hasattr(socket, "send_string") and isinstance(message, str):
                if timeout:
                    await asyncio.wait_for(socket.send_string(message), timeout=timeout)
                else:
                    await socket.send_string(message)
            elif hasattr(socket, "send_multipart") and isinstance(
                message, (list, tuple)
            ):
                if timeout:
                    await asyncio.wait_for(
                        socket.send_multipart(message), timeout=timeout
                    )
                else:
                    await socket.send_multipart(message)
            else:
                if timeout:
                    await asyncio.wait_for(socket.send(message), timeout=timeout)
                else:
                    await socket.send(message)

        except asyncio.CancelledError:
            # Check if this is due to shutdown
            if self._shutdown_initiated.is_set():
                self.debug("ZMQ send cancelled due to graceful shutdown")
            raise

    async def _graceful_shutdown_zmq_operations(self) -> None:
        """
        Initiate graceful shutdown of ZMQ operations.

        This signals to all ZMQ operation wrappers that shutdown has begun
        and they should not start new operations.
        """
        self.debug("Initiating graceful ZMQ shutdown...")

        # Signal shutdown to prevent new operations
        self._shutdown_initiated.set()

        # Give a brief moment for any in-flight operations to notice the shutdown
        await asyncio.sleep(0.1)

        self.debug("Graceful ZMQ shutdown completed")
