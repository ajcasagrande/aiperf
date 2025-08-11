#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Example: Multi-Turn Chat with AIPerf

This example demonstrates how to use AIPerf to test multi-turn conversations
with chat-based AI models. The system processes complete conversations per
credit and maintains conversation context across turns.

Architecture:
- One credit = one complete conversation (all turns)
- Worker processes all turns internally and maintains conversation context
- Produces multiple RequestRecords per credit (one per turn)
- Timing manager issues credits for complete conversations

Usage:
    python examples/multi_turn_chat_example.py
"""

import json
import tempfile


def create_sample_multi_turn_dataset():
    """Create a sample multi-turn conversation dataset."""

    conversations = [
        {
            "session_id": "chat_001",
            "turns": [
                {
                    "role": "user",
                    "text": "Hello! Can you help me understand how neural networks work?",
                    "delay": 0,
                },
                {
                    "role": "user",
                    "text": "What's the difference between supervised and unsupervised learning?",
                    "delay": 2000,  # 2 second delay between turns
                },
                {
                    "role": "user",
                    "text": "Can you give me a simple example of each?",
                    "delay": 1500,
                },
            ],
        },
        {
            "session_id": "chat_002",
            "turns": [
                {
                    "role": "user",
                    "text": "I'm working on a Python project and need help with async programming.",
                    "delay": 0,
                },
                {
                    "role": "user",
                    "text": "What's the difference between async/await and threading?",
                    "delay": 3000,
                },
                {
                    "role": "user",
                    "text": "When should I use each approach?",
                    "delay": 2000,
                },
            ],
        },
        {
            "session_id": "chat_003",
            "turns": [
                {
                    "role": "user",
                    "text": "What are the latest developments in large language models?",
                    "delay": 0,
                },
                {
                    "role": "user",
                    "text": "How do transformer models handle context?",
                    "delay": 2500,
                },
            ],
        },
    ]

    # Create temporary dataset file
    dataset_file = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)

    for conversation in conversations:
        # Convert to multi-turn format
        multi_turn_entry = {
            "type": "multi_turn",
            "session_id": conversation["session_id"],
            "turns": conversation["turns"],
        }
        dataset_file.write(json.dumps(multi_turn_entry) + "\n")

    dataset_file.close()
    return dataset_file.name


def create_sample_config():
    """Create a sample AIPerf configuration for multi-turn chat."""

    config = {
        # Model configuration - replace with your actual endpoint
        "model": {
            "endpoint": {
                "url": "http://localhost:8000/v1/chat/completions",
                "type": "openai_chat_completions",
                "streaming": False,
            },
            "model_name": "gpt-3.5-turbo",
        },
        # Dataset configuration
        "input": {
            "dataset": {
                "type": "custom",
                "custom_type": "multi_turn",
                "path": None,  # Will be set dynamically
            }
        },
        # Load generation configuration
        "loadgen": {
            "timing_mode": "request_rate",  # Use standard request rate for conversations
            "request_rate": 1.0,  # 1 conversation per second
            "request_count": 3,  # Process all 3 conversations
            "concurrency": 1,  # Process one conversation at a time
        },
        # Conversation-specific configuration
        "conversation": {
            "turn": {
                "num": 5,  # Maximum turns per conversation
                "delay": {
                    "mean": 1000,  # Default delay between turns (ms)
                    "stddev": 200,
                },
            }
        },
        # Worker configuration
        "workers": {"max": 2, "health_check_interval": 5.0},
        # Results configuration
        "output": {
            "results_dir": "./multi_turn_results",
            "export_formats": ["json", "csv"],
        },
    }

    return config


def main():
    """Run the multi-turn chat example."""

    print("🤖 AIPerf Multi-Turn Chat Example")
    print("=" * 50)

    # Create sample dataset
    print("📝 Creating sample multi-turn conversation dataset...")
    dataset_path = create_sample_multi_turn_dataset()
    print(f"   Dataset created: {dataset_path}")

    # Create configuration
    print("⚙️  Creating AIPerf configuration...")
    config = create_sample_config()
    config["input"]["dataset"]["path"] = dataset_path

    # Save configuration
    config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(config, config_file, indent=2)
    config_file.close()
    print(f"   Configuration saved: {config_file.name}")

    print("\n🚀 To run this example:")
    print(f"   aiperf --config {config_file.name}")

    print("\n📊 Expected behavior:")
    print("   • Each credit processes one complete conversation")
    print("   • Worker maintains conversation context across turns")
    print("   • Multiple RequestRecords generated per conversation")
    print("   • Turn delays are respected within each conversation")
    print("   • Chat completion API receives full message history")

    print("\n📈 Key metrics to observe:")
    print("   • Conversation completion rate")
    print("   • Per-turn latency within conversations")
    print("   • Context handling accuracy")
    print("   • Turn-to-turn response coherence")

    print("\n🔧 Architecture highlights:")
    print("   • One credit = one complete conversation (all turns)")
    print("   • Conversation state managed within worker")
    print("   • No cross-credit state management needed")
    print("   • Multiple RequestRecords per credit")
    print("   • Built-in conversation history for chat APIs")

    # Cleanup instructions
    print("\n🧹 Cleanup files when done:")
    print(f"   rm {dataset_path}")
    print(f"   rm {config_file.name}")


if __name__ == "__main__":
    main()
