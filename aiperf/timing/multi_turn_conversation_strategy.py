# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time
from typing import Any

from aiperf.common.enums import CreditPhase, TimingMode
from aiperf.common.messages import CreditReturnMessage
from aiperf.timing.credit_issuing_strategy import (
    CreditIssuingStrategy,
    CreditIssuingStrategyFactory,
)


@CreditIssuingStrategyFactory.register(TimingMode.MULTI_TURN_CONVERSATION)
class MultiTurnConversationStrategy(CreditIssuingStrategy):
    """Timing strategy for multi-turn conversations.

    This strategy manages the scheduling of multi-turn conversations by:
    1. Issuing initial credits to start conversations
    2. Tracking conversation progress through credit returns
    3. Automatically issuing follow-up credits for subsequent turns
    4. Maintaining conversation turn delays as specified in the dataset
    """

    def __init__(
        self,
        config,
        credit_manager,
        user_config=None,
        dataset_timing_response=None,
        **kwargs,
    ):
        super().__init__(config=config, credit_manager=credit_manager, **kwargs)
        self.user_config = user_config
        self.dataset_timing_response = dataset_timing_response

        # Track conversation states and turn progress
        self.conversation_turns: dict[
            str, int
        ] = {}  # conversation_id -> current_turn_index
        self.conversation_max_turns: dict[str, int] = {}  # conversation_id -> max_turns
        self.pending_turns: dict[
            str, list[tuple[int, int]]
        ] = {}  # conversation_id -> [(turn_index, delay_ms), ...]

        # Configuration
        if self.user_config:
            self.max_turns_per_conversation = getattr(
                self.user_config.conversation.turn, "num", 5
            )
            self.turn_delay_ms = getattr(
                getattr(self.user_config.conversation.turn, "delay", None), "mean", 0
            )
        else:
            self.max_turns_per_conversation = 5
            self.turn_delay_ms = 0

        self.debug(
            f"MultiTurnConversationStrategy initialized with max_turns={self.max_turns_per_conversation}"
        )

    async def start_strategy(self) -> None:
        """Start the multi-turn conversation strategy."""
        self.info("Starting multi-turn conversation strategy")

        # Get dataset timing information to understand conversation structure
        await self._load_conversation_metadata()

        # Start issuing initial conversation credits
        await self._start_conversation_credits()

        self.info("Multi-turn conversation strategy started")

    async def _load_conversation_metadata(self) -> None:
        """Load conversation metadata from the dataset manager."""
        try:
            from aiperf.common.messages import (
                DatasetTimingRequest,
                DatasetTimingResponse,
            )

            # Request timing data from dataset manager
            timing_response = await self.dataset_timing_request_client.request(
                DatasetTimingRequest(service_id=self.service_id)
            )

            if isinstance(timing_response, DatasetTimingResponse):
                # Process timing data to understand conversation structure
                conversation_turns_count = {}

                for timestamp, conversation_id in timing_response.timing_data:
                    if conversation_id not in conversation_turns_count:
                        conversation_turns_count[conversation_id] = 0
                    conversation_turns_count[conversation_id] += 1

                # Store conversation metadata
                for conversation_id, turn_count in conversation_turns_count.items():
                    self.conversation_max_turns[conversation_id] = turn_count
                    self.conversation_turns[conversation_id] = 0  # Start at turn 0

                    # Prepare pending turns for this conversation
                    self.pending_turns[conversation_id] = [
                        (turn_idx, self.turn_delay_ms)
                        for turn_idx in range(
                            1, turn_count
                        )  # Skip turn 0 as it will be issued immediately
                    ]

                self.info(f"Loaded {len(conversation_turns_count)} conversations")

        except Exception as e:
            self.warning(f"Failed to load conversation metadata: {e}")
            # Fallback to basic configuration
            self.debug("Using fallback conversation configuration")

    async def _start_conversation_credits(self) -> None:
        """Start issuing credits for the first turn of each conversation."""

        # Issue initial credits for conversations
        for conversation_id in self.conversation_max_turns.keys():
            await self.drop_credit(
                credit_phase=CreditPhase.PROFILING,
                conversation_id=conversation_id,
            )

            # Add a small delay between conversation starts to avoid overwhelming
            await asyncio.sleep(0.01)

        self.debug(
            f"Issued initial credits for {len(self.conversation_max_turns)} conversations"
        )

    async def _on_credit_return(self, message: CreditReturnMessage) -> None:
        """Handle credit return to schedule next turn in conversation."""

        # Extract conversation info from the message or track it separately
        # Since CreditReturnMessage doesn't include conversation_id directly,
        # we'll need to track it through the service lifecycle

        # For now, we'll use a simple approach: schedule next turns for all active conversations
        await self._schedule_next_turns()

    async def _schedule_next_turns(self) -> None:
        """Schedule next turns for active conversations."""

        current_time_ms = int(time.time() * 1000)

        for conversation_id, pending_turn_list in list(self.pending_turns.items()):
            if not pending_turn_list:
                continue  # No more turns for this conversation

            # Check if it's time to issue the next turn
            next_turn_index, delay_ms = pending_turn_list[0]
            current_turn = self.conversation_turns.get(conversation_id, 0)

            # Issue the next turn if the current turn is complete
            if current_turn >= next_turn_index - 1:  # Previous turn completed
                # Remove this turn from pending
                pending_turn_list.pop(0)

                # Update conversation state
                self.conversation_turns[conversation_id] = next_turn_index

                # Schedule the credit drop (with delay if specified)
                credit_drop_time_ns = None
                if delay_ms > 0:
                    credit_drop_time_ns = int((current_time_ms + delay_ms) * 1_000_000)

                await self.drop_credit(
                    credit_phase=CreditPhase.PROFILING,
                    conversation_id=conversation_id,
                    credit_drop_ns=credit_drop_time_ns,
                )

                self.debug(
                    f"Scheduled turn {next_turn_index} for conversation {conversation_id}"
                )

                # Clean up if conversation is complete
                if not pending_turn_list:
                    del self.pending_turns[conversation_id]
                    self.debug(f"Completed conversation {conversation_id}")

    async def stop_strategy(self) -> None:
        """Stop the multi-turn conversation strategy."""
        self.info("Stopping multi-turn conversation strategy")

        # Clean up conversation tracking
        self.conversation_turns.clear()
        self.conversation_max_turns.clear()
        self.pending_turns.clear()

        await super().stop_strategy()

    def get_strategy_info(self) -> dict[str, Any]:
        """Get information about the current strategy state."""
        active_conversations = len(
            [conv_id for conv_id, pending in self.pending_turns.items() if pending]
        )

        completed_conversations = (
            len(self.conversation_max_turns) - active_conversations
        )

        return {
            "strategy_type": "multi_turn_conversation",
            "total_conversations": len(self.conversation_max_turns),
            "active_conversations": active_conversations,
            "completed_conversations": completed_conversations,
            "max_turns_per_conversation": self.max_turns_per_conversation,
            "turn_delay_ms": self.turn_delay_ms,
        }
