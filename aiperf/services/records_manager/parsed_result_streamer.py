# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from abc import abstractmethod

from aiperf.common.hooks import aiperf_task
from aiperf.common.mixins import AIPerfLifecycleMixin
from aiperf.common.models import ParsedResponseRecord


class ParsedResponseStreamer(AIPerfLifecycleMixin):
    """
    ParsedResponseStreamer is a base class for all classes that wish to stream the incoming
    ParsedResponseRecords.
    """

    def __init__(self, max_queue_size: int = 100_000, **kwargs) -> None:
        super().__init__(**kwargs)
        self.debug(
            lambda: f"Initializing ParsedResponseStreamer: {self.__class__.__name__} with max_queue_size: {max_queue_size}"
        )
        self.records_queue: asyncio.Queue[ParsedResponseRecord] = asyncio.Queue(
            maxsize=max_queue_size
        )

    @aiperf_task
    async def _stream_records_task(self) -> None:
        while True:
            try:
                record = await self.records_queue.get()
                self.execute_async(self.stream_record(record))
            except asyncio.CancelledError:
                break

    @abstractmethod
    async def stream_record(self, record: ParsedResponseRecord) -> None:
        """Handle the incoming record. This method should be implemented by the subclass."""
        raise NotImplementedError(
            "ParsedResponseStreamer.stream_record method must be implemented by the subclass."
        )
