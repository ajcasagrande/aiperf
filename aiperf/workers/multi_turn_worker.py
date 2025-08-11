# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.base_component_service import BaseComponentService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    CommAddress,
    CommandType,
    CreditPhase,
    MessageType,
)
from aiperf.common.factories import (
    InferenceClientFactory,
    RequestConverterFactory,
)
from aiperf.common.hooks import background_task, on_command, on_pull_message, on_stop
from aiperf.common.messages import (
    CommandAcknowledgedResponse,
    CreditDropMessage,
    CreditReturnMessage,
    ProfileCancelCommand,
    WorkerHealthMessage,
)
from aiperf.common.mixins import ProcessHealthMixin, PullClientMixin
from aiperf.common.models import WorkerPhaseTaskStats
from aiperf.common.protocols import (
    PushClientProtocol,
    RequestClientProtocol,
)
from aiperf.workers.multi_turn_credit_processor_mixin import (
    MultiTurnCreditProcessorMixin,
)


class MultiTurnWorker(
    PullClientMixin,
    BaseComponentService,
    ProcessHealthMixin,
    MultiTurnCreditProcessorMixin,
):
    """Enhanced worker that handles multi-turn conversations with conversation state management.

    This worker extends the standard worker to properly manage conversation context
    across multiple turns, making it suitable for chat-based AI models that require
    conversation history to generate appropriate responses.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
        **kwargs,
    ):
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            pull_client_address=CommAddress.CREDIT_DROP,
            pull_client_bind=False,
            **kwargs,
        )

        self.debug(
            lambda: f"MultiTurnWorker process __init__ (pid: {self.process.pid})"
        )

        self.health_check_interval = self.service_config.workers.health_check_interval

        self.task_stats: dict[CreditPhase, WorkerPhaseTaskStats] = {}

        self.credit_return_push_client: PushClientProtocol = (
            self.comms.create_push_client(
                CommAddress.CREDIT_RETURN,
            )
        )
        self.inference_results_push_client: PushClientProtocol = (
            self.comms.create_push_client(
                CommAddress.RAW_INFERENCE_PROXY_FRONTEND,
            )
        )
        self.conversation_request_client: RequestClientProtocol = (
            self.comms.create_request_client(
                CommAddress.DATASET_MANAGER_PROXY_FRONTEND,
            )
        )

        self.model_endpoint = ModelEndpointInfo.from_user_config(self.user_config)

        self.debug(
            lambda: f"Creating inference client for {self.model_endpoint.endpoint.type}, "
            f"class: {InferenceClientFactory.get_class_from_type(self.model_endpoint.endpoint.type).__name__}",
        )
        self.request_converter = RequestConverterFactory.create_instance(
            self.model_endpoint.endpoint.type,
        )
        self.inference_client = InferenceClientFactory.create_instance(
            self.model_endpoint.endpoint.type,
            model_endpoint=self.model_endpoint,
        )

    @on_pull_message(MessageType.CREDIT_DROP)
    async def _credit_drop_callback(self, message: CreditDropMessage) -> None:
        """Handle an incoming credit drop message from the timing manager with multi-turn support.

        Every credit must be returned after processing. This enhanced version
        maintains conversation state across multiple turns.
        """

        # Create a default credit return message in case of an exception
        credit_return_message = CreditReturnMessage(
            service_id=self.service_id,
            phase=message.phase,
        )

        try:
            # NOTE: This must be awaited to ensure that the max concurrency is respected
            credit_return_message = await self._process_credit_drop_internal(message)
        except Exception as e:
            self.exception(f"Error processing multi-turn credit drop: {e}")
        finally:
            # It is fine to execute the push asynchronously here because the worker is technically
            # ready to process the next credit drop.
            self.execute_async(
                self.credit_return_push_client.push(credit_return_message)
            )

    @on_stop
    async def _shutdown_worker(self) -> None:
        self.debug("Shutting down multi-turn worker")

        # Clean up conversation states
        if hasattr(self, "conversation_states"):
            self.conversation_states.clear()
            self.debug(
                f"Cleaned up {len(self.conversation_states)} conversation states"
            )

        if self.inference_client:
            await self.inference_client.close()

    @background_task(
        immediate=False,
        interval=lambda self: self.health_check_interval,
    )
    async def _health_check_task(self) -> None:
        """Task to report the health of the worker to the worker manager."""
        await self.publish(self.create_health_message())

    def create_health_message(self) -> WorkerHealthMessage:
        """Create a health message with additional multi-turn metrics."""
        health_msg = WorkerHealthMessage(
            service_id=self.service_id,
            process=self.get_process_health(),
            task_stats=self.task_stats,
        )

        # Add conversation state metrics to debug info
        if hasattr(self, "conversation_states"):
            num_active_conversations = len(self.conversation_states)
            self.debug(f"Health check: {num_active_conversations} active conversations")

        return health_msg

    @on_command(CommandType.PROFILE_CANCEL)
    async def _handle_profile_cancel_command(
        self, message: ProfileCancelCommand
    ) -> None:
        self.debug(lambda: f"Received profile cancel command: {message}")
        await self.publish(
            CommandAcknowledgedResponse.from_command_message(message, self.service_id)
        )
        await self.stop()


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(MultiTurnWorker)
