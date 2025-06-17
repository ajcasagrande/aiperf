# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Comprehensive unit tests for aiohttp client components."""

from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from aiperf.clients.http.aiohttp_client import (
    AioHttpClientMixin,
    AioHttpSSEStreamReader,
)
from aiperf.common.models import (
    GenericHTTPClientConfig,
    SSEMessage,
)

################################################################################
# Fixtures
################################################################################


@pytest.fixture
def http_client_config() -> GenericHTTPClientConfig:
    """Fixture providing a standard HTTP client configuration."""
    return GenericHTTPClientConfig(
        url="http://localhost:8080",
        timeout_ms=30000,
        headers={"Content-Type": "application/json"},
        api_key="test-api-key",
    )


@pytest.fixture
def minimal_config() -> GenericHTTPClientConfig:
    """Fixture providing minimal HTTP client configuration."""
    return GenericHTTPClientConfig(url="http://localhost:8080", timeout_ms=5000)


@pytest.fixture
def ssl_config() -> GenericHTTPClientConfig:
    """Fixture providing HTTPS client configuration."""
    return GenericHTTPClientConfig(
        url="https://api.example.com",
        timeout_ms=60000,
        ssl_options={"verify_mode": "cert_required"},
        headers={"Authorization": "Bearer token123"},
    )


@pytest.fixture
async def aiohttp_client(
    http_client_config: GenericHTTPClientConfig,
) -> AioHttpClientMixin:
    """Fixture providing an AioHttpClientMixin instance."""
    client = AioHttpClientMixin(http_client_config)
    yield client
    await client.cleanup()


@pytest.fixture
def mock_aiohttp_response() -> Mock:
    """Fixture providing a mock aiohttp.ClientResponse."""
    response = Mock(spec=aiohttp.ClientResponse)
    response.status = 200
    response.reason = "OK"
    response.content_type = "application/json"
    response.text = AsyncMock(return_value='{"success": true}')

    # Mock content attribute for SSE streaming
    content_mock = Mock()
    content_mock.at_eof.return_value = False
    content_mock.read = AsyncMock()
    content_mock.readuntil = AsyncMock()
    response.content = content_mock

    return response


@pytest.fixture
def mock_sse_response() -> Mock:
    """Fixture providing a mock SSE response."""
    response = Mock(spec=aiohttp.ClientResponse)
    response.status = 200
    response.reason = "OK"
    response.content_type = "text/event-stream"

    # Mock content for SSE streaming
    content_mock = Mock()
    response.content = content_mock

    return response


@pytest.fixture
def sample_sse_chunks() -> list[tuple[bytes, bytes]]:
    """Fixture providing sample SSE chunks as (first_byte, remaining_chunk) tuples."""
    return [
        (b"d", b"ata: Hello\nevent: message\n\n"),
        (b"d", b"ata: World\nid: msg-2\n\n"),
        (b"d", b"ata: [DONE]\n\n"),
    ]


@pytest.fixture
def mock_tcp_connector() -> Mock:
    """Fixture providing a mock TCP connector."""
    connector = Mock(spec=aiohttp.TCPConnector)
    connector.close = AsyncMock()
    return connector


################################################################################
# Test AioHttpSSEStreamReader
################################################################################


class TestAioHttpSSEStreamReader:
    """Test suite for AioHttpSSEStreamReader class."""

    @pytest.fixture
    def mock_response(self) -> Mock:
        """Fixture providing a mock response for SSE stream testing."""
        response = Mock(spec=aiohttp.ClientResponse)
        content_mock = Mock()
        response.content = content_mock
        return response

    def test_init_stores_response(self, mock_response: Mock) -> None:
        """Test that initialization properly stores the response object."""
        reader = AioHttpSSEStreamReader(mock_response)
        assert reader.response == mock_response

    @pytest.mark.asyncio
    async def test_read_complete_stream_success(self, mock_response: Mock) -> None:
        """Test successful reading of complete SSE stream."""
        # Setup mock to simulate stream data
        sse_data = [
            ("data: Hello\nevent: message", 123456789, 123456790),
            ("data: World\nid: msg-2", 123456791, 123456792),
        ]

        async def mock_aiter():
            for data in sse_data:
                yield data

        with (
            patch.object(
                AioHttpSSEStreamReader, "__aiter__", return_value=mock_aiter()
            ),
            patch("aiperf.clients.http.aiohttp_client.parse_sse_message") as mock_parse,
        ):
            mock_messages = [
                SSEMessage(perf_ns=123456789),
                SSEMessage(perf_ns=123456791),
            ]
            mock_parse.side_effect = mock_messages

            reader = AioHttpSSEStreamReader(mock_response)
            result = await reader.read_complete_stream()

            assert len(result) == 2
            assert all(isinstance(msg, SSEMessage) for msg in result)
            assert mock_parse.call_count == 2

    @pytest.mark.asyncio
    async def test_read_complete_stream_empty(self, mock_response: Mock) -> None:
        """Test reading empty SSE stream."""

        async def mock_aiter():
            return
            yield  # This will never be reached

        with patch.object(
            AioHttpSSEStreamReader, "__aiter__", return_value=mock_aiter()
        ):
            reader = AioHttpSSEStreamReader(mock_response)
            result = await reader.read_complete_stream()

            assert result == []

    @pytest.mark.asyncio
    async def test_aiter_single_chunk(self, mock_response: Mock) -> None:
        """Test __aiter__ with single chunk."""
        # Mock content to simulate single SSE message
        mock_response.content.at_eof.return_value = False
        mock_response.content.read = AsyncMock(return_value=b"d")
        mock_response.content.readuntil = AsyncMock(return_value=b"ata: Hello\n\n")

        with patch("time.perf_counter_ns", side_effect=[123456789, 123456790]):
            reader = AioHttpSSEStreamReader(mock_response)
            chunks = []

            async for chunk in reader:
                chunks.append(chunk)

            assert len(chunks) == 1
            raw_message, first_byte_ns, last_byte_ns = chunks[0]
            assert raw_message == "data: Hello"
            assert first_byte_ns == 123456789
            assert last_byte_ns == 123456790

    @pytest.mark.asyncio
    async def test_aiter_multiple_chunks(
        self, mock_response: Mock, sample_sse_chunks: list[tuple[bytes, bytes]]
    ) -> None:
        """Test __aiter__ with multiple chunks."""
        # Setup mock to return multiple chunks
        mock_response.content.at_eof.side_effect = [False, False, False, True]

        read_calls = []
        readuntil_calls = []
        for first_byte, remaining in sample_sse_chunks:
            read_calls.append(first_byte)
            readuntil_calls.append(remaining)

        mock_response.content.read = AsyncMock(side_effect=read_calls)
        mock_response.content.readuntil = AsyncMock(side_effect=readuntil_calls)

        # Mock timestamps
        timestamps = list(range(123456789, 123456789 + len(sample_sse_chunks) * 2, 1))

        with patch("time.perf_counter_ns", side_effect=timestamps):
            reader = AioHttpSSEStreamReader(mock_response)
            chunks = []

            async for chunk in reader:
                chunks.append(chunk)

            assert len(chunks) == 3

            # Verify each chunk
            expected_messages = [
                "data: Hello\nevent: message",
                "data: World\nid: msg-2",
                "data: [DONE]",
            ]

            for i, (raw_message, _, _) in enumerate(chunks):
                assert raw_message == expected_messages[i]

    @pytest.mark.asyncio
    async def test_aiter_unicode_decode_error(self, mock_response: Mock) -> None:
        """Test __aiter__ handling of Unicode decode errors."""
        # Mock content with invalid UTF-8 bytes
        mock_response.content.at_eof.side_effect = [False, True]
        mock_response.content.read = AsyncMock(return_value=b"\xff")
        mock_response.content.readuntil = AsyncMock(
            return_value=b"\xfe\xfd invalid utf8\n\n"
        )

        with patch("time.perf_counter_ns", side_effect=[123456789, 123456790]):
            reader = AioHttpSSEStreamReader(mock_response)
            chunks = []

            async for chunk in reader:
                chunks.append(chunk)

            assert len(chunks) == 1
            raw_message, _, _ = chunks[0]
            # Should use 'replace' error handling
            assert isinstance(raw_message, str)
            assert "�" in raw_message  # Unicode replacement character

    @pytest.mark.asyncio
    async def test_aiter_empty_chunk(self, mock_response: Mock) -> None:
        """Test __aiter__ with empty chunks."""
        # Mock content that returns empty data
        mock_response.content.at_eof.side_effect = [False, True]
        mock_response.content.read = AsyncMock(return_value=b"")

        reader = AioHttpSSEStreamReader(mock_response)
        chunks = []

        async for chunk in reader:
            chunks.append(chunk)

        assert chunks == []

    @pytest.mark.asyncio
    async def test_aiter_timing_accuracy(self, mock_response: Mock) -> None:
        """Test that __aiter__ captures timing accurately."""
        mock_response.content.at_eof.side_effect = [False, True]
        mock_response.content.read = AsyncMock(return_value=b"d")
        mock_response.content.readuntil = AsyncMock(return_value=b"ata: test\n\n")

        first_timestamp = 123456789
        second_timestamp = 123456990

        with patch(
            "time.perf_counter_ns", side_effect=[first_timestamp, second_timestamp]
        ):
            reader = AioHttpSSEStreamReader(mock_response)
            chunks = []

            async for chunk in reader:
                chunks.append(chunk)

            assert len(chunks) == 1
            _, first_byte_ns, last_byte_ns = chunks[0]
            assert first_byte_ns == first_timestamp
            assert last_byte_ns == second_timestamp
            assert last_byte_ns > first_byte_ns
