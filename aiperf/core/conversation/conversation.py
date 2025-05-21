#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import asyncio
import uuid
from typing import Any

from aiperf.core.conversation.interface import (
    ConversationInterface,
)


class Conversation(ConversationInterface):
    """A basic LLM conversation."""

    def __init__(self, id: str | None = None):
        self.messages: list[Any] = []
        self.turn_counter: int = 0
        self._id: str = str(uuid.uuid4()) if id is None else id
        self.complete_event: asyncio.Event = asyncio.Event()

    @property
    def id(self) -> str:
        """Get the ID of the conversation."""
        return self._id

    @property
    def is_complete(self) -> bool:
        """Check if the conversation is complete."""
        return self.complete_event.is_set()

    def current_turn(self) -> Any:
        """Get the current turn of the conversation."""
        return self.turn_counter

    def advance_turn(self, data: Any) -> None:
        """Advance the conversation to the next turn."""
        self.turn_counter += 1
        self.messages.append(data)

    def get_messages(self) -> list[Any]:
        """Get all messages in the conversation."""
        return self.messages

    def complete(self) -> None:
        """Mark the conversation as complete."""
        self.complete_event.set()
