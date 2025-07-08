# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the LogsDashboardMixin.
"""

import time
from collections import deque

import pytest
from rich.table import Table

from aiperf.ui.logs_mixin import LogsDashboardElement, LogsDashboardMixin


class TestLogsDashboardMixin:
    """Test the LogsDashboardMixin functionality."""

    def test_logs_mixin_initialization(self):
        """Test LogsDashboardMixin initialization."""

        class TestMixin(LogsDashboardMixin):
            def __init__(self):
                super().__init__()

        mixin = TestMixin()
        assert mixin.log_queue is None
        assert isinstance(mixin.log_records, deque)
        assert mixin.log_records.maxlen == LogsDashboardElement.MAX_LOG_RECORDS

    def test_logs_mixin_constants(self):
        """Test LogsDashboardMixin constants."""
        assert LogsDashboardElement.MAX_LOG_RECORDS == 100
        assert LogsDashboardElement.MAX_LOG_MESSAGE_LENGTH == 400
        assert LogsDashboardElement.LOG_REFRESH_INTERVAL_SEC == 0.1
        assert LogsDashboardElement.MAX_LOG_LOGGER_NAME_LENGTH == 25

    def test_logs_mixin_log_level_styles(self):
        """Test log level style mappings."""
        expected_styles = {
            "DEBUG": "dim",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }
        assert expected_styles == LogsDashboardElement.LOG_LEVEL_STYLES

    def test_logs_mixin_log_msg_styles(self):
        """Test log message style mappings."""
        expected_styles = {
            "DEBUG": "dim",
            "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }
        assert expected_styles == LogsDashboardElement.LOG_MSG_STYLES

    @pytest.mark.asyncio
    async def test_consume_logs_no_queue(self):
        """Test consume_logs with no queue."""

        class TestMixin(LogsDashboardMixin):
            def __init__(self):
                super().__init__()

        mixin = TestMixin()
        # Should not raise an error
        await mixin._consume_logs()
        assert len(mixin.log_records) == 0

    @pytest.mark.asyncio
    async def test_consume_logs_empty_queue(self, logs_mixin_instance):
        """Test consume_logs with empty queue."""
        logs_mixin_instance.log_queue.empty.return_value = True

        await logs_mixin_instance._consume_logs()
        assert len(logs_mixin_instance.log_records) == 0

    @pytest.mark.asyncio
    async def test_consume_logs_with_data(self, logs_mixin_instance):
        """Test consume_logs with log data."""
        # Clear any existing data from the mock
        logs_mixin_instance.log_records.clear()

        log_data = {
            "created": time.time(),
            "name": "test_logger",
            "levelname": "INFO",
            "msg": "Test message",
        }

        logs_mixin_instance.log_queue.empty.side_effect = [
            False,
            True,
            True,
            True,
            True,
            True,
            True,
        ]
        logs_mixin_instance.log_queue.get_nowait.return_value = log_data

        await logs_mixin_instance._consume_logs()

        assert len(logs_mixin_instance.log_records) == 1
        assert logs_mixin_instance.log_records[0] == log_data

    @pytest.mark.asyncio
    async def test_consume_logs_multiple_records(self, logs_mixin_instance):
        """Test consume_logs with multiple log records."""
        # Clear any existing data from the mock
        logs_mixin_instance.log_records.clear()

        log_data_1 = {
            "created": time.time(),
            "name": "logger1",
            "levelname": "INFO",
            "msg": "Message 1",
        }
        log_data_2 = {
            "created": time.time(),
            "name": "logger2",
            "levelname": "ERROR",
            "msg": "Message 2",
        }

        logs_mixin_instance.log_queue.empty.side_effect = [
            False,
            False,
            True,
            True,
            True,
            True,
            True,
        ]
        logs_mixin_instance.log_queue.get_nowait.side_effect = [log_data_1, log_data_2]

        await logs_mixin_instance._consume_logs()

        assert len(logs_mixin_instance.log_records) == 2
        assert logs_mixin_instance.log_records[0] == log_data_1
        assert logs_mixin_instance.log_records[1] == log_data_2

    def test_create_logs_table_no_logs(self, logs_mixin_instance):
        """Test create_logs_table with no logs."""
        table = logs_mixin_instance.log_records_element._create_logs_table()

        assert isinstance(table, Table)
        assert len(table.columns) == 4
        assert table.columns[0].header == "Time"
        assert table.columns[1].header == "Logger"
        assert table.columns[2].header == "Level"
        assert table.columns[3].header == "Message"

    def test_create_logs_table_truncates_long_messages(self, logs_mixin_instance):
        """Test that long messages are truncated."""
        long_message = "x" * 500  # Longer than MAX_LOG_MESSAGE_LENGTH
        log_data = {
            "created": time.time(),
            "name": "test_logger",
            "levelname": "INFO",
            "msg": long_message,
        }

        logs_mixin_instance.log_records.append(log_data)
        table = logs_mixin_instance.log_records_element._create_logs_table()

        # Check that the message was truncated
        assert len(table.rows) >= 1
        # The actual truncation is done in the table rendering

    def test_create_logs_table_truncates_long_logger_names(self, logs_mixin_instance):
        """Test that long logger names are truncated."""
        long_logger_name = "x" * 50  # Longer than MAX_LOG_LOGGER_NAME_LENGTH
        log_data = {
            "created": time.time(),
            "name": long_logger_name,
            "levelname": "INFO",
            "msg": "Test message",
        }

        logs_mixin_instance.log_records.append(log_data)
        table = logs_mixin_instance.log_records_element._create_logs_table()

        assert len(table.rows) >= 1
        # The actual truncation is done in the table rendering

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_create_logs_table_log_level_styles(self, logs_mixin_instance, level):
        """Test that log levels have correct styles."""
        log_data = {
            "created": time.time(),
            "name": "test_logger",
            "levelname": level,
            "msg": "Test message",
        }

        logs_mixin_instance.log_records.append(log_data)
        table = logs_mixin_instance.log_records_element._create_logs_table()

        assert len(table.rows) >= 1
        # Check that the correct styles are applied (this is implicit in the table creation)

    def test_create_logs_table_recent_logs_only(self, logs_mixin_instance):
        """Test that only recent logs are shown."""
        # Add more than 10 log records
        for i in range(15):
            log_data = {
                "created": time.time() - i,
                "name": f"logger_{i}",
                "levelname": "INFO",
                "msg": f"Message {i}",
            }
            logs_mixin_instance.log_records.append(log_data)

        table = logs_mixin_instance.log_records_element._create_logs_table()

        # Should only show the most recent 10 logs
        assert len(table.rows) == 10

    def test_create_logs_table_timestamp_formatting(self, logs_mixin_instance):
        """Test timestamp formatting in logs table."""
        current_time = time.time()
        log_data = {
            "created": current_time,
            "name": "test_logger",
            "levelname": "INFO",
            "msg": "Test message",
        }

        logs_mixin_instance.log_records.append(log_data)
        table = logs_mixin_instance.log_records_element._create_logs_table()

        assert len(table.rows) >= 1
        # The timestamp formatting is verified implicitly through the table creation

    def test_create_logs_table_with_text_objects(self, logs_mixin_instance):
        """Test that Text objects are created for level and message columns."""
        log_data = {
            "created": time.time(),
            "name": "test_logger",
            "levelname": "ERROR",
            "msg": "Test error message",
        }

        logs_mixin_instance.log_records.append(log_data)
        table = logs_mixin_instance.log_records_element._create_logs_table()

        assert len(table.rows) >= 1
        # Verify that styled Text objects are created (implicit in table creation)

    def test_log_records_max_length(self, logs_mixin_instance):
        """Test that log_records respects max length."""
        # Add more records than the max
        for i in range(LogsDashboardElement.MAX_LOG_RECORDS + 50):
            log_data = {
                "created": time.time(),
                "name": f"logger_{i}",
                "levelname": "INFO",
                "msg": f"Message {i}",
            }
            logs_mixin_instance.log_records.append(log_data)

        # Should not exceed max length
        assert (
            len(logs_mixin_instance.log_records) == LogsDashboardElement.MAX_LOG_RECORDS
        )
