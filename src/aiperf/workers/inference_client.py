# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
import time
from types import MappingProxyType
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import orjson

from aiperf.common.environment import Environment
from aiperf.common.mixins import AIPerfLifecycleMixin
from aiperf.common.models import (
    ErrorDetails,
    ModelEndpointInfo,
    RecordContext,
    RequestInfo,
    RequestRecord,
)
from aiperf.common.redact import redact_headers
from aiperf.plugin import plugins
from aiperf.plugin.enums import PluginType
from aiperf.workers.session_routing import (
    BodyTransformDiagnostics,
    DispatchFacts,
    ResolvedPlan,
    SessionRoutingEmitterError,
    resolve_plan_from_endpoint,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from aiperf.transports.base_transports import FirstTokenCallback

# Shared read-only empty mapping for dispatch turns that author no extra_headers
# (DispatchFacts requires a read-only mapping; avoids per-request allocation).
_EMPTY_TURN_HEADERS: MappingProxyType[str, str] = MappingProxyType({})


def detect_transport_from_url(url: str) -> str:
    """Detect the transport plugin name (e.g. 'http') for a URL.

    Matches registered transports' url_schemes metadata against the URL's
    scheme; raises ValueError when no transport supports it.
    """
    parsed = urlparse(url)
    # urlparse mishandles URLs without schemes (e.g., 'localhost:8765')
    if parsed.scheme and not parsed.netloc:
        parsed = urlparse(f"http://{url}")
    scheme = parsed.scheme.lower() if parsed.scheme else "http"

    for entry in plugins.list_entries(PluginType.TRANSPORT):
        if scheme in entry.metadata.get("url_schemes", []):
            return entry.name

    raise ValueError(f"No transport found for URL scheme '{scheme}' in: {url}")


class InferenceClient(AIPerfLifecycleMixin):
    """Inference client for the worker."""

    def __init__(
        self,
        model_endpoint: ModelEndpointInfo,
        service_id: str,
        *,
        strip_record_payload_bytes: bool = False,
        **kwargs,
    ):
        super().__init__(model_endpoint=model_endpoint, service_id=service_id, **kwargs)
        self.model_endpoint = model_endpoint
        self.service_id = service_id
        # When True, omit canonical request payload bytes from the slim
        # RecordContext after dispatch (memory optimization for large prompts).
        # Resolved by the worker via record payload-retention auto-detection.
        self.strip_record_payload_bytes = strip_record_payload_bytes

        # Session-routing plan (selected via --session-routing): resolved once
        # per worker, invoked at the request-serialization chokepoint to stamp
        # per-session identity (headers and/or body). None when routing is off.
        endpoint_info = model_endpoint.endpoint
        self._routing_plan: ResolvedPlan | None = resolve_plan_from_endpoint(
            endpoint_info
        )
        # Human-readable plan label for log/error messages (comma-joined
        # preset names; None when routing is off).
        self._routing_mode: str | None = (
            ", ".join(entry.preset for entry in endpoint_info.session_routing_plan)
            or None
        )
        # Spec section 5.4 once-per-worker diagnostics: the FIRST dataset-value
        # overwrite by a body emitter and the FIRST non-dict-intermediate
        # replacement each warn once, then stay silent for this worker's life.
        self._warned_body_overwrite = False
        self._warned_non_dict_replacement = False

        # Detect and set transport type if not explicitly set
        if not model_endpoint.transport:
            model_endpoint.transport = detect_transport_from_url(
                model_endpoint.endpoint.base_url,
            )

        # Create endpoint and transport instances
        EndpointClass = plugins.get_class(
            PluginType.ENDPOINT, self.model_endpoint.endpoint.type
        )
        self.endpoint = EndpointClass(model_endpoint=self.model_endpoint)
        TransportClass = plugins.get_class(
            PluginType.TRANSPORT, str(self.model_endpoint.transport)
        )
        self.transport = TransportClass(model_endpoint=self.model_endpoint)
        self.attach_child_lifecycle(self.transport)

    def notify_session_end(self, x_correlation_id: str) -> None:
        """Post-session pass-through to the routing plan (idempotent hook).

        Called by the worker terminal-eviction path on ANY terminal outcome
        (final turn, cancellation, terminal context overflow, cancel-before-
        start). Idempotency is the preset's responsibility -- this hook does
        not dedupe. No-op when session routing is unset.

        Sync hooks run inline; their exceptions are logged (naming the plan
        and session) and swallowed. Async hooks are scheduled fire-and-forget
        via the lifecycle task manager, each wrapped in a guard that logs
        (naming the preset entry and session) and swallows exceptions, and
        abandons the hook with a warning after
        ``AIPERF_ROUTING_SESSION_END_TIMEOUT_S`` seconds. This cleanup hook
        must never break the worker's core session-eviction lifecycle.
        """
        if self._routing_plan is None:
            return
        try:
            for entry_label, awaitable in self._routing_plan.notify_session_end(
                x_correlation_id
            ):
                self.execute_async(
                    self._guarded_session_end_hook(
                        entry_label, x_correlation_id, awaitable
                    )
                )
        except Exception as e:  # noqa: BLE001 - preset cleanup must never break eviction
            self.warning(
                f"session-routing plan {self._routing_mode!r} on_session_end "
                f"failed for session {x_correlation_id!r}; continuing eviction: {e!r}"
            )

    async def _guarded_session_end_hook(
        self,
        entry_label: str,
        x_correlation_id: str,
        awaitable: Awaitable[None],
    ) -> None:
        """Await one async on_session_end hook, attributing and swallowing failures.

        Bounded by ``AIPERF_ROUTING_SESSION_END_TIMEOUT_S`` so a hung preset
        hook cannot pin the worker's task set at shutdown; on timeout or
        exception a warning names the preset entry and the session, and the
        eviction path is never disturbed.
        """
        timeout_s = Environment.ROUTING.SESSION_END_TIMEOUT_S
        try:
            await asyncio.wait_for(awaitable, timeout=timeout_s)
        except asyncio.TimeoutError:
            self.warning(
                f"session-routing {entry_label} on_session_end timed out after "
                f"{timeout_s}s for session {x_correlation_id!r}; hook abandoned"
            )
        except Exception as e:  # noqa: BLE001 - preset cleanup must never break eviction
            self.warning(
                f"session-routing {entry_label} on_session_end failed for "
                f"session {x_correlation_id!r}: {e!r}"
            )

    async def _send_request_to_transport(
        self,
        request_info: RequestInfo,
        first_token_callback: FirstTokenCallback | None = None,
    ) -> RequestRecord:
        """Send request via transport.

        Populates endpoint headers/params, formats the payload, and sends via
        the transport. Cancellation is handled by the transport layer, which
        ensures the request is always sent before being cancelled (simulating
        real client behavior). Returns the RequestRecord with response data.
        """
        request_info.endpoint_headers = self.endpoint.get_endpoint_headers(request_info)
        request_info.endpoint_params = self.endpoint.get_endpoint_params(request_info)

        # Session-routing chokepoint: stamp plan headers now; the same facts
        # feed the body transform below.
        facts: DispatchFacts | None = None
        if self._routing_plan is not None:
            facts = self._apply_session_routing(request_info)

        if request_info.payload_bytes is not None:
            # PAYLOAD_BYTES fast path: incompatible routing plans were already
            # refused by the gate inside _apply_session_routing above.
            formatted_payload = request_info.payload_bytes
        else:
            current_turn = request_info.turns[-1] if request_info.turns else None
            if current_turn and current_turn.raw_payload is not None:
                formatted_payload = current_turn.raw_payload
            else:
                formatted_payload = self.endpoint.format_payload(request_info)
            # Body-based session routing overlays onto the structured body
            # after the endpoint built the dict: endpoint-agnostic, and never
            # mutates a cached Turn (transform_body returns a copy).
            if (
                facts is not None
                and self._routing_plan.mutates_body
                and isinstance(formatted_payload, dict)
            ):
                formatted_payload = self._transform_body_with_plan(
                    formatted_payload, facts
                )
        # Canonicalise to bytes and stash on request_info. Two wins: (1) the
        # transport skips its own orjson.dumps on the dict path, (2) the
        # record processor can drop request_info.turns before the ZMQ hop
        # and still replay the exact wire payload for raw-export.
        if isinstance(formatted_payload, dict):
            formatted_payload = orjson.dumps(formatted_payload)
        request_info.payload_bytes = formatted_payload
        return await self.transport.send_request(
            request_info,
            payload=formatted_payload,
            first_token_callback=first_token_callback,
        )

    def _apply_session_routing(self, request_info: RequestInfo) -> DispatchFacts:
        """Gate, build DispatchFacts, and stamp plan headers for one request.

        Only called when a routing plan is active. Merges the plan's headers
        onto ``request_info.endpoint_headers`` and returns the facts for the
        body-transform step downstream.
        """
        if request_info.payload_bytes is not None:
            # PAYLOAD_BYTES gates: opaque pre-encoded bytes can neither be
            # body-rewritten (without a reparse/redump that defeats the fast
            # path) nor carry extra_headers. Refuse up front (before any
            # emitter runs) so the refusal is deterministic; both raises
            # become error records in _send_request_internal. Header routing
            # from non-header sources stays compatible and is applied below.
            if self._routing_plan.mutates_body:
                raise ValueError(
                    f"session-routing mode {self._routing_mode!r} mutates "
                    "request bodies and is incompatible with the verbatim PAYLOAD_BYTES "
                    "fast path; choose a headers-based mode or a structured-turn dataset."
                )
            if self._routing_plan.reads_turn_headers:
                raise ValueError(
                    f"session-routing mode {self._routing_mode!r} reads "
                    "dispatch-turn headers (header:<name> sources), which the "
                    "verbatim PAYLOAD_BYTES fast path does not carry; choose a "
                    "mode with non-header sources or a structured-turn dataset."
                )
        dispatch_turn = request_info.turns[-1] if request_info.turns else None
        # MappingProxyType is required: the dict is a shared dataset object
        # under recycling and must be mutation-proof through the facts.
        turn_extra_headers = (
            MappingProxyType(dispatch_turn.extra_headers)
            if dispatch_turn is not None and dispatch_turn.extra_headers
            else _EMPTY_TURN_HEADERS
        )
        facts = DispatchFacts(
            x_correlation_id=request_info.x_correlation_id,
            parent_correlation_id=request_info.parent_correlation_id,
            root_correlation_id=(
                request_info.root_correlation_id or request_info.x_correlation_id
            ),
            is_final_turn=request_info.is_final_turn,
            is_parent_final=request_info.is_parent_final,
            is_tree_final=request_info.is_tree_final,
            url_index=(
                request_info.url_index if request_info.url_index is not None else 0
            ),
            turn_extra_headers=turn_extra_headers,
        )
        # Attribute a routing fault to the plan (not the server); emitter
        # faults arrive pre-attributed (SessionRoutingEmitterError) and pass
        # through unwrapped. Both become error records downstream.
        try:
            routing_headers = self._routing_plan.headers(facts)
        except SessionRoutingEmitterError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"session-routing plan {self._routing_mode!r} failed in headers(): {e!r}"
            ) from e
        # Dataset wins: drop any plan-emitted header that case-insensitively
        # collides with a dataset-authored dispatch-turn header, so the wire
        # carries exactly one variant -- the dataset's, under its casing.
        if turn_extra_headers:
            dataset_lowered = {name.lower() for name in turn_extra_headers}
            routing_headers = {
                name: value
                for name, value in routing_headers.items()
                if name.lower() not in dataset_lowered
            }
        request_info.endpoint_headers.update(routing_headers)
        return facts

    def _transform_body_with_plan(self, payload: dict, facts: DispatchFacts) -> dict:
        """Run the plan's body transform, attributing faults and collecting
        the spec-5.4 once-per-worker overwrite diagnostics."""
        diagnostics = BodyTransformDiagnostics()
        try:
            payload = self._routing_plan.transform_body(payload, facts, diagnostics)
        except SessionRoutingEmitterError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"session-routing plan {self._routing_mode!r} failed in transform_body(): {e!r}"
            ) from e
        self._warn_body_transform_diagnostics(diagnostics)
        return payload

    def _warn_body_transform_diagnostics(
        self, diagnostics: BodyTransformDiagnostics
    ) -> None:
        """Emit each spec-5.4 warning kind ONCE per worker, naming the owning
        entry label and the dotted body path of the first occurrence."""
        if diagnostics.overwrites and not self._warned_body_overwrite:
            self._warned_body_overwrite = True
            label, path = diagnostics.overwrites[0]
            self.warning(
                f"session-routing {label} overwrote an existing dataset value at "
                f"body path {path!r}; plan values win at plan-owned paths "
                "(warning once per worker)"
            )
        if diagnostics.non_dict_replacements and not self._warned_non_dict_replacement:
            self._warned_non_dict_replacement = True
            label, path = diagnostics.non_dict_replacements[0]
            self.warning(
                f"session-routing {label} replaced a non-dict value while "
                f"writing body path {path!r}; the original value was discarded "
                "(warning once per worker)"
            )

    async def _send_request_internal(
        self,
        request_info: RequestInfo,
        first_token_callback: FirstTokenCallback | None = None,
    ) -> RequestRecord:
        """Send request to transport and handle exceptions.

        Cancellation is now handled at the transport layer, which ensures the
        request is always sent before being cancelled.
        """
        pre_send_perf_ns, pre_send_timestamp_ns = None, None
        try:
            # Save the current perf_ns before sending the request so it can be used to calculate
            # the start_perf_ns of the request in case of an exception.
            pre_send_perf_ns, pre_send_timestamp_ns = (
                time.perf_counter_ns(),
                time.time_ns(),
            )

            # Transport handles cancellation internally (cancel_after_ns is in request_info)
            result = await self._send_request_to_transport(
                request_info=request_info, first_token_callback=first_token_callback
            )

            if self.is_debug_enabled:
                self.debug(
                    f"pre_send_perf_ns to start_perf_ns latency: {result.start_perf_ns - pre_send_perf_ns} ns"
                )
            return result
        except Exception as e:
            self.error(
                f"Error calling inference server API at {self.model_endpoint.endpoint.base_url}: {e!r}"
            )
            return RequestRecord(
                request_info=request_info,
                timestamp_ns=pre_send_timestamp_ns or time.time_ns(),
                # Try and use the pre_send_perf_ns if it is available, otherwise use the current time.
                start_perf_ns=pre_send_perf_ns or time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns(),
                error=ErrorDetails.from_exception(e),
            )

    async def send_request(
        self,
        request_info: RequestInfo,
        first_token_callback: FirstTokenCallback | None = None,
    ) -> RequestRecord:
        """Send a request to the inference API. Will return an error record if the call fails.

        Args:
            request_info: The request information.
            first_token_callback: Optional callback fired on first SSE message with ttft_ns

        Returns:
            RequestRecord containing the response data and metadata.
        """
        if not request_info.turns and not request_info.payload_bytes:
            raise ValueError(
                f"RequestInfo has no turns (credit_num={request_info.credit_num}, "
                f"conversation_id={request_info.conversation_id})"
            )
        if self.is_trace_enabled and request_info.turns:
            self.trace(f"Calling inference API for turn: {request_info.turns[-1]}")
        record = await self._send_request_internal(request_info, first_token_callback)
        # Redact sensitive headers on the request_info now that the transport has
        # consumed them.  This prevents raw credentials from flowing back through
        # ZMQ messages (which are TRACE-logged as serialised JSON / repr).
        request_info.endpoint_headers = (
            redact_headers(request_info.endpoint_headers) or {}
        )
        return self._enrich_request_record(record=record, request_info=request_info)

    def _enrich_request_record(
        self,
        *,
        record: RequestRecord,
        request_info: RequestInfo,
    ) -> RequestRecord:
        """Enrich a RequestRecord with a slim RecordContext.

        Down-casts the full ``RequestInfo`` (which carries the
        ``ModelEndpointInfo``, transport headers / URL params, and
        pre-send-only timing fields) into a pure ``RecordContext`` before
        attaching it to the record. Only the slim context crosses the ZMQ
        hop to the record processor.

        The tokeniser and the raw-record exporter both read
        ``request_info.payload_bytes`` unless ``strip_record_payload_bytes``
        is set (see ``AIPERF_RECORD_STRIP_PAYLOAD_BYTES``); ``osl_mismatch`` reads
        ``max_tokens``; image/audio/video metrics derive their counts from
        the endpoint's single-pass ``extract_payload_inputs`` at
        parse-time. ``turns`` is never populated on the attached context
        — live records travel turn-less and consumers drive off
        ``payload_bytes``.
        """
        turn_model = request_info.turns[-1].model if request_info.turns else None
        record.model_name = turn_model or self.model_endpoint.primary_model_name

        max_tokens = request_info.turns[-1].max_tokens if request_info.turns else None
        audio_duration_seconds = (
            request_info.turns[-1].audio_duration_seconds
            if request_info.turns
            else None
        )

        payload_bytes = (
            None if self.strip_record_payload_bytes else request_info.payload_bytes
        )

        record.request_info = RecordContext(
            credit_num=request_info.credit_num,
            credit_phase=request_info.credit_phase,
            conversation_id=request_info.conversation_id,
            turn_index=request_info.turn_index,
            source_trace_id=request_info.source_trace_id,
            source_outer_idx=request_info.source_outer_idx,
            source_inner_idx=request_info.source_inner_idx,
            source_kind=request_info.source_kind,
            x_request_id=request_info.x_request_id,
            x_correlation_id=request_info.x_correlation_id,
            credit_issued_ns=request_info.credit_issued_ns,
            agent_depth=request_info.agent_depth,
            parent_correlation_id=request_info.parent_correlation_id,
            root_correlation_id=request_info.root_correlation_id,
            payload_bytes=payload_bytes,
            max_tokens=max_tokens,
            audio_duration_seconds=audio_duration_seconds,
            cache_bust_marker=request_info.cache_bust_marker,
            cache_bust_target=request_info.cache_bust_target,
            # system_message / user_context_message stay on RequestInfo —
            # format_payload inlined them into payload_bytes before dispatch,
            # so the record processor (which reads only payload_bytes) does
            # not need them on the wire.
        )

        # If this is the first turn, calculate the credit drop latency
        if request_info.turn_index == 0 and request_info.drop_perf_ns is not None:
            record.credit_drop_latency = (
                record.start_perf_ns - request_info.drop_perf_ns
            )

        # Always redact at this boundary to guarantee no raw headers leak downstream,
        # even if a transport pre-populates record.request_headers.
        source_headers = (
            record.request_headers
            if record.request_headers is not None
            else request_info.endpoint_headers
        )
        record.request_headers = redact_headers(source_headers)
        return record
