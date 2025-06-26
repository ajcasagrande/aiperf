# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Simple integration test that runs the server in background and tests OpenAI endpoint."""

import asyncio
import json
import subprocess

import httpx
import pytest


class BackgroundServer:
    """Context manager for running the integration server in background."""

    def __init__(self, port: int = 11001, ttft: float = 10.0, itl: float = 5.0):
        self.port = port
        self.ttft = ttft
        self.itl = itl
        self.process = None
        self.base_url = f"http://localhost:{port}"

    async def __aenter__(self):
        """Start the server process."""
        # Start the server using the integration-server CLI command
        self.process = subprocess.Popen(
            [
                "integration-server",
                "--port",
                str(self.port),
                "--host",
                "127.0.0.1",
                "--time-to-first-token-ms",
                str(self.ttft),
                "--inter-token-latency-ms",
                str(self.itl),
                "--log-level",
                "INFO",
            ]
        )

        # Wait for server to be ready
        await self._wait_for_server()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop the server process."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    async def _wait_for_server(self, max_attempts: int = 30):
        """Wait for the server to be ready to accept requests."""
        async with httpx.AsyncClient() as client:
            for _ in range(max_attempts):
                try:
                    response = await client.get(f"{self.base_url}/health", timeout=1.0)
                    if response.status_code == 200:
                        return
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass
                await asyncio.sleep(0.5)

        raise RuntimeError(f"Server failed to start on port {self.port}")


@pytest.mark.asyncio
async def test_simple_chat_completion():
    """Test a simple non-streaming chat completion request."""
    async with (
        BackgroundServer(port=8001, ttft=10.0, itl=5.0) as server,
        httpx.AsyncClient() as client,
    ):
        # Prepare the request
        request_data = {
            "model": "gpt2",
            "messages": [{"role": "user", "content": "Hello, how are you?"}],
            "max_tokens": 10,
            "stream": False,
        }

        # Make the request
        response = await client.post(
            f"{server.base_url}/v1/chat/completions",
            json=request_data,
            timeout=30.0,
        )

        # Verify the response
        assert response.status_code == 200

        data = response.json()
        assert data["object"] == "chat.completion"
        assert data["model"] == "gpt2"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] != ""
        assert data["choices"][0]["finish_reason"] == "stop"

        # Verify usage information
        assert "usage" in data
        assert data["usage"]["prompt_tokens"] > 0
        assert data["usage"]["completion_tokens"] > 0
        assert data["usage"]["total_tokens"] > 0

        print("✅ Chat completion successful!")
        print(f"   Model: {data['model']}")
        print(f"   Response: {data['choices'][0]['message']['content']}")
        print(f"   Tokens used: {data['usage']['total_tokens']}")


@pytest.mark.asyncio
async def test_streaming_chat_completion():
    """Test a simple streaming chat completion request."""
    async with (
        BackgroundServer(port=8002, ttft=10.0, itl=5.0) as server,
        httpx.AsyncClient() as client,
    ):
        # Prepare the request
        request_data = {
            "model": "gpt2",
            "messages": [{"role": "user", "content": "Hi there!"}],
            "max_tokens": 5,
            "stream": True,
        }

        # Make the streaming request
        async with client.stream(
            "POST",
            f"{server.base_url}/v1/chat/completions",
            json=request_data,
            timeout=30.0,
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            chunks = []
            content_parts = []

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_part = line[6:]  # Remove "data: " prefix

                    if data_part == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data_part)
                        chunks.append(chunk_data)

                        # Extract content from delta
                        if (
                            chunk_data.get("choices")
                            and len(chunk_data["choices"]) > 0
                            and "content" in chunk_data["choices"][0].get("delta", {})
                        ):
                            content_parts.append(
                                chunk_data["choices"][0]["delta"]["content"]
                            )
                    except json.JSONDecodeError:
                        continue

            # Verify we received chunks
            assert len(chunks) > 0

            # Verify the structure of the first chunk
            first_chunk = chunks[0]
            assert first_chunk["object"] == "chat.completion.chunk"
            assert first_chunk["model"] == "gpt2"
            assert len(first_chunk["choices"]) == 1

            # Verify we received some content
            full_content = "".join(content_parts)
            assert len(full_content) > 0

            print("✅ Streaming completion successful!")
            print(f"   Model: {first_chunk['model']}")
            print(f"   Chunks received: {len(chunks)}")
            print(f"   Content: {full_content}")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
