#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
OpenAI-Compatible Endpoint Example

Demonstrates benchmarking any OpenAI-compatible inference endpoint.

Many inference servers (vLLM, TGI, Ollama, etc.) provide OpenAI-compatible
APIs, allowing easy integration.

Usage:
    python openai_compatible.py

This example can be adapted for:
    - vLLM (localhost:8000)
    - TGI (localhost:8080)
    - Ollama (localhost:11434/v1)
    - LM Studio (localhost:1234/v1)
    - Jan.ai (localhost:1337/v1)
    - Any custom OpenAI-compatible server
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiperf.cli_runner import run_system_controller
from aiperf.common.config import (
    EndpointConfig,
    InputConfig,
    LoadGeneratorConfig,
    UserConfig,
    load_service_config,
)
from aiperf.common.enums import EndpointType


def benchmark_server(
    server_name: str,
    url: str,
    model_name: str,
    api_key: str = None,
):
    """
    Benchmark an OpenAI-compatible server.

    Args:
        server_name: Display name for the server
        url: Base URL (e.g., http://localhost:8000)
        model_name: Model identifier
        api_key: Optional API key for authentication
    """
    print(f"\n{server_name} Benchmark")
    print("=" * 60)

    # Configure endpoint
    endpoint_config = EndpointConfig(
        model_names=[model_name],
        url=url,
        type=EndpointType.CHAT,  # Most servers support /v1/chat/completions
        streaming=True,
        api_key=api_key,
        timeout_seconds=300.0,
    )

    # Optional: Add custom headers for specific servers
    # For example, some servers require specific headers
    input_config = InputConfig(
        # headers=[("X-Custom-Header", "value")],
        random_seed=42,
    )

    # Standard benchmark configuration
    loadgen_config = LoadGeneratorConfig(
        request_rate=10.0,
        concurrency=5,
        request_count=100,
        warmup_request_count=10,
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        input=input_config,
        loadgen=loadgen_config,
    )

    service_config = load_service_config()

    print(f"  Server: {server_name}")
    print(f"  URL: {url}")
    print(f"  Model: {model_name}")
    print(f"  Authentication: {'Yes (API Key)' if api_key else 'No'}")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)
        print(f"\n{server_name} benchmark completed successfully")

    except KeyboardInterrupt:
        print(f"\n\n{server_name} benchmark cancelled")
        raise
    except Exception as e:
        print(f"\n\n{server_name} benchmark failed: {e}")
        raise


def main():
    """Run benchmarks for common OpenAI-compatible servers."""

    print("OpenAI-Compatible Server Benchmarks")
    print("\nThis script demonstrates benchmarking various inference servers")
    print("that provide OpenAI-compatible APIs.\n")

    # Configuration for different servers
    servers = {
        "1": {
            "name": "vLLM",
            "url": "http://localhost:8000",
            "model": "Qwen/Qwen3-0.6B",
            "description": "High-performance inference with PagedAttention",
        },
        "2": {
            "name": "TGI",
            "url": "http://localhost:8080",
            "model": "Qwen/Qwen3-0.6B",
            "description": "HuggingFace optimized inference",
        },
        "3": {
            "name": "Ollama",
            "url": "http://localhost:11434/v1",
            "model": "qwen2.5:0.5b",
            "description": "Local model runner with easy setup",
        },
        "4": {
            "name": "LM Studio",
            "url": "http://localhost:1234/v1",
            "model": "qwen2.5-0.5b-instruct",
            "description": "Desktop application for local inference",
        },
        "5": {
            "name": "Custom",
            "url": "http://localhost:8000",
            "model": "your-model-name",
            "description": "Your custom OpenAI-compatible server",
        },
    }

    print("Select a server to benchmark:")
    for key, server in servers.items():
        print(f"  {key}. {server['name']}: {server['description']}")

    choice = input("\nEnter choice [1-5]: ").strip()

    if choice not in servers:
        print("Invalid choice")
        sys.exit(1)

    server = servers[choice]

    # Allow customization
    url = input(f"URL [{server['url']}]: ").strip() or server["url"]
    model = input(f"Model [{server['model']}]: ").strip() or server["model"]
    api_key = input("API Key (leave empty if none): ").strip() or None

    try:
        benchmark_server(
            server_name=server["name"],
            url=url,
            model_name=model,
            api_key=api_key,
        )

    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Verify server is running")
        print("  2. Check URL and port are correct")
        print("  3. Verify model is loaded")
        print("  4. Test with curl:")
        print(f"     curl {url}/v1/models")
        sys.exit(1)


if __name__ == "__main__":
    main()
