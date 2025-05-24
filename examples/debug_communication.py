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
Diagnostic script to test communication between timing manager and worker manager.
This helps debug why credit drops aren't being received.
"""

import asyncio
import logging
import sys
import time

# Set up logging to see all debug messages
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import Topic
from aiperf.common.enums.comm_clients import ClientType
from aiperf.common.enums.service import ServiceType
from aiperf.common.models.message import Message
from aiperf.common.models.payload import CreditDropPayload
from aiperf.common.service.base_component_service import BaseComponentService


class TestReceiver(BaseComponentService):
    """Test service to receive credit drops."""

    def __init__(self):
        """Initialize the test receiver."""
        config = ServiceConfig()
        super().__init__(service_config=config, service_id="test-receiver")
        self.received_count = 0

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER_MANAGER

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return []

    async def _test_callback(self, message: Message) -> None:
        """Test callback for receiving messages."""
        self.received_count += 1
        print(f"🎉 RECEIVED MESSAGE #{self.received_count}!")
        print(f"   Message: {message}")
        print(f"   Payload type: {type(message.payload)}")
        print(f"   Payload: {message.payload}")
        print()

    async def start_listening(self):
        """Start listening for credit drops."""
        print("🔊 Setting up credit drop listener...")
        print(f"   Topic: {Topic.CREDIT_DROP}")
        print(f"   Callback: {self._test_callback}")

        try:
            await self.comms.pull(
                topic=Topic.CREDIT_DROP,
                callback=self._test_callback,
            )
            print("✅ Successfully subscribed to credit drops!")
            print("Now listening for messages...")

        except Exception as e:
            print(f"❌ Failed to subscribe: {e}")
            raise


class TestSender(BaseComponentService):
    """Test service to send credit drops."""

    def __init__(self):
        """Initialize the test sender."""
        config = ServiceConfig()
        super().__init__(service_config=config, service_id="test-sender")

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.TIMING_MANAGER

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return []

    async def send_test_credit(self):
        """Send a test credit drop."""
        print("📤 Sending test credit drop...")

        try:
            payload = CreditDropPayload(amount=1, timestamp=time.time_ns())
            message = self.create_message(payload=payload)

            print(f"   Payload: {payload}")
            print(f"   Message: {message}")

            await self.comms.push(topic=Topic.CREDIT_DROP, message=message)

            print("✅ Credit drop sent successfully!")

        except Exception as e:
            print(f"❌ Failed to send credit drop: {e}")
            raise


async def test_receiver():
    """Test receiving credit drops."""
    print("🧪 Testing Credit Drop Reception")
    print("=" * 50)

    receiver = TestReceiver()

    try:
        # Initialize the receiver
        await receiver.start()
        await receiver.start_listening()

        print("Waiting for credit drops for 30 seconds...")
        print("(Run the timing manager or sender test in another terminal)")

        # Wait for messages
        await asyncio.sleep(30)

        print(f"\n📊 Results: Received {receiver.received_count} credit drops")

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        await receiver.stop()


async def test_sender():
    """Test sending credit drops."""
    print("🧪 Testing Credit Drop Sending")
    print("=" * 50)

    sender = TestSender()

    try:
        # Initialize the sender
        await sender.start()

        print("Sending test credit drops every 2 seconds...")
        print("(Run the receiver test in another terminal)")

        for i in range(10):
            await sender.send_test_credit()
            print(f"Sent credit drop {i + 1}/10")
            await asyncio.sleep(2)

        print("\n✅ All test credit drops sent!")

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        await sender.stop()


async def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print("🔧 Communication Test Tool")
        print("=" * 30)
        print("Usage:")
        print("  python debug_communication.py receiver  # Listen for credit drops")
        print("  python debug_communication.py sender    # Send test credit drops")
        print()
        print("Run the receiver in one terminal, then the sender in another")
        print("to test if communication is working between services.")
        return

    mode = sys.argv[1].lower()

    if mode == "receiver":
        await test_receiver()
    elif mode == "sender":
        await test_sender()
    else:
        print(f"❌ Unknown mode: {mode}")
        print("Use 'receiver' or 'sender'")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test stopped")
    except Exception as e:
        print(f"\n💥 Error: {e}")
        import traceback

        traceback.print_exc()
