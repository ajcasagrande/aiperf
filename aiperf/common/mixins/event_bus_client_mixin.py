# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.comms.base_comms import BaseCommunication
from aiperf.common.enums import CommunicationClientAddressType
from aiperf.common.mixins.base_mixin import BaseMixin


class EventBusClientMixin(BaseMixin):
    """Mixin that provides clients for the event bus."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        self.sub_client = comms.create_sub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND
        )
        self.pub_client = comms.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )
        # Pass through the comms and clients to base classes
        super().__init__(
            pub_client=self.pub_client,
            sub_client=self.sub_client,
            **kwargs,
        )
