# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.utils import format_bytes, format_duration


class TestFormatDuration:
    """Test cases for format_duration function."""

    def test_none_input_default_str(self):
        """Test that None input returns default '--' string."""
        result = format_duration(None)
        assert result == "--"

    def test_none_input_custom_str(self):
        """Test that None input returns custom none_str."""
        result = format_duration(None, none_str="N/A")
        assert result == "N/A"

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (0.0, "0.0s"),
            (0.1, "0.1s"),
            (1.0, "1.0s"),
            (30.5, "30.5s"),
            (59.9, "59.9s"),
        ],
    )
    def test_seconds_range(self, seconds, expected):
        """Test formatting for values in seconds range (< 60)."""
        result = format_duration(seconds)
        assert result == expected

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (60.0, "1m"),
            (60.5, "1m 1s"),
            (61.0, "1m 1s"),
            (90.0, "1m 30s"),
            (120.0, "2m"),
            (3599.0, "59m 59s"),
        ],
    )
    def test_minutes_range(self, seconds, expected):
        """Test formatting for values in minutes range (60 <= seconds < 3600)."""
        result = format_duration(seconds)
        assert result == expected

    def test_minutes_range_no_seconds(self):
        """Test formatting for exact minute values with no remaining seconds."""
        result = format_duration(180.0)  # 3 minutes exactly
        assert result == "3m"

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (3600.0, "1h"),
            (3660.0, "1h 1m"),
            (7200.0, "2h"),
            (7260.0, "2h 1m"),
            (86399.0, "23h 59m"),
        ],
    )
    def test_hours_range(self, seconds, expected):
        """Test formatting for values in hours range (3600 <= seconds < 86400)."""
        result = format_duration(seconds)
        assert result == expected

    def test_hours_range_no_minutes(self):
        """Test formatting for exact hour values with no remaining minutes."""
        result = format_duration(10800.0)  # 3 hours exactly
        assert result == "3h"

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (86400.0, "1d"),
            (90000.0, "1d 1h"),
            (172800.0, "2d"),
            (176400.0, "2d 1h"),
            (604800.0, "7d"),
        ],
    )
    def test_days_range(self, seconds, expected):
        """Test formatting for values in days range (>= 86400)."""
        result = format_duration(seconds)
        assert result == expected

    def test_days_range_no_hours(self):
        """Test formatting for exact day values with no remaining hours."""
        result = format_duration(259200.0)  # 3 days exactly
        assert result == "3d"

    def test_boundary_values(self):
        """Test boundary values between different time units."""
        # Just under 1 minute
        assert format_duration(59.999) == "60.0s"

        # Exactly 1 minute
        assert format_duration(60.0) == "1m"

        # Just over 1 minute
        assert format_duration(60.1) == "1m 0s"

        # Just under 1 hour
        assert format_duration(3599.0) == "59m 59s"

        # Exactly 1 hour
        assert format_duration(3600.0) == "1h"

        # Just under 1 day
        assert format_duration(86399.0) == "23h 59m"

        # Exactly 1 day
        assert format_duration(86400.0) == "1d"

    def test_large_values(self):
        """Test very large duration values."""
        # 365 days
        seconds_in_year = 365 * 24 * 60 * 60
        result = format_duration(seconds_in_year)
        assert result == "365d"

        # 365 days + 1 hour
        result = format_duration(seconds_in_year + 3600)
        assert result == "365d 1h"


class TestFormatBytes:
    """Test cases for format_bytes function."""

    def test_none_input_default_str(self):
        """Test that None input returns default '--' string."""
        result = format_bytes(None)
        assert result == "--"

    def test_none_input_custom_str(self):
        """Test that None input returns custom none_str."""
        result = format_bytes(None, none_str="Unknown")
        assert result == "Unknown"

    @pytest.mark.parametrize(
        "bytes_value,expected",
        [
            (0, "0 B"),
            (1, "1 B"),
            (512, "512 B"),
            (1023, "1.0 KB"),
        ],
    )
    def test_bytes_range(self, bytes_value, expected):
        """Test formatting for values in bytes range (< 1024)."""
        result = format_bytes(bytes_value)
        assert result == expected

    @pytest.mark.parametrize(
        "bytes_value,expected",
        [
            (1024, "1.0 KB"),
            (1536, "1.5 KB"),
            (51200, "50.0 KB"),
            (102400, "100 KB"),
            (512000, "500 KB"),
            (1023999, "1000 KB"),
        ],
    )
    def test_kilobytes_range(self, bytes_value, expected):
        """Test formatting for values in kilobytes range."""
        result = format_bytes(bytes_value)
        assert result == expected

    @pytest.mark.parametrize(
        "bytes_value,expected",
        [
            (1024 * 1024, "1.0 MB"),
            (1536 * 1024, "1.5 MB"),
            (51200 * 1024, "50.0 MB"),
            (102400 * 1024, "100 MB"),
            (512000 * 1024, "500 MB"),
        ],
    )
    def test_megabytes_range(self, bytes_value, expected):
        """Test formatting for values in megabytes range."""
        result = format_bytes(bytes_value)
        assert result == expected

    @pytest.mark.parametrize(
        "bytes_value,expected",
        [
            (1024**3, "1.0 GB"),
            (int(1.5 * 1024**3), "1.5 GB"),
            (50 * 1024**3, "50.0 GB"),
            (100 * 1024**3, "100 GB"),
            (500 * 1024**3, "500 GB"),
        ],
    )
    def test_gigabytes_range(self, bytes_value, expected):
        """Test formatting for values in gigabytes range."""
        result = format_bytes(bytes_value)
        assert result == expected

    def test_higher_units(self):
        """Test formatting for TB, PB, and higher units."""
        # 1 TB
        result = format_bytes(1024**4)
        assert result == "1.0 TB"

        # 1 PB
        result = format_bytes(1024**5)
        assert result == "1.0 PB"

        # 1 EB
        result = format_bytes(1024**6)
        assert result == "1.0 EB"

    def test_boundary_values(self):
        """Test boundary values between different byte units."""
        # Just under 1 KB
        assert format_bytes(1023) == "1023 B"

        # Exactly 1 KB
        assert format_bytes(1024) == "1.0 KB"

        # Just over 1 KB
        assert format_bytes(1025) == "1.0 KB"

        # Just under 1 MB
        assert format_bytes(1024 * 1024 - 1) == "1000 KB"

        # Exactly 1 MB
        assert format_bytes(1024 * 1024) == "1.0 MB"

    def test_decimal_precision(self):
        """Test decimal precision rules."""
        # Values < 100 in unit should show 1 decimal place
        assert format_bytes(int(1.5 * 1024)) == "1.5 KB"
        assert format_bytes(int(99.9 * 1024)) == "99.9 KB"

        # Values >= 100 but < 1000 should show 0 decimal places
        assert format_bytes(100 * 1024) == "100 KB"
        assert format_bytes(999 * 1024) == "999 KB"

    def test_large_values_raise_error(self):
        """Test that extremely large values raise ValueError."""
        # Create a value that would exceed the available suffixes
        extremely_large_value = 1024**10  # Way beyond YB

        with pytest.raises(ValueError, match="Bytes value is too large to format"):
            format_bytes(extremely_large_value)

    def test_rounding_behavior(self):
        """Test rounding behavior for decimal values."""
        # Test that values round appropriately
        result = format_bytes(1536)  # 1.5 KB exactly
        assert result == "1.5 KB"

        result = format_bytes(1537)  # Should round to 1.5 KB
        assert result == "1.5 KB"

        result = format_bytes(1740)  # Should round to 1.7 KB
        assert result == "1.7 KB"

    def test_edge_case_zero(self):
        """Test edge case of zero bytes."""
        result = format_bytes(0)
        assert result == "0 B"

    @pytest.mark.parametrize(
        "suffix_index,expected_suffix",
        [
            (0, "B"),
            (1, "KB"),
            (2, "MB"),
            (3, "GB"),
            (4, "TB"),
            (5, "PB"),
            (6, "EB"),
            (7, "ZB"),
            (8, "YB"),
        ],
    )
    def test_all_suffixes(self, suffix_index, expected_suffix):
        """Test that all defined suffixes are used correctly."""
        if suffix_index == 0:
            # Special case for bytes
            bytes_value = 1
            expected = f"1 {expected_suffix}"
        else:
            bytes_value = 1024**suffix_index
            expected = f"1.0 {expected_suffix}"

        result = format_bytes(bytes_value)
        assert result == expected
