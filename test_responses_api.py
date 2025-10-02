#!/usr/bin/env python
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Quick test script for the Responses API endpoint in the mock server."""

import asyncio
import json
import sys

import httpx

sys.path.insert(0, "integration-tests")

BASE_URL = "http://localhost:8000"


async def test_non_streaming_response():
    """Test non-streaming Responses API."""
    print("Testing non-streaming Responses API...")

    request_data = {
        "model": "gpt-4",
        "input": "Hello, how are you?",
        "stream": False,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/v1/responses", json=request_data, timeout=30.0
            )
            response.raise_for_status()

            data = response.json()
            print("✓ Non-streaming response received:")
            print(f"  - Response ID: {data.get('id')}")
            print(f"  - Model: {data.get('model')}")
            print(f"  - Status: {data.get('status')}")
            print(
                f"  - Output text: {data.get('output', [{}])[0].get('content', [{}])[0].get('text', '')[:50]}..."
            )
            print(f"  - Usage: {data.get('usage')}")
            return True
        except Exception as e:
            print(f"✗ Non-streaming test failed: {e}")
            return False


async def test_streaming_response():
    """Test streaming Responses API."""
    print("\nTesting streaming Responses API...")

    request_data = {
        "model": "gpt-4",
        "input": "Hello!",
        "stream": True,
    }

    async with httpx.AsyncClient() as client:
        try:
            event_count = 0
            delta_count = 0

            async with client.stream(
                "POST", f"{BASE_URL}/v1/responses", json=request_data, timeout=30.0
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        event_count += 1
                        data = json.loads(line[6:])
                        event_type = data.get("type")

                        if event_type == "response.output_text.delta":
                            delta_count += 1
                            if delta_count <= 3:  # Print first 3 deltas
                                print(f"  - Delta {delta_count}: {data.get('delta')!r}")

            print("✓ Streaming response received:")
            print(f"  - Total events: {event_count}")
            print(f"  - Delta events: {delta_count}")
            return True
        except Exception as e:
            print(f"✗ Streaming test failed: {e}")
            return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Responses API Mock Server")
    print("=" * 60)
    print(f"Server URL: {BASE_URL}\n")

    # Check if server is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5.0)
            response.raise_for_status()
            print("✓ Server is running\n")
    except Exception as e:
        print(f"✗ Server is not running or not accessible: {e}")
        print(
            "\nPlease start the server first with:\n  uvicorn integration-tests.mock_server.app:app --reload"
        )
        return False

    # Run tests
    results = []
    results.append(await test_non_streaming_response())
    results.append(await test_streaming_response())

    # Summary
    print("\n" + "=" * 60)
    print(f"Test Summary: {sum(results)}/{len(results)} passed")
    print("=" * 60)

    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
