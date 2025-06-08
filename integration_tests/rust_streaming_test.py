#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import asyncio
import os

from aiperf.backend.openai_client_rust_streaming import OpenAIBackendClientRustStreaming
from aiperf.backend.openai_common import (
    OpenAIBackendClientConfig,
    OpenAIChatCompletionRequest,
)
from aiperf.common.constants import NANOS_PER_MILLIS


async def main():
    """Test the new ultra high-performance Rust streaming client."""

    async def send_request():
        """Send a single chat completion request using the Rust streaming client."""
        try:
            client = OpenAIBackendClientRustStreaming(
                client_config=OpenAIBackendClientConfig(
                    url="http://127.0.0.1:8080",
                    api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
                    model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                    timeout_ms=30000,
                )
            )

            # Small delay to avoid overwhelming the server
            await asyncio.sleep(0.0001)

            response = await client.send_chat_completion_request(
                OpenAIChatCompletionRequest(
                    model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                    max_tokens=100,
                    messages=[{"role": "user", "content": "Hello, how are you?"}],
                )
            )

            # Get performance statistics
            stats = client.get_performance_statistics()
            print(f"Request stats: {stats}")

            return response

        except ImportError as e:
            print(f"Rust streaming library not available: {e}")
            print(
                "Please install the aiperf_streaming library: cd lib/streaming && pip install ."
            )
            return None
        except Exception as e:
            print(f"Error in request: {e}")
            return None

    print("🚀 Testing Ultra High-Performance Rust Streaming Client")
    print("=" * 60)

    # Test with different concurrency levels
    concurrency_levels = [1, 5, 10]

    for concurrency in concurrency_levels:
        print(f"\n📊 Testing with concurrency level: {concurrency}")
        print("-" * 40)

        tasks = []
        for _ in range(concurrency):
            task = asyncio.create_task(send_request())
            tasks.append(task)

        try:
            all_responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out None responses and exceptions
            valid_responses = [
                response
                for response in all_responses
                if response is not None and not isinstance(response, Exception)
            ]

            if not valid_responses:
                print("❌ No valid responses received")
                continue

            print(
                f"✅ Received {len(valid_responses)} valid responses out of {len(all_responses)}"
            )

            # Calculate timing metrics (if available)
            try:
                if hasattr(valid_responses[0], "time_to_first_response_ns"):
                    avg_ttft = (
                        sum(
                            response.time_to_first_response_ns
                            for response in valid_responses
                        )
                        / len(valid_responses)
                        / NANOS_PER_MILLIS
                    )
                    avg_ttst = (
                        sum(
                            response.time_to_second_response_ns
                            for response in valid_responses
                        )
                        / len(valid_responses)
                        / NANOS_PER_MILLIS
                    )
                    avg_ttlt = (
                        sum(
                            response.time_to_last_response_ns
                            for response in valid_responses
                        )
                        / len(valid_responses)
                        / NANOS_PER_MILLIS
                    )
                    avg_itl = (
                        sum(
                            response.inter_token_latency_ns
                            for response in valid_responses
                        )
                        / len(valid_responses)
                        / NANOS_PER_MILLIS
                    )

                    print(f"📈 Performance Metrics (Concurrency: {concurrency}):")
                    print(f"   • Time to First Token (TTFT): {avg_ttft:.2f} ms")
                    print(f"   • Time to Second Token (TTST): {avg_ttst:.2f} ms")
                    print(f"   • Time to Last Token (TTLT): {avg_ttlt:.2f} ms")
                    print(f"   • Inter-Token Latency (ITL): {avg_itl:.2f} ms")
                else:
                    print("📋 Response structure:")
                    if valid_responses:
                        response = valid_responses[0]
                        print(f"   • Response type: {type(response)}")
                        print(
                            f"   • Response count: {len(response.responses) if hasattr(response, 'responses') else 'N/A'}"
                        )
                        print(
                            f"   • Start time: {response.start_perf_counter_ns if hasattr(response, 'start_perf_counter_ns') else 'N/A'}"
                        )

            except Exception as e:
                print(f"⚠️  Error calculating metrics: {e}")

        except Exception as e:
            print(f"❌ Error in concurrent execution: {e}")

    print("\n🎯 Rust Streaming Client Test Complete!")


if __name__ == "__main__":
    asyncio.run(main())
