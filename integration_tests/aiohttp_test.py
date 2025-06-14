#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import time

from aiperf.clients.openai.common import OpenAIChatCompletionRequest, OpenAIClientConfig
from aiperf.clients.openai.openai_aiohttp import OpenAIClientAioHttp
from aiperf.common.config.endpoint_config import EndPointConfig
from aiperf.data_exporter.console_exporter import ConsoleExporter
from integration_tests.helpers import post_process_records


async def main():
    async def send_request(due_ns: int):
        client = OpenAIClientAioHttp(
            client_config=OpenAIClientConfig(
                url="http://127.0.0.1:8080",
                api_key=os.getenv("OPENAI_API_KEY"),
                model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            )
        )
        async with client:
            await asyncio.sleep((due_ns - time.monotonic_ns()) / 1e9)
            response = await client.send_chat_completion_request(
                OpenAIChatCompletionRequest(
                    model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                    max_tokens=100,
                    messages=[
                        {
                            "role": "user",
                            "content": " softly smiteth That from the cold stone sparks of fire do fly Whereat a waxen torch forthwith he lighteth Which must be lodestar to his lustful eye And to the flame thus speaks advisedly As from this cold flint I enforced this fire So Lucrece must I force to my desire Here pale with fear he doth premeditate The dangers of his loathsome enterprise And in his inward mind he doth debate What following sorrow may on this arise Then looking scorn",
                        }
                    ],
                )
            )
            return response

    now_ns = time.monotonic_ns()

    tasks = []
    for _ in range(100):
        task = asyncio.create_task(send_request(now_ns + 1000000000))
        tasks.append(task)
        # await task
    all_responses = await asyncio.gather(*tasks)

    res = await post_process_records(all_responses)
    ConsoleExporter(
        endpoint_config=EndPointConfig(
            type="console",
            streaming=True,
        )
    ).export(res.records)


if __name__ == "__main__":
    import uvloop

    uvloop.run(main())
