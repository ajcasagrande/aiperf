#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.pydantic_utils import exclude_if_none as exclude_if_none

class Text(AIPerfBaseModel):
    name: str
    content: list[str]

class Image(AIPerfBaseModel):
    name: str
    content: list[str]

class Audio(AIPerfBaseModel):
    name: str
    content: list[str]

class Turn(AIPerfBaseModel):
    timestamp: int | None
    delay: int | None
    role: str | None
    text: list[Text]
    image: list[Image]
    audio: list[Audio]

class Conversation(AIPerfBaseModel):
    turns: list[Turn]
    session_id: str

class TurnInfo(AIPerfBaseModel):
    conversation_id: str
    turn_index: int
