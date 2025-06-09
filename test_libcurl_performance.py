#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Performance test script for the libcurl OpenAI client.

Tests the libcurl client by sending 20 concurrent requests with different
100-token synthetic payloads and measuring performance metrics.
"""

import asyncio
import os
import time

from aiperf.backend.openai_client_libcurl import OpenAIBackendClientLibcurl
from aiperf.backend.openai_common import (
    OpenAIBackendClientConfig,
    OpenAIChatCompletionRequest,
)


def generate_synthetic_payloads(
    count: int = 20, tokens_per_payload: int = 100
) -> list[str]:
    """Generate synthetic chat payloads with approximately the specified token count."""

    # Base words to create variety (roughly 1 token per word for estimation)
    base_words = [
        "artificial",
        "intelligence",
        "machine",
        "learning",
        "neural",
        "network",
        "algorithm",
        "data",
        "science",
        "technology",
        "computer",
        "programming",
        "software",
        "development",
        "innovation",
        "research",
        "analysis",
        "model",
        "training",
        "optimization",
        "performance",
        "efficiency",
        "scalability",
        "automation",
        "prediction",
        "classification",
        "regression",
        "clustering",
        "deep",
        "reinforcement",
        "supervised",
        "unsupervised",
        "feature",
        "extraction",
        "preprocessing",
        "validation",
        "testing",
        "deployment",
        "production",
        "monitoring",
        "evaluation",
        "metrics",
        "accuracy",
        "precision",
        "recall",
        "framework",
        "library",
        "pipeline",
        "workflow",
    ]

    payloads = []
    for i in range(count):
        # Create a unique prompt for each request
        topic = f"Request {i + 1}"

        # Generate approximately 100 tokens by repeating words
        words_needed = tokens_per_payload - 20  # Account for base prompt structure
        prompt_words = []

        for j in range(words_needed):
            word_idx = (i * words_needed + j) % len(base_words)
            prompt_words.append(base_words[word_idx])

        payload = f"""
        {topic}: Please analyze the following concepts and provide insights on their relationships:
        {" ".join(prompt_words[: tokens_per_payload - 20])}

        Focus on practical applications and future implications.
        """.strip()

        payloads.append(payload)

    return payloads


async def send_single_request(
    client: OpenAIBackendClientLibcurl, payload: str, request_id: int
) -> dict:
    """Send a single chat completion request and measure performance."""

    start_time = time.perf_counter_ns()

    try:
        # Create the request
        request = OpenAIChatCompletionRequest(
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",  # Will be overridden by client config
            max_tokens=100,
            messages=[{"role": "user", "content": payload}],
        )

        # Send the request
        record = await client.send_chat_completion_request(request)

        end_time = time.perf_counter_ns()
        total_duration_ns = end_time - start_time

        # Calculate metrics
        result = {
            "request_id": request_id,
            "success": record.valid and not record.has_error,
            "total_duration_ms": total_duration_ns / 1e6,
            "response_count": len(record.responses),
            "payload_length": len(payload),
        }

        if record.valid:
            result.update(
                {
                    "ttft_ms": record.time_to_first_response_ns / 1e6
                    if record.time_to_first_response_ns
                    else None,
                    "ttst_ms": record.time_to_second_response_ns / 1e6
                    if record.time_to_second_response_ns
                    else None,
                    "ttlt_ms": record.time_to_last_response_ns / 1e6
                    if record.time_to_last_response_ns
                    else None,
                    "itl_ms": record.inter_token_latency_ns / 1e6
                    if record.inter_token_latency_ns
                    else None,
                }
            )
        else:
            # Extract error information
            errors = [r.error for r in record.responses if hasattr(r, "error")]
            result["errors"] = errors

        return result

    except Exception as e:
        end_time = time.perf_counter_ns()
        total_duration_ns = end_time - start_time

        return {
            "request_id": request_id,
            "success": False,
            "total_duration_ms": total_duration_ns / 1e6,
            "error": str(e),
            "response_count": 0,
            "payload_length": len(payload),
        }


async def run_performance_test():
    """Run the complete performance test with 20 concurrent requests."""

    print("🚀 Starting libcurl Client Performance Test")
    print("=" * 60)

    # Configuration
    client_config = OpenAIBackendClientConfig(
        url=os.getenv("OPENAI_API_URL", "http://localhost:8080"),
        api_key=os.getenv("OPENAI_API_KEY", "sk-proj-1234567890"),
        model=os.getenv("OPENAI_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"),
        max_tokens=100,
        endpoint="v1/chat/completions",
        timeout_ms=30000,
    )

    print("📋 Test Configuration:")
    print(f"   • API URL: {client_config.url}")
    print(f"   • Model: {client_config.model}")
    print(f"   • Max Tokens: {client_config.max_tokens}")
    print(f"   • Timeout: {client_config.timeout_ms}ms")
    print("   • Concurrent Requests: 20")
    print()

    # Generate synthetic payloads
    print("📝 Generating synthetic payloads...")
    payloads = generate_synthetic_payloads(count=20, tokens_per_payload=100)

    for i, payload in enumerate(payloads[:3]):  # Show first 3 as examples
        print(f"   Payload {i + 1} ({len(payload)} chars): {payload[:100]}...")
    print(f"   ... and {len(payloads) - 3} more payloads")
    print()

    # Initialize client
    print("🔧 Initializing libcurl client...")
    async with OpenAIBackendClientLibcurl(client_config) as client:
        print("✅ Client initialized successfully")
        print()

        # Run concurrent requests
        print("🎯 Sending 20 concurrent requests...")
        start_time = time.perf_counter()

        # Create tasks for concurrent execution
        tasks = [
            send_single_request(client, payload, i + 1)
            for i, payload in enumerate(payloads)
        ]

        # Execute all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.perf_counter()
        total_test_duration = end_time - start_time

        print(f"✅ All requests completed in {total_test_duration:.2f} seconds")
        print()

        # Analyze results
        print("📊 Performance Analysis:")
        print("-" * 60)

        successful_results = [
            r for r in results if isinstance(r, dict) and r.get("success", False)
        ]
        failed_results = [
            r for r in results if isinstance(r, dict) and not r.get("success", False)
        ]
        exception_results = [r for r in results if isinstance(r, Exception)]

        print(
            f"   📈 Success Rate: {len(successful_results)}/{len(results)} ({len(successful_results) / len(results) * 100:.1f}%)"
        )
        print(f"   ❌ Failed Requests: {len(failed_results)}")
        print(f"   💥 Exceptions: {len(exception_results)}")
        print()

        if successful_results:
            # Calculate timing statistics
            ttft_times = [r["ttft_ms"] for r in successful_results if r.get("ttft_ms")]
            ttst_times = [r["ttst_ms"] for r in successful_results if r.get("ttst_ms")]
            ttlt_times = [r["ttlt_ms"] for r in successful_results if r.get("ttlt_ms")]
            total_times = [r["total_duration_ms"] for r in successful_results]
            response_counts = [r["response_count"] for r in successful_results]

            def stats(values):
                if not values:
                    return {"avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0}
                sorted_vals = sorted(values)
                return {
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "p50": sorted_vals[len(sorted_vals) // 2],
                    "p95": sorted_vals[int(len(sorted_vals) * 0.95)]
                    if len(sorted_vals) > 1
                    else sorted_vals[0],
                }

            print("⏱️  Timing Metrics (successful requests):")

            if ttft_times:
                ttft_stats = stats(ttft_times)
                print("   • Time to First Token (TTFT):")
                print(f"     - Average: {ttft_stats['avg']:.2f} ms")
                print(
                    f"     - Range: {ttft_stats['min']:.2f} - {ttft_stats['max']:.2f} ms"
                )
                print(
                    f"     - P50: {ttft_stats['p50']:.2f} ms, P95: {ttft_stats['p95']:.2f} ms"
                )

            if ttst_times:
                ttst_stats = stats(ttst_times)
                print("   • Time to Second Token (TTST):")
                print(f"     - Average: {ttst_stats['avg']:.2f} ms")
                print(
                    f"     - Range: {ttst_stats['min']:.2f} - {ttst_stats['max']:.2f} ms"
                )
                print(
                    f"     - P50: {ttst_stats['p50']:.2f} ms, P95: {ttst_stats['p95']:.2f} ms"
                )

            if total_times:
                total_stats = stats(total_times)
                print("   • Total Request Duration:")
                print(f"     - Average: {total_stats['avg']:.2f} ms")
                print(
                    f"     - Range: {total_stats['min']:.2f} - {total_stats['max']:.2f} ms"
                )
                print(
                    f"     - P50: {total_stats['p50']:.2f} ms, P95: {total_stats['p95']:.2f} ms"
                )

            if response_counts:
                count_stats = stats(response_counts)
                print("   • Response Tokens per Request:")
                print(f"     - Average: {count_stats['avg']:.1f} tokens")
                print(
                    f"     - Range: {count_stats['min']:.0f} - {count_stats['max']:.0f} tokens"
                )

            print()
            print("🔥 Throughput Metrics:")
            total_responses = sum(response_counts)
            print(f"   • Total Responses: {total_responses} tokens")
            print(
                f"   • Throughput: {total_responses / total_test_duration:.1f} tokens/second"
            )
            print(
                f"   • Request Rate: {len(successful_results) / total_test_duration:.1f} requests/second"
            )
            print(
                f"   • Concurrency Efficiency: {len(successful_results)}/{total_test_duration:.2f}s = {len(successful_results) / total_test_duration:.1f} req/s"
            )

        # Show failed requests
        if failed_results or exception_results:
            print()
            print("❌ Failed Requests Details:")
            for result in failed_results[:5]:  # Show first 5 failures
                req_id = result.get("request_id", "unknown")
                error = result.get("error", result.get("errors", "Unknown error"))
                print(f"   • Request {req_id}: {error}")

            for i, exc in enumerate(exception_results[:5]):  # Show first 5 exceptions
                print(f"   • Exception {i + 1}: {str(exc)}")

        print()
        print("🎉 Performance test completed!")


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "⚠️  Warning: OPENAI_API_KEY not set. Using 'test-key' (requests may fail)"
        )
        print("   Set your API key with: export OPENAI_API_KEY='your-api-key'")
        print()

    # Run the test
    try:
        asyncio.run(run_performance_test())
    except KeyboardInterrupt:
        print("\n⛔ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback

        traceback.print_exc()
