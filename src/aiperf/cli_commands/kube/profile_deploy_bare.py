# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Bare-Pod deploy path for `aiperf kube profile --bare-pod`.

Renders one ConfigMap plus one ``kind: Pod`` (see
:mod:`aiperf.kubernetes.bare_pod`), applies them directly, waits for the
benchmark container to terminate, then prints the container log tail and where
the results landed. No operator, no JobSet, no CRD probe.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from aiperf.cli_commands.kube.profile_deploy import _print_manifests_yaml
from aiperf.config.kube import KubeOptions

if TYPE_CHECKING:
    from kubernetes_asyncio.client import CoreV1Api

    from aiperf.config import AIPerfConfig
    from aiperf.config.deployment import DeploymentConfig

BARE_POD_LOG_TAIL_LINES = 200
"""Lines of container log printed after the Pod reaches a terminal phase."""

BARE_POD_POLL_INTERVAL_SECONDS = 2.0
"""Seconds between ``read_namespaced_pod`` status polls."""

BARE_POD_RESULTS_PATH = "/results"
"""Mount path inside the Pod that holds the benchmark artifacts."""

BARE_POD_MAX_WAIT_SECONDS = 86_400.0
"""Upper bound on the container-termination wait, so a wedged Pod cannot hang the CLI."""


def _resolve_total_workers(config: AIPerfConfig, kube_options: KubeOptions) -> int:
    """Pick the worker-process count for the single Pod.

    An explicit ``--total-workers`` owns the count because CLI flags override
    YAML. Otherwise ``benchmark.runtime.workers`` is canonical. ``bool`` is
    excluded because it is an ``int`` subclass and would silently become 1.
    """
    if "total_workers" in kube_options.model_fields_set:
        return kube_options.total_workers
    configured = config.benchmark.runtime.workers
    if isinstance(configured, int) and not isinstance(configured, bool):
        return configured
    return kube_options.total_workers


def _resolve_deploy_config(
    kube_options: KubeOptions,
    deployment_spec: dict[str, Any] | None,
) -> DeploymentConfig:
    """Build the deployment config, pinning the release image when unset."""
    from aiperf.cli_commands.kube._kube_common import pin_default_direct_image

    if deployment_spec is None:
        deploy_config = kube_options.to_deployment_config()
    else:
        from aiperf.kubernetes.spec_converter import extract_deployment_config

        deploy_config = extract_deployment_config(deployment_spec)
    pin_default_direct_image(deploy_config)
    return deploy_config


async def _create_resource(
    core: CoreV1Api,
    manifest: dict[str, Any],
    namespace: str,
) -> str:
    """Create one bare-Pod resource, returning its ``Kind/ns/name`` label.

    Raises:
        RuntimeError: If the manifest carries a kind this path cannot apply.
        kubernetes_asyncio.client.exceptions.ApiException: Propagated so the
            caller can distinguish a name collision from a real failure.
    """
    kind = manifest["kind"]
    res_name = manifest["metadata"]["name"]
    res_ns = manifest["metadata"].get("namespace") or namespace
    if kind == "ConfigMap":
        await core.create_namespaced_config_map(namespace=res_ns, body=manifest)
    elif kind == "Pod":
        await core.create_namespaced_pod(namespace=res_ns, body=manifest)
    else:
        raise RuntimeError(f"Unsupported bare-Pod manifest kind: {kind}")
    return f"{kind}/{res_ns}/{res_name}"


async def _apply_manifests(
    core: CoreV1Api,
    manifests: list[dict[str, Any]],
    namespace: str,
) -> None:
    """Create the ConfigMap then the Pod, failing closed on any name collision.

    A bare Pod has no owner CR or immutable run UID, so an existing resource
    cannot be proven to belong to this invocation. Adopting a stale ConfigMap
    would run old configuration while reporting a new submission.
    """
    from kubernetes_asyncio.client.exceptions import ApiException

    from aiperf.kubernetes import console as kube_console

    for manifest in manifests:
        kind = manifest["kind"]
        res_name = manifest["metadata"]["name"]
        res_ns = manifest["metadata"].get("namespace") or namespace
        try:
            label = await _create_resource(core, manifest, namespace)
        except ApiException as exc:
            if exc.status == 409:
                raise RuntimeError(
                    f"{kind}/{res_ns}/{res_name} already exists; bare-Pod mode "
                    "refuses to adopt an existing resource. Delete it first with "
                    f"`kubectl delete {kind.lower()} {res_name} -n {res_ns}` or "
                    "choose a unique --name."
                ) from exc
            raise
        kube_console.print_success(f"Created {label}")


async def _wait_for_main_container(
    core: CoreV1Api,
    *,
    pod_name: str,
    namespace: str,
) -> int:
    """Poll until the benchmark container terminates, returning its exit code.

    The Pod itself never reaches ``Succeeded``: the results-holder sidecar
    keeps it ``Running`` so the artifacts stay reachable by ``kubectl cp``.
    Waiting on the container's terminated state is therefore the only signal
    that the benchmark finished.

    Raises:
        SystemExit: The container did not terminate within
            :data:`BARE_POD_MAX_WAIT_SECONDS`.
    """
    from aiperf.kubernetes.bare_pod import BARE_POD_CONTAINER_NAME

    waited = 0.0
    while True:
        pod = await core.read_namespaced_pod(name=pod_name, namespace=namespace)
        statuses = (pod.status.container_statuses if pod.status else None) or []
        main = next(
            (status for status in statuses if status.name == BARE_POD_CONTAINER_NAME),
            None,
        )
        terminated = main.state.terminated if main and main.state else None
        if terminated is not None:
            return int(terminated.exit_code or 0)
        phase = (pod.status.phase if pod.status else None) or ""
        if phase == "Failed":
            return 1
        if waited >= BARE_POD_MAX_WAIT_SECONDS:
            raise SystemExit(
                f"Bare Pod {namespace}/{pod_name} did not finish within "
                f"{BARE_POD_MAX_WAIT_SECONDS:.0f}s (phase {phase or 'unknown'}). "
                f"Inspect it with: kubectl describe pod {pod_name} -n {namespace}"
            )
        await asyncio.sleep(BARE_POD_POLL_INTERVAL_SECONDS)
        waited += BARE_POD_POLL_INTERVAL_SECONDS


async def _print_log_tail(
    core: CoreV1Api,
    *,
    pod_name: str,
    namespace: str,
) -> None:
    """Print the last ``BARE_POD_LOG_TAIL_LINES`` lines of the container log."""
    from kubernetes_asyncio.client.exceptions import ApiException

    from aiperf.kubernetes import console as kube_console
    from aiperf.kubernetes.bare_pod import BARE_POD_CONTAINER_NAME

    try:
        log_text = await core.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=BARE_POD_CONTAINER_NAME,
            tail_lines=BARE_POD_LOG_TAIL_LINES,
        )
    except ApiException as exc:
        kube_console.print_warning(
            f"Could not read logs for {namespace}/{pod_name}: {exc.reason}"
        )
        return
    kube_console.console.print(
        log_text.rstrip("\n") if log_text else "",
        highlight=False,
        markup=False,
        soft_wrap=True,
    )


def _print_results_hint(namespace: str, pod_name: str) -> None:
    """Tell the user where the artifacts are and how to copy them out."""
    from aiperf.kubernetes import console as kube_console
    from aiperf.kubernetes.bare_pod import BARE_POD_RESULTS_HOLDER_NAME

    kube_console.print_header("Results", style="bold green")
    kube_console.print_info(
        f"Artifacts are in the retained Pod at {BARE_POD_RESULTS_PATH}/"
    )
    kube_console.print_action(
        f"kubectl cp {namespace}/{pod_name}:{BARE_POD_RESULTS_PATH} ./results "
        f"-c {BARE_POD_RESULTS_HOLDER_NAME}"
    )


def _print_detach_hint(name: str, namespace: str, pod_name: str) -> None:
    """Report the Pod name and how to follow it after a non-blocking deploy."""
    from aiperf.kubernetes import console as kube_console
    from aiperf.kubernetes.bare_pod import BARE_POD_RESULTS_HOLDER_NAME

    kube_console.print_header(
        f"Benchmark '{name}' deployed successfully!", style="green bold"
    )
    kube_console.print_info(f"Pod: {namespace}/{pod_name}")
    kube_console.print_action(f"kubectl logs -f {pod_name} -n {namespace}")
    kube_console.print_action(
        f"kubectl cp {namespace}/{pod_name}:{BARE_POD_RESULTS_PATH} ./results "
        f"-c {BARE_POD_RESULTS_HOLDER_NAME}"
    )


async def deploy_bare_pod(
    config: AIPerfConfig,
    kube_options: KubeOptions,
    name: str,
    namespace: str,
    *,
    deployment_spec: dict[str, Any] | None = None,
    dry_run: bool,
    detach: bool,
    no_wait: bool,
) -> None:
    """Deploy the benchmark as one bare Pod and follow it to completion.

    Args:
        config: Resolved benchmark configuration.
        kube_options: CLI Kubernetes options (kubeconfig, context, image, name).
        name: Benchmark name used for the ConfigMap and Pod names.
        namespace: Target namespace.
        deployment_spec: Optional CR-shaped spec whose deployment fields should
            override the flat CLI options.
        dry_run: Print the manifests as YAML and return without contacting the
            cluster.
        detach: Return immediately after creating the resources.
        no_wait: Return immediately after creating the resources (advanced).

    Raises:
        RuntimeError: A resource name already exists in the namespace.
        SystemExit: The benchmark container exited non-zero.
    """
    import sys

    from kubernetes_asyncio import client as k8s_client_mod

    from aiperf.kubernetes import console as kube_console
    from aiperf.kubernetes.bare_pod import (
        build_bare_pod_manifests,
        resolve_bare_pod_topology,
    )
    from aiperf.kubernetes.client import k8s_client

    deploy_config = _resolve_deploy_config(kube_options, deployment_spec)
    topology = resolve_bare_pod_topology(
        config,
        _resolve_total_workers(config, kube_options),
        pod_template=deploy_config.pod_template,
    )
    manifests = build_bare_pod_manifests(
        config=config,
        kube_options=kube_options,
        name=name,
        namespace=namespace,
        deploy_config=deploy_config,
        topology=topology,
    )

    if dry_run:
        _print_manifests_yaml(manifests)
        return

    pod_name = manifests[-1]["metadata"]["name"]

    async with k8s_client(
        kubeconfig=kube_options.kubeconfig,
        context=kube_options.kube_context,
    ) as api:
        core = k8s_client_mod.CoreV1Api(api)
        await _apply_manifests(core, manifests, namespace)

        kube_console.save_last_benchmark(name, namespace, name=kube_options.name)

        is_interactive = sys.stdout.isatty()
        if not is_interactive and not detach and not no_wait:
            kube_console.print_warning(
                "Non-interactive environment detected, using detach mode"
            )
        if detach or no_wait or not is_interactive:
            _print_detach_hint(name, namespace, pod_name)
            return

        exit_code = await _wait_for_main_container(
            core, pod_name=pod_name, namespace=namespace
        )
        await _print_log_tail(core, pod_name=pod_name, namespace=namespace)
        _print_results_hint(namespace, pod_name)

        if exit_code != 0:
            raise SystemExit(
                f"Bare Pod {namespace}/{pod_name} failed with exit code "
                f"{exit_code}. Inspect the logs above, then copy any partial "
                f"artifacts with: kubectl cp "
                f"{namespace}/{pod_name}:{BARE_POD_RESULTS_PATH} ./results "
                f"-c results-holder"
            )
