#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging
import socket
import time
import typing
from typing import Any

import aiohttp

from aiperf.common.record_models import SSEField, SSEFieldType, SSEMessage

logger = logging.getLogger(__name__)


class AioHttpSSEStreamReader:
    def __init__(self, response: aiohttp.ClientResponse):
        self.response = response

    async def read_complete_stream(self) -> list[SSEMessage]:
        """Read the complete SSE stream in a performant manner and return a list of
        SSE messages that contain the most accurate timestamp data possible.

        Returns:
            A list of SSE messages.
        """
        messages: list[SSEMessage] = []

        # Parsing logic based on official HTML SSE Living Standard:
        # https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream

        async for raw_message, first_byte_ns, _ in self.__aiter__():
            # logger.error("Byte range: %.3f micros", (last_byte_ns - first_byte_ns) / 1000)
            # Parse the raw SSE message into a SSEMessage object
            message = SSEMessage(perf_ns=first_byte_ns)
            for line in raw_message.split("\n"):
                if not line:
                    continue

                parts = line.split(":", 1)
                if len(parts) < 2:
                    # Fields without a colon have no value, so the whole line is the field name
                    message.packets.append(SSEField(name=parts[0].strip(), value=None))
                    continue

                field_name, value = parts

                if field_name == "":
                    # Field name is empty, so this is a comment
                    field_name = SSEFieldType.COMMENT

                message.packets.append(
                    SSEField(name=field_name.strip(), value=value.strip())
                )

            messages.append(message)

        return messages

    # async def __aiter__(self, chunk_size: int = 1024 * 16) -> typing.AsyncIterator[tuple[str, int, int]]:
    #     """Iterate over the SSE stream in a performant manner and return a tuple of the
    #     raw SSE message, the perf_counter_ns of the first byte, and the perf_counter_ns of the last byte.
    #     This provides the most accurate timing information possible without any delays due to the nature of
    #     the aiohttp library. The first byte is read immediately to capture the timestamp of the first byte,
    #     and the last byte is read after the rest of the chunk is read to capture the timestamp of the last byte.

    #     Returns:
    #         An async iterator of tuples of the raw SSE message, the perf_counter_ns of the first byte, and the perf_counter_ns of the last byte.
    #     """

    #     while not self.response.content.at_eof():
    #         # Read the first byte of the SSE stream
    #         chunk = await self.response.content.read(500)
    #         chunk_ns_first_byte = time.perf_counter_ns()
    #         if not chunk:
    #             break
    #         if not chunk.endswith(b"\n\n"):
    #             logger.error("Chunk does not end with a blank line: %s", chunk)
    #             break

    #         try:
    #             # Use the fastest available decoder
    #             yield chunk.decode("utf-8").strip(), chunk_ns_first_byte, chunk_ns_first_byte
    #         except UnicodeDecodeError:
    #             # Handle potential encoding issues gracefully
    #             yield chunk.decode("utf-8", errors="replace").strip(), chunk_ns_first_byte, chunk_ns_first_byte

    # # # Read the rest of the SSE stream until the next blank line
    # # if chunk_len > 0:
    # #     chunk = b""
    # #     while True:
    # #         segment = await self.response.content.read(chunk_len)
    # #         if not segment:
    # #             break
    # #         chunk += segment
    # # else:
    # # chunk = await self.response.content.readuntil(b"\n\n")
    # chunk = await self.response.content.read(chunk_size)
    # chunk_ns_last_byte = time.perf_counter_ns()

    # if not chunk:
    #     break
    # chunk = chunk + chunk

    # try:
    #     # Use the fastest available decoder
    #     yield chunk.decode("utf-8").strip(), chunk_ns_first_byte, chunk_ns_last_byte
    # except UnicodeDecodeError:
    #     # Handle potential encoding issues gracefully
    #     yield chunk.decode("utf-8", errors="replace").strip(), chunk_ns_first_byte, chunk_ns_last_byte

    async def __aiter__(
        self, chunk_size: int = 8192
    ) -> typing.AsyncIterator[tuple[str, int, int]]:
        """Iterate over the SSE stream in a performant manner and return a tuple of the
        raw SSE message, the perf_counter_ns of the first byte, and the perf_counter_ns of the last byte.
        This provides the most accurate timing information possible without any delays due to the nature of
        the aiohttp library. The first byte is read immediately to capture the timestamp of the first byte,
        and the last byte is read after the rest of the chunk is read to capture the timestamp of the last byte.

        Returns:
            An async iterator of tuples of the raw SSE message, the perf_counter_ns of the first byte, and the perf_counter_ns of the last byte.
        """

        while not self.response.content.at_eof():
            # Read the first byte of the SSE stream
            first_byte = await self.response.content.read(1)
            chunk_ns_first_byte = time.perf_counter_ns()
            if not first_byte:
                break

            chunk = await self.response.content.readuntil(b"\n\n")
            chunk_ns_last_byte = time.perf_counter_ns()

            if not chunk:
                break
            chunk = first_byte + chunk

            try:
                # Use the fastest available decoder
                yield (
                    chunk.decode("utf-8").strip(),
                    chunk_ns_first_byte,
                    chunk_ns_last_byte,
                )
            except UnicodeDecodeError:
                # Handle potential encoding issues gracefully
                yield (
                    chunk.decode("utf-8", errors="replace").strip(),
                    chunk_ns_first_byte,
                    chunk_ns_last_byte,
                )

    # async def __aiter__(self) -> typing.AsyncIterator[tuple[str, int]]:
    #     """Iterate over the SSE stream in a performant manner and return a tuple of the
    #     raw SSE message and the perf_counter_ns of the chunk. This provides the most
    #     accurate timing information possible without any delays due to the nature of
    #     the aiohttp library.

    #     Returns:
    #         An async iterator of tuples of the raw SSE message and the perf_counter_ns of the chunk.
    #     """
    #     while not self.response.content.at_eof():

    #         # Wait for the next chunk to be available and immediately capture the timestamp.
    #         # This will give us the most accurate timing information possible without any delays.
    #         # due to the nature of the aiohttp library, this is the best we can do.
    #         # await self.response.content._wait("read")
    #         # chunk_ns = time.perf_counter_ns()

    #         # In SSE streams, each message is delimited by a blank line (\n\n).
    #         # Read the full raw SSE message.
    #         chunk = await self.response.content.readuntil(b"\n\n")
    #         chunk_ns = time.perf_counter_ns()

    #         if not chunk:
    #             break

    #         try:
    #             # Use the fastest available decoder
    #             yield chunk.decode("utf-8").strip(), chunk_ns
    #         except UnicodeDecodeError:
    #             # Handle potential encoding issues gracefully
    #             yield chunk.decode("utf-8", errors="replace").strip(), chunk_ns


def create_tcp_connector(**kwargs) -> aiohttp.TCPConnector:
    """Create a new connector with the given configuration."""

    def socket_factory(addr_info):
        """Custom socket factory optimized for SSE streaming performance."""
        family, type_, proto, _, _ = addr_info
        sock = socket.socket(family=family, type=type_, proto=proto)

        # Low-latency optimizations for streaming
        sock.setsockopt(
            socket.SOL_TCP, socket.TCP_NODELAY, 1
        )  # Disable Nagle's algorithm

        # Connection keepalive settings for long-lived SSE connections
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Enable keepalive

        # Fine-tune keepalive timing (Linux-specific)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(
                socket.SOL_TCP, socket.TCP_KEEPIDLE, 600
            )  # Start keepalive after 10 min idle
            sock.setsockopt(
                socket.SOL_TCP, socket.TCP_KEEPINTVL, 60
            )  # Keepalive interval: 60 seconds
            sock.setsockopt(
                socket.SOL_TCP, socket.TCP_KEEPCNT, 3
            )  # 3 failed keepalive probes = dead

        # Buffer size optimizations for streaming
        sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 16
        )  # 87380)   # 85KB receive buffer
        sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 16
        )  # 65536)   # 64KB send buffer

        # Linux-specific TCP optimizations
        if hasattr(socket, "TCP_QUICKACK"):
            sock.setsockopt(socket.SOL_TCP, socket.TCP_QUICKACK, 1)  # Quick ACK mode

        if hasattr(socket, "TCP_USER_TIMEOUT"):
            sock.setsockopt(
                socket.SOL_TCP, socket.TCP_USER_TIMEOUT, 30000
            )  # 30 sec timeout

        return sock

    default_kwargs: dict[str, Any] = {
        "limit": 2500,
        "limit_per_host": 2500,
        "ttl_dns_cache": 300,
        "use_dns_cache": True,
        "enable_cleanup_closed": False,
        "force_close": False,
        "keepalive_timeout": 300,
        "happy_eyeballs_delay": None,
        "family": socket.AF_INET,
        "socket_factory": socket_factory,
    }

    default_kwargs.update(kwargs)

    return aiohttp.TCPConnector(
        **default_kwargs,
    )
