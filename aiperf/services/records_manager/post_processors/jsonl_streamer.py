# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio

import aiofiles

from aiperf.common.enums import StreamingPostProcessorType
from aiperf.common.factories import StreamingPostProcessorFactory
from aiperf.common.hooks import on_init, on_stop
from aiperf.common.models import ParsedResponseRecord
from aiperf.services.records_manager.streaming_post_processor import (
    StreamingPostProcessor,
)


@StreamingPostProcessorFactory.register(StreamingPostProcessorType.JSONL)
class JSONLStreamer(StreamingPostProcessor):
    """Streamer that streams all parsed records to a JSONL file."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.jsonl_file_lock = asyncio.Lock()

    @on_init
    async def _initialize_jsonl_file(self) -> None:
        """Initialize the JSONL file."""
        async with self.jsonl_file_lock:
            self.jsonl_file = await aiofiles.open(
                self.user_config.output.artifact_directory
                / self.user_config.output.processed_records_file,
                "w",
            )

    async def stream_record(self, record: ParsedResponseRecord) -> None:
        """Stream a record to the JSONL file."""
        async with self.jsonl_file_lock:
            await self.jsonl_file.write(record.model_dump_json() + "\n")

    @on_stop
    async def _close_jsonl_file(self) -> None:
        """Close the JSONL file."""
        async with self.jsonl_file_lock:
            await self.jsonl_file.close()
