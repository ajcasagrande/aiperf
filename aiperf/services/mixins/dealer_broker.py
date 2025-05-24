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

import asyncio

import zmq
import zmq.asyncio

from aiperf.common.comms.zmq.clients.dealer_router import DealerRouterBroker
from aiperf.common.exceptions.comms import CommunicationError
from aiperf.common.interfaces import SupportsLogging, SupportsZMQConfig


class DealerRouterBrokerMixin(SupportsLogging, SupportsZMQConfig):
    """Mixin for services that need to act as a dealer router broker."""

    async def run_broker(self):
        """Run the broker using DealerRouterBroker."""
        self.logger.info("Starting timing broker process")
        context = zmq.asyncio.Context.instance()

        broker = DealerRouterBroker(
            context=context,
            router_address=self.zmq_config.credit_broker_router_address,
            dealer_address=self.zmq_config.credit_broker_dealer_address,
            control_address=self.zmq_config.credit_broker_control_address,
            capture_address=self.zmq_config.credit_broker_capture_address,
        )

        try:
            await broker.run()
        except CommunicationError as e:
            self.logger.error(f"Broker error: {e}")
        except asyncio.CancelledError:
            self.logger.info("Broker cancelled")
        except Exception as e:
            self.logger.error(f"Unexpected broker error: {e}")

    async def stop_broker(self):
        """Stop the broker."""
        self.logger.info("Stopping timing broker process")
        if self.broker:
            await self.broker.stop()
        self.logger.info("Timing broker process stopped")
