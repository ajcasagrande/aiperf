# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Kube generate command: output Kubernetes YAML manifests to stdout."""

from __future__ import annotations

import asyncio
import math
import sys
from typing import TYPE_CHECKING, Annotated, Any

from cyclopts import App, Parameter

from aiperf.config import AIPerfConfig
from aiperf.config.flags.cli_config import KubeCLIConfig
from aiperf.config.kube import KubeOptions
from aiperf.kubernetes.cr_refs import AIPERF_API_VERSION

if TYPE_CHECKING:
    from aiperf.config.deployment import DeploymentConfig
    from aiperf.kubernetes.bare_pod import BarePodTopology

app = App(name="generate")

AIPERF_KIND = "AIPerfJob"
AIPERF_SWEEP_KIND = "AIPerfSweep"


def _choose_kind(envelope: AIPerfConfig) -> str:
    """Pick the CR kind matching the envelope's required execution path."""
    from aiperf.kubernetes.sweep_routing import requires_sweep_controller

    return AIPERF_SWEEP_KIND if requires_sweep_controller(envelope) else AIPERF_KIND


def _reject_orchestrated_direct_workload(config: AIPerfConfig) -> None:
    """Reject workloads that raw JobSet manifests cannot execute faithfully."""
    from aiperf.kubernetes.sweep_routing import requires_sweep_controller

    if not requires_sweep_controller(config):
        return

    from aiperf import cli_utils

    cli_utils.raise_startup_error_and_exit(
        "`--no-operator` can execute only one benchmark run; it cannot own "
        "parameter-sweep or multi-run orchestration.\n"
        "Use `aiperf kube generate --operator ...` to emit an AIPerfSweep CR, "
        "or submit it directly with `aiperf kube sweep ...`.",
        title="Kubernetes Operator Required",
    )


def _reject_orchestrated_bare_pod_workload(config: AIPerfConfig) -> None:
    """Reject workloads a single bare Pod cannot execute faithfully."""
    from aiperf.kubernetes.sweep_routing import requires_sweep_controller

    if not requires_sweep_controller(config):
        return

    from aiperf import cli_utils

    cli_utils.raise_startup_error_and_exit(
        "`--bare-pod` renders exactly one Pod running one benchmark; it cannot "
        "own parameter-sweep or multi-run orchestration.\n"
        "Use `aiperf kube generate --operator ...` to emit an AIPerfSweep CR, "
        "or submit it directly with `aiperf kube sweep ...`.",
        title="Single Benchmark Required",
    )


def _resolve_bare_pod_workers(config: AIPerfConfig, kube_options: KubeOptions) -> int:
    """Resolve the worker-process count for the Pod's single container.

    An explicit ``--total-workers`` owns the count. Otherwise
    ``benchmark.runtime.workers`` from YAML is canonical. A bare Pod has no
    pod-divisibility constraint, so the ``KubeOptions`` default is used
    verbatim when neither is authored.
    """
    if "total_workers" in kube_options.model_fields_set:
        return kube_options.total_workers
    configured = config.benchmark.runtime.workers
    if isinstance(configured, int) and not isinstance(configured, bool):
        return configured
    return kube_options.total_workers


def _print_manifests_yaml(manifests: list[dict[str, Any]]) -> None:
    """Emit all manifests as a multi-document YAML stream to stdout."""
    import ruamel.yaml

    yaml = ruamel.yaml.YAML()
    yaml.default_flow_style = False
    for i, manifest in enumerate(manifests):
        if i > 0:
            sys.stdout.write("---\n")
        yaml.dump(manifest, sys.stdout)


def _print_bare_pod_summary(
    config: AIPerfConfig,
    topology: BarePodTopology,
    deploy_config: DeploymentConfig,
) -> None:
    """Narrate the single-Pod sizing on stderr, leaving stdout parseable."""
    from aiperf.kubernetes import console as kube_console

    kube_console.stderr_console.print(
        "Bare Pod sizing: "
        f"{topology.total_workers} workers, "
        f"{topology.record_processors} record processors, "
        f"{topology.max_concurrency} peak concurrent requests "
        f"({topology.connections_per_worker} per worker), "
        f"ephemeral ports {topology.port_range_start}-{topology.port_range_end}.",
        highlight=False,
    )
    if deploy_config.resource_mode == "none":
        return

    from aiperf.kubernetes.memory_estimator import estimate_memory

    try:
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
    except ValueError as exc:
        kube_console.stderr_console.print(
            f"Memory estimation skipped: {exc}", highlight=False
        )
        return
    # Mirrors the manifest sizing: worker estimate plus the fixed controller
    # reserve for the whole run's metric-array bookkeeping.
    memory_mib = estimate.worker_pod.total_peak_mib + 8192
    kube_console.stderr_console.print(
        f"Estimated memory: ~{math.ceil(memory_mib / 1024)} GiB "
        "(worker estimate plus 8 GiB controller reserve).",
        highlight=False,
    )


def _dump_bare_pod_manifests(
    *,
    config: AIPerfConfig,
    kube_options: KubeOptions,
    name: str,
    namespace: str,
    deployment_spec: dict[str, Any] | None = None,
) -> None:
    """Render a ConfigMap and one Pod for a single-container benchmark."""
    from aiperf.cli_commands.kube._kube_common import pin_default_direct_image
    from aiperf.kubernetes.bare_pod import (
        build_bare_pod_manifests,
        resolve_bare_pod_topology,
    )

    if deployment_spec is None:
        deploy_config = kube_options.to_deployment_config()
    else:
        from aiperf.kubernetes.spec_converter import extract_deployment_config

        deploy_config = extract_deployment_config(deployment_spec)
    pin_default_direct_image(deploy_config)

    total_workers = _resolve_bare_pod_workers(config, kube_options)
    topology = resolve_bare_pod_topology(
        config, total_workers, pod_template=deploy_config.pod_template
    )
    manifests = build_bare_pod_manifests(
        config=config,
        kube_options=kube_options,
        name=name,
        namespace=namespace,
        deploy_config=deploy_config,
        topology=topology,
    )
    _print_manifests_yaml(manifests)
    _print_bare_pod_summary(config, topology, deploy_config)


def _ensure_sweep_block(spec: dict[str, Any], config: AIPerfConfig) -> None:
    """Add a one-cell carrier when only ``multiRun`` requires orchestration."""
    if config.sweep is not None or spec.get("sweep") is not None:
        return
    from aiperf.kubernetes.sweep_routing import one_cell_sweep

    spec["sweep"] = one_cell_sweep(convergence=config.multi_run.convergence is not None)


def _build_sweep_spec(
    config: AIPerfConfig, kube_options: KubeOptions
) -> dict[str, Any]:
    """Build a flat AIPerfSweep CR spec from an envelope-shaped AIPerfConfig.

    Mirrors :meth:`KubeOptions.to_crd_spec` (used for AIPerfJob) while
    validating the sweep-specific envelope. Output is the flat envelope shape
    AIPerfSweepSpec expects — no template wrapping.
    """
    import math

    envelope = config.model_dump(
        mode="json", by_alias=True, exclude_unset=True, exclude_none=True
    )
    kube_options.apply_total_workers_override(envelope)
    if config._raw_envelope is not None:
        from aiperf.kubernetes.spec_converter import restore_jinja_templates

        envelope = restore_jinja_templates(envelope, config._raw_envelope)
    benchmark = envelope.pop("benchmark")

    dc = kube_options.to_deployment_config()
    from aiperf.common.endpoint_credentials import (
        validate_kubernetes_credential_transport,
    )

    validate_kubernetes_credential_transport(
        config.benchmark.endpoint,
        dc.pod_template.env,
        datasets=config.benchmark.datasets,
    )
    dc_dict = dc.model_dump(
        mode="json", by_alias=True, exclude_unset=True, exclude_none=True
    )
    if (
        "total_workers" in kube_options.model_fields_set
        and kube_options.total_workers > 0
    ):
        concurrency = max(
            (
                getattr(phase, "concurrency", 1) or 1
                for phase in config.benchmark.phases
            ),
            default=1,
        )
        dc_dict["connectionsPerWorker"] = max(
            1, math.ceil(concurrency / kube_options.total_workers)
        )

    sweep_dict = envelope.get("sweep")
    if (
        isinstance(sweep_dict, dict)
        and "type" not in sweep_dict
        and config.sweep is not None
    ):
        # Direct/programmatic configs can omit a defaulted discriminator from
        # their authored field set. The CRD union still requires the tag.
        sweep_dict["type"] = type(config.sweep).model_fields["type"].default

    spec = {"benchmark": benchmark, **envelope, **dc_dict}
    _ensure_sweep_block(spec, config)
    return spec


def _resolve_spec_and_name(
    cli_config: KubeCLIConfig,
    kube_options: KubeOptions,
):
    """Return (spec, config, name) from either an AIPerfJob CR file or CLI flags.

    A parameter sweep or multi-run workload is built for AIPerfSweep; an
    ordinary single run is built for AIPerfJob. Remote dataset references are
    pinned on this machine first; that calls asyncio.run, so the async command
    runs this in a worker thread.
    """
    from aiperf.cli_commands.kube.profile import (
        _build_cr_spec_and_config,
        _resolve_config,
        _try_load_aiperfjob_cr,
        generate_benchmark_name,
    )

    config_file = cli_config.config_file
    cr_raw = _try_load_aiperfjob_cr(config_file) if config_file is not None else None
    if cr_raw is not None:
        # CR format: use spec as primary benchmark config; CLI K8s flags overlay
        spec, config = _build_cr_spec_and_config(
            cr_raw, kube_options, cli_config=cli_config
        )
        from aiperf.kubernetes.sweep_routing import requires_sweep_controller

        if requires_sweep_controller(config):
            _ensure_sweep_block(spec, config)
        cr_name = cr_raw.get("metadata", {}).get("name")
        name = kube_options.name or cr_name or generate_benchmark_name(config)
    else:
        config = _resolve_config(cli_config, config_file)
        from aiperf.kubernetes.remote_datasets import (
            pin_remote_datasets_for_kubernetes,
        )
        from aiperf.kubernetes.sweep_routing import requires_sweep_controller

        sweep = requires_sweep_controller(config)
        pin_remote_datasets_for_kubernetes(config.benchmark, sweep=sweep)
        if sweep:
            spec = _build_sweep_spec(config, kube_options)
        else:
            spec = kube_options.to_crd_spec(config)
        name = kube_options.name or generate_benchmark_name(config)
    from aiperf.kubernetes.remote_datasets import report_remote_dataset_checks

    report_remote_dataset_checks(config.benchmark, spec)
    return spec, config, name


def _dump_raw_manifests(
    *,
    config,
    kube_options: KubeOptions,
    name: str,
    namespace: str,
    yaml,
    deployment_spec: dict[str, Any] | None = None,
):
    """Apply k8s runtime config and write raw manifests (RBAC, ConfigMap, JobSet)."""
    from aiperf.cli_commands.kube._kube_common import (
        pin_default_direct_image,
        resolve_total_workers,
    )
    from aiperf.config import AIPerfConfig
    from aiperf.kubernetes.environment import K8sEnvironment
    from aiperf.kubernetes.resources import KubernetesDeployment
    from aiperf.kubernetes.spec_converter import (
        apply_k8s_runtime_config,
        apply_worker_config,
    )

    config_dict = config.model_dump(
        mode="python",
        exclude_unset=True,
        exclude_none=True,
        context={"include_secrets": True},
    )
    benchmark_dict = config_dict.get("benchmark", {})
    apply_k8s_runtime_config(benchmark_dict, name, namespace)
    config_dict["benchmark"] = benchmark_dict
    config = AIPerfConfig.model_validate(config_dict)

    if deployment_spec is None:
        deploy_config = kube_options.to_deployment_config()
    else:
        from aiperf.kubernetes.spec_converter import extract_deployment_config

        deploy_config = extract_deployment_config(deployment_spec)
    pin_default_direct_image(deploy_config)
    # Longer TTL without operator — pods must stay alive for manual
    # results retrieval via `aiperf kube results`.
    ttl_authored_in_spec = deployment_spec is not None and any(
        key in deployment_spec
        for key in ("ttlSecondsAfterFinished", "ttl_seconds_after_finished")
    )
    if "ttl_seconds" not in kube_options.model_fields_set and not ttl_authored_in_spec:
        deploy_config.ttl_seconds_after_finished = (
            K8sEnvironment.JOBSET.DIRECT_MODE_TTL_SECONDS
        )
    concurrency = max(
        (getattr(phase, "concurrency", 1) or 1 for phase in config.benchmark.phases),
        default=1,
    )
    total_workers = resolve_total_workers(
        kube_options,
        concurrency=concurrency,
        connections_per_worker=deploy_config.connections_per_worker,
        configured_workers=config.benchmark.runtime.workers,
        workers_per_pod=config.benchmark.runtime.workers_per_pod,
    )
    num_pods = apply_worker_config(config, total_workers)

    deployment = KubernetesDeployment(
        job_id=name,
        namespace=namespace,
        worker_replicas=num_pods,
        config=config,
        deployment=deploy_config,
    )
    from aiperf.common.endpoint_credentials import (
        validate_kubernetes_credential_transport,
    )

    validate_kubernetes_credential_transport(
        config.benchmark.endpoint,
        deploy_config.pod_template.env,
        datasets=config.benchmark.datasets,
    )

    manifests = deployment.get_all_manifests()

    for i, manifest in enumerate(manifests):
        if i > 0:
            sys.stdout.write("---\n")
        yaml.dump(manifest, sys.stdout)
    return config


def _print_memory_estimate(config, kube_options: KubeOptions, spec) -> None:
    """Display the shared memory estimate without contaminating YAML stdout."""
    from aiperf.cli_commands.kube._kube_common import print_memory_estimate

    print_memory_estimate(config, kube_options, spec)


@app.default
async def generate(
    *,
    cli_config: KubeCLIConfig,
    kube_options: KubeOptions | None = None,
    operator: Annotated[
        bool,
        Parameter(
            name="--operator",
            negative=(),
            help="Output an AIPerfJob or AIPerfSweep CR (requires the operator).",
        ),
    ] = False,
    no_operator: Annotated[
        bool,
        Parameter(
            name="--no-operator",
            negative=(),
            help="Output raw K8s manifests (Namespace, RBAC, ConfigMap, JobSet).",
        ),
    ] = False,
    bare_pod: Annotated[
        bool,
        Parameter(
            name="--bare-pod",
            negative=(),
            help="Output one Pod running the whole benchmark (no operator, no JobSet).",
        ),
    ] = False,
) -> None:
    """Generate Kubernetes YAML manifests for an AIPerf benchmark.

    Specify --operator to output the matching workload CR (AIPerfJob for one
    run, AIPerfSweep for parameter sweeps and multi-run workloads),
    --no-operator to output raw manifests (Namespace, RBAC, ConfigMap, JobSet)
    that work without the operator, or --bare-pod to output a single Pod that
    runs every worker and record processor in one container.

    Examples:
        # Generate the matching operator workload CR
        aiperf kube generate --operator --model Qwen/Qwen3-0.6B --url localhost:8000 --image aiperf:latest

        # Generate raw manifests (no operator needed)
        aiperf kube generate --no-operator --model Qwen/Qwen3-0.6B --url localhost:8000 --image aiperf:latest

        # Generate a single high-concurrency Pod
        aiperf kube generate --bare-pod --concurrency 50000 --total-workers 100 --model Qwen/Qwen3-0.6B --url localhost:8000 --image aiperf:latest

        # Pipe directly to kubectl
        aiperf kube generate --no-operator ... | kubectl apply -f -
    """
    from aiperf import cli_utils

    if bare_pod and (operator or no_operator):
        conflicting = "--operator" if operator else "--no-operator"
        cli_utils.raise_startup_error_and_exit(
            f"Cannot use both --bare-pod and {conflicting}: choose one output form",
            title="Error Generating Kubernetes Manifests",
        )
    if not operator and not no_operator and not bare_pod:
        cli_utils.raise_startup_error_and_exit(
            "Specify --operator (AIPerfJob CR), --no-operator (raw manifests), "
            "or --bare-pod (single Pod)",
            title="Error Generating Kubernetes Manifests",
        )
    if operator and no_operator:
        cli_utils.raise_startup_error_and_exit(
            "Cannot use both --operator and --no-operator",
            title="Error Generating Kubernetes Manifests",
        )
    import ruamel.yaml

    from aiperf.kubernetes import console as kube_console

    kube_options = kube_options or KubeOptions()
    # stdout carries only the YAML; every log record goes to stderr.
    with (
        cli_utils.exit_on_error(title="Error Generating Kubernetes Manifests"),
        kube_console.machine_readable_stdout(),
    ):
        from aiperf.kubernetes.cli_helpers import resolve_benchmark_namespace

        spec, config, name = await asyncio.to_thread(
            _resolve_spec_and_name, cli_config, kube_options
        )
        # Offline rendering still refuses to guess: a manifest whose namespace
        # was invented here would apply somewhere the author never named.
        namespace = resolve_benchmark_namespace(
            kube_options.namespace,
            kube_options.kubeconfig,
            kube_options.kube_context,
        )

        yaml = ruamel.yaml.YAML()
        yaml.default_flow_style = False

        if bare_pod:
            _reject_orchestrated_bare_pod_workload(config)
            _dump_bare_pod_manifests(
                config=config,
                kube_options=kube_options,
                name=name,
                namespace=namespace,
                deployment_spec=spec,
            )
        elif no_operator:
            _reject_orchestrated_direct_workload(config)
            config = _dump_raw_manifests(
                config=config,
                kube_options=kube_options,
                name=name,
                namespace=namespace,
                yaml=yaml,
                deployment_spec=spec,
            )
        else:
            cr = {
                "apiVersion": AIPERF_API_VERSION,
                "kind": _choose_kind(config),
                "metadata": {"name": name, "namespace": namespace},
                "spec": spec,
            }
            yaml.dump(cr, sys.stdout)

        if not bare_pod:
            _print_memory_estimate(config, kube_options, spec)
