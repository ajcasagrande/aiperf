# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock, Mock, patch

import pytest

from aiperf.clients.http.httpx_client import (
    HttpxClientMixin,
    HttpxSSEStreamReader,
    parse_sse_message,
)
from aiperf.clients.model_endpoint_info import EndpointInfo, ModelEndpointInfo
from aiperf.common.enums import SSEFieldType
from aiperf.common.exceptions import NotInitializedError
from aiperf.common.models import SSEMessage, TextResponse


@pytest.fixture
def mock_model_endpoint():
    """Create a mock model endpoint for testing."""
    endpoint = EndpointInfo(timeout=30.0)
    return ModelEndpointInfo(endpoint=endpoint)


@pytest.fixture
def httpx_client(mock_model_endpoint):
    """Create an HttpxClientMixin instance for testing."""
    return HttpxClientMixin(model_endpoint=mock_model_endpoint)


class TestHttpxClientMixin:
    """Test cases for HttpxClientMixin."""

    def test_init(self, httpx_client, mock_model_endpoint):
        """Test initialization of HttpxClientMixin."""
        assert httpx_client.model_endpoint == mock_model_endpoint
        assert httpx_client.client is None
        assert httpx_client.timeout.connect == 30.0
        assert httpx_client.timeout.read == 30.0

    def test_initialize_session(self, httpx_client):
        """Test session initialization."""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client:
            httpx_client.initialize_session(headers)

            mock_client.assert_called_once()
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["http2"] is True
            assert call_kwargs["headers"] == headers
            assert call_kwargs["verify"] is True
            assert call_kwargs["follow_redirects"] is False

    async def test_close(self, httpx_client):
        """Test client closure."""
        mock_client = AsyncMock()
        httpx_client.client = mock_client

        await httpx_client.close()

        mock_client.aclose.assert_called_once()
        assert httpx_client.client is None

    async def test_post_request_not_initialized(self, httpx_client):
        """Test post_request raises error when session not initialized."""
        with pytest.raises(NotInitializedError):
            await httpx_client.post_request("http://test.com", "{}", {})

    @patch("httpx.AsyncClient")
    async def test_post_request_success_json(self, mock_client_class, httpx_client):
        """Test successful POST request with JSON response."""
        # Setup mocks
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.aread.return_value = b'{"result": "success"}'

        mock_client = AsyncMock()
        mock_client.headers = {}
        mock_client.stream.return_value.__aenter__.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Initialize session and make request
        httpx_client.initialize_session({})
        record = await httpx_client.post_request(
            "http://test.com/api",
            '{"query": "test"}',
            {"Content-Type": "application/json"},
        )

        # Assertions
        assert record.status == 200
        assert record.error is None
        assert len(record.responses) == 1
        assert isinstance(record.responses[0], TextResponse)
        assert record.responses[0].text == '{"result": "success"}'
        assert record.responses[0].content_type == "application/json"

    @patch("httpx.AsyncClient")
    async def test_post_request_error_response(self, mock_client_class, httpx_client):
        """Test POST request with error response."""
        # Setup mocks
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        mock_response.aread.return_value = b"Not found"

        mock_client = AsyncMock()
        mock_client.headers = {}
        mock_client.stream.return_value.__aenter__.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Initialize session and make request
        httpx_client.initialize_session({})
        record = await httpx_client.post_request("http://test.com/api", "{}", {})

        # Assertions
        assert record.status == 404
        assert record.error is not None
        assert record.error.code == 404
        assert record.error.type == "Not Found"
        assert record.error.message == "Not found"

    @patch("httpx.AsyncClient")
    async def test_post_request_sse_stream(self, mock_client_class, httpx_client):
        """Test POST request with SSE stream response."""
        # Setup mocks
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}

        # Mock SSE stream data
        sse_data = [b"data: chunk1\n\n", b"data: chunk2\n\n", b"data: [DONE]\n\n"]
        mock_response.aiter_bytes.return_value.__aiter__.return_value = iter(sse_data)

        mock_client = AsyncMock()
        mock_client.headers = {}
        mock_client.stream.return_value.__aenter__.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Initialize session and make request
        httpx_client.initialize_session({})
        record = await httpx_client.post_request("http://test.com/api", "{}", {})

        # Assertions
        assert record.status == 200
        assert record.error is None
        assert len(record.responses) == 3
        for response in record.responses:
            assert isinstance(response, SSEMessage)


class TestHttpxSSEStreamReader:
    """Test cases for HttpxSSEStreamReader."""

    async def test_read_complete_stream(self):
        """Test reading complete SSE stream."""
        mock_response = Mock()

        # Mock the async iteration
        async def mock_aiter():
            yield ("data: test1", 1000)
            yield ("data: test2", 2000)

        reader = HttpxSSEStreamReader(mock_response)

        with patch.object(reader, "__aiter__", return_value=mock_aiter()):
            messages = await reader.read_complete_stream()

        assert len(messages) == 2
        assert all(isinstance(msg, SSEMessage) for msg in messages)

    async def test_aiter_with_chunks(self):
        """Test async iteration with chunked data."""
        mock_response = AsyncMock()

        # Mock chunked SSE data
        chunks = [b"data: chunk1\n\n", b"data: chunk2\n\ndata: chunk3\n\n"]
        mock_response.aiter_bytes.return_value.__aiter__.return_value = iter(chunks)

        reader = HttpxSSEStreamReader(mock_response)
        messages = []

        async for message, timestamp in reader.__aiter__():
            messages.append((message, timestamp))

        assert len(messages) == 3
        assert messages[0][0] == "data: chunk1"
        assert messages[1][0] == "data: chunk2"
        assert messages[2][0] == "data: chunk3"


class TestParseSSEMessage:
    """Test cases for parse_sse_message function."""

    def test_parse_data_field(self):
        """Test parsing SSE message with data field."""
        raw_message = "data: Hello World"
        message = parse_sse_message(raw_message, 1000)

        assert message.perf_ns == 1000
        assert len(message.packets) == 1
        assert message.packets[0].name == "data"
        assert message.packets[0].value == "Hello World"

    def test_parse_multiple_fields(self):
        """Test parsing SSE message with multiple fields."""
        raw_message = "event: update\ndata: Hello\nid: 123"
        message = parse_sse_message(raw_message, 2000)

        assert message.perf_ns == 2000
        assert len(message.packets) == 3

        fields = {p.name: p.value for p in message.packets}
        assert fields["event"] == "update"
        assert fields["data"] == "Hello"
        assert fields["id"] == "123"

    def test_parse_comment_field(self):
        """Test parsing SSE message with comment field."""
        raw_message = ": This is a comment"
        message = parse_sse_message(raw_message, 3000)

        assert message.perf_ns == 3000
        assert len(message.packets) == 1
        assert message.packets[0].name == SSEFieldType.COMMENT
        assert message.packets[0].value == "This is a comment"

    def test_parse_field_without_value(self):
        """Test parsing SSE message field without value."""
        raw_message = "retry"
        message = parse_sse_message(raw_message, 4000)

        assert message.perf_ns == 4000
        assert len(message.packets) == 1
        assert message.packets[0].name == "retry"
        assert message.packets[0].value is None

    def test_parse_empty_lines(self):
        """Test parsing SSE message with empty lines."""
        raw_message = "data: test\n\n\ndata: test2"
        message = parse_sse_message(raw_message, 5000)

        assert message.perf_ns == 5000
        assert len(message.packets) == 2
        assert message.packets[0].value == "test"
        assert message.packets[1].value == "test2"
