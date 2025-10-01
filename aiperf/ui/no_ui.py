# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from pluggy import HookimplMarker

from aiperf import AIPERF_PROJECT_NAME
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import AIPerfUIType
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.plugin_metadata import AIPerfPluginMetadata
from aiperf.common.protocols import AIPerfUIProtocol


@implements_protocol(AIPerfUIProtocol)
@AIPerfUIFactory.register(AIPerfUIType.NONE)
class NoUI(AIPerfLifecycleMixin):
    """
    A UI that does nothing.

    Implements the :class:`AIPerfUIProtocol` to allow it to be used as a UI, but provides no functionality.

    NOTE: Not inheriting from :class:`BaseAIPerfUI` because it does not need to track progress or workers.
    """

    @staticmethod
    def plugin_metadata() -> AIPerfPluginMetadata:
        """Plugin metadata for the NoUI."""
        return AIPerfPluginMetadata(
            name="none",
            description="A UI that does nothing",
            version="1.0.0",
        )


hookimpl = HookimplMarker(AIPERF_PROJECT_NAME)


@hookimpl
def ui() -> type[NoUI]:
    """Provide the NoUI class to the plugin factory."""
    return NoUI
