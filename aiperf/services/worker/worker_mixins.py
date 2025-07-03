# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import os
import time
from typing import Protocol

import psutil

from aiperf.clients.openai.common import OpenAIClientConfig
from aiperf.common.comms.base import (
    BaseCommunication,
    ClientAddressType,
)
from aiperf.common.config import EndPointConfig, ServiceConfig, UserConfig
from aiperf.common.constants import BYTES_PER_MIB
from aiperf.common.enums import InferenceClientType, MessageType
from aiperf.common.factories import CommunicationFactory, InferenceClientFactory
from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.messages import (
    CPUTimes,
    CreditDropMessage,
    CreditReturnMessage,
    CtxSwitches,
    InferenceResultsMessage,
    RequestRecord,
    WorkerHealthMessage,
)


class InferenceClientUserProtocol(Protocol):
    """Protocol for a user of an inference client."""

    async def call_inference_api(
        self,
        credit_drop_ns: int | None = None,
    ) -> RequestRecord:
        """Call the inference API and return a request record."""
        ...


class UniversalWorker:
    """Worker is primarily responsible for converting the data into the appropriate
    format for the interface being used by the server. Also responsible for managing
    the conversation between turns.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str,
        **kwargs,
    ) -> None:
        self.service_config = service_config
        self.user_config = user_config
        self.service_id = service_id
        self.kwargs = kwargs
        self.logger = logging.getLogger(__name__)

        # Inference client will be initialized in _initialize
        self.inference_client: InferenceClientProtocol | None = None

        self.endpoint_config = EndPointConfig(
            type=os.getenv("AIPERF_ENDPOINT", "v1/chat/completions"),
            streaming=os.getenv("AIPERF_STREAMING", "true").lower() == "true",
        )

        self.health_check_interval = int(
            os.getenv("AIPERF_WORKER_HEALTH_CHECK_INTERVAL", 1)
        )
        self.begin_time = time.time()
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_tasks = 0

        # Initialize process-specific CPU monitoring
        self.process = psutil.Process()
        self.process.cpu_percent()  # throw away the first result (will be 0)

        self.stop_event: asyncio.Event = asyncio.Event()
        self.health_task: asyncio.Task | None = None

        self.zmq_comms: BaseCommunication = CommunicationFactory.create_instance(
            self.service_config.comm_backend,
            config=self.service_config.comm_config,
        )

        self.credit_drop_client = self.zmq_comms.create_pull_client(
            ClientAddressType.CREDIT_DROP_PUSH_PULL,
        )
        self.credit_return_client = self.zmq_comms.create_push_client(
            ClientAddressType.CREDIT_RETURN_PUSH_PULL,
        )
        self.inference_results_client = self.zmq_comms.create_push_client(
            ClientAddressType.PUSH_PULL_FRONTEND,
        )
        self.conversation_data_client = self.zmq_comms.create_req_client(
            ClientAddressType.DEALER_ROUTER_FRONTEND,
        )
        self.pub_client = self.zmq_comms.create_pub_client(
            ClientAddressType.SERVICE_PUB_SUB_FRONTEND,
        )

    async def do_initialize(self) -> None:
        """Initialize worker-specific components."""
        self.logger.debug("Initializing worker")
        await self.zmq_comms.initialize()

        # TODO: better way to get the API key
        api_key = os.environ.get("OPENAI_API_KEY", None)

        openai_client_config = OpenAIClientConfig(
            api_key=api_key,
            base_url=f"http://{os.getenv('AIPERF_HOST', '127.0.0.1')}:{os.getenv('AIPERF_PORT', 8080)}",  # Default OpenAI inference server endpoint
            model=os.getenv(
                "AIPERF_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
            ),  # Default model
        )

        self.inference_client = InferenceClientFactory.create_instance(
            InferenceClientType.OPENAI, client_config=openai_client_config
        )

        await self.credit_drop_client.register_pull_callback(
            MessageType.CREDIT_DROP, self._credit_drop_handler
        )

        self.health_task = asyncio.create_task(self._health_check_task())

        self.logger.debug("Worker initialized")

    async def _credit_drop_handler(self, message: CreditDropMessage) -> None:
        """Handle a credit drop message."""
        self.logger.debug("Received credit drop message: %s", message)
        await self._process_credit_drop(message)

    async def _run_credit_task(self, credit_drop_ns: int | None = None) -> None:
        """Run a credit task for a single credit."""
        self.total_tasks += 1
        # Call the inference API
        record = await self._call_inference_api(credit_drop_ns)
        msg = InferenceResultsMessage(
            service_id=self.service_id,
            record=record,
        )
        if record.valid:
            self.completed_tasks += 1
        else:
            self.failed_tasks += 1

        # Push the record to the inference results message_type
        try:
            await self.inference_results_client.push(
                message=msg,
            )
        except Exception as e:
            # If we fail to push the record, log the error and continue
            self.logger.error(
                "Error pushing request record: %s: %s",
                e.__class__.__name__,
                e,
            )

    async def _process_credit_drop(self, message: CreditDropMessage) -> None:
        """Process a credit drop response.

        Args:
            message: The message received from the credit drop
        """
        self.logger.debug("Processing credit drop: %s", message)

        credit_amount = 0
        tasks: list[asyncio.Task] = []
        try:
            credit_amount = message.amount
            self.logger.debug(
                "Received %s credit(s) for %s", credit_amount, message.credit_drop_ns
            )

            # Make a call to the inference server for each credit concurrently
            for _ in range(credit_amount):
                task = asyncio.create_task(
                    self._run_credit_task(credit_drop_ns=message.credit_drop_ns)
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

        except Exception as e:
            self.logger.error("Error processing credit drop: %s", e)

        finally:
            # Always return the credits
            self.logger.debug("Returning credits, %s", credit_amount)
            await self.credit_return_client.push(
                message=CreditReturnMessage(
                    service_id=self.service_id,
                    amount=credit_amount,
                ),
            )

    async def do_shutdown(self) -> None:
        """Shutdown the worker."""
        self.logger.debug("Shutting down worker")
        self.stop_event.set()
        if self.zmq_comms:
            await self.zmq_comms.shutdown()
        if self.inference_client:
            await self.inference_client.close()
        if self.health_task:
            self.health_task.cancel()
            # await asyncio.wait_for(self.health_task, timeout=TASK_CANCEL_TIMEOUT_SHORT)

    async def _health_check_task(self) -> None:
        """Task to report the health of the worker to the worker manager."""
        while not self.stop_event.is_set():
            try:
                health_message = self._health_check()
                await self.pub_client.publish(health_message)
            except Exception as e:
                self.logger.error("Error reporting health: %s", e)
            await asyncio.sleep(self.health_check_interval)

    def _health_check(self) -> WorkerHealthMessage:
        """Report the health of the worker to the worker manager."""

        # self.logger.info(
        #     [
        #         f"{conn.laddr.ip}:{conn.laddr.port} -> {conn.raddr.ip}:{conn.raddr.port} {conn.status}"
        #         for conn in self.process.net_connections("tcp4")
        #     ]
        # )
        # self.logger.info(
        #     self.process.num_ctx_switches(),
        #     self.process.num_threads(),
        # )

        # Get process-specific CPU and memory usage
        message = WorkerHealthMessage(
            service_id=self.service_id,
            pid=self.process.pid,
            cpu_usage=self.process.cpu_percent(),
            memory_usage=self.process.memory_info().rss / BYTES_PER_MIB,
            uptime=time.time() - self.begin_time,
            completed_tasks=self.completed_tasks,
            failed_tasks=self.failed_tasks,
            total_tasks=self.total_tasks,
            timestamp_ns=time.time_ns(),
            net_connections=len(self.process.net_connections("tcp4")),
            io_counters=self.process.io_counters(),
            cpu_times=CPUTimes(
                *self.process.cpu_times()[:2], self.process.cpu_times()[4]
            ),
            num_ctx_switches=CtxSwitches(*self.process.num_ctx_switches()),
            num_threads=self.process.num_threads(),
        )
        return message
