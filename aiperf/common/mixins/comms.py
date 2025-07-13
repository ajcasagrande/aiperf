# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.comms.base import BaseCommunication, CommunicationFactory
from aiperf.common.hooks import AIPerfHook
from aiperf.common.mixins.hooks import HooksMixin, supports_hooks


@supports_hooks(AIPerfHook.ON_MESSAGE)
class CommunicationsMixin(HooksMixin):
    """Mixin that provides a communications instance."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._service_config = kwargs.get("service_config")
        if not self._service_config:
            raise ValueError("CommunicationsMixin requires a service_config attribute")

        self.comms: BaseCommunication = CommunicationFactory.create_instance(
            self._service_config.comm_backend,
            config=self._service_config.comm_config,
        )
