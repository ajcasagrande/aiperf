# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time
from typing import Any, Protocol, runtime_checkable

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase, EndpointType
from aiperf.common.exceptions import NotInitializedError
from aiperf.common.messages import (
    ConversationRequestMessage,
    ConversationTurnRequestMessage,
    ConversationTurnResponseMessage,
    CreditDropMessage,
    CreditReturnMessage,
    ErrorMessage,
    InferenceResultsMessage,
)
from aiperf.common.models import (
    Conversation,
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


class ConversationState:
    """Maintains conversation state for multi-turn chat sessions."""

    def __init__(self, conversation_id: str, session_id: str):
        self.conversation_id = conversation_id
        self.session_id = session_id
        self.current_turn_index = 0
        self.message_history: list[dict[str, Any]] = []
        self.conversation_data: Conversation | None = None
        self.last_response: str | None = None
        self.created_at_ns = time.time_ns()
        self.last_updated_ns = time.time_ns()

    def update_turn_index(self, turn_index: int) -> None:
        """Update the current turn index and timestamp."""
        self.current_turn_index = turn_index
        self.last_updated_ns = time.time_ns()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.message_history.append({"role": role, "content": content})
        self.last_updated_ns = time.time_ns()

    def get_message_history(self) -> list[dict[str, Any]]:
        """Get the current message history for API calls."""
        return self.message_history.copy()


@runtime_checkable
class MultiTurnCreditProcessorMixinRequirements(AIPerfLoggerProtocol, Protocol):
    """Protocol requirements for MultiTurnCreditProcessorMixin."""

    service_id: str
    inference_client: InferenceClientProtocol
    conversation_request_client: RequestClientProtocol
    inference_results_push_client: PushClientProtocol
    request_converter: RequestConverterProtocol
    model_endpoint: ModelEndpointInfo
    task_stats: dict[CreditPhase, WorkerPhaseTaskStats]


class MultiTurnCreditProcessorMixin(MultiTurnCreditProcessorMixinRequirements):
    """Enhanced credit processor mixin that supports multi-turn conversations."""

    def __init__(self, **kwargs):
        if not isinstance(self, MultiTurnCreditProcessorMixinRequirements):
            raise ValueError(
                "MultiTurnCreditProcessorMixin must be used with MultiTurnCreditProcessorMixinRequirements"
            )
        super().__init__(**kwargs)

        # Conversation state management
        self.conversation_states: dict[str, ConversationState] = {}
        self.state_cleanup_threshold = 3600  # 1 hour in seconds
        self.max_conversation_states = 10000  # Prevent memory leaks

    async def _process_credit_drop_internal(
        self, message: CreditDropMessage
    ) -> CreditReturnMessage:
        """Process a credit drop message with multi-turn support.

        - Every credit must be returned after processing
        - All results or errors should be converted to a RequestRecord and pushed to the inference results client.
        """
        self.trace(lambda: f"Processing multi-turn credit drop: {message}")
        drop_perf_ns = time.perf_counter_ns()

        if message.phase not in self.task_stats:
            self.task_stats[message.phase] = WorkerPhaseTaskStats()
        self.task_stats[message.phase].total += 1

        record: RequestRecord = RequestRecord()
        try:
            record = await self._execute_multi_turn_credit_internal(message)
            self.task_stats[message.phase].succeeded += 1

        except Exception as e:
            self.exception(f"Error processing multi-turn credit drop: {e}")
            self.task_stats[message.phase].failed += 1
            record = RequestRecord(
                conversation_id=message.conversation_id,
                turn_index=0,
                timestamp_ns=time.time_ns(),
                start_perf_ns=drop_perf_ns,
                end_perf_ns=time.perf_counter_ns(),
                error=ErrorDetails.from_exception(e),
            )
        finally:
            # Push the results and return credit
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

    async def _execute_multi_turn_credit_internal(
        self, message: CreditDropMessage
    ) -> RequestRecord:
        """Execute a multi-turn credit drop with conversation state management."""

        if not self.inference_client:
            raise NotInitializedError("Inference server client not initialized.")

        # Clean up old conversation states periodically
        await self._cleanup_old_conversation_states()

        # Get or create conversation state
        conversation_state = await self._get_or_create_conversation_state(message)

        # Get the next turn to process
        turn_response = await self._get_next_turn(conversation_state, message)
        if isinstance(turn_response, ErrorMessage):
            return RequestRecord(
                model_name=self.model_endpoint.primary_model_name,
                conversation_id=message.conversation_id,
                turn_index=conversation_state.current_turn_index,
                timestamp_ns=time.time_ns(),
                start_perf_ns=time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns(),
                error=turn_response.error,
            )

        turn = turn_response.turn
        turn_index = conversation_state.current_turn_index

        # Build conversation context and make API call
        record = await self._call_inference_api_with_context(
            message, turn, conversation_state
        )

        # Update conversation state with the response
        await self._update_conversation_state_with_response(
            conversation_state, turn, record
        )

        # Set record metadata
        record.model_name = self.model_endpoint.primary_model_name
        record.conversation_id = conversation_state.session_id
        record.turn_index = turn_index

        return record

    async def _get_or_create_conversation_state(
        self, message: CreditDropMessage
    ) -> ConversationState:
        """Get existing conversation state or create a new one."""

        conversation_id = message.conversation_id
        if not conversation_id:
            # If no conversation_id, get a random conversation
            conversation_response = await self.conversation_request_client.request(
                ConversationRequestMessage(
                    service_id=self.service_id,
                    credit_phase=message.phase,
                )
            )
            if isinstance(conversation_response, ErrorMessage):
                raise Exception(
                    f"Failed to get conversation: {conversation_response.error}"
                )

            conversation_id = conversation_response.conversation.session_id

        # Check if we already have state for this conversation
        if conversation_id in self.conversation_states:
            return self.conversation_states[conversation_id]

        # Create new conversation state
        conversation_response = await self.conversation_request_client.request(
            ConversationRequestMessage(
                service_id=self.service_id,
                conversation_id=conversation_id,
                credit_phase=message.phase,
            )
        )

        if isinstance(conversation_response, ErrorMessage):
            raise Exception(
                f"Failed to get conversation {conversation_id}: {conversation_response.error}"
            )

        conversation = conversation_response.conversation
        state = ConversationState(conversation_id, conversation.session_id)
        state.conversation_data = conversation

        # Limit number of tracked conversations to prevent memory leaks
        if len(self.conversation_states) >= self.max_conversation_states:
            await self._cleanup_old_conversation_states(force=True)

        self.conversation_states[conversation_id] = state
        self.debug(f"Created new conversation state for {conversation_id}")

        return state

    async def _get_next_turn(
        self, conversation_state: ConversationState, message: CreditDropMessage
    ) -> ConversationTurnResponseMessage | ErrorMessage:
        """Get the next turn to process from the conversation."""

        conversation = conversation_state.conversation_data
        if not conversation or conversation_state.current_turn_index >= len(
            conversation.turns
        ):
            # End of conversation or no more turns
            return ErrorMessage(
                service_id=self.service_id,
                error=ErrorDetails(
                    message=f"No more turns available for conversation {conversation_state.conversation_id}",
                    error_type="EndOfConversation",
                ),
            )

        # Get the specific turn
        turn_response = await self.conversation_request_client.request(
            ConversationTurnRequestMessage(
                service_id=self.service_id,
                conversation_id=conversation_state.conversation_id,
                turn_index=conversation_state.current_turn_index,
            )
        )

        return turn_response

    async def _call_inference_api_with_context(
        self,
        message: CreditDropMessage,
        turn: Turn,
        conversation_state: ConversationState,
    ) -> RequestRecord:
        """Make inference API call with full conversation context."""

        self.trace(
            lambda: f"Calling inference API for turn {conversation_state.current_turn_index}: {turn}"
        )

        # Build conversation context for chat APIs
        if self._is_chat_completion_api():
            enhanced_turn = await self._build_chat_completion_context(
                turn, conversation_state
            )
        else:
            enhanced_turn = turn

        formatted_payload = None
        pre_send_perf_ns = None
        timestamp_ns = None

        try:
            # Format payload for the API request
            formatted_payload = await self.request_converter.format_payload(
                model_endpoint=self.model_endpoint,
                turn=enhanced_turn,
            )

            # Handle timing if specified
            delayed_ns = None
            drop_ns = message.credit_drop_ns
            now_ns = time.time_ns()
            if drop_ns and drop_ns > now_ns:
                self.trace(
                    lambda: f"Waiting for credit drop expected time: {(drop_ns - now_ns) / NANOS_PER_SECOND:.2f} s"
                )
                await asyncio.sleep((drop_ns - now_ns) / NANOS_PER_SECOND)
            elif drop_ns and drop_ns < now_ns:
                delayed_ns = now_ns - drop_ns

            pre_send_perf_ns = time.perf_counter_ns()
            timestamp_ns = time.time_ns()

            # Send the request to the Inference Server API
            result: RequestRecord = await self.inference_client.send_request(
                model_endpoint=self.model_endpoint,
                payload=formatted_payload,
            )

            self.debug(
                lambda: f"pre_send_perf_ns to start_perf_ns latency: {result.start_perf_ns - pre_send_perf_ns} ns"
            )

            result.delayed_ns = delayed_ns
            return result

        except Exception as e:
            self.exception(
                f"Error calling inference server API at {self.model_endpoint.url}: {e}"
            )
            return RequestRecord(
                request=formatted_payload,
                timestamp_ns=timestamp_ns or time.time_ns(),
                start_perf_ns=pre_send_perf_ns or time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns(),
                error=ErrorDetails.from_exception(e),
            )

    def _is_chat_completion_api(self) -> bool:
        """Check if the current endpoint is a chat completion API that needs message history."""
        return self.model_endpoint.endpoint.type in [
            EndpointType.OPENAI_CHAT_COMPLETIONS,
            # Add other chat completion endpoint types as needed
        ]

    async def _build_chat_completion_context(
        self, turn: Turn, conversation_state: ConversationState
    ) -> Turn:
        """Build a turn with full conversation context for chat completion APIs."""

        # For chat completion APIs, we need to include the conversation history
        # in the current turn's context

        # Extract current turn's content
        current_content = ""
        if turn.texts:
            current_content = " ".join(
                content for text in turn.texts for content in text.contents if content
            )

        # Add current user message to state
        user_role = turn.role or "user"
        conversation_state.add_message(user_role, current_content)

        # Create a new turn with the full message history
        # For OpenAI Chat Completions, we'll encode the message history as a special format
        # that the request converter can interpret

        # Encode conversation history as JSON for the request converter
        import json

        from aiperf.common.models import Text

        message_history_json = json.dumps(conversation_state.get_message_history())

        enhanced_turn = Turn(
            texts=[Text(name="conversation_history", contents=[message_history_json])],
            role=turn.role,
            model=turn.model,
            max_tokens=turn.max_tokens,
            timestamp=turn.timestamp,
            delay=turn.delay,
        )

        # Also preserve any images/audio from the original turn
        enhanced_turn.images = turn.images
        enhanced_turn.audios = turn.audios

        return enhanced_turn

    async def _update_conversation_state_with_response(
        self,
        conversation_state: ConversationState,
        turn: Turn,
        record: RequestRecord,
    ) -> None:
        """Update conversation state with the model's response."""

        # Extract response content
        response_content = ""
        if record.responses:
            for response in record.responses:
                if hasattr(response, "content") and response.content:
                    response_content += str(response.content)
                elif hasattr(response, "text") and response.text:
                    response_content += str(response.text)
                elif isinstance(response, dict) and "content" in response:
                    response_content += str(response["content"])

        # Add assistant response to conversation history
        if response_content and self._is_chat_completion_api():
            conversation_state.add_message("assistant", response_content)
            conversation_state.last_response = response_content

        # Move to next turn
        conversation_state.update_turn_index(conversation_state.current_turn_index + 1)

        self.debug(
            f"Updated conversation {conversation_state.conversation_id} to turn {conversation_state.current_turn_index}"
        )

    async def _cleanup_old_conversation_states(self, force: bool = False) -> None:
        """Clean up old conversation states to prevent memory leaks."""

        current_time_ns = time.time_ns()
        threshold_ns = self.state_cleanup_threshold * NANOS_PER_SECOND

        states_to_remove = []

        for conversation_id, state in self.conversation_states.items():
            # Remove states older than threshold or if forced cleanup
            if force or (current_time_ns - state.last_updated_ns) > threshold_ns:
                states_to_remove.append(conversation_id)

        # If forced cleanup, remove oldest states to get below max limit
        if force and len(states_to_remove) == 0:
            sorted_states = sorted(
                self.conversation_states.items(), key=lambda x: x[1].last_updated_ns
            )
            states_to_remove = [
                conv_id
                for conv_id, _ in sorted_states[: len(self.conversation_states) // 2]
            ]

        for conversation_id in states_to_remove:
            del self.conversation_states[conversation_id]
            self.debug(f"Cleaned up conversation state for {conversation_id}")

        if states_to_remove:
            self.debug(f"Cleaned up {len(states_to_remove)} old conversation states")
