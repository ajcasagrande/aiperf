# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from pathlib import Path
from typing import Generic

import aiofiles

from aiperf.common.mixins.task_manager_mixin import TaskManagerMixin
from aiperf.common.types import BaseModelT


class JsonlWriter(TaskManagerMixin, Generic[BaseModelT]):
    def __init__(self, file_path: Path, max_buffer_size: int = 10):
        super().__init__()
        self.file_path = file_path
        self._buffer: asyncio.Queue[BaseModelT] = asyncio.Queue(maxsize=max_buffer_size)
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    async def write(self, data: BaseModelT):
        self._count += 1
        await self._buffer.put(data)
        if self._buffer.full():
            self.execute_async(self._write_buffer())

    async def _write_buffer(self):
        if self.is_debug_enabled:
            self.debug(f"Writing {len(self._buffer)} records to {self.file_path}")

        async with aiofiles.open(self.file_path, "a") as f:
            while not self._buffer.empty():
                item = await self._buffer.get()
                await f.write(item.model_dump_json())
                await f.write("\n")

    async def flush(self) -> None:
        if not self._buffer.empty():
            await self._write_buffer()

    async def close(self) -> None:
        await self.flush()
        await self.wait_for_tasks()
        self.info(f"JsonlWriter wrote {self._count} records to {self.file_path}")
