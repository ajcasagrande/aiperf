# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import time
import uuid
from types import ModuleType

from distributed import Nanny, get_worker
from distributed import Worker as DistributedWorker
from distributed.preloading import Preload
from distributed.scheduler import WorkerState
from rich.console import Console
from rich.logging import RichHandler

from aiperf.common.comms.base import BaseCommunication
from aiperf.common.config import UserConfig, load_service_config
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import Topic
from aiperf.common.factories import CommunicationFactory
from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.models import CreditDropMessage
from aiperf.services.worker.universal import UniversalWorker

logger = logging.getLogger(__name__)


class DaskNanny(Nanny):
    """Dask nanny class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, worker_class=DaskWorker, **kwargs)
        self.logger = logging.getLogger(__name__)
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.addHandler(
            RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_path=True,
                show_level=True,
                console=Console(),
            )
        )


class DaskPreload(Preload):
    """Dask preload class."""

    def __init__(self, dask_object: "DaskWorker"):
        self.dask_object = dask_object
        self.name: str = self.__class__.__name__
        self.argv: list[str] = []
        self.file_dir: str | None = None
        self.module: ModuleType = self.__module__

    async def start(self):
        """Start the preload."""
        await self.dask_object._custom_preload()
        # await super().start()

    async def teardown(self):
        """Teardown the preload."""
        await self.dask_object._custom_teardown()
        # await super().teardown()


class DaskWorker(DistributedWorker, UniversalWorker):
    """Dask worker class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self._inference_client: InferenceClientProtocol | None = None
        self.zmq_comms: BaseCommunication | None = None
        self.service_config: ServiceConfig = load_service_config()
        self.service_id: str = kwargs.get(
            "service_id", f"dask-worker-{uuid.uuid4().hex[:8]}"
        )
        self.user_config: UserConfig = UserConfig()
        UniversalWorker.__init__(
            self,
            service_config=self.service_config,
            user_config=self.user_config,
            service_id=self.service_id,
        )

        self.begin_time: float = time.time()
        self.completed_tasks: int = 0
        self.failed_tasks: int = 0
        self.total_tasks: int = 0

        self._preload = DaskPreload(dask_object=self)
        self.preloads._preloads.append(self._preload)
        self._state: WorkerState

    @property
    def state(self) -> WorkerState:
        return self._state

    @state.setter
    def state(self, value: WorkerState) -> None:
        self._state = value

    async def _custom_preload(self):
        # Initialize communication
        self.zmq_comms = CommunicationFactory.create_instance(
            self.service_config.comm_backend,
            config=self.service_config.comm_config,
        )
        await self.zmq_comms.initialize()

        await self.do_initialize(zmq_comms=self.zmq_comms)
        # """Start the worker. Overrides the base class method to initialize the inference client and ZMQ comms."""
        # self.logger.debug("Starting worker custom preload...")

        # self.inference_client = InferenceClientFactory.create_instance(
        #     InferenceClientType.OPENAI,
        #     client_config=OpenAIClientConfig(
        #         url=f"http://{os.getenv('AIPERF_HOST', '127.0.0.1')}:{os.getenv('AIPERF_PORT', 8080)}",
        #         api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
        #         model=os.getenv(
        #             "AIPERF_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
        #         ),
        #         max_tokens=100,
        #     ),
        # )

        # # Initialize communication
        # self.zmq_comms = CommunicationFactory.create_instance(
        #     self.service_config.comm_backend,
        #     config=self.service_config.comm_config,
        # )
        # await self.zmq_comms.initialize()

        # self.credit_drop_client: PullClientInterface = (
        #     await self.zmq_comms.create_pull_client(
        #         address=self.service_config.comm_config.credit_drop_address,
        #     )
        # )
        # await self.credit_drop_client.initialize()

        # self.credit_return_client: PushClientInterface = (
        #     await self.zmq_comms.create_push_client(
        #         address=self.service_config.comm_config.credit_return_address,
        #     )
        # )
        # await self.credit_return_client.initialize()

        # self.inference_results_client: PushClientInterface = (
        #     await self.zmq_comms.create_push_client(
        #         address=self.service_config.comm_config.inference_push_pull_address,
        #     )
        # )
        # await self.inference_results_client.initialize()

        # await self.credit_drop_client.register_pull_callback(
        #     message_type=MessageType.CREDIT_DROP,
        #     callback=self._credit_drop_handler,
        # )

        # self.logger.debug("Finished worker custom preload")

    async def _custom_teardown(self):
        """Teardown the worker. Overrides the base class method to clean up the inference client and ZMQ comms."""
        await self.do_shutdown()

    # async def _credit_drop_handler(self, message: CreditDropMessage) -> None:
    #     """Handle a credit drop message."""
    #     self.logger.debug("Received credit drop message: %s", message)
    #     asyncio.create_task(self._process_credit_drop(message))

    # async def health_check(self) -> dict:
    #     """Health check."""
    #     return {
    #         "worker_id": self.id,
    #         "status": self.status,
    #         "completed_tasks": self.completed_tasks,
    #         "failed_tasks": self.failed_tasks,
    #         "total_tasks": self.total_tasks,
    #         "cpu_usage": psutil.cpu_percent(interval=0.1),
    #         "memory_usage": psutil.virtual_memory().percent,
    #         "timestamp_ns": time.time_ns(),
    #         "uptime": time.time() - self.begin_time,
    #     }

    # async def _push_result(self, result: RequestRecord) -> None:
    #     """Push the result to the comms."""
    #     asyncio.create_task(
    #         self.inference_results_client.push(
    #             message=InferenceResultsMessage(service_id=self.id, record=result),
    #         )
    #     )

    # async def _push_credit_return(self, amount: int) -> None:
    #     """Push the credit return to the comms."""

    #     asyncio.create_task(
    #         self.credit_return_client.push(
    #             message=CreditReturnMessage(service_id=self.id, amount=amount),
    #         )
    #     )

    # async def _process_credit_drop(self, message: CreditDropMessage) -> None:
    #     """Process a credit drop task (runs on Dask worker)."""
    #     self.total_tasks += 1

    #     result = await self._call_inference_api(conversation_id=message.conversation_id)
    #     if result.valid:
    #         self.completed_tasks += 1
    #     else:
    #         self.failed_tasks += 1

    #     await self._push_result(result)
    #     await self._push_credit_return(message.amount)

    # async def _call_inference_api(
    #     self, conversation_id: str | None = None
    # ) -> RequestRecord:
    #     """Make a call to the inference API."""
    #     try:
    #         logger.debug("Calling inference API")

    #         response = await self.zmq_comms.request(
    #             message=ConversationRequestMessage(
    #                 service_id=self.id, conversation_id=conversation_id
    #             ),
    #         )

    #         # Format payload for the API request
    #         formatted_payload = await self.inference_client.format_payload(
    #             endpoint="v1/chat/completions",
    #             payload={"messages": response.conversation_data},
    #         )

    #         # Send the request to the API
    #         record = await self.inference_client.send_request(
    #             endpoint="v1/chat/completions", payload=formatted_payload
    #         )

    #         if record.valid:
    #             logger.debug(
    #                 "Record: %s milliseconds. %s milliseconds.",
    #                 record.time_to_first_response_ns / NANOS_PER_MILLIS,
    #                 record.time_to_last_response_ns / NANOS_PER_MILLIS,
    #             )
    #         else:
    #             logger.warning("Inference server call returned invalid response")

    #         return record

    #     except Exception as e:
    #         logger.error(
    #             "Error calling inference server: %s %s", e.__class__.__name__, str(e)
    #         )
    #         return RequestRecord(
    #             error=ErrorDetails(
    #                 type=e.__class__.__name__,
    #                 message=str(e),
    #             ),
    #         )


################################################################################
# Task functions
################################################################################
# NOTE: Task functions must be defined outside the DaskWorker class to avoid
#       serialization issues.
################################################################################


async def process_credit_task(credit_message: CreditDropMessage) -> None:
    """Process a credit drop task (runs on Dask worker)."""

    worker = get_worker()
    if isinstance(worker, DaskWorker):
        asyncio.create_task(worker._process_credit_drop(credit_message))
    else:
        logger.error("Worker %s is not a DaskWorker (%s)", worker.id, type(worker))

    return None


async def health_check_task() -> dict | None:
    """Perform health check on worker (runs on Dask worker)."""

    worker = get_worker()
    if isinstance(worker, DaskWorker):
        while not worker.stop_event.is_set():
            message = worker._health_check()
            await worker.pub_client.publish(
                topic=Topic.WORKER_HEALTH,
                message=message,
            )
            await asyncio.sleep(worker.health_check_interval)
        return None
    else:
        logger.error("Worker %s is not a DaskWorker (%s)", worker.id, type(worker))
        return None
