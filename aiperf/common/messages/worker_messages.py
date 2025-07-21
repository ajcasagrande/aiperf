# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic import Field

from aiperf.common.enums.message_enums import MessageType
from aiperf.common.messages import BaseServiceMessage
from aiperf.common.types import MessageTypeT


class SpawnWorkersMessage(BaseServiceMessage):
    """Message sent by the WorkerManager to the SystemController to spawn workers."""

    message_type: MessageTypeT = MessageType.SPAWN_WORKERS

    worker_count: int = Field(..., description="The number of workers to spawn.")


class SpawnWorkersResponseMessage(BaseServiceMessage):
    """Message sent by the SystemController to the WorkerManager to respond to a spawn workers request."""

    message_type: MessageTypeT = MessageType.SPAWN_WORKERS_RESPONSE

    worker_count: int = Field(..., description="The number of workers to spawn.")


class StopWorkersMessage(BaseServiceMessage):
    """Message sent by the WorkerManager to the SystemController to stop workers."""

    message_type: MessageTypeT = MessageType.STOP_WORKERS

    worker_count: int = Field(..., description="The number of workers to stop.")


class StopWorkersResponseMessage(BaseServiceMessage):
    """Message sent by the SystemController to the WorkerManager to respond to a stop workers request."""

    message_type: MessageTypeT = MessageType.STOP_WORKERS_RESPONSE

    worker_count: int = Field(
        ..., description="The number of workers that were stopped."
    )


class StopAllWorkersMessage(BaseServiceMessage):
    """Message sent by the WorkerManager to the SystemController to stop all workers."""

    message_type: MessageTypeT = MessageType.STOP_ALL_WORKERS


class StopAllWorkersResponseMessage(BaseServiceMessage):
    """Message sent by the SystemController to the WorkerManager to respond to a stop all workers request."""

    message_type: MessageTypeT = MessageType.STOP_ALL_WORKERS_RESPONSE
