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
from aiperf.app.services.worker.conversation import Conversation
from aiperf.common.interfaces.conversation_manager_interface import (
    ConversationInterface,
    ConversationManagerInterface,
)


class ConversationManager(ConversationManagerInterface):
    """A conversation manager.

    This class is responsible for managing conversations between the worker and the Backend.
    """

    def __init__(self):
        self.conversations: dict[str, Conversation] = {}

    def create_conversation(self) -> ConversationInterface:
        """Create a new conversation."""
        conversation = Conversation()
        self.conversations[conversation.id] = conversation
        return conversation

    def get_conversation(self, conversation_id: str) -> ConversationInterface:
        """Get a conversation by ID."""
        return self.conversations[conversation_id]

    def complete_conversation(self, conversation_id: str) -> None:
        """Mark a conversation as complete."""
        self.conversations[conversation_id].complete()

    def get_all_conversations(self) -> list[ConversationInterface]:
        """Get all conversations."""
        return list(self.conversations.values())
