#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Custom Single-Turn Dataset Example

This example demonstrates how to create and use a custom single-turn
dataset in JSONL format.

Dataset Format:
    Each line is a JSON object with:
    - text_input: The prompt text
    - model: (optional) Model to use for this request
    - max_tokens: (optional) Maximum output tokens

Usage:
    python custom_single_turn.py

This will:
    1. Generate a sample dataset file
    2. Run a benchmark using that dataset
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def generate_sample_dataset(output_file: Path, num_samples: int = 20):
    """
    Generate a sample single-turn dataset.

    Args:
        output_file: Path to write the dataset
        num_samples: Number of samples to generate
    """
    prompts = [
        "What is the capital of France?",
        "Explain quantum computing in simple terms.",
        "Write a haiku about programming.",
        "What are the benefits of exercise?",
        "Describe the water cycle.",
        "What is machine learning?",
        "How do computers work?",
        "Explain photosynthesis.",
        "What causes earthquakes?",
        "Describe the solar system.",
    ]

    with open(output_file, "w") as f:
        for i in range(num_samples):
            prompt = prompts[i % len(prompts)]

            # Create a single-turn entry
            entry = {
                "text_input": prompt,
                # Optional: specify model (if using multiple models)
                # "model": "model-name",
                # Optional: specify max output tokens
                "max_tokens": 100 if i % 2 == 0 else 200,
            }

            f.write(json.dumps(entry) + "\n")

    print(f"Generated {num_samples} samples in {output_file}")


def run_benchmark_with_dataset(dataset_file: Path):
    """
    Run a benchmark using the custom dataset.

    Args:
        dataset_file: Path to the dataset file
    """
    from aiperf.cli_runner import run_system_controller
    from aiperf.common.config import (
        EndpointConfig,
        InputConfig,
        LoadGeneratorConfig,
        UserConfig,
        load_service_config,
    )
    from aiperf.common.enums import CustomDatasetType, EndpointType

    print("\nRunning benchmark with custom dataset...")
    print("=" * 60)

    # Configure endpoint
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,
    )

    # Configure input with custom dataset
    input_config = InputConfig(
        file=dataset_file,
        custom_dataset_type=CustomDatasetType.SINGLE_TURN,
        random_seed=42,  # For reproducibility
    )

    # Configure load generation
    loadgen_config = LoadGeneratorConfig(
        concurrency=5,
        # No request_count needed - uses all entries in dataset
    )

    # Create user configuration
    user_config = UserConfig(
        endpoint=endpoint_config,
        input=input_config,
        loadgen=loadgen_config,
    )

    # Load service configuration
    service_config = load_service_config()

    print(f"Dataset: {dataset_file}")
    print(f"Dataset type: {CustomDatasetType.SINGLE_TURN.value}")
    print(f"Concurrency: {loadgen_config.concurrency}")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)
    except KeyboardInterrupt:
        print("\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        sys.exit(1)


def main():
    """Main function."""
    # Create output directory
    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)

    # Generate sample dataset
    dataset_file = output_dir / "sample_single_turn.jsonl"
    generate_sample_dataset(dataset_file, num_samples=20)

    print("\nDataset Format Example:")
    print("-" * 60)
    with open(dataset_file) as f:
        # Show first 3 lines
        for i, line in enumerate(f):
            if i >= 3:
                break
            print(json.dumps(json.loads(line), indent=2))
            print()

    # Run benchmark
    response = input("\nRun benchmark with this dataset? [y/N]: ")
    if response.lower() == "y":
        run_benchmark_with_dataset(dataset_file)
    else:
        print(f"\nDataset saved to: {dataset_file}")
        print("You can run a benchmark later with:")
        print(f"  aiperf profile --file {dataset_file} \\")
        print("    --custom-dataset-type single_turn \\")
        print("    --model Qwen/Qwen3-0.6B \\")
        print("    --url http://localhost:8000 \\")
        print("    --endpoint-type chat \\")
        print("    --concurrency 5")


if __name__ == "__main__":
    main()
