#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import statistics
import time

from aiperf.backend.openai_client_aiohttp import OpenAIInferenceClientAioHttp
from aiperf.backend.openai_client_httpx import OpenAIInferenceClientHttpx
from aiperf.backend.openai_common import (
    OpenAIChatCompletionRequest,
    OpenAIClientConfig,
)
from aiperf.common.constants import NANOS_PER_MILLIS


async def test_client_performance(
    client_class,
    client_name: str,
    num_requests: int = 100,
    concurrent_requests: int = 50,
):
    """Test the performance of a client implementation."""

    client = client_class(
        client_config=OpenAIClientConfig(
            url="http://127.0.0.1:8080",
            api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            max_tokens=100,
        )
    )

    async def send_single_request():
        """Send a single request and return timing metrics."""
        start_time = time.perf_counter_ns()

        try:
            response = await client.send_chat_completion_request(
                OpenAIChatCompletionRequest(
                    model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                    max_tokens=100,
                    messages=[{"role": "user", "content": "Hello, how are you today?"}],
                )
            )

            end_time = time.perf_counter_ns()

            return {
                "total_time_ns": end_time - start_time,
                "ttft_ns": response.time_to_first_response_ns,
                "ttst_ns": response.time_to_second_response_ns,
                "ttlt_ns": response.time_to_last_response_ns,
                "itl_ns": response.inter_token_latency_ns,
                "response_count": len(response.responses),
                "success": True,
            }
        except Exception as e:
            return {
                "total_time_ns": time.perf_counter_ns() - start_time,
                "error": str(e),
                "success": False,
            }

    print(
        f"\n🚀 Testing {client_name} with {num_requests} requests ({concurrent_requests} concurrent)"
    )
    print("=" * 80)

    # Run tests in batches to manage concurrency
    all_results = []
    batch_size = concurrent_requests

    overall_start = time.perf_counter()

    for i in range(0, num_requests, batch_size):
        batch_end = min(i + batch_size, num_requests)
        batch_requests = batch_end - i

        print(f"Running batch {i // batch_size + 1}: requests {i + 1}-{batch_end}")

        # Create tasks for this batch
        tasks = [send_single_request() for _ in range(batch_requests)]

        # Run batch
        batch_start = time.perf_counter()
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        batch_end_time = time.perf_counter()

        # Process results
        successful_results = [
            r for r in batch_results if isinstance(r, dict) and r.get("success")
        ]
        failed_results = [
            r for r in batch_results if not (isinstance(r, dict) and r.get("success"))
        ]

        all_results.extend(successful_results)

        batch_duration = batch_end_time - batch_start
        throughput = len(successful_results) / batch_duration

        print(
            f"  ✅ Batch completed: {len(successful_results)}/{batch_requests} successful"
        )
        print(
            f"  ⏱️  Batch time: {batch_duration:.2f}s, Throughput: {throughput:.1f} req/s"
        )

        if failed_results:
            print(f"  ❌ Failed requests: {len(failed_results)}")

    overall_end = time.perf_counter()
    overall_duration = overall_end - overall_start

    # Calculate statistics
    if all_results:
        successful_count = len(all_results)

        total_times = [r["total_time_ns"] for r in all_results]
        ttft_times = [r["ttft_ns"] for r in all_results if r["ttft_ns"] is not None]
        ttst_times = [r["ttst_ns"] for r in all_results if r["ttst_ns"] is not None]
        ttlt_times = [r["ttlt_ns"] for r in all_results if r["ttlt_ns"] is not None]
        itl_times = [r["itl_ns"] for r in all_results if r["itl_ns"] is not None]
        response_counts = [r["response_count"] for r in all_results]

        def stats_summary(times, name):
            if not times:
                return f"{name}: No data"

            mean_ms = statistics.mean(times) / NANOS_PER_MILLIS
            median_ms = statistics.median(times) / NANOS_PER_MILLIS
            p95_ms = (
                statistics.quantiles(times, n=20)[18] / NANOS_PER_MILLIS
            )  # 95th percentile
            p99_ms = (
                statistics.quantiles(times, n=100)[98] / NANOS_PER_MILLIS
            )  # 99th percentile

            return f"{name}: mean={mean_ms:.1f}ms, median={median_ms:.1f}ms, p95={p95_ms:.1f}ms, p99={p99_ms:.1f}ms"

        overall_throughput = successful_count / overall_duration

        print(f"\n📊 {client_name} Performance Summary")
        print("-" * 60)
        print(f"Total requests: {num_requests}")
        print(f"Successful requests: {successful_count}")
        print(f"Failed requests: {num_requests - successful_count}")
        print(f"Success rate: {(successful_count / num_requests) * 100:.1f}%")
        print(f"Overall duration: {overall_duration:.2f}s")
        print(f"Overall throughput: {overall_throughput:.1f} req/s")
        print(f"Average response count: {statistics.mean(response_counts):.1f}")
        print()
        print(stats_summary(total_times, "Total Time"))
        print(stats_summary(ttft_times, "TTFT"))
        print(stats_summary(ttst_times, "TTST"))
        print(stats_summary(ttlt_times, "TTLT"))
        print(stats_summary(itl_times, "ITL"))

        return {
            "client_name": client_name,
            "successful_requests": successful_count,
            "failed_requests": num_requests - successful_count,
            "overall_throughput": overall_throughput,
            "mean_total_time_ms": statistics.mean(total_times) / NANOS_PER_MILLIS,
            "mean_ttft_ms": statistics.mean(ttft_times) / NANOS_PER_MILLIS
            if ttft_times
            else None,
            "mean_ttst_ms": statistics.mean(ttst_times) / NANOS_PER_MILLIS
            if ttst_times
            else None,
            "mean_ttlt_ms": statistics.mean(ttlt_times) / NANOS_PER_MILLIS
            if ttlt_times
            else None,
            "mean_itl_ms": statistics.mean(itl_times) / NANOS_PER_MILLIS
            if itl_times
            else None,
            "p95_ttft_ms": statistics.quantiles(ttft_times, n=20)[18] / NANOS_PER_MILLIS
            if ttft_times
            else None,
            "p99_ttft_ms": statistics.quantiles(ttft_times, n=100)[98]
            / NANOS_PER_MILLIS
            if ttft_times
            else None,
        }
    else:
        print(f"❌ {client_name}: All requests failed!")
        return None


async def main():
    """Run performance comparison between aiohttp and httpx clients."""

    print("🔥 AIPerf OpenAI Client Performance Comparison")
    print("=" * 80)
    print("Comparing aiohttp vs httpx implementations")
    print("Features tested:")
    print("  • Concurrent request handling")
    print("  • Time to First Token (TTFT)")
    print("  • Time to Second Token (TTST)")
    print("  • Time to Last Token (TTLT)")
    print("  • Inter-Token Latency (ITL)")
    print("  • Overall throughput")
    print("  • Connection efficiency")

    # Test configuration
    num_requests = 100
    concurrent_requests = 50

    print("\nTest Configuration:")
    print(f"  • Total requests: {num_requests}")
    print(f"  • Concurrent requests: {concurrent_requests}")
    print(
        f"  • Server: {os.getenv('OPENAI_API_KEY', 'http://127.0.0.1:8080 (default)')}"
    )

    # Test both implementations
    results = []

    # Test HTTPX implementation
    httpx_result = await test_client_performance(
        OpenAIInferenceClientHttpx, "HTTPX (HTTP/2)", num_requests, concurrent_requests
    )
    if httpx_result:
        results.append(httpx_result)

    # Add a small delay between tests
    await asyncio.sleep(2)

    # Test aiohttp implementation
    aiohttp_result = await test_client_performance(
        OpenAIInferenceClientAioHttp, "aiohttp", num_requests, concurrent_requests
    )
    if aiohttp_result:
        results.append(aiohttp_result)

    # Final comparison
    if len(results) == 2:
        print("\n🏆 Final Comparison")
        print("=" * 80)

        httpx_res = next(r for r in results if "HTTPX" in r["client_name"])
        aiohttp_res = next(r for r in results if "aiohttp" in r["client_name"])

        def compare_metric(metric_name, httpx_val, aiohttp_val, higher_is_better=False):
            if httpx_val is None or aiohttp_val is None:
                return f"{metric_name}: Insufficient data"

            improvement = ((httpx_val - aiohttp_val) / aiohttp_val) * 100
            if not higher_is_better:
                improvement = -improvement  # For latency metrics, lower is better

            winner = "HTTPX" if improvement > 0 else "aiohttp"
            symbol = (
                "🚀" if improvement > 5 else "🔄" if abs(improvement) <= 5 else "🐌"
            )

            return f"{metric_name}: {symbol} {winner} {abs(improvement):.1f}% {'better' if improvement > 0 else 'worse'}"

        print(
            compare_metric(
                "Throughput",
                httpx_res["overall_throughput"],
                aiohttp_res["overall_throughput"],
                True,
            )
        )
        print(
            compare_metric(
                "Total Time",
                httpx_res["mean_total_time_ms"],
                aiohttp_res["mean_total_time_ms"],
            )
        )
        print(
            compare_metric(
                "TTFT", httpx_res["mean_ttft_ms"], aiohttp_res["mean_ttft_ms"]
            )
        )
        print(
            compare_metric(
                "TTST", httpx_res["mean_ttst_ms"], aiohttp_res["mean_ttst_ms"]
            )
        )
        print(
            compare_metric(
                "TTLT", httpx_res["mean_ttlt_ms"], aiohttp_res["mean_ttlt_ms"]
            )
        )
        print(
            compare_metric("ITL", httpx_res["mean_itl_ms"], aiohttp_res["mean_itl_ms"])
        )

        # Overall winner
        httpx_wins = 0
        aiohttp_wins = 0

        if httpx_res["overall_throughput"] > aiohttp_res["overall_throughput"]:
            httpx_wins += 1
        else:
            aiohttp_wins += 1

        for metric in [
            "mean_total_time_ms",
            "mean_ttft_ms",
            "mean_ttst_ms",
            "mean_ttlt_ms",
            "mean_itl_ms",
        ]:
            if httpx_res[metric] is not None and aiohttp_res[metric] is not None:
                if (
                    httpx_res[metric] < aiohttp_res[metric]
                ):  # Lower is better for latency
                    httpx_wins += 1
                else:
                    aiohttp_wins += 1

        print(
            f"\n🏅 Overall Winner: {'HTTPX' if httpx_wins > aiohttp_wins else 'aiohttp'}"
        )
        print(f"   HTTPX wins: {httpx_wins}, aiohttp wins: {aiohttp_wins}")

        # Key insights
        print("\n💡 Key Insights:")
        print("  • HTTPX leverages HTTP/2 for better connection multiplexing")
        print("  • HTTPX has more granular timeout control")
        print("  • Both clients use similar socket-level optimizations")
        print("  • Performance may vary based on server HTTP/2 support")
        print("  • Concurrent performance depends on connection pooling efficiency")

    else:
        print("❌ Could not complete comparison - one or both tests failed")


if __name__ == "__main__":
    asyncio.run(main())
