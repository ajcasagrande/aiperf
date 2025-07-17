#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Generic, Protocol

from aiperf.common.messages import Message as Message
from aiperf.common.types import InputT as InputT
from aiperf.common.types import OutputT as OutputT

class PostProcessorProtocol(Generic[InputT, OutputT], Protocol):
    async def process(self, records: dict) -> dict: ...

class DataExporterProtocol(Protocol):
    async def export(self) -> None: ...

class MessageHandlerProtocol(Protocol):
    async def on_message(self, message: Message) -> None: ...
