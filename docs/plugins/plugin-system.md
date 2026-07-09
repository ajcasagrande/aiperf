---
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
sidebar-title: Plugin System
---
# AIPerf Plugin System

The AIPerf plugin system provides a flexible, extensible architecture for customizing benchmark behavior. It uses YAML-based configuration with lazy loading, priority-based conflict resolution, and dynamic enum generation.

## Table of Contents

- [Overview](#overview)
  - [Terminology](#terminology)
  - [Key Components](#key-components)
- [Architecture](#architecture)
- [Plugin Categories](#plugin-categories)
- [Using Plugins](#using-plugins)
- [Creating Custom Plugins](#creating-custom-plugins)
- [Plugin Configuration](#plugin-configuration)
- [CLI Commands](#cli-commands)
- [Advanced Topics](#advanced-topics)

## Overview

The plugin system enables:

- **Extensibility**: Add custom endpoints, exporters, and timing strategies without modifying core code
- **Lazy Loading**: Classes load on first access, avoiding circular imports
- **Conflict Resolution**: Higher priority plugins override lower priority ones
- **Type Safety**: Auto-generated enums provide IDE autocomplete
- **Validation**: Validate plugins without importing them

### Terminology

| Term | Description | Code Type |
|------|-------------|-----------|
| **Registry** | Global singleton holding all plugins | `_PluginRegistry` |
| **Package** | Python package providing plugins | `PackageInfo` |
| **Manifest** | `plugins.yaml` declaring plugins | `PluginsManifest` |
| **Category** | Plugin type (e.g., `endpoint`, `transport`) | `PluginType` enum |
| **Entry** | Single registered plugin (name, class_path, priority, metadata) | `PluginEntry` |
| **Class** | Python class implementing a plugin (lazy-loaded) | `type` |
| **Metadata** | Typed configuration (e.g., `EndpointMetadata`) | Pydantic model |

**Hierarchy:**

```text
Registry (singleton)
└── Package (1+) ─── discovered via entry points
    └── Manifest (1+ per package) ─── plugins.yaml files
        └── Category (1+)
            └── Entry (1+) ─── PluginEntry
                ├── Class ─── lazy-loaded Python class
                └── Metadata ─── optional typed config
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Plugin Registry | `src/aiperf/plugin/plugins.py` | Singleton managing discovery and loading |
| Plugin Entry | `src/aiperf/plugin/types.py` | Lazy-loading entry with metadata |
| Categories | `src/aiperf/plugin/categories.yaml` | Category definitions with protocols |
| Built-in Plugins | `src/aiperf/plugin/plugins.yaml` | Built-in plugin registrations |
| Schemas | `src/aiperf/plugin/schema/schemas.py` | Pydantic models for validation |
| Enums | `src/aiperf/plugin/enums.py` | Auto-generated enums from registry |
| CLI | `src/aiperf/plugin/cli.py` | Plugin exploration commands |

## Architecture

### Discovery Flow

```text
Entry Points → plugins.yaml → Pydantic Validation → Registry
                                                      ↓
                              get_class() → Import Module → Cache
```

| Phase | Action |
|-------|--------|
| 1. Discovery | Scan `aiperf.plugins` entry points for `plugins.yaml` files |
| 2. Loading | Parse YAML, validate with Pydantic, register with conflict resolution |
| 3. Access | `get_class()` imports module, caches class for reuse |

### Registry Singleton Pattern

The plugin registry follows the singleton pattern with module-level exports:

```python
from aiperf.plugin import plugins
from aiperf.plugin.enums import PluginType

# Get a plugin class by name
EndpointClass = plugins.get_class(PluginType.ENDPOINT, "chat")

# Iterate all plugins in a category
for entry, cls in plugins.iter_all(PluginType.ENDPOINT):
    print(f"{entry.name}: {entry.description}")
```

## Plugin Categories

AIPerf supports 31 plugin categories organized by function:

### Timing Categories

| Category | Enum | Description |
|----------|------|-------------|
| `timing_strategy` | `TimingMode` | Request scheduling strategies (fixed schedule, request rate, user-centric, agentic replay) |
| `arrival_pattern` | `ArrivalPattern` | Inter-arrival time distributions (constant, Poisson, gamma, concurrency burst) |
| `ramp` | `RampType` | Value ramping strategies (linear, exponential, Poisson) |

### Dataset Categories

| Category | Enum | Description |
|----------|------|-------------|
| `dataset_backing_store` | `DatasetBackingStoreType` | Server-side dataset storage |
| `dataset_client_store` | `DatasetClientStoreType` | Worker-side dataset access |
| `dataset_sampler` | `DatasetSamplingStrategy` | Sampling strategies (random, sequential, shuffle) |
| `dataset_composer` | `ComposerType` | Dataset generation (synthetic, custom, synthetic_rankings, public) |
| `custom_dataset_loader` | `CustomDatasetType` | JSONL format loaders |
| `public_dataset_loader` | `PublicDatasetType` | Shared benchmark datasets fetched without a local file (HTTP, HuggingFace) |

### Endpoint and Transport Categories

| Category | Enum | Description |
|----------|------|-------------|
| `endpoint` | `EndpointType` | API endpoint implementations (chat, completions, embeddings, etc.) |
| `transport` | `TransportType` | Network transport (HTTP via aiohttp) |

### Session Routing Category

| Category | Enum | Description |
|----------|------|-------------|
| `session_routing` | `SessionRoutingType` | Stamps per-session identity (headers or body metadata) onto outbound requests so an external router pins every turn of a session to one worker; selected via `--session-routing` |

**Purpose.** A session-routing preset gives an external router (SGLang Model Gateway, Dynamo, a
generic session-affinity load balancer) the identity of the session a request belongs to, so all of
a conversation's turns re-land on the replica holding its KV prefix. A preset is a named,
options-validated bundle of *emitters* (header/body writers over per-request `DispatchFacts`);
the selected preset resolves into a validated emitter plan invoked by `InferenceClient` at the
request-serialization chokepoint. The base class is `SessionRoutingPreset`
(`src/aiperf/workers/session_routing/presets.py`).

**Built-ins:**

| Name | Class | Emits | Options (defaults) |
|------|-------|-------|--------------------|
| `dynamo_headers` | `DynamoHeaders` | header `X-Dynamo-Session-ID` ← `session`; header `X-Dynamo-Parent-Session-ID` ← `parent` (skipped for root sessions) | none |
| `dynamo_nvext` | `DynamoNvext` | body `nvext.session_control` (bind on non-final turns, close on the final turn) | `timeout_seconds` (300, ge=1) — inactivity TTL carried on every bind. `scope` (`conversation`\|`lineage`, default `conversation`) — `conversation` binds/closes each session under its own correlation ID; `lineage` binds every session in an agent tree under the tree ROOT's correlation ID so the whole lineage co-locates on the worker holding the shared parent prefix (for Dynamo builds without KV-event prefix indexing), and closes the shared key only on a request stamped provably-last for the whole tree (`is_tree_final`, agentic replay) — otherwise the `session_control` TTL reclaims it. Mutates the body (forgoes the PAYLOAD_BYTES fast path). |
| `smg_routing_key` | `SmgRoutingKey` | header `X-SMG-Routing-Key` ← `source` | `source` (`session`; any source spec, e.g. `header:x-dynamo-session-id` to route on a dataset-recorded key). `missing` (`error`\|`skip`, default `error`; legal only when `source` is a `header:<name>` spec). Works for the SMG `manual` and `consistent_hashing` policies. See the SMG baseline caveat below. |
| `session_id_header` | `SessionIdHeader` | header `<header_name>` ← `session` | `header_name` (`X-Session-ID`). |
| `sglang_session` | `SglangSession` | body `<field>` ← `source` | `field` (`session_id`; a **literal** key — dots are NOT nesting, use `custom` for nested paths). `source` (`session`; accepts `header:<name>`). `missing` (`error`\|`skip`, default `error`; legal only with a `header:` source). Mutates the body (forgoes the PAYLOAD_BYTES fast path). |
| `url_index_header` | `UrlIndexHeader` | header `<header_name>` ← `url_index` | `header_name` (`X-URL-Index`). See the vLLM dp-rank recipe below; a single configured `--url` is a config error. |
| `claude_code_headers` | `ClaudeCodeHeaders` | header `<session_header_name>` ← `root` (always); header `<agent_header_name>` ← `agent` (subagent sessions, depth ≥ 1 only); header `<parent_header_name>` ← `agent_parent` (depth ≥ 2 only — omitted at depth 1 where the parent is the root) | `session_header_name` (`x-claude-code-session-id`), `agent_header_name` (`x-claude-code-agent-id`), `parent_header_name` (`x-claude-code-parent-agent-id`). Defaults match the consuming Dynamo router contract. |
| `custom` | `Custom` | arbitrary scalar header/body emitters | `headers` (map: header name → source) and `body` (nested map: a string leaf is a source, a mapping descends). At least one assignment required; `header:` sources here are always `missing=error`. See "The `custom` preset" below. |

Value sources shared by every preset: `session` (this session's correlation ID, stable across
turns), `parent` (immediate parent's ID; skips root sessions), `root` (session-tree root's ID,
for whole-tree affinity), `url_index` (assigned round-robin URL slot, post-fallback), `agent`
(this session's ID, emitted only for non-root sessions), `agent_parent` (parent's ID, emitted
only at depth ≥ 2), and `header:<name>` (a dataset-authored dispatch-turn header, case-insensitive
lookup). A `header:<name>` source reads the **dispatch turn only** — multi-turn datasets must
author the header on every turn.

**Options (`--session-routing-opt key=value`).** Each preset exposes an `Options` Pydantic model
(`extra="forbid"`, so unknown keys are rejected at startup). Repeated `--session-routing-opt`
pairs populate it; values are coerced to the model's field types and canonicalized at config
resolution, so downstream code always sees typed values. Commas inside a value are passed through
to the preset (repeat the flag for multiple opts). `custom` takes JSON values, e.g.
`--session-routing-opt 'headers={"X-Affinity":"session"}'`. `--session-routing-opt` without
`--session-routing` is an error, and `dynamo_headers` rejects every opt key.

**Stacking presets.** `--session-routing` is repeatable; each occurrence appends a preset to an
ordered plan. Presets must write **disjoint** surfaces (no two emitters may write the same header
case-insensitively, or overlapping body paths) — `resolve_plan` rejects overlaps at config load,
naming both contributing entries. A preset name may appear **at most once** per plan; for
repeated emission of one value under several names, use a single `custom`.

Because write-sets are disjoint, emitter order is semantically irrelevant (it affects only
deterministic logging).

Stacked example — SGLang Model Gateway stickiness in front of engine-side session radix cache.
The gateway routes on `X-SMG-Routing-Key` and the engine keys its radix cache on a body
`session_id`. In fixed-schedule replay the two identities **must match** so the gateway sends a
recorded session to the engine that holds its prefix — so **both** emitters source the same
recorded identity header, not the live per-request `session`:

```bash
# Replay-faithful stack. NOTE: /v1/completions only — see the passthrough table (SMG drops
# session_id from re-serialized chat bodies). Both emitters read the SAME recorded identity;
# a live routing key would scatter each recorded session across engines while the body
# session_id groups them.
aiperf profile ... \
  --endpoint-type completions \
  --session-routing smg_routing_key \
  --session-routing sglang_session \
  --session-routing-opt smg_routing_key.source=header:x-dynamo-session-id \
  --session-routing-opt sglang_session.source=header:x-dynamo-session-id
```

A `header:<name>` source routes on a header the **dataset** authored on each dispatch turn
(`Turn.extra_headers`) — a forward-looking extension point for datasets or custom loaders that
record a per-turn identity (e.g. a replay trace's original session id). No built-in dataset in
this release authors per-turn headers, so a `header:` source is only usable against a dataset
that does; the runtime's dataset-load fail-fast aborts the run at startup if the plan reads a
`header:` source that no turn provides.

Equivalent YAML (canonical form; CLI is its flat encoding):

```yaml
endpoint:
  session_routing:
    - smg_routing_key:
        source: header:x-dynamo-session-id
    - sglang_session:
        source: header:x-dynamo-session-id
```

The opt-key grammar for stacked plans, in priority order:

1. `headers.<Name>` / `body.<dotted.path>` — assignments for the `custom` preset (config error
   if `custom` is not configured). `headers.` consumes exactly one segment; the remainder is the
   header name **verbatim, dots included**. `body.` descends on dots.
2. `<preset>.<key>` where `<preset>` is a configured preset — the namespaced form. **Always
   accepted, even with a single configured preset**, so stacked examples stay copy-pasteable.
3. A bare `<key>` — binds to the sole configured preset; a config error listing the configured
   presets when more than one is present.

Supplying the same option twice — bare and namespaced across repeated `--session-routing-opt`
flags, or the flat `session_routing_opts` map plus an inline entry opt — is a config error naming
both spellings (no silent last-writer-wins). The one legacy exception: a CLI `--session-routing-opt`
silently overrides the flat `session_routing_opts` dict on the same path, preserving the pre-plan
`{**flat, **cli}` merge.

A plan header whose name case-insensitively matches a `--header` you configured is a config
error — the gateway would otherwise receive two conflicting values on the wire (the header merge
chain is case-sensitive, so both variants would ship and the router would pick one
nondeterministically). Remove the `--header` entry or pick a preset/option writing a different
header.

**The `custom` preset.** Reach for `custom` when a router needs arbitrary header names, the same
value stamped under several names (layered routers), or bespoke nested body paths. Two option
maps, named identically in CLI and YAML — `headers` (header name → source) and `body` (a nested
map where a **string leaf is a source** and a **mapping descends** into the payload):

```yaml
endpoint:
  session_routing:
    - custom:
        headers:
          X-Sticky-Key: session
          X-Tree-ID: root
        body:
          session_id: session          # body["session_id"]
          nvext:
            session_id: session         # body["nvext"]["session_id"]
```

At least one assignment (across `headers` and `body`) is required — an empty `custom` routes
nothing and is a config error. Sources validate against the shared registry; an unknown source
error enumerates the full registry.

On the CLI, the `custom` maps are encoded with dotted keys or JSON values:

```bash
# dotted-key form: headers.<Name> takes the header name verbatim; body.<path> descends on dots
aiperf profile ... \
  --session-routing custom \
  --session-routing-opt headers.X-Sticky-Key=session \
  --session-routing-opt headers.X-Tree-ID=root \
  --session-routing-opt body.nvext.session_id=session

# JSON form (equivalent) — one flag per map
aiperf profile ... \
  --session-routing custom \
  --session-routing-opt 'headers={"X-Sticky-Key":"session","X-Tree-ID":"root"}' \
  --session-routing-opt 'body={"nvext":{"session_id":"session"}}'
```

Body keys containing a literal dot can only be expressed in YAML (the CLI `body.` form treats
dots as descent). Every built-in preset has a `custom` equivalent, e.g. `dynamo_headers` ≡
`headers={"X-Dynamo-Session-ID":"session","X-Dynamo-Parent-Session-ID":"parent"}`.

**vLLM data-parallel-rank pinning (`url_index_header`).** vLLM's `X-data-parallel-rank` header
pins a request to a specific DP rank, but **only in internal-load-balancer mode** (a single API
server fronting all ranks). aiperf assigns each URL slot a `url_index`, so to sweep all `dp_size`
ranks you **repeat the same frontend URL once per rank** and emit the slot index as the rank
header:

```bash
# dp_size = 2: repeat the URL twice, emit the slot index as X-data-parallel-rank
aiperf profile ... \
  --url http://localhost:8000 --url http://localhost:8000 \
  --session-routing url_index_header \
  --session-routing-opt header_name=X-data-parallel-rank
```

SGLang's OpenAI endpoints honor the **same header name**, and upstream Dynamo accepts it as an
alias — the invocation above is identical for all three.

Sharp edges:

- **A single configured `--url` is a config error** — every request would carry index 0, silently
  pinning the whole run to rank 0. The error carries the repeat-URL recipe:

  > session-routing plan reads the 'url_index' source, but only one --url is configured, so every
  > request would carry index 0. If each rank shares one frontend URL, repeat the URL once per
  > rank: --url U --url U ...

- **Internal-LB mode only.** The header is a no-op when vLLM is not fronting ranks with a single
  API server.
- **Out-of-range rank → per-request error** (e.g. more URL slots than DP ranks).
- **Non-integer header value → silently ignored** by vLLM (aiperf's `url_index` is always an
  integer, so this only bites hand-authored `header:` overrides).

**SMG baseline caveat (`smg_routing_key`).** When a request carries no `X-SMG-Routing-Key`, the
SGLang Model Gateway does **not** always spread requests randomly:

- Under the `manual` policy, a missing key routes to a random worker.
- Under the `consistent_hashing` policy, the gateway falls back to an **implicit affinity key**
  hashed from the request's `authorization`, `x-forwarded-for`, or `cookie` header **before**
  random. A benchmark that sends a single API key therefore pins **every** request to one worker
  as its "no routing" baseline — not a random spread.

Consequence for A/B comparisons: a "routing off vs. routing on" experiment under
`consistent_hashing` must account for this — the "off" arm is single-worker-pinned by the shared
`authorization` header, not balanced. Vary the implicit-affinity inputs (or use the `manual`
policy) to get a genuine random baseline. Bare SGLang engines also read `X-SMG-Routing-Key`
harmlessly, so the preset is safe to leave on when talking directly to an engine.

**Proxy passthrough — will my header/body survive the hop?** Stacked scenarios that put a proxy
(SMG, Dynamo) in front of the engine only work if the proxy forwards the inner surface. This is
**not** free. Verified wire contracts:

| Emitted surface | Direct to engine | Through SMG | Through upstream Dynamo |
|---|---|---|---|
| `X-SMG-Routing-Key` header | passthrough (engine ignores it) | consumed by the gateway | forwarded |
| Other custom/routing **headers** | passthrough | **dropped** unless on the SMG allowlist (`authorization`, `x-request-id`, `x-correlation-id`, `traceparent`, `tracestate`, `x-smg-routing-key`, `x-request-id-*`) | passthrough |
| Body `session_id` (or any unknown top-level body field) on **`/v1/chat/completions`** | passthrough | **dropped** — SMG re-serializes chat through a typed schema with no `session_id` field and no catch-all | **HTTP 400** — Dynamo rejects unknown top-level body fields (`DYN_IGNORE_OPENAI_FE_UNSUPPORTED_FIELDS` drops them instead) |
| Body `session_id` on **`/v1/completions`** | passthrough | **passthrough** — the completions route preserves unknown fields | HTTP 400 (same as chat) |
| `nvext.session_control` (`dynamo_nvext`) | requires a Dynamo build implementing `session_control` | n/a | **rejected** — upstream Dynamo `nvext` is `deny_unknown_fields` with no `session_control`; every request 400s |

Practical rules that follow:

- **`smg_routing_key` + `sglang_session` works only on `/v1/completions`** — chat is blocked at the
  SMG hop because the typed re-serialization drops `session_id`.
- **`dynamo_headers` + `sglang_session` is blocked upstream** — Dynamo 400s on the body
  `session_id`; it needs Dynamo passthrough support.
- **`dynamo_nvext` targets non-upstream Dynamo builds only.** Against upstream Dynamo main the
  failure signature is 100% HTTP 400 "invalid nvext" — use `dynamo_headers` there.
- **`url_index_header` + `session_id_header` works direct-to-engine** (no SMG hop, so no allowlist
  filtering).

Scenario status summary (**Works** / **Conditional** / **Blocked**):

| Scenario | Invocation | Status |
|---|---|---|
| Dynamo header affinity | `dynamo_headers` | Works (upstream Dynamo) |
| Dynamo nvext bind/close | `dynamo_nvext` | Conditional — non-upstream Dynamo builds only |
| SMG stickiness | `smg_routing_key` | Works (manual + consistent-hashing; baseline caveat above) |
| SGLang radix cache, bare engine | `sglang_session` | Works |
| SMG + engine cache | stack `smg_routing_key` + `sglang_session` (both `source=header:…`) | Conditional — `/v1/completions` only; chat blocked on gateway; needs a dataset authoring per-turn `extra_headers` |
| Dynamo router → SGLang engines | stack `dynamo_headers` + `sglang_session` | Blocked — Dynamo 400s on `session_id` |
| Replay → SGLang (recorded IDs) | `sglang_session` + `source=header:x-dynamo-session-id` | Conditional — requires a dataset authoring per-turn `extra_headers`; no built-in loader stamps it yet (Exgentic port deferred) |
| vLLM dp-rank pinning | `url_index_header` + `header_name=X-data-parallel-rank`, URL repeated `dp_size`× | Works (internal-LB mode) |
| SGLang dp-rank pinning | same invocation (SGLang mirrors the header) | Works |
| dp-rank + session header | stack `url_index_header` + `session_id_header` | Works (direct-to-engine) |
| Claude Code agent-tree headers | `claude_code_headers` | Works (upstream Dynamo) |
| Unknown router, tree affinity | `custom` headers `{X-Sticky: session, X-Tree: root}` | Works |

**Migrating from `identity_headers`.** The single-mode `identity_headers` preset (an early
session-routing draft) is removed; it never merged and was never ported to this branch, so most
invocations are unaffected — but any socialized `identity_headers` example rewrites cleanly to
`custom`. `identity_headers` stamped one or more fixed header names with a session identity via
tier-named options (`session` / `parent` / `root`, each a comma-separable list of header names);
the `custom` preset expresses the same thing declaratively:

```bash
# BEFORE (removed)
--session-routing identity_headers --session-routing-opt session=X-Affinity

# AFTER
--session-routing custom --session-routing-opt 'headers={"X-Affinity":"session"}'
```

```yaml
# AFTER, YAML
endpoint:
  session_routing:
    - custom:
        headers:
          X-Affinity: session
```

Everything else keeps working: multi-URL `url_index_header`, bare-string YAML
(`session_routing: dynamo_headers`), and the flat `session_routing_opts` map (accepted with a
single configured preset). The one other deliberate break: `url_index_header` with a **single**
configured URL now hard-errors instead of silently pinning to rank 0 (repeat the URL once per
rank).

**Body emission and the PAYLOAD_BYTES fast path.** A plan's `mutates_body` flag is derived: it is
True exactly when the plan contains a body emitter (`dynamo_nvext`, `sglang_session`, `custom`
with body assignments). Body-mutating plans are incompatible with the verbatim PAYLOAD_BYTES mmap
fast path and are gated off it at four points: preformat suppression, dataset build, cache hit,
and runtime. Header-only
plans leave the body untouched and keep the fast path. Body emitters never mutate their input —
the structured path shares cached `Turn.raw_payload` dicts with the dataset — merges are
copy-on-write.

**Plan validation.** `resolve_plan` enforces cross-emitter invariants regardless of which presets
are combined: header names must be RFC 9110 tokens, `x-request-id` / `x-correlation-id` are
reserved, and no two emitters may write the same header (case-insensitive) or overlapping body
paths (prefix-freedom). Failures raise `SessionRoutingConfigError` naming the offending entries.

Header layering order on the wire — later layers override earlier ones. The transport merge chain
itself is a case-sensitive `dict.update`; only the plan-vs-dataset collision is resolved
case-insensitively (at the request-serialization chokepoint, the dataset-authored value wins and
the plan's variant is dropped, so a single merged header ships on the wire):

```mermaid
flowchart LR
    A["Universal<br/>(X-Request-ID, correlation)"] --> B["Endpoint / user --header"]
    B --> C["Session-routing plan"]
    C --> D["Dataset turn headers"]
    D --> E["Transport<br/>(Content-Type, always last)"]
```

**`on_session_end` contract.** Fires strictly after the session's last worker-side activity, on
every terminal path (final turn, cancellation, terminal context overflow, cancel-before-start). It
is post-session cleanup only and must be idempotent (default sync no-op; async hooks are scheduled
fire-and-forget).

**Stateful-preset rule.** A stateful preset must key its instance state on `x_correlation_id`
only. A session tree deliberately spans workers, so tree-keyed worker state fragments across
processes. For tree-scoped behavior, use the stateless per-request dispatch facts
`root_correlation_id` and `is_tree_final` instead of accumulating state.

### Processing Categories

| Category | Enum | Description |
|----------|------|-------------|
| `record_processor` | `RecordProcessorType` | Per-record metric computation |
| `accumulator` | `AccumulatorType` | Record ingestion, time-range queries, and summarization |
| `stream_exporter` | `StreamExporterType` | Streaming record export (e.g. JSONL files) |
| `data_exporter` | `DataExporterType` | File format exporters (CSV, JSON, Parquet) |
| `console_exporter` | `ConsoleExporterType` | Terminal output exporters |

### Accuracy Categories

| Category | Enum | Description |
|----------|------|-------------|
| `accuracy_benchmark` | `AccuracyBenchmarkType` | Accuracy benchmark problem sets (MMLU, AIME, HellaSwag, BigBench, etc.) |
| `accuracy_grader` | `AccuracyGraderType` | Grading strategies for accuracy evaluation (exact match, math, multiple choice, code execution) |

### UI and Selection Categories

| Category | Enum | Description |
|----------|------|-------------|
| `ui` | `UIType` | UI implementations (dashboard, simple, none) |
| `url_selection_strategy` | `URLSelectionStrategy` | Request distribution (round-robin) |

### Service Categories

| Category | Enum | Description |
|----------|------|-------------|
| `service` | `ServiceType` | Core AIPerf services |
| `service_manager` | `ServiceRunType` | Service orchestration (multiprocessing, Kubernetes) |
| `api_router` | `APIRouterType` | Lifecycle-managed HTTP/WebSocket routers exposed by the controller API |

### Visualization and Telemetry Categories

| Category | Enum | Description |
|----------|------|-------------|
| `plot` | `PlotType` | Chart types (scatter, histogram, timeline, etc.) |
| `gpu_telemetry_collector` | `GPUTelemetryCollectorType` | GPU metric collection (DCGM, pynvml) |

### Infrastructure Categories (Internal)

| Category | Enum | Description |
|----------|------|-------------|
| `communication` | `CommunicationBackend` | ZMQ backends (IPC, TCP, dual-bind) |
| `communication_client` | `CommClientType` | Socket patterns (PUB, SUB, PUSH, PULL) |
| `zmq_proxy` | `ZMQProxyType` | Message routing proxies |

## Using Plugins

```python
from aiperf.plugin import plugins
from aiperf.plugin.enums import PluginType, EndpointType

# Get class by name, enum, or full path
ChatEndpoint = plugins.get_class(PluginType.ENDPOINT, "chat")
ChatEndpoint = plugins.get_class(PluginType.ENDPOINT, EndpointType.CHAT)
ChatEndpoint = plugins.get_class(PluginType.ENDPOINT, "aiperf.endpoints.openai_chat:ChatEndpoint")

# Iterate plugins
for entry, cls in plugins.iter_all(PluginType.ENDPOINT):
    print(f"{entry.name}: {entry.class_path}")

# Get metadata (raw dict or typed)
metadata = plugins.get_metadata("endpoint", "chat")
endpoint_meta = plugins.get_endpoint_metadata("chat")  # Returns EndpointMetadata
```

| Function | Returns | Use Case |
|----------|---------|----------|
| `get_class(category, name)` | `type` | Get plugin class |
| `iter_all(category)` | `Iterator[tuple[PluginEntry, type]]` | List all plugins |
| `get_metadata(category, name)` | `dict` | Raw metadata |
| `get_endpoint_metadata(name)` | `EndpointMetadata` | Typed endpoint config |
| `get_transport_metadata(name)` | `TransportMetadata` | Typed transport config |
| `get_plot_metadata(name)` | `PlotMetadata` | Typed plot config |
| `get_service_metadata(name)` | `ServiceMetadata` | Typed service config |

## Creating Custom Plugins

> [!TIP]
> **Contributing directly to AIPerf?** You only need two things:
> 1. Add your class under `src/aiperf/`
> 2. Register it in `src/aiperf/plugin/plugins.yaml`
>
> The `pyproject.toml` entry points and separate package install below are only needed for external/third-party plugins.

**Quick Start** (4 steps):

| Step | File | Action |
|------|------|--------|
| 1 | `my_endpoint.py` | Create class extending `BaseEndpoint` |
| 2 | `plugins.yaml` | Register with class path, description, and metadata |
| 3 | `pyproject.toml` | Add entry point: `my-package = "my_package:plugins.yaml"` |
| 4 | Terminal | `pip install -e . && aiperf plugins endpoint my_custom` |

### Minimal Endpoint Example

```python
# my_package/endpoints/custom_endpoint.py
class MyCustomEndpoint(BaseEndpoint):
    def format_payload(self, request_info: RequestInfo) -> dict[str, Any]:
        turn = request_info.turns[-1]
        texts = [content for text in turn.texts for content in text.contents if content]
        return {"prompt": texts[0] if texts else ""}

    def parse_response(self, response: InferenceServerResponse) -> ParsedResponse | None:
        if json_obj := response.get_json():
            return ParsedResponse(perf_ns=response.perf_ns, data=TextResponseData(text=json_obj.get("text", "")))
        return None
```

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/ai-dynamo/aiperf/refs/heads/main/src/aiperf/plugin/schema/plugins.schema.json
# my_package/plugins.yaml
schema_version: "1.0"
endpoint:
  my_custom:
    class: my_package.endpoints.custom_endpoint:MyCustomEndpoint
    description: Custom endpoint for my API.
    metadata: { endpoint_path: /v1/generate, supports_streaming: true, produces_tokens: true, tokenizes_input: true, metrics_title: My Custom Metrics }
```

> [!NOTE]
> Extend base classes (`BaseEndpoint`, etc.) to get logging, helpers, and default implementations. Only implement core methods.

## Plugin Configuration

### categories.yaml Schema

Defines plugin categories with their protocols and metadata schemas:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/ai-dynamo/aiperf/refs/heads/main/src/aiperf/plugin/schema/categories.schema.json
schema_version: "1.0"

endpoint:
  protocol: aiperf.endpoints.protocols:EndpointProtocol
  metadata_class: aiperf.plugin.schema.schemas:EndpointMetadata
  enum: EndpointType
  description: |
    Endpoints define how to format requests and parse responses for different APIs.
  internal: false  # Set to true for infrastructure categories
```

### plugins.yaml Schema

Registers plugin implementations:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/ai-dynamo/aiperf/refs/heads/main/src/aiperf/plugin/schema/plugins.schema.json
schema_version: "1.0"

endpoint:
  chat:
    class: aiperf.endpoints.openai_chat:ChatEndpoint
    description: OpenAI Chat Completions endpoint.
    priority: 0  # Higher priority wins conflicts
    metadata:
      endpoint_path: /v1/chat/completions
      supports_streaming: true
      produces_tokens: true
      tokenizes_input: true
      metrics_title: LLM Metrics
```

### Metadata Schemas

Category-specific metadata is validated against Pydantic models in `aiperf.plugin.schema.schemas`:

| Model | Key Fields |
|-------|------------|
| `EndpointMetadata` | `endpoint_path`, `supports_streaming`, `produces_tokens`, `tokenizes_input`, `metrics_title` + optional streaming/service/multimodal/polling fields |
| `TransportMetadata` | `transport_type`, `url_schemes` |
| `PlotMetadata` | `display_name`, `category` |
| `ServiceMetadata` | `required`, `auto_start`, `disable_gc`, `replicable` |

## CLI Commands

| Command | Output |
|---------|--------|
| `aiperf plugins` | Installed packages with versions and plugin counts |
| `aiperf plugins --all` | All categories with registered plugins |
| `aiperf plugins endpoint` | All endpoint types with descriptions |
| `aiperf plugins endpoint chat` | Details: class path, package, metadata |
| `aiperf plugins --validate` | Validates class paths and existence |

```bash
$ aiperf plugins endpoint chat
╭───────────────── endpoint:chat ─────────────────╮
│ Type: chat                                      │
│ Category: endpoint                              │
│ Package: aiperf                                 │
│ Class: aiperf.endpoints.openai_chat:ChatEndpoint│
│                                                 │
│ OpenAI Chat Completions endpoint. Supports      │
│ multi-modal inputs and streaming responses.     │
╰─────────────────────────────────────────────────╯
```

## Advanced Topics

### Conflict Resolution

| Priority | Rule |
|----------|------|
| 1 | Higher `priority` value wins |
| 2 | Non-built-in packages beat built-in (when priority is equal) |
| 3 | First registered wins (with warning) |

> [!TIP]
> Shadowed plugins remain accessible via full class path: `plugins.get_class("endpoint", "my_pkg.endpoints:MyEndpoint")`

### API Reference

```python
# Runtime registration (testing)
plugins.register("endpoint", "test", TestEndpoint, priority=10)
plugins.reset_registry()  # Reset to initial state

# Dynamic enum generation
MyEndpointType = plugins.create_enum(PluginType.ENDPOINT, "MyEndpointType", module=__name__)

# Validation without importing
errors = plugins.validate_all(check_class=True)  # {category: [(name, error), ...]}

# Reverse lookup
name = plugins.find_registered_name(PluginType.ENDPOINT, ChatEndpoint)  # "chat"

# Package metadata
pkg = plugins.get_package_metadata("aiperf")  # PackageInfo(version, author, ...)
```

> **Type Safety**: `get_class()` returns typed results (e.g., `type[EndpointProtocol]`) with IDE autocomplete.

## Built-in Plugins Reference

### Endpoints

| Name | Class | Description |
|------|-------|-------------|
| `chat` | `ChatEndpoint` | OpenAI Chat Completions API |
| `chat_embeddings` | `ChatEmbeddingsEndpoint` | vLLM multimodal embeddings via chat API |
| `completions` | `CompletionsEndpoint` | OpenAI Completions API |
| `cohere_rankings` | `CohereRankingsEndpoint` | Cohere Reranking API |
| `embeddings` | `EmbeddingsEndpoint` | OpenAI Embeddings API |
| `hf_tei_rankings` | `HFTeiRankingsEndpoint` | HuggingFace TEI Rankings |
| `huggingface_generate` | `HuggingFaceGenerateEndpoint` | HuggingFace TGI |
| `image_generation` | `ImageGenerationEndpoint` | OpenAI Image Generation API |
| `image_retrieval` | `ImageRetrievalEndpoint` | NIM Image Retrieval (e.g., bounding-box detection) via /v1/infer |
| `nim_embeddings` | `NIMEmbeddingsEndpoint` | NVIDIA NIM Embeddings |
| `nim_rankings` | `NIMRankingsEndpoint` | NVIDIA NIM Rankings |
| `responses` | `ResponsesEndpoint` | OpenAI Responses API (multi-modal, streaming) via /v1/responses |
| `solido_rag` | `SolidoEndpoint` | Solido RAG Pipeline |
| `raw` | `RawEndpoint` | Raw payload passthrough for verbatim API replay |
| `template` | `TemplateEndpoint` | Template for custom endpoints |
| `video_generation` | `VideoGenerationEndpoint` | Text-to-video generation API |

### Timing Strategies

| Name | Class | Description |
|------|-------|-------------|
| `fixed_schedule` | `FixedScheduleStrategy` | Send requests at exact timestamps |
| `request_rate` | `RequestRateStrategy` | Send requests at specified rate |
| `user_centric_rate` | `UserCentricStrategy` | Each session acts as separate user |
| `agentic_replay` | `AgenticReplayStrategy` | Multi-turn trajectory replay (InferenceX AgentX-MVP) |

### Arrival Patterns

| Name | Class | Description |
|------|-------|-------------|
| `constant` | `ConstantIntervalGenerator` | Fixed intervals between requests |
| `poisson` | `PoissonIntervalGenerator` | Poisson process arrivals |
| `gamma` | `GammaIntervalGenerator` | Gamma distribution with tunable smoothness |
| `concurrency_burst` | `ConcurrencyBurstIntervalGenerator` | Send ASAP up to concurrency limit |

### Dataset Composers

| Name | Class | Description |
|------|-------|-------------|
| `synthetic` | `SyntheticDatasetComposer` | Generate synthetic conversations |
| `custom` | `CustomDatasetComposer` | Load from JSONL files |
| `synthetic_rankings` | `SyntheticRankingsDatasetComposer` | Generate ranking tasks |
| `public` | `PublicDatasetComposer` | Loads public benchmark datasets via registered public_dataset_loader plugins |

### UI Types

| Name | Class | Description |
|------|-------|-------------|
| `dashboard` | `AIPerfDashboardUI` | Rich terminal dashboard |
| `simple` | `TQDMProgressUI` | Simple tqdm progress bar |
| `none` | `NoUI` | Headless execution |

### Accuracy Benchmarks

| Name | Class | Description |
|------|-------|-------------|
| `mmlu` | `MMLUBenchmark` | Massive Multitask Language Understanding |
| `aime` | `AIMEBenchmark` | American Invitational Mathematics Examination |
| `aime24` | `AIME24Benchmark` | AIME 2024 competition problems |
| `aime25` | `AIME25Benchmark` | AIME 2025 competition problems |
| `hellaswag` | `HellaSwagBenchmark` | HellaSwag commonsense reasoning |
| `bigbench` | `BigBenchBenchmark` | BIG-Bench benchmark tasks |
| `math_500` | `Math500Benchmark` | MATH-500 problem set |
| `gpqa_diamond` | `GPQADiamondBenchmark` | GPQA Diamond graduate-level science |
| `lcb_codegeneration` | `LCBCodeGenerationBenchmark` | LiveCodeBench code generation |

### Accuracy Graders

| Name | Class | Description |
|------|-------|-------------|
| `exact_match` | `ExactMatchGrader` | Exact string matching |
| `math` | `MathGrader` | Mathematical expression evaluation |
| `multiple_choice` | `MultipleChoiceGrader` | Multiple choice answer extraction |
| `code_execution` | `CodeExecutionGrader` | Code execution and output comparison |

## Troubleshooting

### Plugin Not Found

```text
TypeNotFoundError: Type 'my_plugin' not found for category 'endpoint'.
```

**Solutions**:
1. Verify the plugin is registered in `plugins.yaml`
2. Check the entry point is defined in `pyproject.toml`
3. Reinstall the package: `pip install -e .`
4. Run `aiperf plugins --validate` to check for errors

### Module Import Errors

```text
ImportError: Failed to import module for endpoint:my_plugin
```

**Solutions**:
1. Verify the class path format: `module.path:ClassName`
2. Check all dependencies are installed
3. Verify the module is importable: `python -c "import module.path"`

### Class Not Found

```text
AttributeError: Class 'MyClass' not found
```

**Solutions**:
1. Verify the class name matches exactly (case-sensitive)
2. Ensure the class is exported from the module
3. Run `aiperf plugins --validate` for detailed error

### Conflict Resolution Issues

If your plugin is being shadowed by another:

1. Use higher priority: `priority: 10` in `plugins.yaml`
2. Access by full class path: `plugins.get_class("endpoint", "my_pkg.endpoints:MyEndpoint")`
3. Check `aiperf plugins` to see which packages are loaded
