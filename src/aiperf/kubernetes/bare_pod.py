# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Single bare-Pod rendering for high-concurrency benchmarks.

A JobSet deployment always creates a controller Pod plus one or more worker
Pods, so it cannot express "the whole benchmark in one Pod". This module
renders that shape: one ``kind: Pod`` running ``aiperf profile`` in
multiprocessing mode, with every worker and record processor as a child
process inside the single container.

The shape exists because a single node -- and therefore a single Slurm node or
a single Kubernetes Pod -- can hold at most one network namespace's worth of
concurrent outbound connections. Linux's default ephemeral port range
(``32768 60999`` on most distributions) is below the 50,000-connection AgentX
target, so the Pod must widen ``net.ipv4.ip_local_port_range`` before the
benchmark starts. Kubernetes exposes that sysctl as a *safe* Pod sysctl, which
is why this renderer sets it on the Pod's ``securityContext`` rather than
requiring a privileged init container.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from aiperf.common.enums import AIPerfLogLevel
from aiperf.common.environment import Environment
from aiperf.config.deployment import (
    DENIED_EXTRA_POD_SPEC_KEYS,
    DeploymentConfig,
    PodTemplateConfig,
)
from aiperf.config.loader.errors import ConfigurationError
from aiperf.kubernetes.constants import AIPerfLabels
from aiperf.kubernetes.environment import K8sEnvironment
from aiperf.kubernetes.jobset_helpers import (
    MMAP_CACHE_ENABLED_ENV,
    REMOTE_CACHE_ENV,
    REMOTE_CACHE_MOUNT_PATH,
    REMOTE_CACHE_VOLUME,
    build_security_context,
)
from aiperf.kubernetes.jobset_specs import (
    _POD_TEMPLATE_PASSTHROUGH,
    _build_init_containers,
    merge_pod_security_context,
)
from aiperf.plugin.enums import ServiceRunType, UIType

# The widest unprivileged range Linux allows: 1024-65535. Ports below 1024 are
# privileged, so this is the ceiling a single Pod's network namespace can offer.
DEFAULT_EPHEMERAL_PORT_START = 1024
DEFAULT_EPHEMERAL_PORT_END = 65535

# The Pod always claims the whole range. AgentX subagent fanout pushes
# in-flight requests above --concurrency, so sizing the range to the nominal
# lane count would strand the extra connections the workload is allowed to
# open.
MAX_BARE_POD_CONNECTIONS = DEFAULT_EPHEMERAL_PORT_END - DEFAULT_EPHEMERAL_PORT_START + 1

# AIPERF_HTTP_CONNECTION_LIMIT's own upper bound. The Pod raises the per-worker
# connector to this value rather than rejecting a high concurrency-per-worker
# ratio: the ratio is a planning estimate, not a runtime cap.
MAX_HTTP_CONNECTION_LIMIT = 65_000

BARE_POD_CONTAINER_NAME = "aiperf"
BARE_POD_RESULTS_HOLDER_NAME = "results-holder"
BARE_POD_CONFIG_FILE = "config.yaml"


@dataclass(frozen=True, slots=True)
class BarePodTopology:
    """Resolved single-Pod topology for one benchmark run."""

    total_workers: int
    """Worker processes spawned inside the Pod's single container."""

    record_processors: int
    """Record-processor processes spawned inside the same container."""

    max_concurrency: int
    """Peak phase concurrency the Pod must be able to hold open."""

    connections_per_worker: int
    """Peak concurrent requests each worker process may hold."""

    port_range_start: int
    """First port in the Pod's ephemeral range."""

    port_range_end: int
    """Last port in the Pod's ephemeral range."""

    @property
    def port_capacity(self) -> int:
        """Number of ephemeral ports the Pod may allocate."""
        return self.port_range_end - self.port_range_start + 1


def _max_phase_concurrency(phases: Any) -> int:
    """Return the largest concurrency declared by any phase."""
    values = [
        int(getattr(phase, "concurrency", 1) or 1)
        for phase in phases
        if getattr(phase, "concurrency", None) is not None
    ]
    return max(values, default=1)


def _resolve_port_range(
    required_connections: int,
    pod_template: PodTemplateConfig | None,
) -> tuple[int, int]:
    """Resolve the ephemeral port range, honoring a user-authored override.

    A user-supplied ``net.ipv4.ip_local_port_range`` is authoritative only when
    it is large enough; silently replacing it would discard a deliberate
    choice, while accepting a too-small range would fail mid-run with
    ``EADDRNOTAVAIL`` and no clue why.
    """
    start = DEFAULT_EPHEMERAL_PORT_START
    end = DEFAULT_EPHEMERAL_PORT_END

    authored = _authored_port_range(pod_template)
    if authored is None:
        return start, end

    authored_start, authored_end = authored
    if authored_end - authored_start + 1 < required_connections:
        raise ConfigurationError(
            "podTemplate.podSecurityContext.sysctls sets "
            f"net.ipv4.ip_local_port_range={authored_start} {authored_end} "
            f"({authored_end - authored_start + 1} ports), but this benchmark "
            f"needs at least {required_connections} concurrent outbound "
            "connections. Widen the range (for example '1024 65000') or reduce "
            "--concurrency."
        )
    return authored_start, authored_end


def _authored_port_range(
    pod_template: PodTemplateConfig | None,
) -> tuple[int, int] | None:
    """Read a user-authored ``ip_local_port_range`` sysctl, if present."""
    if pod_template is None:
        return None
    sysctls = pod_template.pod_security_context.get("sysctls")
    if not isinstance(sysctls, list):
        return None
    for entry in sysctls:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") != "net.ipv4.ip_local_port_range":
            continue
        value = entry.get("value")
        if not isinstance(value, str):
            continue
        parts = value.split()
        if len(parts) != 2:
            continue
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            continue
    return None


def resolve_bare_pod_topology(
    config: Any,
    total_workers: int,
    *,
    pod_template: PodTemplateConfig | None = None,
) -> BarePodTopology:
    """Resolve and validate the single-Pod worker topology.

    Args:
        config: Validated :class:`AIPerfConfig` for the benchmark.
        total_workers: Requested worker-process count inside the Pod.
        pod_template: Optional pod template carrying a user-authored sysctl
            override.

    Returns:
        The validated topology, including the ephemeral port range the Pod
        must apply.

    Raises:
        ConfigurationError: The requested concurrency cannot fit in one Pod's
            network namespace, or the per-worker connection budget exceeds the
            largest connector limit the Pod can configure.
    """
    if total_workers < 1:
        raise ConfigurationError("total_workers must be at least 1")

    max_concurrency = _max_phase_concurrency(config.benchmark.phases)
    # More workers than in-flight slots cannot increase throughput: the worker
    # manager caps itself at concurrency anyway. Clamp here so the manifest and
    # the runtime agree on the process count.
    effective_workers = min(total_workers, max_concurrency)
    connections_per_worker = max(1, math.ceil(max_concurrency / effective_workers))

    # The ratio is a planning estimate, not a runtime cap. AgentX subagent
    # fanout pushes in-flight requests above --concurrency, so the Pod raises
    # its connector limit instead of rejecting a high ratio.
    if connections_per_worker > MAX_HTTP_CONNECTION_LIMIT:
        raise ConfigurationError(
            f"--concurrency {max_concurrency} across {effective_workers} worker "
            f"processes needs {connections_per_worker} concurrent connections "
            f"per worker, above the largest configurable "
            f"AIPERF_HTTP_CONNECTION_LIMIT={MAX_HTTP_CONNECTION_LIMIT}. "
            f"Use at least "
            f"{math.ceil(max_concurrency / MAX_HTTP_CONNECTION_LIMIT)} workers."
        )

    if max_concurrency > MAX_BARE_POD_CONNECTIONS:
        raise ConfigurationError(
            f"--concurrency {max_concurrency} exceeds the {MAX_BARE_POD_CONNECTIONS} "
            "ephemeral ports a single Pod's network namespace can hold "
            f"({DEFAULT_EPHEMERAL_PORT_START}-{DEFAULT_EPHEMERAL_PORT_END}). "
            "Split the run across multiple Pods or lower --concurrency."
        )

    port_start, port_end = _resolve_port_range(max_concurrency, pod_template)

    runtime = config.benchmark.runtime
    # The 4-workers-per-processor default is sized for small runs. At 50,000
    # lanes the record pipeline is a real bottleneck, so large Pods get at
    # least 32 processors even when the ratio would ask for fewer.
    minimum_processors = 32 if effective_workers >= 32 else 1
    record_processors = runtime.record_processors or max(
        minimum_processors,
        math.ceil(effective_workers / Environment.RECORD.PROCESSOR_SCALE_FACTOR),
    )

    return BarePodTopology(
        total_workers=effective_workers,
        record_processors=record_processors,
        max_concurrency=max_concurrency,
        connections_per_worker=connections_per_worker,
        port_range_start=port_start,
        port_range_end=port_end,
    )


def bare_pod_sysctls(topology: BarePodTopology) -> list[dict[str, str]]:
    """Return the Pod sysctls required to hold the requested concurrency."""
    return [
        {
            "name": "net.ipv4.ip_local_port_range",
            "value": f"{topology.port_range_start} {topology.port_range_end}",
        }
    ]


def apply_bare_pod_runtime_config(
    benchmark_dict: dict[str, Any],
    topology: BarePodTopology,
) -> None:
    """Rewrite the benchmark runtime for single-container multiprocessing.

    The Kubernetes JobSet path forces ``service_run_type=kubernetes`` and wires
    cross-Pod ZMQ/API endpoints. A bare Pod runs the ordinary ``aiperf profile``
    stack, so those settings must be removed rather than inherited.

    Args:
        benchmark_dict: The ``benchmark`` mapping from an AIPerfConfig dump.
        topology: Resolved single-Pod topology.
    """
    benchmark_dict.setdefault("artifacts", {})
    benchmark_dict["artifacts"]["dir"] = "/results"

    runtime = benchmark_dict.setdefault("runtime", {})
    runtime.update(
        {
            "service_run_type": str(ServiceRunType.MULTIPROCESSING),
            "ui": str(UIType.NONE),
            "workers": topology.total_workers,
            "record_processors": topology.record_processors,
            "workers_min": None,
            "workers_per_pod": None,
            "record_processors_per_pod": None,
            "dataset_api_base_url": None,
            "api_port": None,
            "api_host": None,
        }
    )

    benchmark_dict.setdefault("logging", {})
    benchmark_dict["logging"].setdefault("level", str(AIPerfLogLevel.INFO))


def _bare_pod_labels(name: str, job_id: str | None = None) -> dict[str, str]:
    """Stable labels shared by the ConfigMap and Pod."""
    labels = {
        AIPerfLabels.APP_KEY: AIPerfLabels.APP_VALUE,
        AIPerfLabels.JOB_ID: job_id or name,
    }
    if name:
        labels[AIPerfLabels.NAME] = name
    return labels


def _bare_pod_volumes(
    configmap_name: str, pod_template: PodTemplateConfig
) -> list[dict[str, Any]]:
    """Volumes for a single-container benchmark Pod."""
    volumes: list[dict[str, Any]] = [
        {"name": "config", "configMap": {"name": configmap_name}},
        {"name": "results", "emptyDir": {}},
        {"name": "tmp", "emptyDir": {}},
        {"name": "tokenizer-cache", "emptyDir": {}},
        {"name": REMOTE_CACHE_VOLUME, "emptyDir": {}},
    ]
    volumes.extend(pod_template.volumes)
    return volumes


def _bare_pod_volume_mounts(
    pod_template: PodTemplateConfig,
) -> list[dict[str, Any]]:
    """Mount points for a single-container benchmark Pod."""
    mounts: list[dict[str, Any]] = [
        {
            "name": "config",
            "mountPath": K8sEnvironment.JOBSET.CONFIG_MOUNT_PATH,
            "readOnly": True,
        },
        {"name": "results", "mountPath": "/results"},
        {"name": "tmp", "mountPath": "/tmp"},
        {"name": "tokenizer-cache", "mountPath": "/tmp/hf"},
        {"name": REMOTE_CACHE_VOLUME, "mountPath": REMOTE_CACHE_MOUNT_PATH},
    ]
    mounts.extend(pod_template.volume_mounts)
    return mounts


def _bare_pod_env(
    pod_template: PodTemplateConfig | None,
    topology: BarePodTopology,
) -> list[dict[str, Any]]:
    """Environment for the benchmark container.

    Deliberately minimal: the JobSet env builder injects cross-Pod controller
    addresses and operator markers that a multiprocessing run must not see.

    The registration timeout scales with the process count. Spawning 100
    workers plus 32 record processors takes far longer than the 10-second
    default, and a worker that misses the window is killed as "died before
    registering" even though startup was healthy -- the failure the first
    100-worker bare-Pod run hit.
    """
    registration_timeout = max(60.0, float(topology.total_workers) * 1.5)
    defaults: list[dict[str, Any]] = [
        {"name": "HF_HOME", "value": "/tmp/hf"},
        {"name": "AIPERF_UI_REALTIME_METRICS_ENABLED", "value": "false"},
        # The cross-run mmap cache defaults to ~/.cache, which is on the
        # read-only root filesystem here. The JobSet path disables it for the
        # same reason; without this the AgentX trace dataset fails during
        # configuration, before a single request is sent.
        {"name": MMAP_CACHE_ENABLED_ENV, "value": "false"},
        {"name": REMOTE_CACHE_ENV, "value": REMOTE_CACHE_MOUNT_PATH},
        # Subagent fanout can put more requests in flight than --concurrency.
        # Raising the connector ceiling keeps the extra connections legal
        # instead of queueing them behind the 2,500 default.
        {
            "name": "AIPERF_HTTP_CONNECTION_LIMIT",
            "value": str(MAX_HTTP_CONNECTION_LIMIT),
        },
        {
            "name": "AIPERF_SERVICE_REGISTRATION_TIMEOUT",
            "value": str(math.ceil(registration_timeout)),
        },
        {
            "name": "AIPERF_SERVICE_REGISTRATION_MAX_ATTEMPTS",
            "value": str(max(10, math.ceil(registration_timeout) + 1)),
        },
    ]
    # Explicit podTemplate.env wins, and keying by name prevents the duplicate
    # entries that would otherwise let the last copy win by accident.
    env_by_name: dict[str, dict[str, Any]] = {}
    if pod_template is not None:
        for item in pod_template.env:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                env_by_name[item["name"]] = item
    for item in defaults:
        env_by_name.setdefault(item["name"], item)
    return list(env_by_name.values())


def _bare_pod_resources(
    config: Any,
    topology: BarePodTopology,
    deploy_config: DeploymentConfig,
) -> dict[str, dict[str, str]] | None:
    """Size the single container from the shared memory estimator.

    The estimator models a worker Pod and the controller Pod separately. A bare
    Pod runs both in one container, so the request is their sum. CPU is a
    coarse I/O-bound allowance: four workers per core, floored at 4 cores so
    the controller's 50,000-lane bookkeeping is not starved.
    """
    if deploy_config.resource_mode == "none":
        return None

    from aiperf.kubernetes.memory_estimator import estimate_memory

    # The estimator's Kubernetes path defaults to one record processor per
    # worker; the bare-Pod config runs one per four. Pin the rendered count so
    # the request matches the process topology instead of over-reserving.
    estimate_config = config.model_copy(deep=True)
    estimate_config.benchmark.runtime.record_processors = topology.record_processors
    estimate_config.benchmark.runtime.record_processors_per_pod = (
        topology.record_processors
    )
    estimate = estimate_memory(
        estimate_config,
        total_workers=topology.total_workers,
        workers_per_pod=topology.total_workers,
        connections_per_worker=topology.connections_per_worker,
    )
    # The controller estimate is dominated by metric-array capacity for the
    # whole run, which a single container shares with the workers; charging it
    # verbatim would make the Pod unschedulable on any real node. Reserve a
    # fixed 8 GiB for the controller's 50,000-lane bookkeeping and size the
    # rest from the worker estimate, which is the part that scales with
    # in-flight requests.
    memory_mib = estimate.worker_pod.total_peak_mib + 8192
    memory_gi = max(1, math.ceil(memory_mib / 1024))
    cpu_cores = max(4, math.ceil(topology.total_workers / 4))

    resources: dict[str, dict[str, str]] = {
        "requests": {"cpu": str(cpu_cores), "memory": f"{memory_gi}Gi"}
    }
    if deploy_config.resource_mode == "guaranteed":
        resources["limits"] = dict(resources["requests"])
    return resources


def build_bare_pod_manifests(
    *,
    config: Any,
    kube_options: Any,
    name: str,
    namespace: str,
    deploy_config: DeploymentConfig,
    topology: BarePodTopology,
) -> list[dict[str, Any]]:
    """Render the ConfigMap and single Pod for a bare-Pod benchmark.

    Args:
        config: Validated :class:`AIPerfConfig`.
        kube_options: CLI Kubernetes options (name, image, placement).
        name: Benchmark name (DNS label).
        namespace: Target namespace.
        deploy_config: Deployment settings (image, pod template, resources).
        topology: Resolved single-Pod topology.

    Returns:
        ``[ConfigMap, Pod]`` in creation order.
    """
    import io

    import ruamel.yaml

    from aiperf.kubernetes.resources import ConfigMapSpec

    pod_template = deploy_config.pod_template
    job_id = name
    configmap_name = f"aiperf-{name}-config"

    config_dict = config.model_dump(
        mode="json",
        exclude_unset=True,
        exclude_none=True,
    )
    benchmark_dict = config_dict.get("benchmark")
    if not isinstance(benchmark_dict, dict):
        raise ConfigurationError(
            "Bare Pod rendering requires a benchmark config envelope"
        )
    apply_bare_pod_runtime_config(benchmark_dict, topology)
    config_dict = _prune_none(config_dict)

    yaml = ruamel.yaml.YAML()
    yaml.default_flow_style = False
    stream = io.StringIO()
    yaml.dump(config_dict, stream)

    configmap = ConfigMapSpec(
        name=configmap_name,
        namespace=namespace,
        data={BARE_POD_CONFIG_FILE: stream.getvalue()},
        labels=_bare_pod_labels(kube_options.name or name, job_id=job_id),
    )
    configmap.validate_size()

    pod_spec: dict[str, Any] = {
        "restartPolicy": "Never",
        "containers": [],
        "volumes": _bare_pod_volumes(configmap_name, pod_template),
    }

    security_context = merge_pod_security_context(pod_template.pod_security_context)
    # Preserve every user-authored sysctl; only the port range is ours to own,
    # because resolve_bare_pod_topology already validated an authored value and
    # a missing one would fail mid-run with EADDRNOTAVAIL.
    authored_sysctls = [
        entry
        for entry in security_context.get("sysctls") or []
        if entry.get("name") != "net.ipv4.ip_local_port_range"
    ]
    security_context["sysctls"] = [*authored_sysctls, *bare_pod_sysctls(topology)]
    pod_spec["securityContext"] = security_context

    if pod_template.init_containers:
        pod_spec["initContainers"] = _build_init_containers(pod_template, job_id)

    for attr, key in _POD_TEMPLATE_PASSTHROUGH:
        value = getattr(pod_template, attr)
        if value:
            pod_spec[key] = value
    if pod_template.image_pull_secrets:
        pod_spec["imagePullSecrets"] = list(pod_template.image_pull_secrets)
    if pod_template.share_process_namespace:
        pod_spec["shareProcessNamespace"] = True
    pod_spec["terminationGracePeriodSeconds"] = (
        pod_template.termination_grace_period_seconds
        if pod_template.termination_grace_period_seconds is not None
        else 120
    )
    if pod_template.extra_pod_spec:
        pod_spec.update(
            {
                key: value
                for key, value in pod_template.extra_pod_spec.items()
                if key not in DENIED_EXTRA_POD_SPEC_KEYS
            }
        )

    container: dict[str, Any] = {
        "name": BARE_POD_CONTAINER_NAME,
        "image": deploy_config.image,
        "command": ["aiperf"],
        "args": [
            "profile",
            "--config",
            f"{K8sEnvironment.JOBSET.CONFIG_MOUNT_PATH}/{BARE_POD_CONFIG_FILE}",
        ],
        "env": _bare_pod_env(pod_template, topology),
        "volumeMounts": _bare_pod_volume_mounts(pod_template),
        "securityContext": build_security_context(pod_template, job_id),
    }
    if deploy_config.image_pull_policy is not None:
        container["imagePullPolicy"] = str(deploy_config.image_pull_policy)

    resources = _bare_pod_resources(config, topology, deploy_config)
    if resources is not None:
        container["resources"] = resources

    pod_spec["containers"].append(container)

    # A completed Pod cannot be `kubectl cp`'d from: the copy uses exec, and
    # the benchmark container has already exited. Keep a tiny holder alive on
    # the results volume so the artifacts remain reachable after the run.
    results_holder: dict[str, Any] = {
        "name": BARE_POD_RESULTS_HOLDER_NAME,
        "image": deploy_config.image,
        "command": ["python", "-c", "import time; time.sleep(10**9)"],
        "volumeMounts": [{"name": "results", "mountPath": "/results"}],
        "securityContext": build_security_context(pod_template, job_id),
    }
    if deploy_config.resource_mode != "none":
        results_holder["resources"] = {"requests": {"cpu": "10m", "memory": "32Mi"}}
    pod_spec["containers"].append(results_holder)

    labels = dict(pod_template.labels)
    labels.update(_bare_pod_labels(kube_options.name or name, job_id=job_id))
    metadata: dict[str, Any] = {
        "name": f"aiperf-{name}",
        "namespace": namespace,
        "labels": labels,
    }
    if pod_template.annotations:
        metadata["annotations"] = dict(pod_template.annotations)

    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": metadata,
        "spec": pod_spec,
    }

    return [configmap.to_k8s_manifest(), pod]


def _prune_none(value: Any) -> Any:
    """Drop ``None`` leaves so the rendered config stays minimal."""
    if isinstance(value, dict):
        return {
            key: _prune_none(child) for key, child in value.items() if child is not None
        }
    if isinstance(value, list):
        return [_prune_none(child) for child in value]
    return value
