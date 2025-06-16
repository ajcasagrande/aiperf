# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pytest configuration and shared fixtures for the test suite."""

import time
from collections.abc import Generator

import pytest

from aiperf.common.models.record_models import SSEField, SSEFieldType


@pytest.fixture(scope="session")
def sample_perf_ns() -> int:
    """Fixture providing a consistent performance counter timestamp for tests."""
    return int(time.perf_counter_ns())


@pytest.fixture
def sse_field_types() -> list[SSEFieldType]:
    """Fixture providing all standard SSE field types."""
    return [
        SSEFieldType.DATA,
        SSEFieldType.EVENT,
        SSEFieldType.ID,
        SSEFieldType.RETRY,
        SSEFieldType.COMMENT,
    ]


@pytest.fixture
def sample_sse_fields() -> list[SSEField]:
    """Fixture providing sample SSE fields for testing."""
    return [
        SSEField(name=SSEFieldType.DATA, value="test data"),
        SSEField(name=SSEFieldType.EVENT, value="test event"),
        SSEField(name=SSEFieldType.ID, value="test-id-123"),
        SSEField(name=SSEFieldType.RETRY, value="5000"),
        SSEField(name=SSEFieldType.COMMENT, value="test comment"),
        SSEField(name="custom-field", value="custom value"),
        SSEField(name="field-without-value", value=None),
    ]


@pytest.fixture
def complex_sse_message_data() -> dict[str, str]:
    """Fixture providing complex SSE message test data."""
    return {
        "openai_chunk": """event: message
data: {"id": "chatcmpl-123", "object": "chat.completion.chunk"}
data: {"choices": [{"delta": {"content": "Hello"}, "index": 0}]}
id: msg_123
retry: 5000""",
        "with_comments": """data: first line
: This is a comment
data: second line
: Another comment
event: custom""",
        "mixed_format": """data: {"json": "value"}
custom-header: custom-value
field-without-value
: comment line
retry: 3000""",
        "empty_and_whitespace": """data: test

event: message

: comment
data: final""",
    }


@pytest.fixture
def edge_case_inputs() -> dict[str, str]:
    """Fixture providing edge case inputs for robust testing."""
    return {
        "empty_string": "",
        "only_newlines": "\n\n\n",
        "only_whitespace": "   \t   ",
        "mixed_whitespace": "  \n  \t  \n  ",
        "single_colon": ":",
        "multiple_colons": "data: value: with: many: colons",
        "unicode_content": "data: 你好世界 🚀💻",
        "special_chars": "data: !@#$%^&*()_+-=[]{}|;':\",./<>?",
        "very_long_value": f"data: {'x' * 1000}",
    }


@pytest.fixture
def performance_test_data() -> Generator[list[str], None, None]:
    """Fixture providing data for performance testing."""
    # Generate a large number of SSE messages for performance testing
    messages = []
    for i in range(1000):
        message = f"""event: message-{i}
data: {{"index": {i}, "content": "Message number {i}"}}
id: msg-{i}
retry: {1000 + i}"""
        messages.append(message)

    yield messages


# Configure pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, isolated)"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests (may be slow)"
    )
    config.addinivalue_line("markers", "edge_case: marks tests that test edge cases")


# Configure test collection
def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their names and locations."""
    for item in items:
        # Mark all tests in this file as unit tests by default
        if "test_sse_utils" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Mark performance tests
        if "performance" in item.name.lower():
            item.add_marker(pytest.mark.performance)

        # Mark edge case tests
        if "edge" in item.name.lower() or "special" in item.name.lower():
            item.add_marker(pytest.mark.edge_case)
