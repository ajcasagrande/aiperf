#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio

import httpx
from aiperf_timing import TimingMetrics


async def measure_latency(url: str):
    collector = TimingMetrics()

    async with httpx.AsyncClient() as client:
        collector.start_request()

        try:
            async with client.stream("GET", url) as response:
                await response.aread()  # Wait for headers
                collector.record_first_byte()

                async for _ in response.aiter_bytes():
                    collector.record_chunk()

        except Exception as e:
            print(f"Request failed: {e}")
            return None

    return {
        "ttft_us": collector.get_ttft(),
        "inter_token_latencies": collector.get_metrics(),
        "total_chunks": len(collector.get_metrics()),
    }


async def main():
    url = "http://127.0.0.1:8080"
    metrics = await measure_latency(url)

    if metrics:
        print(f"Time to First Token: {metrics['ttft_us']:.2f}µs")
        print(f"Inter-token latencies (µs): {metrics['inter_token_latencies'][:5]}...")
        print(f"Total chunks received: {metrics['total_chunks']}")


if __name__ == "__main__":
    asyncio.run(main())
