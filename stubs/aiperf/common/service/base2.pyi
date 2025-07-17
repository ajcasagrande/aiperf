#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import ClassVar

from _typeshed import Incomplete

from aiperf.common.config._service import ServiceConfig as ServiceConfig
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.hooks import on_cleanup as on_cleanup
from aiperf.common.hooks import on_init as on_init
from aiperf.common.mixins import AIPerfLifecycleMixin as AIPerfLifecycleMixin
from aiperf.common.mixins import AIPerfProfileMixin as AIPerfProfileMixin
from aiperf.common.mixins import EventBusClientMixin as EventBusClientMixin

class AIPerfServiceMixin(AIPerfLifecycleMixin, EventBusClientMixin):
    service_type: ClassVar[ServiceType]
    service_config: Incomplete
    service_id: Incomplete
    logger: Incomplete
    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None: ...
    @on_init
    async def initialize(self) -> None: ...
    @on_cleanup
    async def cleanup(self) -> None: ...

class AIPerfComponentServiceMixin(AIPerfProfileMixin, AIPerfServiceMixin):
    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None: ...
    @on_init
    async def initialize(self) -> None: ...
    @on_cleanup
    async def cleanup(self) -> None: ...
