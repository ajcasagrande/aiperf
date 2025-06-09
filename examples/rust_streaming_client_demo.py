#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Demo script for the ultra high-performance Rust streaming OpenAI client.

This script demonstrates:
- Basic usage of the Rust streaming client
- Performance optimization configurations
- Advanced timing analysis with Pydantic models
- Concurrent request handling
- Error handling and fallback strategies
"""

import asyncio
import json
import os

from aiperf.backend.openai_client_rust_streaming import (
    OpenAIBackendClientRustStreaming,
    RustStreamingPerformanceConfig,
)
from aiperf.backend.openai_common import (
    OpenAIBackendClientConfig,
    OpenAIChatCompletionRequest,
)


async def demo_basic_usage():
    """Demonstrate basic usage of the Rust streaming client."""
    print("🚀 Demo 1: Basic Rust Streaming Client Usage")
    print("=" * 50)

    try:
        # Create client configuration
        config = OpenAIBackendClientConfig(
            url="http://127.0.0.1:8080",  # Your OpenAI-compatible API endpoint
            api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            max_tokens=50,
            timeout_ms=30000,
        )

        # Initialize the ultra high-performance Rust streaming client
        async with OpenAIBackendClientRustStreaming(config) as client:
            print(f"✅ Client initialized with config: {config.model}")

            # Create a chat completion request
            request = OpenAIChatCompletionRequest(
                model=config.model,
                max_tokens=config.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": "Explain quantum computing in simple terms.",
                    }
                ],
            )

            print("📤 Sending streaming request...")

            # Send the request with nanosecond precision timing
            response = await client.send_chat_completion_request(request)

            print(f"✅ Received {len(response.responses)} response chunks")

            # Display performance statistics
            stats = client.get_performance_statistics()
            print("📊 Performance Statistics:")
            for key, value in stats.items():
                if key != "performance_config":
                    print(f"   • {key}: {value}")

            # Show first few response chunks
            print("\n📋 First few response chunks:")
            for i, chunk in enumerate(response.responses[:3]):
                if hasattr(chunk, "response") and hasattr(chunk, "timestamp_ns"):
                    print(f"   Chunk {i + 1}: {chunk.response[:100]}...")
                    print(f"   Timestamp: {chunk.timestamp_ns}")

    except ImportError:
        print("❌ Rust streaming library not available.")
        print("   Please install: cd lib/streaming && pip install .")
    except Exception as e:
        print(f"❌ Error: {e}")


async def demo_performance_optimization():
    """Demonstrate performance optimization features."""
    print("\n🔧 Demo 2: Performance Optimization Configuration")
    print("=" * 55)

    try:
        # Create optimized performance configuration
        perf_config = RustStreamingPerformanceConfig(
            timeout_ms=60000,  # 60 second timeout
            connect_timeout_ms=3000,  # 3 second connect timeout
            chunk_buffer_size=16384,  # 16KB buffer size
            max_concurrent_requests=20,  # Support 20 concurrent requests
            enable_gzip_compression=True,  # Enable compression
            keep_alive_timeout_ms=45000,  # 45 second keep-alive
            user_agent="aiperf-rust-demo/1.0",
        )

        config = OpenAIBackendClientConfig(
            url="http://127.0.0.1:8080",
            api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            max_tokens=100,
            temperature=0.7,
            top_p=0.9,
            timeout_ms=perf_config.timeout_ms,
        )

        async with OpenAIBackendClientRustStreaming(config) as client:
            # Override performance config
            client.perf_config = perf_config

            print("🚀 Client configured with optimized performance settings:")
            print(f"   • Timeout: {perf_config.timeout_ms}ms")
            print(f"   • Buffer size: {perf_config.chunk_buffer_size} bytes")
            print(f"   • Max concurrent: {perf_config.max_concurrent_requests}")
            print(f"   • Compression: {perf_config.enable_gzip_compression}")

            # Test with a more complex request
            request = OpenAIChatCompletionRequest(
                model=config.model,
                max_tokens=config.max_tokens,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {
                        "role": "user",
                        "content": "Write a short story about a robot learning to paint.",
                    },
                ],
                kwargs={
                    "temperature": config.temperature,
                    "top_p": config.top_p,
                },
            )

            print("\n📤 Sending optimized streaming request...")
            response = await client.send_chat_completion_request(request)

            print(f"✅ Received {len(response.responses)} chunks")

            # Show detailed performance metrics
            stats = client.get_performance_statistics()
            print("\n📈 Detailed Performance Metrics:")
            for key, value in stats.items():
                print(f"   • {key}: {value}")

    except Exception as e:
        print(f"❌ Error: {e}")


async def demo_concurrent_requests():
    """Demonstrate concurrent request handling."""
    print("\n🚁 Demo 3: Concurrent Request Handling")
    print("=" * 45)

    try:
        config = OpenAIBackendClientConfig(
            url="http://localhost:8080",
            api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            max_tokens=100,
            timeout_ms=20000,
        )

        async def send_concurrent_request(prompt: str, request_id: int):
            """Send a single concurrent request."""
            async with OpenAIBackendClientRustStreaming(config) as client:
                request = OpenAIChatCompletionRequest(
                    model=config.model,
                    max_tokens=config.max_tokens,
                    messages=[
                        {"role": "user", "content": f"{prompt} (Request {request_id})"}
                    ],
                )

                response = await client.send_chat_completion_request(request)
                print(f"\n\nResponse {request_id}:")
                prev = response.start_perf_counter_ns
                for i, r in enumerate(response.responses):
                    print(
                        f"\tPayload {i}: {(r.timestamp_ns - prev) / 1_000_000:10.2f} ms"
                    )
                    prev = r.timestamp_ns
                stats = client.get_performance_statistics()

                return {
                    "request_id": request_id,
                    "response_count": len(response.responses),
                    "stats": stats,
                }

        # Create concurrent requests
        prompts = [
            " HECTOR Who must we answer AENEAS The noble Menelaus HECTOR O you my lord By Mars his gauntlet thanks Mock not that I affect the untraded oath Your quondam wife swears still by Venus glove Shes well but bade me not commend her to you MENELAUS Name her not now sir shes a deadly theme HECTOR O pardon I offend NESTOR I have thou gallant Trojan seen thee oft Labouring for destiny make cruel way Through ranks of Greekish youth and I have seen thee As hot as Perseus spur thy Phrygian steed Despising",
        ] * 10

        print(f"📤 Sending {len(prompts)} concurrent requests...")

        # Execute requests concurrently
        tasks = [
            send_concurrent_request(prompt, i + 1) for i, prompt in enumerate(prompts)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        print("✅ Concurrent requests completed!")

        # Analyze results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        failed_results = [r for r in results if isinstance(r, Exception)]

        print("\n📊 Results Summary:")
        print(f"   • Successful: {len(successful_results)}")
        print(f"   • Failed: {len(failed_results)}")

        if successful_results:
            avg_response_count = sum(
                r["response_count"] for r in successful_results
            ) / len(successful_results)
            print(f"   • Average response chunks: {avg_response_count:.1f}")

        if failed_results:
            print("❌ Failed requests:")
            for i, error in enumerate(failed_results):
                print(f"   Request {i + 1}: {error}")

    except Exception as e:
        print(f"❌ Error: {e}")


async def demo_advanced_analytics():
    """Demonstrate advanced analytics and timing analysis."""
    print("\n📊 Demo 4: Advanced Analytics and Timing Analysis")
    print("=" * 55)

    try:
        config = OpenAIBackendClientConfig(
            url="http://127.0.0.1:8080",
            api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            max_tokens=75,
            timeout_ms=25000,
        )

        # Collect multiple requests for analysis
        # request_models = []

        async with OpenAIBackendClientRustStreaming(config) as client:
            print("🔍 Collecting data for advanced analysis...")

            test_prompts = [
                "Explain photosynthesis.",
                "What is the capital of France?",
                "How do computers work?",
            ]

            for i, prompt in enumerate(test_prompts):
                request = OpenAIChatCompletionRequest(
                    model=config.model,
                    max_tokens=config.max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )

                print(f"   Request {i + 1}: {prompt}")
                response = await client.send_chat_completion_request(request)

                # Note: The exact conversion to StreamingRequestModel would depend on
                # the specific API of the Rust library. This is a placeholder.
                print(f"   ✅ Received {len(response.responses)} chunks")

                # Add a small delay between requests
                await asyncio.sleep(0.1)

            # Get comprehensive performance statistics
            stats = client.get_performance_statistics()
            print("\n📈 Comprehensive Performance Analysis:")
            print(json.dumps(stats, indent=2, default=str))

    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Run all demo scenarios."""
    print("🎯 Ultra High-Performance Rust Streaming Client Demo")
    print("=" * 60)
    print("This demo showcases the capabilities of the new Rust streaming client.")
    print()

    # Run all demos
    # await demo_basic_usage()
    # await demo_performance_optimization()
    await demo_concurrent_requests()
    # await demo_advanced_analytics()

    print("\n🎉 Demo complete! The Rust streaming client provides:")
    print("   ✅ Nanosecond precision timing")
    print("   ✅ Ultra-high performance streaming")
    print("   ✅ Zero-copy chunk processing")
    print("   ✅ Advanced performance analytics")
    print("   ✅ Configurable optimization settings")
    print("   ✅ Concurrent request support")
    print("\n💡 To use in production, install the Rust library:")
    print("   cd lib/streaming && pip install .")


if __name__ == "__main__":
    asyncio.run(main())
