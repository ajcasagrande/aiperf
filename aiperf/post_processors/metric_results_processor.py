# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Any

from aiperf.common.decorators import implements_protocol
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.models import RecordProcessorResult
from aiperf.common.protocols import ResultsProcessorProtocol


@implements_protocol(ResultsProcessorProtocol)
class MetricResultsProcessor(AIPerfLifecycleMixin):
    """Processor for metric results.

    This is the final stage of the metrics processing pipeline, and is done is a unified manner by the RecordsManager.
    It is responsible for processing the results and returning them to the RecordsManager, as well as summarizing the results.
    """

    async def process_result(self, result: RecordProcessorResult) -> None:
        """Process a result."""
        pass

    # TODO: Add a type for the result of the summarization
    async def summarize(self) -> Any:
        """Summarize the results."""
        pass
