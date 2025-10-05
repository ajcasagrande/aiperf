# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models for integration test internal data."""

from pathlib import Path

from pydantic import BaseModel, Field


class AIPerfRunResult(BaseModel):
    """Result from running AIPerf subprocess."""

    returncode: int
    stdout: str
    stderr: str
    output_dir: Path


class ValidatedOutput(BaseModel):
    """Validated AIPerf output with all artifact paths."""

    json_results: dict  # Keep as dict - will be parsed by BenchmarkResult
    csv_content: str
    actual_dir: Path
    log_file: Path
    json_file: Path
    csv_file: Path


class MockServerInfo(BaseModel):
    """Mock server connection information."""

    model_config = {"arbitrary_types_allowed": True}

    host: str
    port: int
    url: str
    process: object = Field(exclude=True)  # Subprocess
