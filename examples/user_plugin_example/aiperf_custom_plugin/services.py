# SPDX-FileCopyrightText: Copyright (c) 2025 User Plugin Example
# SPDX-License-Identifier: Apache-2.0
"""Custom service implementations for AIPerf."""

from typing import Any
from aiperf.common.base_service import BaseService
from aiperf.common.protocol_validation import validate_implementation
from aiperf.common.protocols import ServiceProtocol


@validate_implementation(ServiceProtocol)
class CustomWorkerService(BaseService):
    """Custom worker service with specialized processing."""

    service_type = "custom_worker"

    def __init__(self, service_config, user_config, worker_count: int = 4, **kwargs):
        super().__init__(service_config, user_config, **kwargs)
        self.worker_count = worker_count
        self.processed_items = 0

    async def start(self) -> None:
        """Start the custom worker service."""
        self.info(f"Starting custom worker service with {self.worker_count} workers")
        await super().start()

    async def stop(self) -> None:
        """Stop the custom worker service."""
        self.info(f"Stopping custom worker service. Processed {self.processed_items} items")
        await super().stop()

    async def process_request(self, request: Any) -> Any:
        """Process a request with custom logic."""
        self.processed_items += 1
        # Custom processing logic here
        return f"Custom processed: {request}"


@validate_implementation(ServiceProtocol)
class AdvancedProcessorService(BaseService):
    """Advanced processor with machine learning capabilities."""

    service_type = "advanced_processor"

    def __init__(self, service_config, user_config, model_path: str = None, **kwargs):
        super().__init__(service_config, user_config, **kwargs)
        self.model_path = model_path
        self.model = None

    async def start(self) -> None:
        """Start and load the ML model."""
        self.info("Loading ML model for advanced processing")
        # Load your ML model here
        # self.model = load_model(self.model_path)
        await super().start()

    async def process_batch(self, batch: list[Any]) -> list[Any]:
        """Process a batch of items using ML model."""
        if not self.model:
            return [f"No model loaded: {item}" for item in batch]

        # Process batch with ML model
        results = []
        for item in batch:
            # result = self.model.predict(item)
            result = f"ML processed: {item}"
            results.append(result)

        return results
