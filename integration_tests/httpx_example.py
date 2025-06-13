#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import asyncio
import os

from aiperf.backend.openai_client_httpx import OpenAIClientHttpx
from aiperf.backend.openai_common import (
    OpenAIChatCompletionRequest,
    OpenAIClientConfig,
)
from aiperf.common.constants import NANOS_PER_MILLIS


async def main():
    """Example usage of the HTTPX OpenAI client."""

    print("🚀 HTTPX OpenAI Client Example")
    print("=" * 50)

    # Create client configuration
    client_config = OpenAIClientConfig(
        url="http://127.0.0.1:8080",  # Your OpenAI-compatible server
        api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
        model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
        max_tokens=100,
        temperature=0.7,
    )

    # Create the client
    client = OpenAIClientHttpx(client_config)

    print("✅ Client configured:")
    print(f"   • URL: {client_config.url}")
    print(f"   • Model: {client_config.model}")
    print(f"   • Max tokens: {client_config.max_tokens}")
    print("   • HTTP/2 enabled: ✅")
    print("   • Socket optimizations: ✅")

    # Create a chat completion request
    request = OpenAIChatCompletionRequest(
        model=client_config.model,
        max_tokens=client_config.max_tokens,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": "Write a short poem about artificial intelligence.",
            },
        ],
    )

    print("\n📤 Sending request...")
    print(f"   • Messages: {len(request.messages)}")
    print("   • Streaming: enabled")

    try:
        # Send the request
        response = await client.send_chat_completion_request(request)

        print("\n📥 Response received:")
        print(f"   • Response chunks: {len(response.responses)}")
        print(f"   • Success: {'✅' if response.responses else '❌'}")

        # Display timing metrics
        if response.time_to_first_response_ns:
            ttft_ms = response.time_to_first_response_ns / NANOS_PER_MILLIS
            print(f"   • Time to First Token: {ttft_ms:.1f}ms")

        if response.time_to_second_response_ns:
            ttst_ms = response.time_to_second_response_ns / NANOS_PER_MILLIS
            print(f"   • Time to Second Token: {ttst_ms:.1f}ms")

        if response.time_to_last_response_ns:
            ttlt_ms = response.time_to_last_response_ns / NANOS_PER_MILLIS
            print(f"   • Time to Last Token: {ttlt_ms:.1f}ms")

        if response.inter_token_latency_ns:
            itl_ms = response.inter_token_latency_ns / NANOS_PER_MILLIS
            print(f"   • Inter-Token Latency: {itl_ms:.1f}ms")

        # Show first few response chunks
        print("\n💬 Response preview:")
        for i, resp in enumerate(response.responses[:5]):
            timestamp_ms = resp.perf_ns / NANOS_PER_MILLIS
            print(f"   [{i + 1}] @ {timestamp_ms:.1f}ms: {type(resp).__name__}")

        if len(response.responses) > 5:
            print(f"   ... and {len(response.responses) - 5} more chunks")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        # Clean up
        await client.__aexit__(None, None, None)
        print("\n🧹 Client cleaned up")


async def concurrent_example():
    """Example of concurrent requests with HTTPX client."""

    print("\n🔥 Concurrent Requests Example")
    print("=" * 50)

    client_config = OpenAIClientConfig(
        url="http://127.0.0.1:8080",
        api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
        model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
        max_tokens=50,
    )

    client = OpenAIClientHttpx(client_config)

    async def send_request(prompt: str, request_id: int):
        """Send a single request."""
        request = OpenAIChatCompletionRequest(
            model=client_config.model,
            max_tokens=client_config.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        response = await client.send_chat_completion_request(request)

        ttft_ms = (
            response.time_to_first_response_ns / NANOS_PER_MILLIS
            if response.time_to_first_response_ns
            else 0
        )
        return {
            "id": request_id,
            "chunks": len(response.responses),
            "ttft_ms": ttft_ms,
        }

    # Create multiple requests
    prompts = [
        "What is machine learning?",
        "Explain quantum computing",
        "How does the internet work?",
        "What is artificial intelligence?",
        "Describe blockchain technology",
    ]

    print(f"📤 Sending {len(prompts)} concurrent requests...")

    try:
        # Send all requests concurrently
        start_time = asyncio.get_event_loop().time()

        tasks = [send_request(prompt, i + 1) for i, prompt in enumerate(prompts)]
        results = await asyncio.gather(*tasks)

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        print("\n📊 Results:")
        print(f"   • Total time: {duration:.2f}s")
        print(f"   • Throughput: {len(prompts) / duration:.1f} req/s")
        print(
            f"   • Average TTFT: {sum(r['ttft_ms'] for r in results) / len(results):.1f}ms"
        )

        for result in results:
            print(
                f"   • Request {result['id']}: {result['chunks']} chunks, TTFT: {result['ttft_ms']:.1f}ms"
            )

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        await client.__aexit__(None, None, None)


if __name__ == "__main__":
    # Run the basic example
    asyncio.run(main())

    # Run the concurrent example
    asyncio.run(concurrent_example())
