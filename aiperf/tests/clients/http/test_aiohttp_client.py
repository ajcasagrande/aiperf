# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Comprehensive unit tests for aiohttp client components."""

import asyncio
import json
import socket
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest

from aiperf.clients.http.aiohttp_client import (
    AioHttpClientMixin,
    AioHttpSSEStreamReader,
    create_tcp_connector,
)
from aiperf.common.models import (
    GenericHTTPClientConfig,
    RequestRecord,
    SSEMessage,
    TextResponse,
)

################################################################################
# Custom Assertions and Test Helpers
################################################################################
#
# This section contains custom assertion functions and helper methods to reduce
# code duplication throughout the test suite. Key improvements include:
#
# 1. assert_successful_request_record() - Standardizes checking successful requests
# 2. assert_error_request_record() - Standardizes checking error requests
# 3. create_mock_response() - Creates standardized mock responses
# 4. create_mock_sse_response() - Creates standardized SSE mock responses
# 5. setup_mock_session() - Unified session setup for all HTTP methods
# 6. assert_socket_options_called() - Simplifies socket option verification
#
# These helpers eliminate ~200+ lines of duplicated code and make tests more
# readable and maintainable.
################################################################################


def assert_successful_request_record(
    record: RequestRecord,
    expected_status: int = 200,
    expected_response_count: int = 1,
    expected_response_type: type = TextResponse,
) -> None:
    """Assert that a RequestRecord represents a successful request."""
    assert isinstance(record, RequestRecord)
    assert record.status == expected_status
    assert record.error is None
    assert len(record.responses) == expected_response_count
    assert record.start_perf_ns is not None
    assert record.end_perf_ns is not None

    if expected_response_count > 0:
        if expected_response_type == TextResponse:
            assert all(isinstance(resp, TextResponse) for resp in record.responses)
        elif expected_response_type == SSEMessage:
            assert all(isinstance(resp, SSEMessage) for resp in record.responses)


def assert_error_request_record(
    record: RequestRecord,
    expected_error_code: int | None = None,
    expected_error_type: str | None = None,
    expected_error_message: str | None = None,
) -> None:
    """Assert that a RequestRecord represents a failed request."""
    assert isinstance(record, RequestRecord)
    assert record.error is not None
    assert len(record.responses) == 0

    if expected_error_code is not None:
        assert record.error.code == expected_error_code
    if expected_error_type is not None:
        assert record.error.type == expected_error_type
    if expected_error_message is not None:
        assert record.error.message == expected_error_message


def create_mock_response(
    status: int = 200,
    reason: str = "OK",
    content_type: str = "application/json",
    text_content: str = '{"success": true}',
) -> Mock:
    """Create a standardized mock aiohttp.ClientResponse."""
    response = Mock(spec=aiohttp.ClientResponse)
    response.status = status
    response.reason = reason
    response.content_type = content_type
    response.text = AsyncMock(return_value=text_content)

    # Mock content attribute for SSE streaming
    content_mock = Mock()
    content_mock.at_eof.return_value = False
    content_mock.read = AsyncMock()
    content_mock.readuntil = AsyncMock()
    response.content = content_mock

    return response


def create_mock_sse_response() -> Mock:
    """Create a standardized mock SSE response."""
    response = Mock(spec=aiohttp.ClientResponse)
    response.status = 200
    response.reason = "OK"
    response.content_type = "text/event-stream"

    # Mock content for SSE streaming
    content_mock = Mock()
    response.content = content_mock

    return response


def setup_mock_session(
    mock_session_class: Mock,
    mock_response: Mock,
    methods: list[str] | None = None,
) -> AsyncMock:
    """
    Simplified helper to set up aiohttp session mocks with proper async context manager support.

    Args:
        mock_session_class: The mocked aiohttp.ClientSession class
        mock_response: The mock response object to return
        methods: List of HTTP methods to mock (defaults to common ones)

    Returns:
        The mock session object
    """
    if methods is None:
        methods = ["get", "post", "put", "patch", "delete", "head", "options"]

    mock_session = AsyncMock()

    # Create a factory function that accepts the ClientSession parameters and returns the context manager
    def session_factory(*args, **kwargs):
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)
        return mock_session_context

    # Set the session class to return our factory
    mock_session_class.side_effect = session_factory

    # Setup context managers for all HTTP methods
    for method in methods:
        mock_method_context = AsyncMock()
        mock_method_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_method_context.__aexit__ = AsyncMock(return_value=None)
        setattr(mock_session, method, Mock(return_value=mock_method_context))

    return mock_session


def assert_socket_options_called(
    mock_socket: Mock, expected_calls: list[tuple[int, int, Any]]
) -> None:
    """Assert that specific socket options were set on a mock socket."""
    for option_level, option_name, option_value in expected_calls:
        mock_socket.setsockopt.assert_any_call(option_level, option_name, option_value)


def create_mock_error_response(status: int, reason: str, error_text: str) -> Mock:
    """Create a mock response for HTTP error testing."""
    return create_mock_response(status=status, reason=reason, text_content=error_text)


def setup_sse_content_mock(
    mock_response: Mock,
    chunks: list[tuple[bytes, bytes]],
    timestamps: list[int] | None = None,
) -> None:
    """Setup SSE content mock with chunks and timing."""
    num_chunks = len(chunks)
    mock_response.content.at_eof.side_effect = [False] * num_chunks + [True]

    read_calls = [chunk[0] for chunk in chunks]
    readuntil_calls = [chunk[1] for chunk in chunks]

    mock_response.content.read = AsyncMock(side_effect=read_calls)
    mock_response.content.readuntil = AsyncMock(side_effect=readuntil_calls)


def setup_single_sse_chunk(
    mock_response: Mock,
    first_byte: bytes = b"d",
    remaining: bytes = b"ata: Hello\n\n",
) -> None:
    """Setup a single SSE chunk for testing."""
    setup_sse_content_mock(mock_response, [(first_byte, remaining)])


def create_sse_chunk_list(messages: list[str]) -> list[tuple[bytes, bytes]]:
    """Create SSE chunk list from messages."""
    chunks = []
    for message in messages:
        # Split on first space to separate data: from content
        if message.startswith("data: "):
            remaining_content = message[6:]  # Remove "data: " prefix
            chunks.append((b"d", f"ata: {remaining_content}\n\n".encode()))
        else:
            chunks.append((b"d", f"ata: {message}\n\n".encode()))
    return chunks


def create_aiohttp_exception(
    exception_class: type[Exception], message: str
) -> Exception:
    """Create aiohttp-specific exceptions with proper initialization."""
    if exception_class == aiohttp.ClientConnectorError:
        os_error = OSError(message)
        return aiohttp.ClientConnectorError(
            connection_key=MagicMock(), os_error=os_error
        )
    elif exception_class == aiohttp.ClientResponseError:
        mock_request_info = Mock()
        mock_request_info.url = "http://test.com"
        mock_request_info.method = "POST"
        return aiohttp.ClientResponseError(
            request_info=mock_request_info,
            history=(),
            status=500,
            message=message,
        )
    else:
        return exception_class(message)


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
):
    """Fixture providing an AioHttpClientMixin instance."""
    client = AioHttpClientMixin(http_client_config)
    yield client
    await client.cleanup()


@pytest.fixture
def mock_aiohttp_response() -> Mock:
    """Fixture providing a mock aiohttp.ClientResponse."""
    return create_mock_response()


@pytest.fixture
def mock_sse_response() -> Mock:
    """Fixture providing a mock SSE response."""
    return create_mock_sse_response()


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
# Test AioHttpClientMixin
################################################################################


class TestAioHttpClientMixin:
    """Test suite for AioHttpClientMixin class."""

    def test_init_creates_connector_and_timeout(
        self, http_client_config: GenericHTTPClientConfig
    ) -> None:
        """Test that initialization creates TCP connector and timeout configurations."""
        with patch(
            "aiperf.clients.http.aiohttp_client.create_tcp_connector"
        ) as mock_create:
            mock_connector = Mock()
            mock_create.return_value = mock_connector

            client = AioHttpClientMixin(http_client_config)

            assert client.client_config == http_client_config
            assert client.tcp_connector == mock_connector
            assert isinstance(client.timeout, aiohttp.ClientTimeout)
            assert client.timeout.total == 30.0  # 30000ms / 1000
            assert client.timeout.connect == 30.0
            mock_create.assert_called_once()

    @pytest.mark.parametrize(
        "timeout_ms,expected_seconds",
        [
            (1000, 1.0),
            (5000, 5.0),
            (30000, 30.0),
            (300000, 300.0),
        ],
    )
    def test_timeout_conversion(self, timeout_ms: int, expected_seconds: float) -> None:
        """Test that timeout milliseconds are correctly converted to seconds."""
        config = GenericHTTPClientConfig(url="http://test.com", timeout_ms=timeout_ms)

        with patch("aiperf.clients.http.aiohttp_client.create_tcp_connector"):
            client = AioHttpClientMixin(config)

            assert client.timeout.total == expected_seconds
            assert client.timeout.connect == expected_seconds
            assert client.timeout.sock_connect == expected_seconds
            assert client.timeout.sock_read == expected_seconds
            assert client.timeout.ceil_threshold == expected_seconds

    async def test_cleanup_closes_connector(
        self, aiohttp_client: AioHttpClientMixin
    ) -> None:
        """Test that cleanup properly closes the TCP connector."""
        mock_connector = Mock()
        mock_connector.close = AsyncMock()
        aiohttp_client.tcp_connector = mock_connector

        await aiohttp_client.cleanup()

        mock_connector.close.assert_called_once()
        assert aiohttp_client.tcp_connector is None

    async def test_cleanup_handles_none_connector(
        self, aiohttp_client: AioHttpClientMixin
    ) -> None:
        """Test that cleanup handles None connector gracefully."""
        aiohttp_client.tcp_connector = None

        # Should not raise an exception
        await aiohttp_client.cleanup()

        assert aiohttp_client.tcp_connector is None

    @pytest.mark.asyncio
    async def test_successful_json_request(
        self, aiohttp_client: AioHttpClientMixin, mock_aiohttp_response: Mock
    ) -> None:
        """Test successful JSON request handling."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            setup_mock_session(mock_session_class, mock_aiohttp_response, ["post"])

            record = await aiohttp_client.request(
                "http://test.com/api",
                '{"test": "data"}',
                {"Content-Type": "application/json"},
            )

            assert_successful_request_record(record)

    @pytest.mark.asyncio
    async def test_sse_stream_request(
        self, aiohttp_client: AioHttpClientMixin, mock_sse_response: Mock
    ) -> None:
        """Test SSE stream request handling."""
        mock_messages = [
            SSEMessage(perf_ns=123456789),
            SSEMessage(perf_ns=123456790),
        ]

        with (
            patch("aiohttp.ClientSession") as mock_session_class,
            patch(
                "aiperf.clients.http.aiohttp_client.AioHttpSSEStreamReader"
            ) as mock_reader_class,
        ):
            setup_mock_session(mock_session_class, mock_sse_response, ["post"])

            mock_reader = Mock()
            mock_reader.read_complete_stream = AsyncMock(return_value=mock_messages)
            mock_reader_class.return_value = mock_reader

            record = await aiohttp_client.request(
                "http://test.com/stream",
                '{"stream": true}',
                {"Accept": "text/event-stream"},
            )

            assert_successful_request_record(
                record, expected_response_count=2, expected_response_type=SSEMessage
            )
            mock_reader.read_complete_stream.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,reason,error_text",
        [
            (400, "Bad Request", "Invalid request format"),
            (401, "Unauthorized", "Authentication failed"),
            (404, "Not Found", "Resource not found"),
            (500, "Internal Server Error", "Server error occurred"),
            (503, "Service Unavailable", "Service temporarily unavailable"),
        ],
    )
    async def test_http_error_handling(
        self,
        aiohttp_client: AioHttpClientMixin,
        status_code: int,
        reason: str,
        error_text: str,
    ) -> None:
        """Test HTTP error response handling."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = create_mock_error_response(status_code, reason, error_text)
            setup_mock_session(mock_session_class, mock_response, ["post"])

            record = await aiohttp_client.request("http://test.com", "{}", {})

            assert_error_request_record(
                record,
                expected_error_code=status_code,
                expected_error_type=reason,
                expected_error_message=error_text,
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exception_class,exception_message",
        [
            (aiohttp.ClientConnectionError, "Request timeout"),
            (ConnectionError, "Network connection failed"),
            (ValueError, "Invalid value provided"),
        ],
    )
    async def test_exception_handling(
        self,
        aiohttp_client: AioHttpClientMixin,
        exception_class: type[Exception],
        exception_message: str,
    ) -> None:
        """Test various exception handling scenarios."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_class.side_effect = exception_class(exception_message)

            record = await aiohttp_client.request("http://test.com", "{}", {})

            assert_error_request_record(
                record,
                expected_error_type=exception_class.__name__,
                expected_error_message=exception_message,
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exception_class,message,expected_type",
        [
            (aiohttp.ClientConnectorError, "Connection failed", "ClientConnectorError"),
            (
                aiohttp.ClientResponseError,
                "Internal Server Error",
                "ClientResponseError",
            ),
        ],
    )
    async def test_aiohttp_specific_exceptions(
        self,
        aiohttp_client: AioHttpClientMixin,
        exception_class: type[Exception],
        message: str,
        expected_type: str,
    ) -> None:
        """Test handling of aiohttp-specific exceptions."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            exception = create_aiohttp_exception(exception_class, message)
            mock_session_class.side_effect = exception

            record = await aiohttp_client.request("http://test.com", "{}", {})

            assert_error_request_record(record, expected_error_type=expected_type)

    @pytest.mark.asyncio
    async def test_delayed_request_flag(
        self, aiohttp_client: AioHttpClientMixin, mock_aiohttp_response: Mock
    ) -> None:
        """Test that delayed flag is properly set in request record."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            setup_mock_session(mock_session_class, mock_aiohttp_response, ["post"])

            record = await aiohttp_client.request(
                "http://test.com", "{}", {}, delayed=True
            )

            assert_successful_request_record(record)
            assert record.delayed is True

    @pytest.mark.asyncio
    async def test_kwargs_passed_to_session_post(
        self, aiohttp_client: AioHttpClientMixin, mock_aiohttp_response: Mock
    ) -> None:
        """Test that additional kwargs are passed to session.post."""
        extra_kwargs = {"ssl": False, "proxy": "http://proxy.example.com"}

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = setup_mock_session(
                mock_session_class, mock_aiohttp_response, ["post"]
            )

            record = await aiohttp_client.request(
                "http://test.com", "{}", {}, **extra_kwargs
            )

            assert_successful_request_record(record)
            mock_session.post.assert_called_once()
            call_kwargs = mock_session.post.call_args[1]
            assert "ssl" in call_kwargs
            assert "proxy" in call_kwargs

    @pytest.mark.asyncio
    async def test_session_configuration(
        self, aiohttp_client: AioHttpClientMixin, mock_aiohttp_response: Mock
    ) -> None:
        """Test that ClientSession is configured correctly."""
        headers = {"Authorization": "Bearer token", "Custom-Header": "value"}

        with patch("aiohttp.ClientSession") as mock_session_class:
            setup_mock_session(mock_session_class, mock_aiohttp_response, ["post"])

            record = await aiohttp_client.request("http://test.com", "{}", headers)

            assert_successful_request_record(record)
            mock_session_class.assert_called_once()
            call_kwargs = mock_session_class.call_args[1]
            assert call_kwargs["connector"] == aiohttp_client.tcp_connector
            assert call_kwargs["timeout"] == aiohttp_client.timeout
            assert call_kwargs["headers"] == headers
            assert call_kwargs["connector_owner"] is False
            assert "Authorization" in call_kwargs["skip_auto_headers"]
            assert "Custom-Header" in call_kwargs["skip_auto_headers"]


################################################################################
# Test AioHttpSSEStreamReader
################################################################################


class TestAioHttpSSEStreamReader:
    """Test suite for AioHttpSSEStreamReader class."""

    @pytest.fixture
    def mock_response(self) -> Mock:
        """Fixture providing a mock response for SSE stream testing."""
        return create_mock_sse_response()

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
        setup_single_sse_chunk(mock_response)

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
        setup_sse_content_mock(mock_response, sample_sse_chunks)

        timestamps = list(range(123456789, 123456789 + len(sample_sse_chunks) * 2, 1))

        with patch("time.perf_counter_ns", side_effect=timestamps):
            reader = AioHttpSSEStreamReader(mock_response)
            chunks = []

            async for chunk in reader:
                chunks.append(chunk)

            assert len(chunks) == 3

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
        setup_single_sse_chunk(
            mock_response, first_byte=b"\xff", remaining=b"\xfe\xfd invalid utf8\n\n"
        )

        with patch("time.perf_counter_ns", side_effect=[123456789, 123456790]):
            reader = AioHttpSSEStreamReader(mock_response)
            chunks = []

            async for chunk in reader:
                chunks.append(chunk)

            assert len(chunks) == 1
            raw_message, _, _ = chunks[0]
            assert isinstance(raw_message, str)
            assert "�" in raw_message  # Unicode replacement character

    @pytest.mark.asyncio
    async def test_aiter_empty_chunk(self, mock_response: Mock) -> None:
        """Test __aiter__ with empty chunks."""
        setup_single_sse_chunk(mock_response, first_byte=b"", remaining=b"")

        reader = AioHttpSSEStreamReader(mock_response)
        chunks = []

        async for chunk in reader:
            chunks.append(chunk)

        assert chunks == []

    @pytest.mark.asyncio
    async def test_aiter_timing_accuracy(self, mock_response: Mock) -> None:
        """Test that __aiter__ captures timing accurately."""
        setup_single_sse_chunk(mock_response, remaining=b"ata: test\n\n")

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


################################################################################
# Test create_tcp_connector
################################################################################


class TestCreateTcpConnector:
    """Test suite for create_tcp_connector function."""

    def test_create_default_connector(self) -> None:
        """Test creating connector with default parameters."""
        with patch("aiohttp.TCPConnector") as mock_connector_class:
            mock_connector = Mock()
            mock_connector_class.return_value = mock_connector

            result = create_tcp_connector()

            assert result == mock_connector
            mock_connector_class.assert_called_once()
            call_kwargs = mock_connector_class.call_args[1]

            # Verify default parameters
            assert call_kwargs["limit"] == 2500
            assert call_kwargs["limit_per_host"] == 2500
            assert call_kwargs["ttl_dns_cache"] == 300
            assert call_kwargs["use_dns_cache"] is True
            assert call_kwargs["enable_cleanup_closed"] is False
            assert call_kwargs["force_close"] is False
            assert call_kwargs["keepalive_timeout"] == 300
            assert call_kwargs["happy_eyeballs_delay"] is None
            assert call_kwargs["family"] == socket.AF_INET
            assert callable(call_kwargs["socket_factory"])

    def test_create_connector_with_custom_kwargs(self) -> None:
        """Test creating connector with custom parameters."""
        custom_kwargs = {
            "limit": 1000,
            "limit_per_host": 500,
            "ttl_dns_cache": 600,
            "keepalive_timeout": 120,
        }

        with patch("aiohttp.TCPConnector") as mock_connector_class:
            mock_connector = Mock()
            mock_connector_class.return_value = mock_connector

            result = create_tcp_connector(**custom_kwargs)

            assert result == mock_connector
            call_kwargs = mock_connector_class.call_args[1]

            # Verify custom parameters override defaults
            assert call_kwargs["limit"] == 1000
            assert call_kwargs["limit_per_host"] == 500
            assert call_kwargs["ttl_dns_cache"] == 600
            assert call_kwargs["keepalive_timeout"] == 120

            # Verify other defaults are preserved
            assert call_kwargs["use_dns_cache"] is True
            assert call_kwargs["family"] == socket.AF_INET

    def test_socket_factory_configuration(self) -> None:
        """Test that socket factory configures sockets correctly."""
        with patch("aiohttp.TCPConnector") as mock_connector_class:
            create_tcp_connector()

            # Get the socket factory from the call
            call_kwargs = mock_connector_class.call_args[1]
            socket_factory = call_kwargs["socket_factory"]

            # Test socket factory with mock socket
            with patch("socket.socket") as mock_socket_class:
                mock_socket = Mock()
                mock_socket_class.return_value = mock_socket

                # Call socket factory
                addr_info = (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("127.0.0.1", 80),
                )
                result_socket = socket_factory(addr_info)

                assert result_socket == mock_socket

                # Verify socket was created with correct parameters
                mock_socket_class.assert_called_once_with(
                    family=socket.AF_INET,
                    type=socket.SOCK_STREAM,
                    proto=socket.IPPROTO_TCP,
                )

                # Verify socket options were set
                expected_calls = [
                    (socket.SOL_TCP, socket.TCP_NODELAY, 1),
                    (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
                    (socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 85),
                    (socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 64),
                ]

                assert_socket_options_called(mock_socket, expected_calls)

    @pytest.mark.parametrize(
        "has_attribute,attribute_name,tcp_option,expected_value",
        [
            (True, "TCP_KEEPIDLE", socket.TCP_KEEPIDLE, 600),
            (True, "TCP_KEEPINTVL", socket.TCP_KEEPINTVL, 60),
            (True, "TCP_KEEPCNT", socket.TCP_KEEPCNT, 3),
            (True, "TCP_QUICKACK", socket.TCP_QUICKACK, 1),
            (True, "TCP_USER_TIMEOUT", socket.TCP_USER_TIMEOUT, 30000),
            (False, "TCP_KEEPIDLE", socket.TCP_KEEPIDLE, None),
        ],
    )
    def test_socket_factory_linux_specific_options(
        self,
        has_attribute: bool,
        attribute_name: str,
        tcp_option: int,
        expected_value: int | None,
    ) -> None:
        """Test socket factory handles Linux-specific TCP options."""
        with patch("aiohttp.TCPConnector") as mock_connector_class:
            create_tcp_connector()

            socket_factory = mock_connector_class.call_args[1]["socket_factory"]

            with (
                patch("socket.socket") as mock_socket_class,
                # patch("builtins.hasattr", return_value=has_attribute) as mock_hasattr,
            ):
                mock_socket = Mock()
                mock_socket_class.return_value = mock_socket

                addr_info = (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("127.0.0.1", 80),
                )
                socket_factory(addr_info)

                if has_attribute and expected_value is not None:
                    # Mock the socket attribute to exist
                    with patch.object(
                        socket, attribute_name, expected_value, create=True
                    ):
                        mock_socket.setsockopt.assert_any_call(
                            socket.SOL_TCP, tcp_option, expected_value
                        )

    @pytest.mark.parametrize(
        "family,sock_type,proto",
        [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP),
            (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP),
        ],
    )
    def test_socket_factory_different_address_families(
        self, family: int, sock_type: int, proto: int
    ) -> None:
        """Test socket factory with different address families."""
        with patch("aiohttp.TCPConnector") as mock_connector_class:
            create_tcp_connector()

            socket_factory = mock_connector_class.call_args[1]["socket_factory"]

            with patch("socket.socket") as mock_socket_class:
                mock_socket = Mock()
                mock_socket_class.return_value = mock_socket

                addr_info = (family, sock_type, proto, "", ("127.0.0.1", 80))
                result = socket_factory(addr_info)

                assert result == mock_socket
                mock_socket_class.assert_called_once_with(
                    family=family, type=sock_type, proto=proto
                )


################################################################################
# Integration Tests
################################################################################


class TestIntegration:
    """Integration tests for aiohttp client components."""

    @pytest.mark.asyncio
    async def test_end_to_end_json_request(
        self, http_client_config: GenericHTTPClientConfig
    ) -> None:
        """Test end-to-end JSON request flow."""
        test_response = {"message": "success", "data": [1, 2, 3]}

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = create_mock_response(text_content=json.dumps(test_response))
            setup_mock_session(mock_session_class, mock_response, ["post"])

            client = AioHttpClientMixin(http_client_config)
            try:
                record = await client.request(
                    "http://test.com/api",
                    json.dumps({"query": "test"}),
                    {"Content-Type": "application/json"},
                )

                assert_successful_request_record(record)

            finally:
                await client.cleanup()

    @pytest.mark.asyncio
    async def test_end_to_end_sse_request(
        self, http_client_config: GenericHTTPClientConfig
    ) -> None:
        """Test end-to-end SSE request flow."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = create_mock_sse_response()

            sse_chunks = [
                (b"d", b"ata: Hello\nevent: message\n\n"),
                (b"d", b"ata: World\n\n"),
            ]
            setup_sse_content_mock(mock_response, sse_chunks)
            setup_mock_session(mock_session_class, mock_response, ["post"])

            client = AioHttpClientMixin(http_client_config)
            try:
                with patch(
                    "time.perf_counter_ns", side_effect=range(123456789, 123456799)
                ):
                    record = await client.request(
                        "http://test.com/stream",
                        json.dumps({"stream": True}),
                        {"Accept": "text/event-stream"},
                    )

                assert_successful_request_record(
                    record, expected_response_count=2, expected_response_type=SSEMessage
                )

            finally:
                await client.cleanup()

    @pytest.mark.asyncio
    async def test_concurrent_requests(
        self, http_client_config: GenericHTTPClientConfig
    ) -> None:
        """Test handling of concurrent requests."""
        num_requests = 5

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = create_mock_response()
            setup_mock_session(mock_session_class, mock_response, ["post"])

            client = AioHttpClientMixin(http_client_config)
            try:
                tasks = []
                for i in range(num_requests):
                    task = client.request(
                        f"http://test.com/api/{i}",
                        f'{{"request": {i}}}',
                        {"Content-Type": "application/json"},
                    )
                    tasks.append(task)

                records = await asyncio.gather(*tasks)

                assert len(records) == num_requests
                for record in records:
                    assert_successful_request_record(record)

            finally:
                await client.cleanup()


################################################################################
# Performance Tests
################################################################################


class TestPerformance:
    """Performance-focused tests."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_sse_stream_performance(
        self, http_client_config: GenericHTTPClientConfig
    ) -> None:
        """Test SSE stream reading performance with large number of messages."""
        num_messages = 1000

        messages = [f"Message {i}" for i in range(num_messages)]
        sse_chunks = create_sse_chunk_list(messages)

        mock_response = create_mock_sse_response()
        setup_sse_content_mock(mock_response, sse_chunks)

        reader = AioHttpSSEStreamReader(mock_response)

        start_time = time.perf_counter()

        with patch(
            "time.perf_counter_ns",
            side_effect=range(123456789, 123456789 + num_messages * 2),
        ):
            chunks = []
            async for chunk in reader:
                chunks.append(chunk)

        end_time = time.perf_counter()
        processing_time = end_time - start_time

        assert len(chunks) == num_messages
        assert processing_time < 1.0, (
            f"Processing took {processing_time:.3f}s, expected < 1.0s"
        )

    @pytest.mark.performance
    def test_tcp_connector_creation_performance(self) -> None:
        """Test TCP connector creation performance."""
        num_iterations = 100

        start_time = time.perf_counter()

        connectors = []
        for _ in range(num_iterations):
            with patch("aiohttp.TCPConnector") as mock_connector_class:
                mock_connector = Mock()
                mock_connector_class.return_value = mock_connector
                connector = create_tcp_connector()
                connectors.append(connector)

        end_time = time.perf_counter()
        creation_time = end_time - start_time

        assert len(connectors) == num_iterations
        assert creation_time < 0.1, (
            f"Creation took {creation_time:.3f}s, expected < 0.1s"
        )


################################################################################
# Edge Case Tests
################################################################################


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.edge_case
    @pytest.mark.asyncio
    async def test_empty_response_body(
        self, aiohttp_client: AioHttpClientMixin
    ) -> None:
        """Test handling of empty response body."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = create_mock_response(text_content="")
            setup_mock_session(mock_session_class, mock_response, ["post"])

            record = await aiohttp_client.request("http://test.com", "{}", {})

            assert_successful_request_record(record)

    @pytest.mark.edge_case
    @pytest.mark.asyncio
    async def test_very_large_payload(self, aiohttp_client: AioHttpClientMixin) -> None:
        """Test handling of very large payloads."""
        large_payload = "x" * (1024 * 1024)  # 1MB payload

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = create_mock_response(text_content='{"received": "ok"}')
            mock_session = setup_mock_session(
                mock_session_class, mock_response, ["post"]
            )

            record = await aiohttp_client.request("http://test.com", large_payload, {})

            assert_successful_request_record(record)
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert call_args[1]["data"] == large_payload

    @pytest.mark.edge_case
    @pytest.mark.asyncio
    async def test_malformed_sse_stream(self, mock_sse_response: Mock) -> None:
        """Test handling of malformed SSE stream."""
        content_mock = Mock()
        content_mock.at_eof.side_effect = [False, True]
        content_mock.read = AsyncMock(return_value=b"d")
        content_mock.readuntil = AsyncMock(side_effect=Exception("Stream corruption"))
        mock_sse_response.content = content_mock

        reader = AioHttpSSEStreamReader(mock_sse_response)

        with pytest.raises(Exception, match="Stream corruption"):
            async for _ in reader:
                pass

    @pytest.mark.edge_case
    def test_invalid_socket_options(self) -> None:
        """Test socket factory with invalid options."""
        with patch("aiohttp.TCPConnector") as mock_connector_class:
            create_tcp_connector()

            socket_factory = mock_connector_class.call_args[1]["socket_factory"]

            with patch("socket.socket") as mock_socket_class:
                mock_socket = Mock()
                mock_socket.setsockopt.side_effect = OSError("Invalid socket option")
                mock_socket_class.return_value = mock_socket

                addr_info = (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("127.0.0.1", 80),
                )

                with pytest.raises(OSError, match="Invalid socket option"):
                    socket_factory(addr_info)
