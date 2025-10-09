# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from aiperf.common.config import UserConfig
from aiperf.common.config.config_defaults import OutputDefaults
from aiperf.common.config.profile_export_config import parse_profile_export_file
from aiperf.common.enums import EndpointType, ExportLevel


class TestProfileExportFileParsing:
    """Tests for parse_profile_export_file dual-purpose parser."""

    def test_none_returns_defaults(self):
        """Test that None returns default level and path."""
        result = parse_profile_export_file(None)

        assert result.export_level == ExportLevel(OutputDefaults.EXPORT_LEVEL)
        assert result.file_path == OutputDefaults.PROFILE_EXPORT_FILE

    def test_enum_only_uses_default_path(self):
        """Test that just 'records' sets level and uses default path."""
        result = parse_profile_export_file("records")

        assert result.export_level == ExportLevel.RECORDS
        assert result.file_path == OutputDefaults.PROFILE_EXPORT_FILE

    def test_all_enum_values_work(self):
        """Test all valid enum values."""
        for level in ["summary", "records", "raw"]:
            result = parse_profile_export_file(level)
            assert result.export_level == ExportLevel(level)
            assert result.file_path == OutputDefaults.PROFILE_EXPORT_FILE

    def test_path_only_uses_default_level(self):
        """Test that just 'custom.json' sets path and uses default level."""
        result = parse_profile_export_file("custom.json")

        assert result.export_level == ExportLevel(OutputDefaults.EXPORT_LEVEL)
        assert result.file_path == Path("custom.json")

    def test_enum_colon_path_sets_both(self):
        """Test that 'records:custom.json' sets both level and path."""
        result = parse_profile_export_file("records:custom.json")

        assert result.export_level == ExportLevel.RECORDS
        assert result.file_path == Path("custom.json")

    def test_all_combinations(self):
        """Test all level:path combinations."""
        test_cases = [
            ("summary:summary_export.json", ExportLevel.SUMMARY, "summary_export.json"),
            ("records:records_export.json", ExportLevel.RECORDS, "records_export.json"),
            ("raw:raw_export.json", ExportLevel.RAW, "raw_export.json"),
        ]

        for input_str, expected_level, expected_path in test_cases:
            result = parse_profile_export_file(input_str)
            assert result.export_level == expected_level
            assert result.file_path == Path(expected_path)

    def test_path_with_directory(self):
        """Test that paths with directories work."""
        result = parse_profile_export_file("path/to/export.json")

        assert result.export_level == ExportLevel(OutputDefaults.EXPORT_LEVEL)
        assert result.file_path == Path("path/to/export.json")

    def test_enum_with_complex_path(self):
        """Test enum with complex path."""
        result = parse_profile_export_file("records:exports/debug/run1.json")

        assert result.export_level == ExportLevel.RECORDS
        assert result.file_path == Path("exports/debug/run1.json")

    def test_whitespace_stripped(self):
        """Test that whitespace is stripped from both parts."""
        result = parse_profile_export_file(" records : custom.json ")

        assert result.export_level == ExportLevel.RECORDS
        assert result.file_path == Path("custom.json")

    def test_invalid_enum_raises_error(self):
        """Test that invalid enum value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid export level"):
            parse_profile_export_file("invalid:custom.json")

    def test_case_insensitive_enum(self):
        """Test that enum values are case insensitive."""
        result = parse_profile_export_file("RECORDS")

        assert result.export_level == ExportLevel.RECORDS


class TestOutputConfigWithProfileExportFile:
    """Tests for OutputConfig integration with --profile-export-file."""

    def test_default_config(self):
        """Test default configuration."""
        config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT}
        )

        assert config.output.export_level == ExportLevel.SUMMARY
        assert config.output.export_file_path == OutputDefaults.PROFILE_EXPORT_FILE

    def test_profile_export_file_enum_only(self):
        """Test --profile-export-file with enum only."""
        config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
            output={"profile_export_file": "records"},
        )

        assert config.output.export_level == ExportLevel.RECORDS
        assert config.output.export_file_path == OutputDefaults.PROFILE_EXPORT_FILE

    def test_profile_export_file_path_only(self):
        """Test --profile-export-file with path only."""
        config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
            output={"profile_export_file": "my_export.json"},
        )

        assert config.output.export_level == ExportLevel.SUMMARY
        assert config.output.export_file_path == Path("my_export.json")

    def test_profile_export_file_both(self):
        """Test --profile-export-file with both enum and path."""
        config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
            output={"profile_export_file": "raw:debug_export.json"},
        )

        assert config.output.export_level == ExportLevel.RAW
        assert config.output.export_file_path == Path("debug_export.json")
