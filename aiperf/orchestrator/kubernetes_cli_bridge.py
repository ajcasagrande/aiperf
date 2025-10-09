# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Bridge between local CLI orchestrator and Kubernetes cluster."""

import asyncio
from typing import TYPE_CHECKING

from aiperf.common.base_service import BaseService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import MessageType
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.hooks import on_init, on_message, on_start, on_stop
from aiperf.common.logging import get_global_log_queue
from aiperf.common.messages import (
    ProcessRecordsResultMessage,
    ProcessTelemetryResultMessage,
    TelemetryStatusMessage,
)
from aiperf.common.models import ProcessRecordsResult, TelemetryResults
from aiperf.common.models.error_models import ExitErrorInfo
from aiperf.common.protocols import AIPerfUIProtocol

if TYPE_CHECKING:
    from aiperf.kubernetes.orchestrator import KubernetesOrchestrator


class KubernetesCliBridge(BaseService):
    """Bridge between local CLI and Kubernetes cluster.

    This component runs LOCALLY and provides:
    - UI management (local display)
    - Result aggregation (from cluster pods)
    - Status monitoring (via K8s API)
    - Artifact retrieval coordination

    The SystemController runs IN THE CLUSTER and manages services there.
    """

    def __init__(
        self,
        user_config: UserConfig,
        service_config: ServiceConfig,
        k8s_orchestrator: "KubernetesOrchestrator",
        service_id: str | None = None,
    ):
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id or "k8s_cli_bridge",
        )

        self.k8s_orchestrator = k8s_orchestrator

        # Create UI locally
        self.ui: AIPerfUIProtocol = AIPerfUIFactory.create_instance(
            self.service_config.ui_type,
            service_config=self.service_config,
            user_config=self.user_config,
            log_queue=get_global_log_queue(),
            controller=None,  # No local controller reference
        )
        self.attach_child_lifecycle(self.ui)

        # Results tracking
        self._profile_results: ProcessRecordsResult | None = None
        self._telemetry_results: TelemetryResults | None = None
        self._exit_errors: list[ExitErrorInfo] = []
        self._was_cancelled = False

    @on_init
    async def _initialize_bridge(self) -> None:
        """Initialize the CLI bridge."""
        self.debug("Initializing Kubernetes CLI bridge")

    @on_start
    async def _start_bridge(self) -> None:
        """Start the CLI bridge and UI."""
        self.info("CLI orchestrator monitoring cluster...")

    # Note: In K8s mode, we poll the cluster for status rather than receiving ZMQ messages
    # This keeps the CLI completely separate from the cluster

    @on_stop
    async def _stop_bridge(self) -> None:
        """Stop the bridge and display results."""
        # Wait for UI to stop
        await self.ui.stop()
        await self.ui.wait_for_tasks()
        await asyncio.sleep(0.1)

        # Results display will be handled after artifact retrieval

    def set_profile_results(self, results: ProcessRecordsResult) -> None:
        """Set profile results after retrieval from cluster."""
        self._profile_results = results

    def set_telemetry_results(self, results: TelemetryResults | None) -> None:
        """Set telemetry results after retrieval from cluster."""
        self._telemetry_results = results

    def set_exit_errors(self, errors: list[ExitErrorInfo]) -> None:
        """Set exit errors from cluster."""
        self._exit_errors = errors

    def get_exit_code(self) -> int:
        """Get exit code based on errors."""
        return 1 if self._exit_errors else 0
