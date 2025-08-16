# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import time
import typing
from typing import Any

import httpx

from aiperf.clients.http.defaults import HttpxDefaults
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import SSEFieldType
from aiperf.common.exceptions import NotInitializedError
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import (
    ErrorDetails,
    RequestRecord,
    SSEField,
    SSEMessage,
    TextResponse,
)

################################################################################
# HTTPX HTTP/2 Client
################################################################################


class HttpxClientMixin(AIPerfLoggerMixin):
    """A high-performance HTTP/2 client for communicating with HTTP based REST APIs using httpx.

    This class is optimized for maximum performance with HTTP/2 support, connection sharing,
    and accurate timing measurements, making it ideal for benchmarking scenarios.
    """

    def __init__(self, model_endpoint: ModelEndpointInfo, **kwargs) -> None:
        self.model_endpoint = model_endpoint
        super().__init__(model_endpoint=model_endpoint, **kwargs)

        # Create HTTP/2 optimized limits and socket options
        self.limits = httpx.Limits(
            max_connections=HttpxDefaults.MAX_CONNECTIONS,
            max_keepalive_connections=HttpxDefaults.MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=HttpxDefaults.KEEPALIVE_EXPIRY,
        )

        # Configure timeout settings
        self.timeout = httpx.Timeout(
            connect=self.model_endpoint.endpoint.timeout,
            read=self.model_endpoint.endpoint.timeout,
            write=self.model_endpoint.endpoint.timeout,
            pool=self.model_endpoint.endpoint.timeout,
        )

        self.client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        """Close the client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    def initialize_session(self, headers: dict[str, str]) -> None:
        """Initialize the HTTP/2 client session with optimized settings."""
        self.client = httpx.AsyncClient(
            http2=HttpxDefaults.HTTP2,
            limits=self.limits,
            timeout=self.timeout,
            headers=headers,
            verify=HttpxDefaults.VERIFY_SSL,
            trust_env=HttpxDefaults.TRUST_ENV,
            follow_redirects=HttpxDefaults.FOLLOW_REDIRECTS,
            max_redirects=HttpxDefaults.MAX_REDIRECTS,
        )

    async def post_request(
        self,
        url: str,
        payload: str,
        headers: dict[str, str],
        **kwargs: Any,
    ) -> RequestRecord:
        """Send a streaming or non-streaming POST request to the specified URL with the given payload and headers.

        If the response is an SSE stream, the response will be parsed into a list of SSE messages.
        Otherwise, the response will be parsed into a TextResponse object.
        """

        self.debug(lambda: "Sending HTTP/2 POST request to %s", url)

        record: RequestRecord = RequestRecord(
            start_perf_ns=time.perf_counter_ns(),
        )

        try:
            if not self.client:
                raise NotInitializedError("Client session not initialized")

            # Make HTTP/2 request with precise timing
            record.start_perf_ns = time.perf_counter_ns()

            # Merge headers for this specific request
            request_headers = {**self.client.headers, **headers}

            async with self.client.stream(
                "POST", url, content=payload, headers=request_headers, **kwargs
            ) as response:
                record.status = response.status_code

                # Check for HTTP errors
                if response.status_code != 200:
                    error_text = await response.aread()
                    record.error = ErrorDetails(
                        code=response.status_code,
                        type=response.reason_phrase,
                        message=error_text.decode("utf-8", errors="replace"),
                    )
                    return record

                record.recv_start_perf_ns = time.perf_counter_ns()

                content_type = response.headers.get("content-type", "")
                if content_type.split(";")[0].strip() == "text/event-stream":
                    # Parse SSE stream with optimal performance
                    messages = await HttpxSSEStreamReader(
                        response
                    ).read_complete_stream()
                    record.responses.extend(messages)
                else:
                    raw_response = await response.aread()
                    record.end_perf_ns = time.perf_counter_ns()
                    record.responses.append(
                        TextResponse(
                            perf_ns=record.end_perf_ns,
                            content_type=content_type,
                            text=raw_response.decode("utf-8", errors="replace"),
                        )
                    )
                record.end_perf_ns = time.perf_counter_ns()

        except Exception as e:
            record.end_perf_ns = time.perf_counter_ns()
            self.error("Error in httpx request: %s", e)
            record.error = ErrorDetails(type=e.__class__.__name__, message=str(e))

        return record


_logger = AIPerfLogger(__name__)


class HttpxSSEStreamReader:
    """A helper class for reading an SSE stream from an httpx.Response object.

    This class is optimized for maximum performance with HTTP/2 support and accurate timing measurements,
    making it ideal for benchmarking scenarios.
    """

    def __init__(self, response: httpx.Response):
        self.response = response

    async def read_complete_stream(self) -> list[SSEMessage]:
        """Read the complete SSE stream in a performant manner and return a list of
        SSE messages that contain the most accurate timestamp data possible.

        Returns:
            A list of SSE messages.
        """
        messages: list[SSEMessage] = []

        async for raw_message, first_byte_ns in self.__aiter__():
            # Parse the raw SSE message into a SSEMessage object
            message = parse_sse_message(raw_message, first_byte_ns)
            messages.append(message)

        return messages

    async def __aiter__(self) -> typing.AsyncIterator[tuple[str, int]]:
        """Iterate over the SSE stream in a performant manner and return a tuple of the
        raw SSE message and the perf_counter_ns of the first byte.
        This provides the most accurate timing information possible for HTTP/2 streams.

        Returns:
            An async iterator of tuples of the raw SSE message, and the perf_counter_ns of the first byte
        """
        buffer = b""

        async for chunk in self.response.aiter_bytes(chunk_size=1):
            chunk_ns_first_byte = time.perf_counter_ns()
            buffer += chunk

            # Process complete SSE messages (delimited by \n\n)
            while b"\n\n" in buffer:
                message_bytes, buffer = buffer.split(b"\n\n", 1)

                if not message_bytes:
                    continue

                try:
                    # Use the fastest available decoder
                    yield (
                        message_bytes.decode("utf-8").strip(),
                        chunk_ns_first_byte,
                    )
                except UnicodeDecodeError:
                    # Handle potential encoding issues gracefully
                    yield (
                        message_bytes.decode("utf-8", errors="replace").strip(),
                        chunk_ns_first_byte,
                    )

        # Process any remaining data in buffer
        if buffer.strip():
            try:
                yield (
                    buffer.decode("utf-8").strip(),
                    time.perf_counter_ns(),
                )
            except UnicodeDecodeError:
                yield (
                    buffer.decode("utf-8", errors="replace").strip(),
                    time.perf_counter_ns(),
                )


def parse_sse_message(raw_message: str, perf_ns: int) -> SSEMessage:
    """Parse a raw SSE message into an SSEMessage object.

    Parsing logic based on official HTML SSE Living Standard:
    https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream
    """

    message = SSEMessage(perf_ns=perf_ns)
    for line in raw_message.split("\n"):
        if not (line := line.strip()):
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

        message.packets.append(SSEField(name=field_name.strip(), value=value.strip()))

    return message
