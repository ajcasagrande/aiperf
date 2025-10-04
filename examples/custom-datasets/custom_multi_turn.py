#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Custom Multi-Turn Dataset Example

This example demonstrates creating and using multi-turn conversation datasets.

Multi-turn datasets enable benchmarking:
- Conversational AI systems
- Context retention
- Multi-exchange interactions
- Turn delays (simulating user think time)

Usage:
    python custom_multi_turn.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def generate_multi_turn_dataset(output_file: Path, num_conversations: int = 10):
    """
    Generate a sample multi-turn conversation dataset.

    Multi-turn format (one conversation per line):
    {
        "session_id": "unique-id",
        "turns": [
            {
                "text_input": "Hello, how are you?",
                "delay": 0,
                "role": "user"
            },
            {
                "text_input": "What's the weather like?",
                "delay": 2000,  # 2 second delay
                "role": "user"
            }
        ]
    }

    Args:
        output_file: Path to write the dataset
        num_conversations: Number of conversations to generate
    """

    conversation_templates = [
        # Technical support conversation
        {
            "turns": [
                {"text": "My application is running slowly.", "delay": 0},
                {"text": "I've tried restarting already.", "delay": 3000},
                {"text": "How do I check the logs?", "delay": 5000},
            ]
        },
        # Information gathering
        {
            "turns": [
                {"text": "What is machine learning?", "delay": 0},
                {"text": "Can you give me an example?", "delay": 4000},
                {"text": "How is that different from AI?", "delay": 3000},
            ]
        },
        # Problem solving
        {
            "turns": [
                {"text": "I need to optimize my code.", "delay": 0},
                {"text": "It's a Python web server.", "delay": 2000},
                {"text": "How do I profile it?", "delay": 4000},
            ]
        },
    ]

    with open(output_file, "w") as f:
        for i in range(num_conversations):
            template = conversation_templates[i % len(conversation_templates)]

            # Create conversation with session_id
            conversation = {
                "session_id": f"conversation_{i:04d}",
                "turns": [
                    {
                        "text_input": turn["text"],
                        "delay": turn["delay"],
                        "role": "user",
                        # Optional: model per turn
                        # "model": "specific-model",
                        # Optional: max tokens per turn
                        # "max_tokens": 150,
                    }
                    for turn in template["turns"]
                ],
            }

            f.write(json.dumps(conversation) + "\n")

    print(f"Generated {num_conversations} multi-turn conversations")
    print(f"File: {output_file}")


def run_multi_turn_benchmark(dataset_file: Path):
    """
    Run a benchmark with multi-turn conversations.

    Args:
        dataset_file: Path to the multi-turn dataset
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

    print("\nRunning multi-turn conversation benchmark...")
    print("=" * 60)

    # Configure endpoint
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,
    )

    # Configure input with multi-turn dataset
    input_config = InputConfig(
        file=dataset_file,
        custom_dataset_type=CustomDatasetType.MULTI_TURN,
        random_seed=42,
    )

    # Configure load generation
    # Concurrency applies to conversations, not individual turns
    loadgen_config = LoadGeneratorConfig(
        concurrency=3,  # 3 conversations in parallel
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        input=input_config,
        loadgen=loadgen_config,
    )

    service_config = load_service_config()

    print(f"Dataset: {dataset_file}")
    print("Type: Multi-turn conversations")
    print(f"Concurrency: {loadgen_config.concurrency} conversations")
    print("\nNote: Each conversation's turns execute sequentially with delays.")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)

        print("\n" + "=" * 60)
        print("Multi-Turn Metrics Explained")
        print("=" * 60)
        print("\nIn multi-turn benchmarks:")
        print("  - Request metrics are computed PER TURN")
        print("  - Each turn is an independent request to the API")
        print("  - Delays between turns simulate user think time")
        print("  - Conversation history is maintained across turns")
        print("\nThe request count in results = total turns across all conversations")

    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        sys.exit(1)


def main():
    """Main function."""
    # Create output directory
    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)

    # Generate sample dataset
    dataset_file = output_dir / "sample_multi_turn.jsonl"
    generate_multi_turn_dataset(dataset_file, num_conversations=10)

    print("\nDataset Format Example:")
    print("-" * 60)
    with open(dataset_file) as f:
        # Show first conversation
        line = f.readline()
        conv = json.loads(line)
        print(json.dumps(conv, indent=2))

    # Run benchmark
    response = input("\nRun multi-turn benchmark? [y/N]: ")
    if response.lower() == "y":
        run_multi_turn_benchmark(dataset_file)
    else:
        print(f"\nDataset saved to: {dataset_file}")
        print("\nYou can run the benchmark later with:")
        print(f"  aiperf profile --file {dataset_file} \\")
        print("    --custom-dataset-type multi_turn \\")
        print("    --model Qwen/Qwen3-0.6B \\")
        print("    --url http://localhost:8000 \\")
        print("    --endpoint-type chat \\")
        print("    --concurrency 3")


if __name__ == "__main__":
    main()
