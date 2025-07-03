# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import time

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.messages import ConversationResponseMessage, ErrorMessage
from aiperf.common.record_models import ErrorDetails, RequestRecord
from aiperf.common.types import ModelEndpointInfo
from aiperf.services.worker.protocols import WorkerCommunicationsProtocol


class InferenceWorkerMixin:
    """Mixin that provides the functionality of calling an Inference Server."""

    def __init__(
        self,
        worker_comms: WorkerCommunicationsProtocol,
        inference_client: InferenceClientProtocol,
        model_endpoint: ModelEndpointInfo,
    ) -> None:
        super().__init__()
        self.worker_comms = worker_comms
        self.inference_client = inference_client
        self.model_endpoint = model_endpoint
        self.endpoint_info = model_endpoint.endpoint
        self.logger = logging.getLogger(__class__.__name__)

    async def call_inference_api(
        self, credit_drop_ns: int | None = None, conversation_id: str | None = None
    ) -> RequestRecord:
        """Make a single call to the inference API. Will return an error record if the call fails."""
        try:
            self.logger.debug("Calling inference API")

            if not self.inference_client:
                self.logger.warning(
                    "Inference server client not initialized, skipping API call"
                )
                return RequestRecord(
                    error=ErrorDetails(
                        type="Inference server client not initialized",
                        message="Inference server client not initialized",
                    ),
                )

            # retrieve the prompt from the dataset
            response: ConversationResponseMessage = (
                await self.worker_comms.request_conversation_data(
                    conversation_id=conversation_id
                )
            )
            self.logger.debug("Received response message: %s", response)

            if isinstance(response, ErrorMessage):
                return RequestRecord(
                    error=response.error,
                )

            # Format payload for the API request
            formatted_payload = await self.inference_client.format_payload(
                model_endpoint=self.model_endpoint,
                payload=response.conversation.turns[0],  # todo: handle multiple turns
                # payload={
                #     "messages": [
                #         {
                #             "role": "user",
                #             "content": "IO Sir you say well and well you do conceive And since you do profess to be a suitor You must as we do gratify this gentleman To whom we all rest generally beholding TRANIO Sir I shall not be slack in sign whereof Please ye we may contrive this afternoon And quaff carouses to our mistress health And do as adversaries do in law Strive mightily but eat and drink as friends GRUMIO BIONDELLO O excellent motion Fellows lets be gone HORT",
                #         },
                #     ],
                # },
            )

            delayed = False
            if credit_drop_ns and credit_drop_ns > time.time_ns():
                await asyncio.sleep(
                    (credit_drop_ns - time.time_ns()) / NANOS_PER_SECOND
                )
            elif credit_drop_ns and credit_drop_ns < time.time_ns():
                delayed = True

            # Send the request to the Inference Server API and wait for the response
            return await self.inference_client.send_request(
                model_endpoint=self.model_endpoint,
                payload=formatted_payload,
                delayed=delayed,
            )

        except Exception as e:
            self.logger.error(
                "Error calling inference server: %s %s", e.__class__.__name__, str(e)
            )
            return RequestRecord(
                error=ErrorDetails.from_exception(e),
            )
