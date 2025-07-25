# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC

from aiperf.common.config import ServiceConfig
from aiperf.common.constants import DEFAULT_PULL_CLIENT_MAX_CONCURRENCY
from aiperf.common.enums import CommAddress
from aiperf.common.factories import CommunicationFactory
from aiperf.common.hooks import (
    AIPerfHook,
    PullHookParams,
    on_init,
    provides_hooks,
)
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.protocols import CommunicationProtocol


@provides_hooks(AIPerfHook.ON_PULL_MESSAGE)
class PullClientMixin(AIPerfLifecycleMixin, ABC):
    """Mixin to provide a pull client for AIPerf components using a PullClient for the specified CommAddress.
    Add the @on_pull_message hook to specify a function that will be called when a pull is received.

    NOTE: This currently only supports a single pull client per service, as that is our current use case.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        pull_client_address: CommAddress,
        pull_client_bind: bool = False,
        pull_client_max_concurrency: int | None = DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,
        **kwargs,
    ) -> None:
        self.comms: CommunicationProtocol = CommunicationFactory.get_or_create_instance(
            service_config.comm_backend,
            config=service_config.comm_config,
        )
        self.pull_client_address = pull_client_address
        self.pull_client_bind = pull_client_bind
        self.pull_client_max_concurrency = pull_client_max_concurrency
        super().__init__(
            service_config=service_config,
            pull_client_address=pull_client_address,
            pull_client_bind=pull_client_bind,
            pull_client_max_concurrency=pull_client_max_concurrency,
            **kwargs,
        )
        # NOTE: The pull client will be automatically managed by the self.comms instance.
        #       This is why we don't need to initialize or start/stop the pull client.
        self.pull_client = self.comms.create_pull_client(
            self.pull_client_address, bind=self.pull_client_bind
        )

    @on_init
    async def _setup_pull_handler_hooks(self) -> None:
        """Configure the pull client to register callbacks for all @on_pull_message hook decorators."""
        for hook in self.get_hooks(AIPerfHook.ON_PULL_MESSAGE):
            if not isinstance(hook.params, PullHookParams):
                raise ValueError(
                    f"Invalid hook params: {hook.params}. Expected PullHookParams but got {type(hook.params)}"
                )
            self.debug(lambda hook=hook: f"Registering pull handler {hook!r}")
            for message_type in hook.params.message_types:
                await self.pull_client.register_pull_callback(
                    message_type=message_type,
                    callback=hook.func,
                    max_concurrency=hook.params.max_concurrency,
                )
