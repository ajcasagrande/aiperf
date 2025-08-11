# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time
from typing import Protocol, runtime_checkable

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase, EndpointType
from aiperf.common.exceptions import NotInitializedError
from aiperf.common.messages import (
    ConversationRequestMessage,
    ConversationResponseMessage,
    CreditDropMessage,
    CreditReturnMessage,
    ErrorMessage,
    InferenceResultsMessage,
)
from aiperf.common.models import (
    ErrorDetails,
    RequestRecord,
    Turn,
    WorkerPhaseTaskStats,
)
from aiperf.common.protocols import (
    AIPerfLoggerProtocol,
    InferenceClientProtocol,
    PushClientProtocol,
    RequestClientProtocol,
    RequestConverterProtocol,
)


@runtime_checkable
class ConversationCreditProcessorMixinRequirements(AIPerfLoggerProtocol, Protocol):
    """Protocol requirements for ConversationCreditProcessorMixin."""

    service_id: str
    inference_client: InferenceClientProtocol
    conversation_request_client: RequestClientProtocol
    inference_results_push_client: PushClientProtocol
    request_converter: RequestConverterProtocol
    model_endpoint: ModelEndpointInfo
    task_stats: dict[CreditPhase, WorkerPhaseTaskStats]


class ConversationCreditProcessorMixin(ConversationCreditProcessorMixinRequirements):
    """Credit processor mixin that handles complete conversations (all turns) per credit."""

    def __init__(self, **kwargs):
        if not isinstance(self, ConversationCreditProcessorMixinRequirements):
            raise ValueError(
                "ConversationCreditProcessorMixin must be used with ConversationCreditProcessorMixinRequirements"
            )
        super().__init__(**kwargs)

    async def _process_credit_drop_internal(
        self, message: CreditDropMessage
    ) -> CreditReturnMessage:
        """Process a credit drop message for a complete conversation.

        - Every credit must be returned after processing
        - All results or errors should be converted to RequestRecords and pushed to the inference results client.
        - One credit processes ALL turns in a conversation
        """
        self.trace(lambda: f"Processing conversation credit drop: {message}")
        drop_perf_ns = time.perf_counter_ns()

        if message.phase not in self.task_stats:
            self.task_stats[message.phase] = WorkerPhaseTaskStats()
        self.task_stats[message.phase].total += 1

        records: list[RequestRecord] = []
        try:
            records = await self._execute_complete_conversation_internal(message)
            self.task_stats[message.phase].succeeded += 1

        except Exception as e:
            self.exception(f"Error processing conversation credit drop: {e}")
            self.task_stats[message.phase].failed += 1

            # Create error record for the conversation
            error_record = RequestRecord(
                conversation_id=message.conversation_id,
                turn_index=0,
                timestamp_ns=time.time_ns(),
                start_perf_ns=drop_perf_ns,
                end_perf_ns=time.perf_counter_ns(),
                error=ErrorDetails.from_exception(e),
            )
            records = [error_record]

        finally:
            # Push ALL results from the conversation
            for record in records:
                await self.inference_results_push_client.push(
                    InferenceResultsMessage(
                        service_id=self.service_id,
                        record=record,
                    )
                )

            return_message = CreditReturnMessage(
                service_id=self.service_id,
                phase=message.phase,
            )
            return return_message

    async def _execute_complete_conversation_internal(
        self, message: CreditDropMessage
    ) -> list[RequestRecord]:
        """Execute a complete conversation (all turns) and return all RequestRecords."""

        if not self.inference_client:
            raise NotInitializedError("Inference server client not initialized.")

        # Get the complete conversation from the dataset
        conversation_response: ConversationResponseMessage = (
            await self.conversation_request_client.request(
                ConversationRequestMessage(
                    service_id=self.service_id,
                    conversation_id=message.conversation_id,
                    credit_phase=message.phase,
                )
            )
        )
        self.trace(lambda: f"Received conversation response: {conversation_response}")

        if isinstance(conversation_response, ErrorMessage):
            error_record = RequestRecord(
                model_name=self.model_endpoint.primary_model_name,
                conversation_id=message.conversation_id,
                turn_index=0,
                timestamp_ns=time.time_ns(),
                start_perf_ns=time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns(),
                error=conversation_response.error,
            )
            return [error_record]

        conversation = conversation_response.conversation
        self.debug(
            f"Processing conversation {conversation.session_id} with {len(conversation.turns)} turns"
        )

        # Process all turns in the conversation
        records = []
        conversation_history = []  # For chat completion APIs

        for turn_index, turn in enumerate(conversation.turns):
            self.trace(
                f"Processing turn {turn_index} of conversation {conversation.session_id}"
            )

            try:
                # Handle timing for the turn
                await self._handle_turn_timing(turn, message.credit_drop_ns)

                # Build context-aware turn for chat completion APIs
                context_turn = await self._build_turn_with_context(
                    turn, conversation_history, turn_index
                )

                # Make the API call
                record = await self._call_inference_api_internal(
                    message, context_turn, turn_index
                )

                # Set conversation metadata
                record.model_name = self.model_endpoint.primary_model_name
                record.conversation_id = conversation.session_id
                record.turn_index = turn_index

                records.append(record)

                # Update conversation history for future turns
                await self._update_conversation_history(
                    conversation_history, turn, record
                )

            except Exception as e:
                self.exception(f"Error processing turn {turn_index}: {e}")

                # Create error record for this turn
                error_record = RequestRecord(
                    model_name=self.model_endpoint.primary_model_name,
                    conversation_id=conversation.session_id,
                    turn_index=turn_index,
                    timestamp_ns=time.time_ns(),
                    start_perf_ns=time.perf_counter_ns(),
                    end_perf_ns=time.perf_counter_ns(),
                    error=ErrorDetails.from_exception(e),
                )
                records.append(error_record)

                # Continue with remaining turns despite error
                continue

        self.debug(
            f"Completed conversation {conversation.session_id}: {len(records)} records generated"
        )
        return records

    async def _handle_turn_timing(self, turn: Turn, credit_drop_ns: int | None) -> None:
        """Handle timing delays for individual turns."""

        # Handle turn-specific delays
        if turn.delay and turn.delay > 0:
            self.trace(f"Waiting for turn delay: {turn.delay}ms")
            await asyncio.sleep(turn.delay / 1000.0)

        # Handle credit drop timing (only for first turn)
        if credit_drop_ns:
            now_ns = time.time_ns()
            if credit_drop_ns > now_ns:
                delay_seconds = (credit_drop_ns - now_ns) / NANOS_PER_SECOND
                self.trace(f"Waiting for credit drop time: {delay_seconds:.2f}s")
                await asyncio.sleep(delay_seconds)

    async def _build_turn_with_context(
        self, turn: Turn, conversation_history: list, turn_index: int
    ) -> Turn:
        """Build a turn with conversation context for chat completion APIs."""

        if not self._is_chat_completion_api():
            return turn  # No context needed for non-chat APIs

        # Extract current turn content
        current_content = ""
        if turn.texts:
            current_content = " ".join(
                content for text in turn.texts for content in text.contents if content
            )

        # Add current user message to history
        user_role = turn.role or "user"
        conversation_history.append({"role": user_role, "content": current_content})

        # Create enhanced turn with conversation history
        import json

        from aiperf.common.models import Text

        # Encode full conversation history for the request converter
        message_history_json = json.dumps(conversation_history.copy())

        context_turn = Turn(
            texts=[Text(name="conversation_history", contents=[message_history_json])],
            role=turn.role,
            model=turn.model,
            max_tokens=turn.max_tokens,
            timestamp=turn.timestamp,
            delay=turn.delay,
            images=turn.images,  # Preserve multi-modal content
            audios=turn.audios,
        )

        return context_turn

    async def _update_conversation_history(
        self, conversation_history: list, turn: Turn, record: RequestRecord
    ) -> None:
        """Update conversation history with the model's response."""

        if not self._is_chat_completion_api():
            return  # No history tracking needed

        # Extract response content from the record
        response_content = ""
        if record.responses:
            for response in record.responses:
                if hasattr(response, "content") and response.content:
                    response_content += str(response.content)
                elif hasattr(response, "text") and response.text:
                    response_content += str(response.text)
                elif isinstance(response, dict) and "content" in response:
                    response_content += str(response["content"])

        # Add assistant response to history
        if response_content:
            conversation_history.append(
                {"role": "assistant", "content": response_content}
            )
            self.trace(
                f"Added assistant response to conversation history: {len(response_content)} chars"
            )

    def _is_chat_completion_api(self) -> bool:
        """Check if the current endpoint is a chat completion API that needs message history."""
        return self.model_endpoint.endpoint.type in [
            EndpointType.OPENAI_CHAT_COMPLETIONS,
            # Add other chat completion endpoint types as needed
        ]

    async def _call_inference_api_internal(
        self,
        message: CreditDropMessage,
        turn: Turn,
        turn_index: int,
    ) -> RequestRecord:
        """Make a single inference API call for a turn."""

        self.trace(lambda: f"Calling inference API for turn {turn_index}: {turn}")
        formatted_payload = None
        pre_send_perf_ns = None
        timestamp_ns = None

        try:
            # Format payload for the API request
            formatted_payload = await self.request_converter.format_payload(
                model_endpoint=self.model_endpoint,
                turn=turn,
            )

            pre_send_perf_ns = time.perf_counter_ns()
            timestamp_ns = time.time_ns()

            # Send the request to the Inference Server API
            result: RequestRecord = await self.inference_client.send_request(
                model_endpoint=self.model_endpoint,
                payload=formatted_payload,
            )

            self.debug(
                lambda: f"Turn {turn_index} latency: {result.start_perf_ns - pre_send_perf_ns} ns"
            )

            return result

        except Exception as e:
            self.exception(
                f"Error calling inference server API for turn {turn_index} at {self.model_endpoint.url}: {e}"
            )
            return RequestRecord(
                request=formatted_payload,
                timestamp_ns=timestamp_ns or time.time_ns(),
                start_perf_ns=pre_send_perf_ns or time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns(),
                error=ErrorDetails.from_exception(e),
            )
