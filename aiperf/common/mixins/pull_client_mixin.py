# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC

from aiperf.common.config import ServiceConfig
from aiperf.common.enums import CommAddress
from aiperf.common.hooks import (
    AIPerfHook,
    PullHookParams,
    on_init,
    provides_hooks,
)
from aiperf.common.mixins.communication_mixin import CommunicationMixin


@provides_hooks(AIPerfHook.ON_PULL_MESSAGE)
class PullClientMixin(CommunicationMixin, ABC):
    """Mixin to provide a pull client for AIPerf components using a PullClient for the specified CommAddress.
    Add the @on_pull_message decorator to specify a function that will be called when a pull is received.

    NOTE: This currently only supports a single pull client per service, as that is our current use case.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        pull_client_address: CommAddress,
        pull_client_bind: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(service_config=service_config, **kwargs)
        # NOTE: The communication base class will automatically manage the pull client's lifecycle.
        self.pull_client = self.comms.create_pull_client(
            pull_client_address, bind=pull_client_bind
        )

    @on_init
    async def _setup_pull_handler_hooks(self) -> None:
        """Configure the pull client to register callbacks for all @on_pull_message hook decorators."""
        for hook in self.get_hooks(AIPerfHook.ON_PULL_MESSAGE):
            params = hook.resolve_params(self)
            if not isinstance(params, PullHookParams):
                raise ValueError(
                    f"Invalid hook params: {params}. Expected PullHookParams but got {type(params)}"
                )
            self.debug(lambda hook=hook: f"Registering pull handler {hook!r}")
            for message_type in params.message_types:
                await self.pull_client.register_pull_callback(
                    message_type=message_type,
                    callback=hook.func,
                    max_concurrency=params.max_concurrency,
                )
