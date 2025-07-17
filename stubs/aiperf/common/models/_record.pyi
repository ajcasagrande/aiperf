#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from functools import cached_property as cached_property
from typing import Any

from pydantic import SerializeAsAny as SerializeAsAny

from aiperf.common.constants import NANOS_PER_SECOND as NANOS_PER_SECOND
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import SSEFieldType as SSEFieldType
from aiperf.common.models import AIPerfBaseModel as AIPerfBaseModel

class MetricResult(AIPerfBaseModel):
    tag: str
    unit: str
    header: str
    avg: float | None
    min: float | None
    max: float | None
    p1: float | None
    p5: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p90: float | None
    p95: float | None
    p99: float | None
    std: float | None
    count: int | None
    streaming_only: bool

class InferenceServerResponse(AIPerfBaseModel):
    perf_ns: int

class TextResponse(InferenceServerResponse):
    content_type: str | None
    text: str

class ErrorDetails(AIPerfBaseModel):
    code: int | None
    type: str | None
    message: str
    def __eq__(self, other: Any) -> bool: ...
    def __hash__(self) -> int: ...
    @classmethod
    def from_exception(cls, e: Exception) -> ErrorDetails: ...

class ErrorDetailsCount(AIPerfBaseModel):
    error_details: ErrorDetails
    count: int

class SSEField(AIPerfBaseModel):
    name: SSEFieldType | str
    value: str | None

class SSEMessage(InferenceServerResponse):
    packets: list[SSEField]
    def extract_data_content(self) -> list[str]: ...

class RequestRecord(AIPerfBaseModel):
    request: Any | None
    conversation_id: str | None
    turn_index: int | None
    model_name: str | None
    timestamp_ns: int
    start_perf_ns: int
    end_perf_ns: int | None
    recv_start_perf_ns: int | None
    status: int | None
    responses: SerializeAsAny[
        list[SSEMessage | TextResponse | InferenceServerResponse | Any]
    ]
    error: ErrorDetails | None
    delayed_ns: int | None
    credit_phase: CreditPhase
    @property
    def delayed(self) -> bool: ...
    @property
    def has_error(self) -> bool: ...
    @property
    def valid(self) -> bool: ...
    @property
    def time_to_first_response_ns(self) -> int | None: ...
    @property
    def time_to_second_response_ns(self) -> int | None: ...
    @property
    def time_to_last_response_ns(self) -> int | None: ...
    @property
    def inter_token_latency_ns(self) -> float | None: ...
    def token_latency_ns(self, index: int) -> float | None: ...

class ResponseData(AIPerfBaseModel):
    perf_ns: int
    raw_text: list[str]
    parsed_text: list[str | None]
    token_count: int | None
    metadata: dict[str, Any]

class ParsedResponseRecord(AIPerfBaseModel):
    worker_id: str
    request: RequestRecord
    responses: list[ResponseData]
    isl: int | None
    @cached_property
    def token_count(self) -> int | None: ...
    @cached_property
    def start_perf_ns(self) -> int: ...
    @cached_property
    def timestamp_ns(self) -> int: ...
    @cached_property
    def end_perf_ns(self) -> int: ...
    @cached_property
    def request_duration_ns(self) -> int: ...
    @cached_property
    def tokens_per_second(self) -> float | None: ...
    @cached_property
    def has_error(self) -> bool: ...
    @cached_property
    def valid(self) -> bool: ...
