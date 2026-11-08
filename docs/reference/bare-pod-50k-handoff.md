---
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
sidebar-title: Bare Pod 50k AgentX Handoff
---

# Bare Pod 50k AgentX Handoff

State as of 2026-11-08. Branch `ajc/bare-pod-50k-agentx`, commit `b263e099b`,
pushed to `ajcasagrande/aiperf`.

## What landed

- `aiperf kube generate --bare-pod` / `aiperf kube profile --bare-pod`: one
  ConfigMap plus one `kind: Pod`, running `aiperf profile --config` in
  multiprocessing mode. No operator, JobSet, or CRD.
- 50k topology: 100 workers, 32 record processors, 500 connections/worker.
- The Pod always claims `net.ipv4.ip_local_port_range=1024 65535` (64,512
  ports) and sets `AIPERF_HTTP_CONNECTION_LIMIT=65000`, because AgentX
  subagent fanout exceeds the nominal concurrency.
- `results-holder` sidecar keeps `/results` reachable after the benchmark
  container exits; `kube profile --bare-pod` waits on the container's
  `state.terminated.exit_code`, not the Pod phase.
- Dataset caches moved off the read-only root filesystem:
  `AIPERF_DATASET_MMAP_CACHE_ENABLED=false`, remote cache on
  `/aiperf/remote-cache`.
- Registration timeout scales with worker count (`150s` / `151` attempts at
  100 workers).
- `--agentx-fast`: mandatory snapshot primers only, 1,200 s profile,
  `submission_valid=false`.
- `--warmup-requests-per-lane 0` allowed (primers only), with the
  `total_expected_requests` zero-count backstop fixed.

## Receipts

- 116 focused tests pass; 4,311 kube unit tests; 3,668 property/scenario/config
  tests.
- 512 concurrency against a Rust mock calibrated to the MLPerf DS4.1-Flash /
  Vera Rubin headline: TTFT min 301.89 ms, ITL min 9.55 ms, 104.72 tok/s/user,
  0 errors.
- 50k concurrency, 100 workers, default ephemeral range: 44,619 in flight,
  28,233 client connections (exactly the 28,232-port default range), 0 errors.
  This is the proof the default range is the wall.
- 50k with the official `semianalysisai/cc-traces-weka-062126` corpus: dataset
  downloaded (1.8 GB); the Pod's exact `aiperf profile --config` payload is
  ready to run.

## Open work

1. **Finish the official-corpus 50k run** and record the profiling metrics.
   The dataset's first load generates the 393-example train split (one-time,
   then cached under `HF_HOME`).
2. **Measure the drain speedup.** The controller's single `timing_manager`
   event loop is the bottleneck (145 ms overhead every ~2 s). Candidate
   levers, already wired into `/tmp/pod-config-fast.yaml`:
   - `AIPERF_SERVICE_CREDIT_PROGRESS_REPORT_INTERVAL=30` (the 2 s progress
     report scans all 50k lanes)
   - `AIPERF_SERVICE_EVENT_LOOP_HEALTH_ENABLED=false`
   - `--log-level WARNING`
   - `--stats-interval 0`
   - `--no-server-metrics`
   - `--slice-duration 3600`
   Compare the warmup `returned/elapsed` rate against the baseline (~88/s).
3. **Sharded JSONL** (next task): branch `origin/ajc/unify-shard-writer-mixin`
   adds `post_processors/shard_writer.py` and
   `record_shard_jsonl_writer.py`, replacing `record_export_jsonl_writer.py`.
   Each RecordProcessor writes `records_shards/records_{id}.jsonl`; an
   aggregator concatenates at completion.
4. **Real cluster run.** This sandbox has no Kubernetes API or container
   runtime (no Docker, containerd, podman, kind, k3s, minikube), so the Pod
   cannot be scheduled here. Apply the generated manifest where a kubeconfig
   is available.

## Exact commands

Generate the Pod with the official corpus:

```bash
aiperf kube generate --bare-pod --namespace bench \
  --scenario agentx \
  --public-dataset semianalysis_cc_traces_weka_062126 \
  --model deepseek-v4.1-flash \
  --url <endpoint> \
  --concurrency 50000 --total-workers 100 \
  --warmup-requests-per-lane 0 \
  --benchmark-duration 60 \
  --export-level summary \
  --unsafe-override \
  --image <image> > bare-pod.yaml
```

Local execution of the Pod's payload (no cluster):

```bash
HF_HOME=<writable-hf-home> \
AIPERF_SERVICE_REGISTRATION_TIMEOUT=150 \
AIPERF_SERVICE_REGISTRATION_MAX_ATTEMPTS=151 \
AIPERF_DATASET_MMAP_CACHE_ENABLED=false \
AIPERF_DATASET_REMOTE_CACHE_DIR=/tmp/remote-cache \
aiperf profile --config pod-config.yaml
```

## Environment caveats

- The sandbox's `/proc/sys/net/ipv4/ip_local_port_range` is read-only
  (`32768 60999`). Local 50k runs use three loopback destination IPs
  (`127.0.0.1/2/3:8020`) so the ephemeral port tuple space is large enough.
  The Pod sets the sysctl instead and needs one destination.
- The Rust mock server must be built in release mode:
  `cargo build --release -p aiperf-mock-server` from `NVIDIA-dev/aiperf-rs`,
  then run with `--fast` for capacity tests.
- The 45,000-primer count observed with the 10-trace fixture is the fixture's
  single-turn trace (`trace_01_n1`, duration 0): its 5,000 lanes have
  `next_turn_index == 0` and contribute no primer. The official corpus has
  fewer zero-duration traces.
