# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from aiperf.common.config import UserConfig
from aiperf.common.enums import EndpointType, ExportLevel


class TestExportLevelConfiguration:
    """Tests for --export-level configuration."""

    def test_default_is_summary(self):
        """Test that default export level is summary."""
        config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT}
        )

        assert config.output.export_level == ExportLevel.SUMMARY

    def test_can_set_to_records(self):
        """Test setting export level to records."""
        config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
            output={"export_level": ExportLevel.RECORDS},
        )

        assert config.output.export_level == ExportLevel.RECORDS

    def test_can_set_to_raw(self):
        """Test setting export level to raw."""
        config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
            output={"export_level": ExportLevel.RAW},
        )

        assert config.output.export_level == ExportLevel.RAW

    def test_accepts_string_values(self):
        """Test that export level accepts string values."""
        config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
            output={"export_level": "records"},
        )

        assert config.output.export_level == ExportLevel.RECORDS

    def test_case_insensitive(self):
        """Test that export level is case insensitive."""
        config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
            output={"export_level": "RECORDS"},
        )

        assert config.output.export_level == ExportLevel.RECORDS

    def test_all_valid_values(self):
        """Test all valid export level values."""
        for level in ["summary", "records", "raw"]:
            config = UserConfig(
                endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
                output={"export_level": level},
            )
            assert config.output.export_level in [
                ExportLevel.SUMMARY,
                ExportLevel.RECORDS,
                ExportLevel.RAW,
            ]
