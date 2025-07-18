# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import ResponseStreamerType
from aiperf.common.factories import ParsedResponseStreamerFactory
from aiperf.common.models._record import ParsedResponseRecord
from aiperf.services.records_manager.parsed_result_streamer import (
    ParsedResponseStreamer,
)


@ParsedResponseStreamerFactory.register(ResponseStreamerType.RECORDS_MANAGER)
class RecordsManagerStreamer(ParsedResponseStreamer):
    """Streamer for records manager."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    async def stream_record(self, record: ParsedResponseRecord) -> None:
        """Stream a record."""
        pass
