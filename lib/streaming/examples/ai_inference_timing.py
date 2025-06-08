#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
AI Inference Timing Example for aiperf_streaming.

This example demonstrates how to measure streaming AI inference response timing
for various AI services like OpenAI, Anthropic, or local models.
"""

import json
import os
import statistics
from typing import Any

import requests
from aiperf_streaming import (
    PrecisionTimer,  # type: ignore
    StreamingHttpClient,  # type: ignore
    StreamingRequest,  # type: ignore
)


class AIServiceConfig:
    """Configuration for different AI services."""

    @staticmethod
    def openai_config(api_key: str) -> dict[str, Any]:
        """OpenAI API configuration."""
        return {
            "base_url": "https://api.openai.com/v1/chat/completions",
            "headers": {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Accept": "text/event-stream",
            },
        }

    @staticmethod
    def anthropic_config(api_key: str) -> dict[str, Any]:
        """Anthropic API configuration."""
        return {
            "base_url": "https://api.anthropic.com/v1/messages",
            "headers": {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Accept": "text/event-stream",
            },
        }

    @staticmethod
    def local_model_config(base_url: str) -> dict[str, Any]:
        """Local model server configuration (e.g., Ollama, vLLM)."""
        return {
            "base_url": f"{base_url}/v1/chat/completions",
            "headers": {
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        }


def create_openai_payload(
    prompt: str, model: str = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
) -> str:
    """Create OpenAI streaming request payload."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": 100,
    }
    return json.dumps(payload)


def create_anthropic_payload(
    prompt: str, model: str = "claude-3-sonnet-20240229"
) -> str:
    """Create Anthropic streaming request payload."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": 150,
    }
    return json.dumps(payload)


def check_server_availability(base_url: str) -> bool:
    """Check if the target server is available."""
    try:
        # Try a simple GET request to check if server is running
        test_url = base_url.replace("/v1/chat/completions", "/health")
        if "127.0.0.1:8080" in base_url:
            # For local servers, try the base URL
            test_url = base_url.replace("/v1/chat/completions", "")

        requests.get(test_url, timeout=2)
        return True
    except requests.exceptions.RequestException:
        return False


def validate_streaming_request(request: StreamingRequest) -> dict[str, Any]:
    """Validate that a streaming request actually succeeded."""
    validation = {"is_valid": True, "errors": [], "warnings": []}

    # Check if request has an error message
    if hasattr(request, "error_message") and request.error_message:
        validation["is_valid"] = False
        validation["errors"].append(f"Request error: {request.error_message}")

    # Check HTTP status code if available
    if hasattr(request, "status_code") and request.status_code:  # noqa: SIM102
        if request.status_code < 200 or request.status_code >= 300:
            validation["is_valid"] = False
            validation["errors"].append(f"HTTP error: {request.status_code}")

    # Check if we got any meaningful data
    if request.total_bytes < 50:  # Less than 50 bytes suggests an error
        validation["is_valid"] = False
        validation["errors"].append(
            f"Too little data received ({request.total_bytes} bytes)"
        )

    # Check if we got only one chunk (often indicates an error response)
    if request.chunk_count == 1 and request.total_bytes < 100:
        validation["is_valid"] = False
        validation["errors"].append("Single small chunk suggests error response")

    # Check if duration is suspiciously fast
    duration_ms = request.duration_ns() / 1e6 if request.duration_ns() else 0
    if duration_ms < 10:  # Less than 10ms for an AI inference is suspicious
        validation["warnings"].append(
            f"Suspiciously fast response ({duration_ms:.2f}ms)"
        )

    return validation


def get_sample_error_response(request: StreamingRequest) -> str:
    """Get a sample of the response data to help debug issues."""
    duration_ms = request.duration_ns() / 1e6 if request.duration_ns() else 0

    # Build basic info
    info_parts = [
        f"Status: {getattr(request, 'status_code', 'Unknown')}",
        f"Chunks: {request.chunk_count}",
        f"Bytes: {request.total_bytes}",
        f"Duration: {duration_ms:.2f}ms",
    ]

    # Add error message if available
    if hasattr(request, "error_message") and request.error_message:
        info_parts.append(f"Error: {request.error_message}")

    # Add response preview if we have response data
    if hasattr(request, "get_response_preview"):
        try:
            preview = request.get_response_preview(100)  # First 100 chars
            if preview.strip():
                info_parts.append(f"Response: {preview}")
        except Exception:
            pass  # If method doesn't exist yet, skip

    return " | ".join(info_parts)


def analyze_streaming_performance(
    requests: list[StreamingRequest], timer: PrecisionTimer
) -> dict[str, Any]:
    """Analyze streaming performance metrics."""

    # Calculate timing statistics
    durations = [
        req.duration_ns() / 1e6 for req in requests if req.duration_ns()
    ]  # Convert to ms
    throughputs = [req.throughput_bps() for req in requests if req.throughput_bps()]
    chunk_counts = [req.chunk_count for req in requests]
    total_bytes = [req.total_bytes for req in requests]

    # Calculate Time To First Token (TTFT) metrics
    ttft_times = []
    for req in requests:
        # TTFT is calculated as the time from request start to first chunk arrival
        if req.chunk_count > 0:
            try:
                # Get the first chunk directly
                first_chunk = req.get_chunk(0)  # Use get_chunk(index) method
                if first_chunk:
                    # TTFT = first_chunk.timestamp_ns - request.start_time_ns
                    ttft_ns = first_chunk.timestamp_ns - req.start_time_ns
                    ttft_times.append(ttft_ns / 1e6)  # Convert to ms
            except (AttributeError, TypeError):
                # If get_chunk method doesn't work, skip this request
                continue

    # Calculate Time To Second Token (TTST) metrics
    ttst_times = []
    for req in requests:
        # TTST is calculated as the time from first chunk to second chunk arrival
        if req.chunk_count > 1:
            try:
                first_chunk = req.get_chunk(0)
                second_chunk = req.get_chunk(1)
                if first_chunk and second_chunk:
                    # TTST = second_chunk.timestamp_ns - first_chunk.timestamp_ns
                    ttst_ns = second_chunk.timestamp_ns - first_chunk.timestamp_ns
                    ttst_times.append(ttst_ns / 1e6)  # Convert to ms
            except (AttributeError, TypeError):
                continue

    # Calculate Inter-Token Latency (ITL) metrics
    all_inter_token_latencies = []
    for req in requests:
        # ITL is the time between each consecutive chunk
        if req.chunk_count > 1:
            try:
                for i in range(1, req.chunk_count):
                    prev_chunk = req.get_chunk(i - 1)
                    curr_chunk = req.get_chunk(i)
                    if prev_chunk and curr_chunk:
                        itl_ns = curr_chunk.timestamp_ns - prev_chunk.timestamp_ns
                        all_inter_token_latencies.append(itl_ns / 1e6)  # Convert to ms
            except (AttributeError, TypeError):
                continue

    # Analyze chunk timing patterns
    all_chunk_intervals = []
    for req in requests:
        timings = req.chunk_timings()
        if len(timings) > 1:
            intervals = [timings[i] - timings[i - 1] for i in range(1, len(timings))]
            all_chunk_intervals.extend(
                [interval / 1e6 for interval in intervals]
            )  # Convert to ms

    analysis: dict[str, Any] = {
        "request_performance": {
            "count": len(requests),
            "avg_duration_ms": statistics.mean(durations) if durations else 0,
            "median_duration_ms": statistics.median(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "duration_stdev_ms": statistics.stdev(durations)
            if len(durations) > 1
            else 0,
        },
        "ttft_performance": {
            "count": len(ttft_times),
            "avg_ttft_ms": statistics.mean(ttft_times) if ttft_times else 0,
            "median_ttft_ms": statistics.median(ttft_times) if ttft_times else 0,
            "min_ttft_ms": min(ttft_times) if ttft_times else 0,
            "max_ttft_ms": max(ttft_times) if ttft_times else 0,
            "ttft_stdev_ms": statistics.stdev(ttft_times) if len(ttft_times) > 1 else 0,
        },
        "ttst_performance": {
            "count": len(ttst_times),
            "avg_ttst_ms": statistics.mean(ttst_times) if ttst_times else 0,
            "median_ttst_ms": statistics.median(ttst_times) if ttst_times else 0,
            "min_ttst_ms": min(ttst_times) if ttst_times else 0,
            "max_ttst_ms": max(ttst_times) if ttst_times else 0,
            "ttst_stdev_ms": statistics.stdev(ttst_times) if len(ttst_times) > 1 else 0,
        },
        "inter_token_latency": {
            "count": len(all_inter_token_latencies),
            "avg_itl_ms": statistics.mean(all_inter_token_latencies)
            if all_inter_token_latencies
            else 0,
            "median_itl_ms": statistics.median(all_inter_token_latencies)
            if all_inter_token_latencies
            else 0,
            "min_itl_ms": min(all_inter_token_latencies)
            if all_inter_token_latencies
            else 0,
            "max_itl_ms": max(all_inter_token_latencies)
            if all_inter_token_latencies
            else 0,
            "itl_stdev_ms": statistics.stdev(all_inter_token_latencies)
            if len(all_inter_token_latencies) > 1
            else 0,
        },
        "throughput_performance": {
            "avg_throughput_bps": statistics.mean(throughputs) if throughputs else 0,
            "avg_throughput_mbps": statistics.mean(throughputs) / (1024 * 1024)
            if throughputs
            else 0,
            "median_throughput_bps": statistics.median(throughputs)
            if throughputs
            else 0,
            "max_throughput_bps": max(throughputs) if throughputs else 0,
        },
        "chunk_performance": {
            "avg_chunks_per_request": statistics.mean(chunk_counts)
            if chunk_counts
            else 0,
            "total_chunks": sum(chunk_counts),
            "avg_chunk_interval_ms": statistics.mean(all_chunk_intervals)
            if all_chunk_intervals
            else 0,
            "chunk_interval_stdev_ms": statistics.stdev(all_chunk_intervals)
            if len(all_chunk_intervals) > 1
            else 0,
            "min_chunk_interval_ms": min(all_chunk_intervals)
            if all_chunk_intervals
            else 0,
            "max_chunk_interval_ms": max(all_chunk_intervals)
            if all_chunk_intervals
            else 0,
        },
        "data_transfer": {
            "total_bytes": sum(total_bytes),
            "total_mb": sum(total_bytes) / (1024 * 1024),
            "avg_bytes_per_request": statistics.mean(total_bytes) if total_bytes else 0,
        },
    }

    return analysis


def benchmark_ai_service(
    service_name: str,
    config: dict[str, Any],
    payload: str,
    num_requests: int = 5,
    concurrent: bool = False,
) -> dict[str, Any]:
    """Benchmark an AI service's streaming performance."""

    print(
        f"\n🔍 Benchmarking {service_name} ({'concurrent' if concurrent else 'sequential'})"
    )
    print("-" * 60)

    # Check if the server is available first
    if not check_server_availability(config["base_url"]):
        print(f"⚠️  WARNING: Server at {config['base_url']} appears to be unavailable!")
        print("   Make sure your AI service is running and accessible.")

        # Continue anyway for demonstration, but warn user
        print("   Continuing anyway to demonstrate error handling...")

    # Initialize timer and client
    timer = PrecisionTimer()
    client = StreamingHttpClient(
        timeout_ms=60000,  # 60 second timeout for AI inference
        default_headers=config["headers"],
        user_agent="aiperf_streaming/0.1.0 (AI Performance Analysis)",
    )

    # Create requests
    requests = []
    for _ in range(num_requests):
        req = StreamingRequest(
            url=config["base_url"],
            method="POST",
            body=payload,
            timeout_ms=60000,
            headers=config["headers"],
        )
        requests.append(req)

    print(f"📤 Created {num_requests} requests to {config['base_url']}")

    # Execute requests
    start_time = timer.now_ns()

    try:
        if concurrent:
            completed_requests = client.stream_requests_concurrent(
                requests,
                max_concurrent=min(
                    num_requests, 1000
                ),  # Limit concurrency to be respectful
            )
        else:
            completed_requests: list[StreamingRequest] = []
            for i, req in enumerate(requests):
                print(f"   Executing request {i + 1}/{num_requests}...")
                completed: StreamingRequest = client.stream_request(req)
                completed_requests.append(completed)

                # Validate each request as we go for sequential
                validation = validate_streaming_request(completed)
                if not validation["is_valid"]:
                    print(
                        f"   ❌ Request {i + 1} failed: {', '.join(validation['errors'])}"
                    )
                    if i == 0:  # Show details for first failed request
                        print(
                            f"      Sample response info: {get_sample_error_response(completed)}"
                        )
    except Exception as e:
        print(f"❌ Request execution failed: {e}")
        return {
            "service_name": service_name,
            "concurrent": concurrent,
            "error": str(e),
            "request_performance": {"count": 0},
            "throughput_performance": {},
            "chunk_performance": {},
            "data_transfer": {},
        }

    end_time = timer.now_ns()
    total_time_ms = (end_time - start_time) / 1e6

    # Validate all completed requests
    valid_requests = []
    failed_requests = []

    for req in completed_requests:
        validation = validate_streaming_request(req)
        if validation["is_valid"]:
            valid_requests.append(req)
        else:
            failed_requests.append((req, validation))

    print(f"✅ Completed {len(completed_requests)} requests in {total_time_ms:.2f}ms")
    print(f"   📊 Valid responses: {len(valid_requests)}")
    print(f"   ❌ Failed/Invalid responses: {len(failed_requests)}")

    if failed_requests:
        print("\n❌ Request Failures Analysis:")
        for i, (req, validation) in enumerate(
            failed_requests[:3]
        ):  # Show first 3 failures
            print(f"   Request {i + 1}: {', '.join(validation['errors'])}")
            print(f"      Response: {get_sample_error_response(req)}")

    # Only analyze valid requests for performance metrics
    if valid_requests:
        analysis = analyze_streaming_performance(valid_requests, timer)
    else:
        print("⚠️  No valid requests to analyze - all requests failed!")
        analysis = {
            "request_performance": {
                "count": 0,
                "avg_duration_ms": 0,
                "median_duration_ms": 0,
                "min_duration_ms": 0,
                "max_duration_ms": 0,
                "duration_stdev_ms": 0,
            },
            "ttft_performance": {
                "count": 0,
                "avg_ttft_ms": 0,
                "median_ttft_ms": 0,
                "min_ttft_ms": 0,
                "max_ttft_ms": 0,
                "ttft_stdev_ms": 0,
            },
            "ttst_performance": {
                "count": 0,
                "avg_ttst_ms": 0,
                "median_ttst_ms": 0,
                "min_ttst_ms": 0,
                "max_ttst_ms": 0,
                "ttst_stdev_ms": 0,
            },
            "inter_token_latency": {
                "count": 0,
                "avg_itl_ms": 0,
                "median_itl_ms": 0,
                "min_itl_ms": 0,
                "max_itl_ms": 0,
                "itl_stdev_ms": 0,
            },
            "throughput_performance": {
                "avg_throughput_bps": 0,
                "avg_throughput_mbps": 0,
                "median_throughput_bps": 0,
                "max_throughput_bps": 0,
            },
            "chunk_performance": {
                "avg_chunks_per_request": 0,
                "total_chunks": 0,
                "avg_chunk_interval_ms": 0,
                "chunk_interval_stdev_ms": 0,
                "min_chunk_interval_ms": 0,
                "max_chunk_interval_ms": 0,
            },
            "data_transfer": {
                "total_bytes": 0,
                "total_mb": 0,
                "avg_bytes_per_request": 0,
            },
        }

    # Add additional metadata - cast to Any to handle mixed types
    extended_analysis: dict[str, Any] = dict(analysis)
    extended_analysis["execution_time_ms"] = total_time_ms
    extended_analysis["service_name"] = service_name
    extended_analysis["concurrent"] = concurrent
    extended_analysis["total_requests"] = len(completed_requests)
    extended_analysis["valid_requests"] = len(valid_requests)
    extended_analysis["failed_requests"] = len(failed_requests)

    return extended_analysis


def print_performance_analysis(analysis: dict[str, Any]):
    """Print formatted performance analysis."""

    print(f"\n📊 Performance Analysis for {analysis['service_name']}")
    print("=" * 50)

    # Show request success/failure summary
    total_reqs = analysis.get("total_requests", 0)
    valid_reqs = analysis.get("valid_requests", 0)
    failed_reqs = analysis.get("failed_requests", 0)

    if "error" in analysis:
        print(f"❌ Benchmark failed with error: {analysis['error']}")
        return

    print("📋 Request Summary:")
    print(f"   • Total requests sent: {total_reqs}")
    print(f"   • Successful requests: {valid_reqs}")
    print(f"   • Failed requests: {failed_reqs}")
    if failed_reqs > 0:
        print(f"   • Success rate: {(valid_reqs / total_reqs * 100):.1f}%")

    if valid_reqs == 0:
        print("\n⚠️  No valid requests to analyze!")
        print("🔧 Troubleshooting suggestions:")
        print("   • Check if your AI service is running")
        print("   • Verify the URL and authentication")
        print("   • Check network connectivity")
        print("   • Review error messages above")
        return

    req_perf = analysis["request_performance"]
    print("\n🕐 Request Performance:")
    print(f"   • Valid requests analyzed: {req_perf['count']}")
    print(f"   • Average duration: {req_perf['avg_duration_ms']:.2f}ms")
    print(f"   • Median duration: {req_perf['median_duration_ms']:.2f}ms")
    print(
        f"   • Duration range: {req_perf['min_duration_ms']:.2f}ms - {req_perf['max_duration_ms']:.2f}ms"
    )
    print(f"   • Standard deviation: {req_perf['duration_stdev_ms']:.2f}ms")

    # Time To First Token (TTFT) Performance
    ttft_perf = analysis.get("ttft_performance", {})
    if ttft_perf.get("count", 0) > 0:
        print("\n⚡ Time To First Token (TTFT):")
        print(f"   • Requests with TTFT data: {ttft_perf['count']}")
        print(f"   • Average TTFT: {ttft_perf['avg_ttft_ms']:.2f}ms")
        print(f"   • Median TTFT: {ttft_perf['median_ttft_ms']:.2f}ms")
        print(
            f"   • TTFT range: {ttft_perf['min_ttft_ms']:.2f}ms - {ttft_perf['max_ttft_ms']:.2f}ms"
        )
        print(f"   • TTFT standard deviation: {ttft_perf['ttft_stdev_ms']:.2f}ms")

    # Time To Second Token (TTST) Performance
    ttst_perf = analysis.get("ttst_performance", {})
    if ttst_perf.get("count", 0) > 0:
        print("\n🥈 Time To Second Token (TTST):")
        print(f"   • Requests with TTST data: {ttst_perf['count']}")
        print(f"   • Average TTST: {ttst_perf['avg_ttst_ms']:.2f}ms")
        print(f"   • Median TTST: {ttst_perf['median_ttst_ms']:.2f}ms")
        print(
            f"   • TTST range: {ttst_perf['min_ttst_ms']:.2f}ms - {ttst_perf['max_ttst_ms']:.2f}ms"
        )
        print(f"   • TTST standard deviation: {ttst_perf['ttst_stdev_ms']:.2f}ms")

    # Inter-Token Latency (ITL) Performance
    itl_perf = analysis.get("inter_token_latency", {})
    if itl_perf.get("count", 0) > 0:
        print("\n🔄 Inter-Token Latency (ITL):")
        print(f"   • Total token intervals measured: {itl_perf['count']}")
        print(f"   • Average ITL: {itl_perf['avg_itl_ms']:.2f}ms")
        print(f"   • Median ITL: {itl_perf['median_itl_ms']:.2f}ms")
        print(
            f"   • ITL range: {itl_perf['min_itl_ms']:.2f}ms - {itl_perf['max_itl_ms']:.2f}ms"
        )
        print(f"   • ITL standard deviation: {itl_perf['itl_stdev_ms']:.2f}ms")

    throughput_perf = analysis["throughput_performance"]
    print("\n🚀 Throughput Performance:")
    print(f"   • Average throughput: {throughput_perf['avg_throughput_mbps']:.2f} MB/s")
    print(
        f"   • Peak throughput: {throughput_perf['max_throughput_bps'] / (1024 * 1024):.2f} MB/s"
    )

    chunk_perf = analysis["chunk_performance"]
    print("\n📦 Chunk Performance:")
    print(f"   • Total chunks received: {chunk_perf['total_chunks']}")
    print(
        f"   • Average chunks per request: {chunk_perf['avg_chunks_per_request']:.1f}"
    )
    if chunk_perf["avg_chunk_interval_ms"] > 0:
        print(
            f"   • Average chunk interval: {chunk_perf['avg_chunk_interval_ms']:.2f}ms"
        )
        print(
            f"   • Chunk interval range: {chunk_perf['min_chunk_interval_ms']:.2f}ms - {chunk_perf['max_chunk_interval_ms']:.2f}ms"
        )

    data_perf = analysis["data_transfer"]
    print("\n💾 Data Transfer:")
    print(f"   • Total data transferred: {data_perf['total_mb']:.2f} MB")
    print(f"   • Average per request: {data_perf['avg_bytes_per_request']:.0f} bytes")

    # Performance quality assessment
    print("\n🎯 Performance Assessment:")
    avg_duration = req_perf["avg_duration_ms"]
    avg_throughput = throughput_perf["avg_throughput_mbps"]
    avg_ttft = ttft_perf.get("avg_ttft_ms", 0)
    avg_ttst = ttst_perf.get("avg_ttst_ms", 0)
    avg_itl = itl_perf.get("avg_itl_ms", 0)

    if avg_duration < 100:
        print("   ⚡ Very fast response times (<100ms)")
    elif avg_duration < 1000:
        print("   ✅ Good response times (<1s)")
    elif avg_duration < 5000:
        print("   ⏳ Moderate response times (1-5s)")
    else:
        print("   🐌 Slow response times (>5s)")

    if avg_ttft > 0:
        if avg_ttft < 50:
            print("   ⚡ Excellent TTFT (<50ms)")
        elif avg_ttft < 200:
            print("   ✅ Good TTFT (<200ms)")
        elif avg_ttft < 1000:
            print("   ⏳ Moderate TTFT (<1s)")
        else:
            print("   🐌 Slow TTFT (>1s)")

    if avg_ttst > 0:
        if avg_ttst < 20:
            print("   ⚡ Excellent TTST (<20ms)")
        elif avg_ttst < 100:
            print("   ✅ Good TTST (<100ms)")
        elif avg_ttst < 500:
            print("   ⏳ Moderate TTST (<500ms)")
        else:
            print("   🐌 Slow TTST (>500ms)")

    if avg_itl > 0:
        if avg_itl < 20:
            print("   ⚡ Excellent ITL (<20ms)")
        elif avg_itl < 100:
            print("   ✅ Good ITL (<100ms)")
        elif avg_itl < 500:
            print("   ⏳ Moderate ITL (<500ms)")
        else:
            print("   🐌 Slow ITL (>500ms)")

    if avg_throughput > 10:
        print("   🚀 High throughput (>10 MB/s)")
    elif avg_throughput > 1:
        print("   ✅ Good throughput (>1 MB/s)")
    else:
        print("   📉 Low throughput (<1 MB/s)")


def main():
    """Main AI inference timing example."""

    print("🤖 AI Inference Streaming Performance Analysis")
    print("=" * 60)
    print("📈 Measuring nanosecond-precision timing for AI streaming responses")
    print(
        "⚡ Including TTFT, TTST, and Inter-Token Latency analysis for streaming AI services"
    )

    # Demo with local service (will likely fail - for demonstration)
    print("\n🧪 Demo Configuration:")
    print("   This example will attempt to connect to a local AI service.")
    print("   Since no service is likely running, it will demonstrate error handling.")
    print("\n💡 For real testing, set up one of these services:")
    print("   • OpenAI API: Set OPENAI_API_KEY environment variable")
    print("   • Anthropic API: Set ANTHROPIC_API_KEY environment variable")
    print("   • Local model server (Ollama, vLLM, etc.) at localhost:8080")

    demo_config = {
        "base_url": "http://127.0.0.1:8080/v1/chat/completions",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        },
    }

    # Check for real API keys and provide real examples if available
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    scenarios = []

    if openai_key:
        print("\n✅ Found OpenAI API key - will test real OpenAI service")
        openai_config = AIServiceConfig.openai_config(openai_key)
        scenarios.extend(
            [
                (
                    "OpenAI GPT-3.5 Sequential",
                    openai_config,
                    create_openai_payload("Explain quantum computing in simple terms."),
                    3,
                    False,
                ),
                (
                    "OpenAI GPT-3.5 Concurrent",
                    openai_config,
                    create_openai_payload("Explain quantum computing in simple terms."),
                    5,
                    True,
                ),
            ]
        )

    if anthropic_key:
        print("\n✅ Found Anthropic API key - will test real Anthropic service")
        anthropic_config = AIServiceConfig.anthropic_config(anthropic_key)
        scenarios.extend(
            [
                (
                    "Anthropic Claude Sequential",
                    anthropic_config,
                    create_anthropic_payload(
                        "Explain quantum computing in simple terms."
                    ),
                    3,
                    False,
                ),
            ]
        )

    # Always include demo scenario to show error handling
    scenarios.extend(
        [
            (
                "Demo Service Sequential (will likely fail)",
                demo_config,
                create_openai_payload("Explain quantum computing in simple terms."),
                0,
                False,
            ),
            (
                "Demo Service Concurrent (will likely fail)",
                demo_config,
                create_openai_payload("Explain quantum computing in simple terms."),
                20,
                False,
            ),
        ]
    )

    if not openai_key and not anthropic_key:
        print("\n⚠️  No API keys found - running demo scenarios only")
        print("   These will demonstrate error handling for unavailable services")

    results = []

    for service_name, config, payload, num_requests, concurrent in scenarios:
        analysis = benchmark_ai_service(
            service_name, config, payload, num_requests, concurrent
        )
        results.append(analysis)
        print_performance_analysis(analysis)

    # Compare results (only valid ones)
    valid_results = [r for r in results if r.get("valid_requests", 0) > 0]

    if valid_results:
        print("\n🔬 Performance Comparison")
        print("=" * 40)

        for analysis in valid_results:
            req_perf = analysis["request_performance"]
            throughput_perf = analysis["throughput_performance"]
            ttft_perf = analysis.get("ttft_performance", {})
            ttst_perf = analysis.get("ttst_performance", {})
            itl_perf = analysis.get("inter_token_latency", {})
            execution_mode = "concurrent" if analysis["concurrent"] else "sequential"

            print(f"\n{analysis['service_name']} ({execution_mode}):")
            print(f"   • Avg latency: {req_perf['avg_duration_ms']:.2f}ms")
            if ttft_perf.get("avg_ttft_ms", 0) > 0:
                print(f"   • Avg TTFT: {ttft_perf['avg_ttft_ms']:.2f}ms")
            if ttst_perf.get("avg_ttst_ms", 0) > 0:
                print(f"   • Avg TTST: {ttst_perf['avg_ttst_ms']:.2f}ms")
            if itl_perf.get("avg_itl_ms", 0) > 0:
                print(f"   • Avg ITL: {itl_perf['avg_itl_ms']:.2f}ms")
            print(f"   • Throughput: {throughput_perf['avg_throughput_mbps']:.2f} MB/s")
            print(f"   • Total time: {analysis['execution_time_ms']:.2f}ms")
            print(
                f"   • Success rate: {analysis['valid_requests']}/{analysis['total_requests']}"
            )
    else:
        print("\n⚠️  No successful benchmarks to compare")
        print("   All requests failed - check service availability and configuration")

    print("\n💡 Setup Guide for Real AI Service Testing:")
    print("   🔐 API Keys (set as environment variables):")
    print("       export OPENAI_API_KEY='your-openai-key'")
    print("       export ANTHROPIC_API_KEY='your-anthropic-key'")
    print("   🏠 Local Services:")
    print("       • Ollama: ollama serve (default port 11434)")
    print("       • vLLM: python -m vllm.entrypoints.api_server --model <model>")
    print("       • Text Generation Inference: Use appropriate endpoints")
    print("   📊 Usage Tips:")
    print("       • Start with small request counts for testing")
    print("       • Monitor rate limits and costs for paid APIs")
    print("       • Use representative prompts for your use case")
    print("       • Test different concurrency levels")
    print("       • TTFT (Time To First Token) measures AI responsiveness")
    print("       • TTST (Time To Second Token) measures generation ramp-up")
    print("       • ITL (Inter-Token Latency) measures streaming consistency")
    print("       • Lower values = better user experience for streaming")

    print("\n🎯 Analysis completed successfully!")


if __name__ == "__main__":
    main()
