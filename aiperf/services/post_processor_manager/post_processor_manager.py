# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import sys

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType
from aiperf.common.factories import MetricProviderFactory, ServiceFactory
from aiperf.common.hooks import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.metrics import BaseMetricProvider
from aiperf.common.models import BasePayload
from aiperf.common.service.base_component_service import BaseComponentService


@ServiceFactory.register(ServiceType.POST_PROCESSOR_MANAGER)
class PostProcessorManager(BaseComponentService):
    """PostProcessorManager is primarily responsible for iterating over the
    records to generate metrics and other conclusions from the records.
    """

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.info("Creating post processor manager")
        self.running_providers: list[BaseMetricProvider] = []

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.POST_PROCESSOR_MANAGER

    @on_init
    async def _initialize(self) -> None:
        """Initialize post processor manager-specific components."""
        self.logger.info("Initializing post processor manager")
        # TODO: Implement post processor manager initialization

    @on_start
    async def _start(self) -> None:
        """Start the post processor manager."""
        self.logger.info("Starting post processor manager")
        # TODO: Implement post processor manager start

        for provider_type in MetricProviderFactory.get_all_types():
            provider = MetricProviderFactory.create_instance(provider_type)
            await provider.initialize()
            self.running_providers.append(provider)

    @on_stop
    async def _stop(self) -> None:
        """Stop the post processor manager."""
        self.logger.info("Stopping post processor manager")
        # TODO: Implement post processor manager stop
        for provider in self.running_providers:
            metrics = provider.get_metrics()
            self.logger.info(f"Metrics from {provider.__class__.__name__}: {metrics}")
            await provider.stop()

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up post processor manager-specific components."""
        self.logger.info("Cleaning up post processor manager")
        # TODO: Implement post processor manager cleanup

    @on_configure
    async def _configure(self, payload: BasePayload) -> None:
        """Configure the post processor manager."""
        self.logger.info(f"Configuring post processor manager with payload: {payload}")
        # TODO: Implement post processor manager configuration


def main() -> None:
    """Main entry point for the post processor manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(PostProcessorManager)


if __name__ == "__main__":
    sys.exit(main())
