# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Any

from aiperf.common.decorators import implements_protocol
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.models import RecordProcessorResult
from aiperf.common.protocols import StreamingResultsProcessorProtocol


@implements_protocol(StreamingResultsProcessorProtocol)
class MetricResultsStreamer(AIPerfLifecycleMixin):
    """Streamer for metric results.

    This is the final stage of the metrics processing pipeline, and is done is a unified manner by the RecordsManager.
    It is responsible for streaming the results to the RecordsManager, and summarizing the results.
    """

    async def stream_result(self, result: RecordProcessorResult) -> None:
        """Stream a result."""
        pass

    # TODO: Add a type for the result of the summarization
    async def summarize(self) -> Any:
        """Summarize the results."""
        pass
