# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic import (
    Field,
    SerializeAsAny,
)

from aiperf.common.enums import (
    MessageType,
)
from aiperf.common.messages.service_messages import BaseServiceMessage
from aiperf.common.models import (
    ParsedResponseRecord,
    RequestRecord,
)
from aiperf.common.models.error_models import ErrorDetails
from aiperf.common.models.record_models import MetricRecords
from aiperf.common.types import MessageTypeT


class InferenceResultsMessage(BaseServiceMessage):
    """Message for a inference results."""

    message_type: MessageTypeT = MessageType.INFERENCE_RESULTS

    record: SerializeAsAny[RequestRecord] = Field(
        ..., description="The inference results record"
    )


class ParsedInferenceResultsMessage(BaseServiceMessage):
    """Message for a parsed inference results."""

    message_type: MessageTypeT = MessageType.PARSED_INFERENCE_RESULTS

    worker_id: str = Field(
        ..., description="The ID of the worker that processed the request."
    )
    record: SerializeAsAny[ParsedResponseRecord] = Field(
        ..., description="The post process results record"
    )


class MetricRecordsMessage(BaseServiceMessage):
    """Message from the result parser to the records manager to notify it
    of the metric records for a single request."""

    message_type: MessageTypeT = MessageType.METRIC_RECORDS

    worker_id: str = Field(
        ..., description="The ID of the worker that processed the request."
    )
    metric_records: MetricRecords = Field(..., description="The metric records")
    # TODO: Does this need to be a list? Or can we just use a single ErrorDetails | None instead?
    error_records: list[ErrorDetails] = Field(
        default_factory=list,
        description="The error records",
    )
