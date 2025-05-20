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
from abc import ABC, abstractmethod
from typing import Any


class ConversationInterface(ABC):
    """Interface for a conversation."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Get the ID of the conversation."""
        pass

    @abstractmethod
    def current_turn(self) -> Any:
        """Get the current turn data of the conversation."""
        pass

    @abstractmethod
    def advance_turn(self, data: Any) -> None:
        """Advance the conversation to the next turn."""
        pass


class ConversationManagerInterface(ABC):
    """Interface for a conversation manager."""

    @abstractmethod
    def create_conversation(self) -> ConversationInterface:
        """Create a new conversation."""
        pass

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> ConversationInterface:
        """Get a conversation by ID."""
        pass

    @abstractmethod
    def complete_conversation(self, conversation_id: str) -> None:
        """Mark a conversation as complete."""
        pass

    @abstractmethod
    def get_all_conversations(self) -> list[ConversationInterface]:
        """Get all conversations."""
        pass
