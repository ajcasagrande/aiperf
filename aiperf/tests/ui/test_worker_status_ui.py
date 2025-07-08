# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the WorkerStatusElement UI component.
"""

import time
from unittest.mock import patch

from rich.align import Align
from rich.console import Group
from rich.table import Table
from rich.text import Text

from aiperf.ui.worker_status_ui import WorkerStatusElement


class TestWorkerStatusElement:
    """Test the WorkerStatusElement functionality."""

    def test_worker_status_element_initialization(
        self, worker_health_dict, worker_last_seen_dict
    ):
        """Test WorkerStatusElement initialization."""
        element = WorkerStatusElement(worker_health_dict, worker_last_seen_dict)

        assert element.key == "worker_status"
        assert isinstance(element.title, Text)
        assert element.title.plain == "Worker Status"
        assert element.border_style == "blue"
        assert element.worker_health == worker_health_dict
        assert element.worker_last_seen == worker_last_seen_dict

    def test_worker_status_element_class_variables(self):
        """Test WorkerStatusElement class variables."""
        assert WorkerStatusElement.key == "worker_status"
        assert isinstance(WorkerStatusElement.title, Text)
        assert WorkerStatusElement.title.plain == "Worker Status"
        assert WorkerStatusElement.border_style == "blue"

    def test_get_content_no_worker_data(self):
        """Test get_content with no worker data."""
        element = WorkerStatusElement({}, {})
        content = element.get_content()

        assert isinstance(content, Align)
        assert content.align == "center"
        assert content.vertical == "middle"

        text_content = content.renderable
        assert isinstance(text_content, Text)
        assert "No worker data available" in text_content.plain
        assert "dim yellow" in str(text_content.style)

    def test_get_content_with_worker_data(self, worker_status_element):
        """Test get_content with worker data."""
        with patch("time.time", return_value=1234567890.0):
            content = worker_status_element.get_content()

        assert isinstance(content, Group)
        assert len(content.renderables) == 2

        # First should be summary text
        summary = content.renderables[0]
        assert isinstance(summary, Text)
        assert "Summary:" in summary.plain

        # Second should be the workers table
        table = content.renderables[1]
        assert isinstance(table, Table)

    def test_get_content_worker_table_structure(self, worker_status_element):
        """Test worker table structure."""
        with patch("time.time", return_value=1234567890.0):
            content = worker_status_element.get_content()

        table = content.renderables[1]

        # Check table columns
        expected_columns = [
            "Worker ID",
            "Status",
            "Active",
            "Completed",
            "Failed",
            "CPU",
            "Memory",
            "Read",
            "Write",
        ]
        assert len(table.columns) == len(expected_columns)

        # Check that we have header row plus worker rows
        assert len(table.rows) >= 1  # At least the header row

        for i, column in enumerate(table.columns):
            assert column.header == expected_columns[i]

    def test_worker_status_stale_workers(self, worker_health_dict):
        """Test detection of stale workers."""
        current_time = time.time()
        # Make one worker stale (last seen > 30 seconds ago)
        worker_last_seen_dict = {
            list(worker_health_dict.keys())[0]: current_time - 35,  # Stale
            list(worker_health_dict.keys())[1]: current_time - 5,  # Recent
            list(worker_health_dict.keys())[2]: current_time - 10,  # Recent
        }

        element = WorkerStatusElement(worker_health_dict, worker_last_seen_dict)

        with patch("time.time", return_value=current_time):
            content = element.get_content()

        assert isinstance(content, Group)
        summary = content.renderables[0]
        assert "stale" in summary.plain

    def test_worker_status_high_error_rate(self, sample_worker_health_message):
        """Test detection of workers with high error rate."""
        # Create a worker with high error rate
        sample_worker_health_message.total_tasks = 100
        sample_worker_health_message.completed_tasks = 80
        sample_worker_health_message.failed_tasks = 20  # 20% error rate

        worker_health_dict = {
            sample_worker_health_message.service_id: sample_worker_health_message
        }
        worker_last_seen_dict = {sample_worker_health_message.service_id: time.time()}

        element = WorkerStatusElement(worker_health_dict, worker_last_seen_dict)

        with patch("time.time", return_value=1234567890.0):
            content = element.get_content()

        assert isinstance(content, Group)
        summary = content.renderables[0]
        assert "errors" in summary.plain

    def test_worker_status_idle_workers(self, sample_worker_health_message):
        """Test detection of idle workers."""
        # Create an idle worker (no tasks processed)
        sample_worker_health_message.total_tasks = 0
        sample_worker_health_message.completed_tasks = 0
        sample_worker_health_message.failed_tasks = 0

        worker_health_dict = {
            sample_worker_health_message.service_id: sample_worker_health_message
        }
        worker_last_seen_dict = {sample_worker_health_message.service_id: time.time()}

        element = WorkerStatusElement(worker_health_dict, worker_last_seen_dict)

        with patch("time.time", return_value=1234567890.0):
            content = element.get_content()

        assert isinstance(content, Group)
        summary = content.renderables[0]
        assert "idle" in summary.plain

    def test_summary_counters(self, worker_status_element):
        """Test summary counter logic."""
        with patch("time.time", return_value=1234567890.0):
            content = worker_status_element.get_content()

        assert isinstance(content, Group)
        summary = content.renderables[0]
        assert isinstance(summary, Text)

        # Check that summary contains all counter types
        summary_text = summary.plain
        assert "healthy" in summary_text
        assert "high load" in summary_text
        assert "errors" in summary_text
        assert "idle" in summary_text
        assert "stale" in summary_text

    def test_worker_table_column_formatting(self, worker_status_element):
        """Test worker table column formatting."""
        with patch("time.time", return_value=1234567890.0):
            content = worker_status_element.get_content()

        table = content.renderables[1]

        # Check column properties
        assert table.columns[0].header == "Worker ID"
        assert table.columns[1].header == "Status"
        assert table.columns[2].header == "Active"
        assert table.columns[3].header == "Completed"
        assert table.columns[4].header == "Failed"
        assert table.columns[5].header == "CPU"
        assert table.columns[6].header == "Memory"
        assert table.columns[7].header == "Read"
        assert table.columns[8].header == "Write"

    def test_worker_table_data_formatting(self, worker_status_element):
        """Test worker table data formatting."""
        with patch("time.time", return_value=1234567890.0):
            content = worker_status_element.get_content()

        table = content.renderables[1]

        # Should have header row plus worker rows
        assert len(table.rows) >= 2  # Header + at least one worker

    def test_empty_worker_health_dict(self):
        """Test with empty worker health dictionary."""
        element = WorkerStatusElement({}, {})
        content = element.get_content()

        assert isinstance(content, Align)
        assert "No worker data available" in content.renderable.plain

    def test_partial_worker_last_seen_dict(self, worker_health_dict):
        """Test with partial worker last seen dictionary."""
        # Only include some workers in last_seen
        partial_last_seen = {list(worker_health_dict.keys())[0]: time.time()}

        element = WorkerStatusElement(worker_health_dict, partial_last_seen)

        with patch("time.time", return_value=1234567890.0):
            content = element.get_content()

        assert isinstance(content, Group)
        # Should handle missing last_seen entries gracefully
