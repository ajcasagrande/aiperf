#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
import os

from aiperf.backend import OpenAIBackendClientHttpx
from aiperf.backend.openai_client_httpx import (
    OpenAIBackendClientConfig,
    OpenAIChatCompletionRequest,
)
from aiperf.common.constants import NANOS_PER_MILLIS


async def main():
    async def send_request():
        client = OpenAIBackendClientHttpx(
            client_config=OpenAIBackendClientConfig(
                url="http://127.0.0.1:8080",
                api_key=os.getenv("OPENAI_API_KEY"),
                model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            )
        )
        response = await client.send_chat_completion_request(
            OpenAIChatCompletionRequest(
                model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                max_tokens=100,
                messages=[{"role": "user", "content": "Hello, how are you?"}],
            )
        )
        return response

    tasks = []
    for _ in range(10):
        task = asyncio.create_task(send_request())
        tasks.append(task)
        # await task
    all_responses = await asyncio.gather(*tasks)

    print(
        f"httpx ttft: {sum(response.time_to_first_response_ns for response in all_responses) / len(all_responses) / NANOS_PER_MILLIS}"
    )
    print(
        f"httpx ttst: {sum(response.time_to_second_response_ns for response in all_responses) / len(all_responses) / NANOS_PER_MILLIS}"
    )
    print(
        f"httpx ttlt: {sum(response.time_to_last_response_ns for response in all_responses) / len(all_responses) / NANOS_PER_MILLIS}"
    )
    print(
        f"httpx  itl: {sum(response.inter_token_latency_ns for response in all_responses) / len(all_responses) / NANOS_PER_MILLIS}"
    )


if __name__ == "__main__":
    asyncio.run(main())
