# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Benchmark Test Helpers

Utilities for creating test configurations and running benchmarks in tests.
"""

from pathlib import Path

from aiperf.common.config import (
    EndpointConfig,
    InputConfig,
    LoadGeneratorConfig,
    PromptConfig,
    ServiceConfig,
    UserConfig,
)
from aiperf.common.config.prompt_config import InputTokensConfig, OutputTokensConfig
from aiperf.common.enums import AIPerfUIType, EndpointType


def create_test_user_config(
    model_name: str = "test-model",
    url: str = "http://localhost:8000",
    request_count: int = 10,
    concurrency: int = 2,
    streaming: bool = True,
) -> UserConfig:
    """Create a standard UserConfig for tests.

    Args:
        model_name: Model name to use
        url: Endpoint URL
        request_count: Number of requests
        concurrency: Concurrent request limit
        streaming: Enable streaming

    Returns:
        UserConfig instance for testing
    """
    endpoint_config = EndpointConfig(
        model_names=[model_name],
        url=url,
        type=EndpointType.CHAT,
        streaming=streaming,
        timeout_seconds=30.0,
    )

    prompt_config = PromptConfig(
        input_tokens=InputTokensConfig(mean=50, stddev=10),
        output_tokens=OutputTokensConfig(mean=50, stddev=10),
    )

    input_config = InputConfig(
        prompt=prompt_config,
        random_seed=42,
    )

    loadgen_config = LoadGeneratorConfig(
        request_count=request_count,
        concurrency=concurrency,
        warmup_request_count=0,
    )

    return UserConfig(
        endpoint=endpoint_config,
        input=input_config,
        loadgen=loadgen_config,
    )


def create_test_service_config(
    ui_type: AIPerfUIType = AIPerfUIType.NO_UI,
    log_level: str = "INFO",
) -> ServiceConfig:
    """Create a standard ServiceConfig for tests.

    Args:
        ui_type: UI type to use
        log_level: Log level

    Returns:
        ServiceConfig instance for testing
    """
    return ServiceConfig(
        ui_type=ui_type,
        log_level=log_level,
    )


def create_minimal_dataset_file(output_path: Path, num_prompts: int = 10) -> Path:
    """Create a minimal single-turn dataset for testing.

    Args:
        output_path: Path to write the dataset
        num_prompts: Number of prompts to generate

    Returns:
        Path to the created dataset file
    """
    import json

    prompts = [
        "What is AI?",
        "Explain machine learning.",
        "What is deep learning?",
        "How do neural networks work?",
        "What is NLP?",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for i in range(num_prompts):
            entry = {
                "text_input": prompts[i % len(prompts)],
            }
            f.write(json.dumps(entry) + "\n")

    return output_path


def create_trace_dataset_file(
    output_path: Path,
    num_requests: int = 20,
    duration_seconds: int = 10,
) -> Path:
    """Create a trace dataset for testing.

    Args:
        output_path: Path to write the dataset
        num_requests: Number of requests in trace
        duration_seconds: Total duration of trace

    Returns:
        Path to the created dataset file
    """
    import json
    import time

    start_time_ms = int(time.time() * 1000)
    interval_ms = (duration_seconds * 1000) // num_requests

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for i in range(num_requests):
            timestamp_ms = start_time_ms + (i * interval_ms)
            entry = {
                "timestamp": timestamp_ms,
                "text_input": f"Request {i}",
            }
            f.write(json.dumps(entry) + "\n")

    return output_path
