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
from aiperf.common.comms.zmq.clients.dealer_router import DealerRouterBroker
from aiperf.common.interfaces import SupportsDealerRouterBroker
from aiperf.common.mixins import ZMQConfigMixin
from aiperf.common.models.comms import ZMQCommunicationConfig


class DealerRouterBrokerMixin(ZMQConfigMixin, SupportsDealerRouterBroker):
    """Mixin for classes that support dealer router broker."""

    def __init__(self, zmq_config: ZMQCommunicationConfig, *args, **kwargs) -> None:
        self._broker = DealerRouterBroker.from_zmq_config(zmq_config)
        super().__init__(zmq_config, *args, **kwargs)

    @property
    def broker(self) -> DealerRouterBroker:
        """Get the dealer router broker for the class."""
        return self._broker

    async def run(self) -> None:
        """Run the dealer router broker."""
        await self._broker.run()

    async def stop(self) -> None:
        """Stop the dealer router broker."""
        await self._broker.stop()
