#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
import os

from aiperf.backend.openai_client_aiohttp import OpenAIBackendClientAioHttp
from aiperf.backend.openai_common import (
    OpenAIBackendClientConfig,
    OpenAIChatCompletionRequest,
)
from aiperf.common.constants import NANOS_PER_MILLIS


async def main():
    async def send_request():
        client = OpenAIBackendClientAioHttp(
            client_config=OpenAIBackendClientConfig(
                url="http://127.0.0.1:8080",
                api_key=os.getenv("OPENAI_API_KEY"),
                model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            )
        )
        await asyncio.sleep(0.0001)
        response = await client.send_chat_completion_request(
            OpenAIChatCompletionRequest(
                model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                max_tokens=100,
                messages=[{"role": "user", "content": "Hello, how are you?"}],
            )
        )
        return response

    tasks = []
    for _ in range(100):
        task = asyncio.create_task(send_request())
        tasks.append(task)
        # await task
    all_responses = await asyncio.gather(*tasks)

    print(
        f"aiohttp ttft: {sum(response.time_to_first_response_ns for response in all_responses) / len(all_responses) / NANOS_PER_MILLIS}"
    )
    print(
        f"aiohttp ttst: {sum(response.time_to_second_response_ns for response in all_responses) / len(all_responses) / NANOS_PER_MILLIS}"
    )
    print(
        f"aiohttp ttlt: {sum(response.time_to_last_response_ns for response in all_responses) / len(all_responses) / NANOS_PER_MILLIS}"
    )
    print(
        f"aiohttp itl: {sum(response.inter_token_latency_ns for response in all_responses) / len(all_responses) / NANOS_PER_MILLIS}"
    )


if __name__ == "__main__":
    asyncio.run(main())
