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
Test script to verify the worker fix for processing HTTP request data.
"""

import asyncio
import json
import sys

# Add the project root to the path
sys.path.insert(0, "..")

from aiperf.services.worker_manager.zmq_worker_manager import (
    http_request_worker_handler,
)


async def test_worker_handler():
    """Test the HTTP worker handler with credit drop data."""
    print("🧪 Testing Worker Handler with HTTP Request Data")
    print("=" * 50)

    # Simulate the HTTP request data that worker manager sends
    test_http_request = {
        "method": "POST",
        "path": "/api/credit-drop",
        "headers": {
            "Content-Type": "application/json",
            "X-Credit-Amount": "1",
            "X-Credit-Timestamp": "1748062479968869956",
        },
        "json": {
            "credit_drop": {
                "amount": 1,
                "timestamp": 1748062479968869956,
                "request_id": None,
                "service_id": "timing_manager_test",
            }
        },
    }

    # Convert to bytes like the dealer client would send
    message_bytes = json.dumps(test_http_request).encode()

    print(f"📤 Test message: {test_http_request}")
    print(f"📦 Message bytes length: {len(message_bytes)}")
    print()

    try:
        # Test the worker handler
        print("🔄 Calling worker handler...")
        result = await http_request_worker_handler(
            message=message_bytes, worker_id="test-worker-0"
        )

        print("✅ Worker handler completed!")
        print(f"📥 Result type: {type(result)}")

        if isinstance(result, bytes):
            try:
                result_data = json.loads(result.decode())
                print(f"📥 Result data: {json.dumps(result_data, indent=2)}")

                # Check if it was successful
                if result_data.get("success"):
                    print("🎉 SUCCESS: Worker processed HTTP request successfully!")
                else:
                    print(
                        f"⚠️ PARTIAL: Worker completed but with issues: {result_data.get('error', 'Unknown')}"
                    )

            except (json.JSONDecodeError, UnicodeDecodeError):
                print(f"📥 Raw result: {result}")
        else:
            print(f"📥 Result: {result}")

    except Exception as e:
        print(f"❌ FAILED: Worker handler raised exception: {e}")
        import traceback

        traceback.print_exc()


async def test_different_formats():
    """Test worker handler with different message formats."""
    print("\n🧪 Testing Different Message Formats")
    print("=" * 40)

    test_cases = [
        ("Bytes JSON", json.dumps({"method": "GET", "path": "/"}).encode()),
        ("String JSON", json.dumps({"method": "POST", "path": "/test"})),
        ("Raw string", "simple string message"),
        ("Dict (should default)", {"direct": "dict"}),
    ]

    for case_name, message in test_cases:
        print(f"\n📋 Testing {case_name}:")
        try:
            result = await http_request_worker_handler(message, f"test-{case_name}")
            if isinstance(result, bytes):
                result_data = json.loads(result.decode())
                print(f"  ✅ Success: {result_data.get('success', False)}")
            else:
                print(f"  ✅ Result: {result}")
        except Exception as e:
            print(f"  ❌ Error: {e}")


async def main():
    """Main test function."""
    await test_worker_handler()
    await test_different_formats()


if __name__ == "__main__":
    asyncio.run(main())
