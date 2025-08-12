# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio

from aiperf.common.config import ServiceConfig
from aiperf.common.enums import MessageType
from aiperf.common.hooks import AIPerfHook, on_message, provides_hooks
from aiperf.common.messages.inference_messages import MetricsPreviewMessage
from aiperf.common.mixins.message_bus_mixin import MessageBusClientMixin
from aiperf.common.models import MetricResult
from aiperf.controller.system_controller import SystemController


@provides_hooks(AIPerfHook.ON_METRICS_PREVIEW)
class MetricsPreviewMixin(MessageBusClientMixin):
    """A mixin that provides a hook for metrics preview."""

    def __init__(
        self, service_config: ServiceConfig, controller: SystemController, **kwargs
    ):
        super().__init__(service_config=service_config, controller=controller, **kwargs)
        self._controller = controller
        self._metrics_preview: list[MetricResult] = []
        self._metrics_preview_lock = asyncio.Lock()

    @on_message(MessageType.METRICS_PREVIEW)
    async def _on_metrics_preview(self, message: MetricsPreviewMessage):
        """Update the metrics preview from a metrics preview message."""
        async with self._metrics_preview_lock:
            self._metrics_preview = message.metrics
        await self.run_hooks(
            AIPerfHook.ON_METRICS_PREVIEW,
            metrics_preview=self._metrics_preview,
        )
