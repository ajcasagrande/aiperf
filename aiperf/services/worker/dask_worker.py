#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import os
from typing import Any

from distributed import get_worker

from aiperf.clients.openai.common import OpenAIClientConfig
from aiperf.common.comms.base import BaseCommunication
from aiperf.common.constants import NANOS_PER_MILLIS
from aiperf.common.enums import CommunicationBackend, InferenceClientType, Topic
from aiperf.common.factories import CommunicationFactory, InferenceClientFactory
from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.messages import (
    ConversationRequestMessage,
    CreditDropMessage,
    CreditReturnMessage,
    InferenceResultsMessage,
)
from aiperf.common.record_models import ErrorDetails, RequestRecord

logger = logging.getLogger(__name__)

_INFERENCE_CLIENT: InferenceClientProtocol | None = None
_COMMS: BaseCommunication | None = None


# Task functions must be defined outside the class to avoid serialization issues
async def process_credit_task(credit_message: CreditDropMessage) -> None:
    """Process a credit drop task (runs on Dask worker)."""

    asyncio.create_task(_process_credit_task(credit_message))
    return None


def health_check_task() -> dict:
    """Perform health check on worker (runs on Dask worker)."""
    import time

    import psutil
    from dask.distributed import get_worker

    worker = get_worker()

    return {
        "worker_id": worker.id,
        "cpu_usage": psutil.cpu_percent(interval=0.1),  # Reduced interval
        "memory_usage": psutil.virtual_memory().percent,
        "timestamp": time.time_ns(),
        "status": "healthy",
    }


def compute_task(data: Any) -> dict:
    """Generic compute task (runs on Dask worker)."""
    from dask.distributed import get_worker

    worker = get_worker()

    # Placeholder for actual computation
    result = {"worker_id": worker.id, "result": "computed", "input": str(data)}

    return result


def _get_inference_client() -> InferenceClientProtocol:
    """Get the inference client."""
    global _INFERENCE_CLIENT
    if _INFERENCE_CLIENT is None:
        _INFERENCE_CLIENT = InferenceClientFactory.create_instance(
            InferenceClientType.OPENAI,
            config=OpenAIClientConfig(
                url="http://127.0.0.1:8080",
                api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
                model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                max_tokens=100,
            ),
        )
    return _INFERENCE_CLIENT


async def _get_comms() -> BaseCommunication:
    """Get the comms."""
    global _COMMS
    if _COMMS is None:
        _COMMS = CommunicationFactory.create_instance(CommunicationBackend.ZMQ_TCP)
        await _COMMS.initialize()
    return _COMMS


async def _push_result(worker_id: str, result: RequestRecord) -> None:
    """Push the result to the comms."""
    comms = await _get_comms()
    asyncio.create_task(
        comms.push(
            topic=Topic.INFERENCE_RESULTS,
            message=InferenceResultsMessage(service_id=worker_id, record=result),
        )
    )


async def _push_credit_return(worker_id: str, amount: int) -> None:
    """Push the credit return to the comms."""

    comms = await _get_comms()
    asyncio.create_task(
        comms.push(
            topic=Topic.CREDIT_RETURN,
            message=CreditReturnMessage(service_id=worker_id, amount=amount),
        )
    )


async def _process_credit_task(credit_message: CreditDropMessage) -> None:
    """Process a credit drop task (runs on Dask worker)."""
    result = await _call_backend_api()

    _ = await _get_comms()
    worker = get_worker()
    worker_id = worker.id

    asyncio.create_task(_push_result(worker_id, result))

    asyncio.create_task(_push_credit_return(worker_id, credit_message.amount))


async def _call_backend_api() -> RequestRecord:
    """Make a call to the backend API."""
    try:
        logger.debug("Calling backend API")

        if not _get_inference_client():
            logger.warning("Inference server client not initialized, skipping API call")
            return RequestRecord(
                error=ErrorDetails(
                    type="Inference server client not initialized",
                    message="Inference server client not initialized",
                )
            )

        # retrieve the prompt from the dataset
        worker = get_worker()
        worker_id = worker.id

        comms = await _get_comms()
        response = await comms.request(
            topic=Topic.CONVERSATION_DATA,
            message=ConversationRequestMessage(
                service_id=worker_id, conversation_id="123"
            ),
        )
        # messages = OpenAIChatCompletionRequest(
        #     model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
        #     messages=[
        #         {
        #             "role": "user",
        #             "content": "softly smiteth That from the cold stone sparks of fire do fly Whereat a waxen torch forthwith he lighteth Which must be lodestar to his lustful eye And to the flame thus speaks advisedly As from this cold flint I enforced this fire So Lucrece must I force to my desire Here pale with fear he doth premeditate The dangers of his loathsome enterprise And in his inward mind he doth debate What following sorrow may on this arise Then looking scorn",
        #         }
        #     ],
        #     max_tokens=100,
        # )

        # response.conversation_data

        # Sample messages for the API call
        # messages = [
        #     {"role": "system", "content": "You are a helpful assistant."},
        #     {
        #         "role": "user",
        #         "content": "Tell me about NVIDIA AI performance testing.",
        #     },
        # ]

        # Format payload for the API request
        formatted_payload = await _get_inference_client().format_payload(
            endpoint="v1/chat/completions",
            payload={"messages": response.conversation_data},
        )

        # Send the request to the API
        record = await _get_inference_client().send_request(
            endpoint="v1/chat/completions", payload=formatted_payload
        )

        if record.valid:
            logger.debug(
                "Record: %s milliseconds. %s milliseconds.",
                record.time_to_first_response_ns / NANOS_PER_MILLIS,
                record.time_to_last_response_ns / NANOS_PER_MILLIS,
            )
        else:
            logger.warning("Inference server call returned invalid response")

        return record

    except Exception as e:
        logger.error(
            "Error calling inference server: %s %s", e.__class__.__name__, str(e)
        )
        return RequestRecord(
            error=ErrorDetails(
                type=e.__class__.__name__,
                message=str(e),
            ),
        )
