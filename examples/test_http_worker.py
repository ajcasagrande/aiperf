#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""
Test script for the HTTP worker functionality.
Demonstrates sending various HTTP requests through the ZMQ worker system.
"""

import asyncio
import json

import httpx


async def test_http_worker():
    """Test the HTTP worker with various request types."""

    # Test requests to send to workers
    test_requests = [
        {"method": "GET", "path": "/", "headers": {"Content-Type": "application/json"}},
        {
            "method": "POST",
            "path": "/api/test",
            "headers": {"Content-Type": "application/json"},
            "json": {"test": "data", "timestamp": "2025-01-09"},
        },
        {"method": "GET", "path": "/health", "params": {"check": "full"}},
        {
            "method": "PUT",
            "path": "/api/update",
            "json": {"id": 123, "status": "updated"},
        },
        {"method": "DELETE", "path": "/api/item/456"},
    ]

    print("HTTP Worker Test Examples")
    print("=" * 50)

    for i, request in enumerate(test_requests, 1):
        print(f"\nTest {i}: {request['method']} {request['path']}")
        print(f"Request payload: {json.dumps(request, indent=2)}")
        print("-" * 30)

        # This demonstrates what the worker would receive
        message_bytes = json.dumps(request).encode()
        print(f"Message size: {len(message_bytes)} bytes")

        # Show what would be sent to FastAPI
        print(f"Would make request to: http://localhost:9797{request['path']}")

        if "json" in request:
            print(f"With JSON data: {request['json']}")
        if "params" in request:
            print(f"With params: {request['params']}")


async def test_fastapi_connection():
    """Test direct connection to FastAPI server."""

    print("\nTesting FastAPI Server Connection")
    print("=" * 40)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:9797/health")
            print("✅ FastAPI server is running!")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")

    except httpx.ConnectError:
        print("❌ FastAPI server is not running on port 9797")
        print("Please start the server with: python examples/fastapi_server.py")

    except Exception as e:
        print(f"❌ Error connecting to FastAPI server: {e}")


if __name__ == "__main__":
    print("Testing HTTP Worker Functionality\n")

    # Test FastAPI connection first
    asyncio.run(test_fastapi_connection())

    # Show example requests
    asyncio.run(test_http_worker())

    print("\n" + "=" * 50)
    print("To use with ZMQ Worker Manager:")
    print("1. Start FastAPI server: python examples/fastapi_server.py")
    print("2. Start ZMQ Worker Manager with http_request_worker_handler")
    print("3. Send credit drop messages with HTTP request data")
    print("4. Workers will make HTTP requests and return responses")
