# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Comprehensive unit tests for aiohttp client components."""

import asyncio
import json
import socket
import time
from unittest.mock import AsyncMock, Mock, patch

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
# Helper Functions
################################################################################


def setup_mock_session_with_response(
    mock_session_class: Mock, mock_response: Mock
) -> AsyncMock:
    """Helper function to set up a proper mock session with async context manager support."""
    mock_session = AsyncMock()
    mock_session_class.return_value.__aenter__.return_value = mock_session

    # Create a proper async context manager for post
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__.return_value = mock_response
    mock_session.post.return_value = mock_post_context

    return mock_session


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
        url = "http://test.com/api"
        payload = '{"test": "data"}'
        headers = {"Content-Type": "application/json"}

        with patch("aiohttp.ClientSession") as mock_session_class:
            setup_mock_session_with_response(mock_session_class, mock_aiohttp_response)

            record = await aiohttp_client.request(url, payload, headers)

            assert isinstance(record, RequestRecord)
            assert record.status == 200
            assert record.error is None
            assert len(record.responses) == 1
            assert isinstance(record.responses[0], TextResponse)
            assert record.responses[0].text == '{"success": true}'
            assert record.responses[0].content_type == "application/json"
            assert record.start_perf_ns is not None
            assert record.end_perf_ns is not None

    @pytest.mark.asyncio
    async def test_sse_stream_request(
        self, aiohttp_client: AioHttpClientMixin, mock_sse_response: Mock
    ) -> None:
        """Test SSE stream request handling."""
        url = "http://test.com/stream"
        payload = '{"stream": true}'
        headers = {"Accept": "text/event-stream"}

        # Mock SSE messages
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
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_sse_response

            mock_reader = Mock()
            mock_reader.read_complete_stream = AsyncMock(return_value=mock_messages)
            mock_reader_class.return_value = mock_reader

            record = await aiohttp_client.request(url, payload, headers)

            assert isinstance(record, RequestRecord)
            assert record.status == 200
            assert record.error is None
            assert len(record.responses) == 2
            assert all(isinstance(resp, SSEMessage) for resp in record.responses)
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
        mock_response = Mock(spec=aiohttp.ClientResponse)
        mock_response.status = status_code
        mock_response.reason = reason
        mock_response.text = AsyncMock(return_value=error_text)

        with patch("aiohttp.ClientSession") as mock_session_class:
            setup_mock_session_with_response(mock_session_class, mock_response)

            record = await aiohttp_client.request("http://test.com", "{}", {})

            assert isinstance(record, RequestRecord)
            assert record.status is None  # Not set for error responses
            assert record.error is not None
            assert record.error.code == status_code
            assert record.error.type == reason
            assert record.error.message == error_text
            assert len(record.responses) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exception_class,exception_message",
        [
            (aiohttp.ClientTimeout, "Request timeout"),
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

            assert isinstance(record, RequestRecord)
            assert record.error is not None
            assert record.error.type == exception_class.__name__
            assert record.error.message == exception_message
            assert record.end_perf_ns is not None

    @pytest.mark.asyncio
    async def test_aiohttp_specific_exceptions(
        self, aiohttp_client: AioHttpClientMixin
    ) -> None:
        """Test handling of aiohttp-specific exceptions."""
        # Test ClientConnectorError with proper arguments
        with patch("aiohttp.ClientSession") as mock_session_class:
            os_error = OSError("Connection failed")
            connector_error = aiohttp.ClientConnectorError(
                connection_key=None, os_error=os_error
            )
            mock_session_class.side_effect = connector_error

            record = await aiohttp_client.request("http://test.com", "{}", {})

            assert isinstance(record, RequestRecord)
            assert record.error is not None
            assert record.error.type == "ClientConnectorError"

        # Test ClientResponseError with proper arguments
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_request_info = Mock()
            mock_request_info.url = "http://test.com"
            mock_request_info.method = "POST"
            response_error = aiohttp.ClientResponseError(
                request_info=mock_request_info,
                history=(),
                status=500,
                message="Internal Server Error",
            )
            mock_session_class.side_effect = response_error

            record = await aiohttp_client.request("http://test.com", "{}", {})

            assert isinstance(record, RequestRecord)
            assert record.error is not None
            assert record.error.type == "ClientResponseError"

    @pytest.mark.asyncio
    async def test_delayed_request_flag(
        self, aiohttp_client: AioHttpClientMixin, mock_aiohttp_response: Mock
    ) -> None:
        """Test that delayed flag is properly set in request record."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            setup_mock_session_with_response(mock_session_class, mock_aiohttp_response)

            record = await aiohttp_client.request(
                "http://test.com", "{}", {}, delayed=True
            )

            assert record.delayed is True

    @pytest.mark.asyncio
    async def test_kwargs_passed_to_session_post(
        self, aiohttp_client: AioHttpClientMixin, mock_aiohttp_response: Mock
    ) -> None:
        """Test that additional kwargs are passed to session.post."""
        extra_kwargs = {"ssl": False, "proxy": "http://proxy.example.com"}

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = setup_mock_session_with_response(
                mock_session_class, mock_aiohttp_response
            )

            await aiohttp_client.request("http://test.com", "{}", {}, **extra_kwargs)

            # Verify kwargs were passed to session.post
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
            setup_mock_session_with_response(mock_session_class, mock_aiohttp_response)

            await aiohttp_client.request("http://test.com", "{}", headers)

            # Verify session was created with correct parameters
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
        mock_response.content.at_eof.side_effect = [False, True]
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

        # Create async mock methods for read and readuntil
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
                    ((socket.SOL_TCP, socket.TCP_NODELAY, 1),),
                    ((socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),),
                    ((socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 85),),
                    ((socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 64),),
                ]

                for expected_call in expected_calls:
                    mock_socket.setsockopt.assert_any_call(*expected_call[0])

    @pytest.mark.parametrize(
        "has_attribute,attribute_name,expected_value",
        [
            (True, "TCP_KEEPIDLE", 600),
            (True, "TCP_KEEPINTVL", 60),
            (True, "TCP_KEEPCNT", 3),
            (True, "TCP_QUICKACK", 1),
            (True, "TCP_USER_TIMEOUT", 30000),
            (False, "TCP_KEEPIDLE", None),
        ],
    )
    def test_socket_factory_linux_specific_options(
        self,
        has_attribute: bool,
        attribute_name: str,
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
                        tcp_option = getattr(socket, attribute_name)
                        mock_socket.setsockopt.assert_any_call(
                            socket.SOL_TCP, tcp_option, expected_value
                        )

    def test_socket_factory_different_address_families(self) -> None:
        """Test socket factory with different address families."""
        with patch("aiohttp.TCPConnector") as mock_connector_class:
            create_tcp_connector()

            socket_factory = mock_connector_class.call_args[1]["socket_factory"]

            test_families = [
                (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP),
                (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP),
            ]

            for family, sock_type, proto in test_families:
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
            # Setup mock session and response
            mock_session = AsyncMock()
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content_type = "application/json"
            mock_response.text = AsyncMock(return_value=json.dumps(test_response))

            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response

            # Create client and make request
            client = AioHttpClientMixin(http_client_config)
            try:
                record = await client.request(
                    "http://test.com/api",
                    json.dumps({"query": "test"}),
                    {"Content-Type": "application/json"},
                )

                assert record.status == 200
                assert record.error is None
                assert len(record.responses) == 1

                response = record.responses[0]
                assert isinstance(response, TextResponse)
                assert json.loads(response.text) == test_response

            finally:
                await client.cleanup()

    @pytest.mark.asyncio
    async def test_end_to_end_sse_request(
        self, http_client_config: GenericHTTPClientConfig
    ) -> None:
        """Test end-to-end SSE request flow."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            # Setup mock SSE response
            mock_session = AsyncMock()
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content_type = "text/event-stream"

            # Mock content stream
            content_mock = Mock()
            content_mock.at_eof.side_effect = [False, False, True]
            content_mock.read.side_effect = [b"d", b"d"]
            content_mock.readuntil.side_effect = [
                b"ata: Hello\nevent: message\n\n",
                b"ata: World\n\n",
            ]
            mock_response.content = content_mock

            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response

            # Create client and make request
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

                assert record.status == 200
                assert record.error is None
                assert len(record.responses) == 2
                assert all(isinstance(resp, SSEMessage) for resp in record.responses)

            finally:
                await client.cleanup()

    @pytest.mark.asyncio
    async def test_concurrent_requests(
        self, http_client_config: GenericHTTPClientConfig
    ) -> None:
        """Test handling of concurrent requests."""
        num_requests = 5

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_response = Mock()
            mock_response.status = 200
            mock_response.content_type = "application/json"
            mock_response.text = AsyncMock(return_value='{"success": true}')

            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response

            client = AioHttpClientMixin(http_client_config)
            try:
                # Create multiple concurrent requests
                tasks = []
                for i in range(num_requests):
                    task = client.request(
                        f"http://test.com/api/{i}",
                        f'{{"request": {i}}}',
                        {"Content-Type": "application/json"},
                    )
                    tasks.append(task)

                # Wait for all requests to complete
                records = await asyncio.gather(*tasks)

                assert len(records) == num_requests
                for record in records:
                    assert record.status == 200
                    assert record.error is None
                    assert len(record.responses) == 1

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

        # Generate test SSE data
        sse_chunks = []
        for i in range(num_messages):
            first_byte = b"d"
            remaining = f"ata: Message {i}\nevent: test\nid: {i}\n\n".encode()
            sse_chunks.append((first_byte, remaining))

        mock_response = Mock()
        mock_response.content.at_eof.side_effect = [False] * num_messages + [True]

        read_calls = [chunk[0] for chunk in sse_chunks]
        readuntil_calls = [chunk[1] for chunk in sse_chunks]

        mock_response.content.read = AsyncMock(side_effect=read_calls)
        mock_response.content.readuntil = AsyncMock(side_effect=readuntil_calls)

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
        # Performance assertion: should process 1000 messages in under 1 second
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
        # Performance assertion: should create 100 connectors in under 0.1 seconds
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
        mock_response = Mock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.text = AsyncMock(return_value="")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response

            record = await aiohttp_client.request("http://test.com", "{}", {})

            assert record.status == 200
            assert len(record.responses) == 1
            assert isinstance(record.responses[0], TextResponse)
            assert record.responses[0].text == ""

    @pytest.mark.edge_case
    @pytest.mark.asyncio
    async def test_very_large_payload(self, aiohttp_client: AioHttpClientMixin) -> None:
        """Test handling of very large payloads."""
        large_payload = "x" * (1024 * 1024)  # 1MB payload

        mock_response = Mock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.text = AsyncMock(return_value='{"received": "ok"}')

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = setup_mock_session_with_response(
                mock_session_class, mock_response
            )

            record = await aiohttp_client.request("http://test.com", large_payload, {})

            assert record.status == 200
            assert record.error is None

            # Verify large payload was passed to session.post
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert call_args[1]["data"] == large_payload

    @pytest.mark.edge_case
    @pytest.mark.asyncio
    async def test_malformed_sse_stream(self, mock_sse_response: Mock) -> None:
        """Test handling of malformed SSE stream."""
        # Mock malformed SSE data
        content_mock = Mock()
        content_mock.at_eof.side_effect = [False, True]
        content_mock.read = AsyncMock(return_value=b"d")
        content_mock.readuntil = AsyncMock(side_effect=Exception("Stream corruption"))
        mock_sse_response.content = content_mock

        reader = AioHttpSSEStreamReader(mock_sse_response)

        # Should handle exception gracefully
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

                # Should handle socket option errors gracefully
                with pytest.raises(OSError, match="Invalid socket option"):
                    socket_factory(addr_info)
