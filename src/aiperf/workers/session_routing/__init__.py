# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Session-routing emitter plans: per-request identity on the wire.

Package layout: facts (DispatchFacts), sources (value vocabulary),
emitters (scalar + structured wire writers), plan (validated emitter
plans), presets (registered one-word stacks).
"""

from aiperf.workers.session_routing.emitters import (
    BodyEmitter,
    HeaderEmitter,
    MissingTurnHeaderError,
    NvextSessionControlEmitter,
    merge_at_path,
)
from aiperf.workers.session_routing.facts import DispatchFacts
from aiperf.workers.session_routing.plan import (
    BodyTransformDiagnostics,
    PlanEntry,
    ResolvedPlan,
    SessionRoutingConfigError,
    SessionRoutingEmitterError,
    resolve_plan,
    resolve_plan_from_endpoint,
)
from aiperf.workers.session_routing.presets import (
    ClaudeCodeHeaders,
    Custom,
    DynamoHeaders,
    DynamoNvext,
    DynamoNvextOptions,
    EmptyRoutingOptions,
    SessionIdHeader,
    SessionRoutingPreset,
    SglangSession,
    SmgRoutingKey,
    UrlIndexHeader,
)
from aiperf.workers.session_routing.sources import (
    SOURCE_NAMES,
    is_header_source,
    resolve_source,
)

__all__ = [
    "SOURCE_NAMES",
    "BodyEmitter",
    "BodyTransformDiagnostics",
    "ClaudeCodeHeaders",
    "Custom",
    "DispatchFacts",
    "DynamoHeaders",
    "DynamoNvext",
    "DynamoNvextOptions",
    "EmptyRoutingOptions",
    "HeaderEmitter",
    "MissingTurnHeaderError",
    "NvextSessionControlEmitter",
    "PlanEntry",
    "ResolvedPlan",
    "SessionIdHeader",
    "SessionRoutingConfigError",
    "SessionRoutingEmitterError",
    "SessionRoutingPreset",
    "SglangSession",
    "SmgRoutingKey",
    "UrlIndexHeader",
    "is_header_source",
    "merge_at_path",
    "resolve_plan",
    "resolve_plan_from_endpoint",
    "resolve_source",
]
