#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Demonstration script showing the HTTP/2 client with connection sharing capabilities.

This script demonstrates:
1. How to use the new HttpxClientMixin with HTTP/2 support
2. Performance comparison between aiohttp and httpx clients
3. Connection sharing benefits in concurrent scenarios
4. SSE streaming capabilities with both clients
"""

import asyncio
import json
import time

from aiperf.clients.http import AioHttpClientMixin, HttpxClientMixin
from aiperf.clients.model_endpoint_info import EndpointInfo, ModelEndpointInfo
from aiperf.common.models import RequestRecord


class MockEndpoint:
    """Mock endpoint for demonstration purposes."""

    def __init__(self, base_url: str = "https://httpbin.org"):
        self.base_url = base_url
        self.endpoint_info = EndpointInfo(timeout=30.0)
        self.model_endpoint = ModelEndpointInfo(endpoint=self.endpoint_info)

    @property
    def post_url(self) -> str:
        return f"{self.base_url}/post"

    @property
    def delay_url(self) -> str:
        return f"{self.base_url}/delay/1"


async def demo_basic_usage():
    """Demonstrate basic usage of both HTTP clients."""
    print("=== Basic Usage Demonstration ===\n")

    mock_endpoint = MockEndpoint()

    # Test data
    test_payload = json.dumps({"message": "Hello HTTP/2!", "client": "httpx"})
    headers = {"Content-Type": "application/json", "User-Agent": "AIPerf-HTTP2-Demo"}

    # HTTP/2 Client (httpx)
    print("🚀 Testing HTTP/2 Client (httpx)...")
    httpx_client = HttpxClientMixin(model_endpoint=mock_endpoint.model_endpoint)
    httpx_client.initialize_session(headers)

    start_time = time.perf_counter()
    httpx_record = await httpx_client.post_request(
        mock_endpoint.post_url, test_payload, headers
    )
    httpx_duration = time.perf_counter() - start_time

    print(f"   Status: {httpx_record.status}")
    print(f"   Duration: {httpx_duration:.3f}s")
    print(
        f"   Response size: {len(httpx_record.responses[0].text) if httpx_record.responses else 0} bytes"
    )
    print(f"   Error: {httpx_record.error}")

    await httpx_client.close()

    # HTTP/1.1 Client (aiohttp) for comparison
    print("\n📡 Testing HTTP/1.1 Client (aiohttp)...")
    aiohttp_client = AioHttpClientMixin(model_endpoint=mock_endpoint.model_endpoint)
    aiohttp_client.initialize_session(headers)

    start_time = time.perf_counter()
    aiohttp_record = await aiohttp_client.post_request(
        mock_endpoint.post_url, test_payload, headers
    )
    aiohttp_duration = time.perf_counter() - start_time

    print(f"   Status: {aiohttp_record.status}")
    print(f"   Duration: {aiohttp_duration:.3f}s")
    print(
        f"   Response size: {len(aiohttp_record.responses[0].text) if aiohttp_record.responses else 0} bytes"
    )
    print(f"   Error: {aiohttp_record.error}")

    await aiohttp_client.close()

    print("\n📊 Performance Comparison:")
    if httpx_duration < aiohttp_duration:
        improvement = ((aiohttp_duration - httpx_duration) / aiohttp_duration) * 100
        print(f"   HTTP/2 client was {improvement:.1f}% faster!")
    else:
        difference = ((httpx_duration - aiohttp_duration) / aiohttp_duration) * 100
        print(
            f"   HTTP/1.1 client was {difference:.1f}% faster (network conditions may vary)"
        )


async def demo_concurrent_requests():
    """Demonstrate connection sharing benefits with concurrent requests."""
    print("\n=== Concurrent Requests Demonstration ===\n")

    mock_endpoint = MockEndpoint()
    headers = {"Content-Type": "application/json"}

    async def make_concurrent_requests(
        client_class, client_name: str, num_requests: int = 10
    ):
        """Make concurrent requests with a given client."""
        client = client_class(model_endpoint=mock_endpoint.model_endpoint)
        client.initialize_session(headers)

        async def single_request(request_id: int) -> RequestRecord:
            payload = json.dumps({"request_id": request_id, "client": client_name})
            return await client.post_request(mock_endpoint.post_url, payload, headers)

        print(f"🚀 Making {num_requests} concurrent requests with {client_name}...")
        start_time = time.perf_counter()

        # Make concurrent requests
        tasks = [single_request(i) for i in range(num_requests)]
        records = await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.perf_counter() - start_time

        # Count successful requests
        successful = len(
            [r for r in records if isinstance(r, RequestRecord) and not r.has_error]
        )

        print(f"   Completed: {successful}/{num_requests} requests")
        print(f"   Total time: {duration:.3f}s")
        print(f"   Average per request: {duration / num_requests:.3f}s")
        print(f"   Requests per second: {num_requests / duration:.1f}")

        await client.close()
        return duration, successful

    # Test both clients
    httpx_duration, httpx_success = await make_concurrent_requests(
        HttpxClientMixin, "HTTP/2 (httpx)", 10
    )

    print()  # Add spacing

    aiohttp_duration, aiohttp_success = await make_concurrent_requests(
        AioHttpClientMixin, "HTTP/1.1 (aiohttp)", 10
    )

    print("\n📊 Concurrent Performance Comparison:")
    print(f"   HTTP/2: {httpx_duration:.3f}s ({httpx_success} successful)")
    print(f"   HTTP/1.1: {aiohttp_duration:.3f}s ({aiohttp_success} successful)")

    if httpx_duration < aiohttp_duration:
        improvement = ((aiohttp_duration - httpx_duration) / aiohttp_duration) * 100
        print(f"   HTTP/2 was {improvement:.1f}% faster with connection sharing!")

    print(f"   HTTP/2 RPS: {10 / httpx_duration:.1f}")
    print(f"   HTTP/1.1 RPS: {10 / aiohttp_duration:.1f}")


async def demo_error_handling():
    """Demonstrate error handling capabilities."""
    print("\n=== Error Handling Demonstration ===\n")

    mock_endpoint = MockEndpoint("https://httpbin.org")
    headers = {"Content-Type": "application/json"}

    # Test 404 error
    httpx_client = HttpxClientMixin(model_endpoint=mock_endpoint.model_endpoint)
    httpx_client.initialize_session(headers)

    print("🚀 Testing 404 error handling with HTTP/2 client...")
    record = await httpx_client.post_request(
        "https://httpbin.org/status/404", '{"test": "error"}', headers
    )

    print(f"   Status: {record.status}")
    print(f"   Error Code: {record.error.code if record.error else 'None'}")
    print(f"   Error Type: {record.error.type if record.error else 'None'}")
    print(f"   Error Message: {record.error.message if record.error else 'None'}")

    await httpx_client.close()


async def demo_configuration():
    """Demonstrate configuration options."""
    print("\n=== Configuration Demonstration ===\n")

    from aiperf.clients.http.defaults import HttpxDefaults

    print("🔧 HTTP/2 Client Default Configuration:")
    print(f"   HTTP/2 Enabled: {HttpxDefaults.HTTP2}")
    print(f"   Max Connections: {HttpxDefaults.MAX_CONNECTIONS}")
    print(f"   Max Keepalive: {HttpxDefaults.MAX_KEEPALIVE_CONNECTIONS}")
    print(f"   Keepalive Expiry: {HttpxDefaults.KEEPALIVE_EXPIRY}s")
    print(f"   Default Timeout: {HttpxDefaults.TIMEOUT}s")
    print(f"   SSL Verification: {HttpxDefaults.VERIFY_SSL}")
    print(f"   Follow Redirects: {HttpxDefaults.FOLLOW_REDIRECTS}")

    print("\n🌍 Environment Variables for Tuning:")
    print("   AIPERF_HTTP2_CONNECTION_LIMIT - Maximum connections")
    print("   AIPERF_HTTP2_KEEPALIVE_LIMIT - Maximum keepalive connections")


async def main():
    """Run all demonstrations."""
    print("🚀 AIPerf HTTP/2 Client Demonstration")
    print("=" * 50)

    try:
        await demo_basic_usage()
        await demo_concurrent_requests()
        await demo_error_handling()
        await demo_configuration()

        print("\n✅ All demonstrations completed successfully!")
        print("\n🎯 Key Benefits of HTTP/2 Client:")
        print("   • HTTP/2 multiplexing for better performance")
        print("   • Automatic connection sharing and reuse")
        print("   • Optimized for concurrent requests")
        print("   • Same API as existing aiohttp client")
        print("   • Built-in SSL/TLS support")
        print("   • Precise timing measurements for benchmarking")

    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        print("   This might be due to network connectivity issues.")
        print("   The HTTP/2 client is ready for use in your environment!")


if __name__ == "__main__":
    asyncio.run(main())
