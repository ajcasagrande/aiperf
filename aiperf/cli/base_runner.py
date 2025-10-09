# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Base classes and protocols for AIPerf deployment runners."""

from abc import ABC, abstractmethod

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.models import ProcessRecordsResult


class BaseDeploymentRunner(ABC):
    """Base class for deployment runners.

    Deployment runners are responsible for managing the execution of AIPerf
    in different environments (local multiprocess, Kubernetes, etc).

    They coordinate:
    - System Controller lifecycle
    - UI lifecycle (independent of controller)
    - Result collection and display
    - Graceful shutdown
    """

    def __init__(
        self,
        user_config: UserConfig,
        service_config: ServiceConfig,
    ):
        self.user_config = user_config
        self.service_config = service_config
        self.logger = AIPerfLogger(__name__)
        self._profile_results: ProcessRecordsResult | None = None

    @abstractmethod
    async def run(self) -> ProcessRecordsResult | None:
        """Run the deployment and return results.

        This method should:
        1. Deploy/start the System Controller
        2. Start the UI (if configured)
        3. Wait for completion
        4. Collect results
        5. Clean up resources

        Returns:
            Profile results if successful, None otherwise
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the deployment gracefully."""
        pass
