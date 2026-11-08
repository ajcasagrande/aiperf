# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the single bare-Pod renderer."""

from __future__ import annotations

import pytest
import ruamel.yaml

from aiperf.config import AIPerfConfig
from aiperf.config.deployment import PodTemplateConfig
from aiperf.config.kube import KubeOptions
from aiperf.config.loader.errors import ConfigurationError
from aiperf.kubernetes.bare_pod import (
    BARE_POD_CONFIG_FILE,
    build_bare_pod_manifests,
    resolve_bare_pod_topology,
)

_PORT_RANGE_SYSCTL = "net.ipv4.ip_local_port_range"


def _config(
    concurrency: int,
    *,
    scenario: str | None = "agentx",
    api_key: str | None = None,
) -> AIPerfConfig:
    """Build a minimal benchmark config for topology and manifest tests."""
    endpoint: dict[str, object] = {"urls": ["http://svc:8000"]}
    if api_key is not None:
        endpoint["api_key"] = api_key
    benchmark: dict[str, object] = {
        "models": ["test-model"],
        "endpoint": endpoint,
        "datasets": [{"name": "main", "type": "synthetic"}],
        "phases": [
            {
                "name": "profiling",
                "type": "concurrency",
                "requests": 10,
                "concurrency": concurrency,
            }
        ],
    }
    if scenario is not None:
        benchmark["scenario"] = scenario
    return AIPerfConfig.model_validate({"benchmark": benchmark})


def _pod_template_with_port_range(value: str) -> PodTemplateConfig:
    """Return a pod template carrying an authored ephemeral port range."""
    return PodTemplateConfig(
        pod_security_context={"sysctls": [{"name": _PORT_RANGE_SYSCTL, "value": value}]}
    )


def _manifests(config: AIPerfConfig, *, total_workers: int = 100) -> list[dict]:
    kube_options = KubeOptions(image="aiperf:test", name="bench")
    topology = resolve_bare_pod_topology(config, total_workers)
    return build_bare_pod_manifests(
        config=config,
        kube_options=kube_options,
        name="bench",
        namespace="ns",
        deploy_config=kube_options.to_deployment_config(),
        topology=topology,
    )


def test_resolve_topology_50k_concurrency_across_100_workers() -> None:
    topology = resolve_bare_pod_topology(_config(50_000), 100)

    assert topology.total_workers == 100
    assert topology.record_processors == 32
    assert topology.connections_per_worker == 500
    assert topology.max_concurrency == 50_000
    assert topology.port_range_end == 65535
    assert topology.port_range_start >= 1024
    assert topology.port_capacity >= 50_000


def test_resolve_topology_50k_concurrency_across_10_workers_allowed() -> None:
    """The ratio is a planning estimate; the Pod raises its connector limit."""
    topology = resolve_bare_pod_topology(_config(50_000), 10)

    assert topology.connections_per_worker == 5_000
    assert topology.port_range_start == 1024
    assert topology.port_range_end == 65535


def test_resolve_topology_above_single_pod_connection_capacity_rejected() -> None:
    with pytest.raises(ConfigurationError, match="ephemeral ports"):
        resolve_bare_pod_topology(_config(70_000), 100)


def test_resolve_topology_rejects_too_small_authored_port_range() -> None:
    pod_template = _pod_template_with_port_range("32768 60999")

    with pytest.raises(ConfigurationError, match="needs at least"):
        resolve_bare_pod_topology(_config(50_000), 100, pod_template=pod_template)


def test_resolve_topology_honors_large_enough_authored_port_range() -> None:
    pod_template = _pod_template_with_port_range("1024 65535")

    topology = resolve_bare_pod_topology(
        _config(50_000), 100, pod_template=pod_template
    )

    assert (topology.port_range_start, topology.port_range_end) == (1024, 65535)


def test_build_manifests_renders_one_pod_and_one_configmap() -> None:
    config = _config(50_000)
    topology = resolve_bare_pod_topology(config, 100)

    configmap, pod = _manifests(config)

    assert configmap["kind"] == "ConfigMap"
    assert pod["kind"] == "Pod"
    assert pod["spec"]["restartPolicy"] == "Never"
    assert len(pod["spec"]["containers"]) == 2

    container = pod["spec"]["containers"][0]
    assert container["args"] == [
        "profile",
        "--config",
        f"/etc/aiperf/{BARE_POD_CONFIG_FILE}",
    ]
    assert pod["spec"]["securityContext"]["sysctls"] == [
        {
            "name": _PORT_RANGE_SYSCTL,
            "value": f"{topology.port_range_start} {topology.port_range_end}",
        }
    ]

    assert BARE_POD_CONFIG_FILE in configmap["data"]


def test_build_manifests_embeds_multiprocessing_runtime_config() -> None:
    config = _config(50_000)

    configmap, _ = _manifests(config)
    embedded = ruamel.yaml.YAML(typ="safe").load(
        configmap["data"][BARE_POD_CONFIG_FILE]
    )
    benchmark = embedded["benchmark"]

    assert benchmark["runtime"]["service_run_type"] == "multiprocessing"
    assert benchmark["runtime"]["workers"] == 100
    assert benchmark["runtime"]["record_processors"] == 32
    assert benchmark["scenario"] == "agentx"
    assert benchmark["artifacts"]["dir"] == "/results"
    assert "workers_per_pod" not in benchmark["runtime"]


def test_build_manifests_does_not_leak_api_key_into_configmap() -> None:
    config = _config(4, scenario=None, api_key="super-secret")

    configmap, _ = _manifests(config, total_workers=2)

    assert "super-secret" not in configmap["data"][BARE_POD_CONFIG_FILE]


def _manifests_with_template(
    config: AIPerfConfig,
    pod_template: PodTemplateConfig,
    *,
    total_workers: int = 100,
) -> list[dict]:
    kube_options = KubeOptions(image="aiperf:test", name="bench")
    deploy_config = kube_options.to_deployment_config()
    deploy_config.pod_template = pod_template
    topology = resolve_bare_pod_topology(
        config, total_workers, pod_template=pod_template
    )
    return build_bare_pod_manifests(
        config=config,
        kube_options=kube_options,
        name="bench",
        namespace="ns",
        deploy_config=deploy_config,
        topology=topology,
    )


def test_build_manifests_preserves_authored_sysctls() -> None:
    pod_template = PodTemplateConfig(
        pod_security_context={
            "sysctls": [
                {"name": "net.core.somaxconn", "value": "4096"},
                {"name": _PORT_RANGE_SYSCTL, "value": "1024 65535"},
            ]
        }
    )

    _, pod = _manifests_with_template(_config(50_000), pod_template)

    sysctls = pod["spec"]["securityContext"]["sysctls"]
    assert {"name": "net.core.somaxconn", "value": "4096"} in sysctls
    assert [entry for entry in sysctls if entry["name"] == _PORT_RANGE_SYSCTL] == [
        {"name": _PORT_RANGE_SYSCTL, "value": "1024 65535"}
    ]


def test_build_manifests_appends_pod_template_volumes_and_mounts() -> None:
    pod_template = PodTemplateConfig(
        volumes=[{"name": "dataset", "persistentVolumeClaim": {"claimName": "data"}}],
        volume_mounts=[{"name": "dataset", "mountPath": "/data", "readOnly": True}],
    )

    _, pod = _manifests_with_template(_config(50_000), pod_template)

    assert {"name": "dataset", "persistentVolumeClaim": {"claimName": "data"}} in (
        pod["spec"]["volumes"]
    )
    assert {"name": "dataset", "mountPath": "/data", "readOnly": True} in (
        pod["spec"]["containers"][0]["volumeMounts"]
    )


def test_build_manifests_merges_pod_template_labels() -> None:
    pod_template = PodTemplateConfig(labels={"team": "inference"})

    _, pod = _manifests_with_template(_config(50_000), pod_template)

    assert pod["metadata"]["labels"]["team"] == "inference"
    assert pod["metadata"]["labels"]["app"] == "aiperf"


def test_build_manifests_renders_init_containers_and_extra_pod_spec() -> None:
    pod_template = PodTemplateConfig(
        init_containers=[{"name": "setup", "image": "busybox"}],
        extra_pod_spec={"schedulingGates": [{"name": "hold"}]},
    )

    _, pod = _manifests_with_template(_config(50_000), pod_template)

    assert pod["spec"]["initContainers"][0]["name"] == "setup"
    assert pod["spec"]["schedulingGates"] == [{"name": "hold"}]


def test_build_manifests_scales_registration_timeout_with_worker_count() -> None:
    _, pod = _manifests(_config(50_000), total_workers=100)

    env = {
        entry["name"]: entry["value"] for entry in pod["spec"]["containers"][0]["env"]
    }
    assert int(env["AIPERF_SERVICE_REGISTRATION_TIMEOUT"]) >= 120
    assert int(env["AIPERF_SERVICE_REGISTRATION_MAX_ATTEMPTS"]) >= 120


def test_build_manifests_disables_mmap_cache_and_redirects_remote_cache() -> None:
    """The read-only root filesystem has no writable ~/.cache."""
    _, pod = _manifests(_config(50_000))

    env = {
        entry["name"]: entry["value"] for entry in pod["spec"]["containers"][0]["env"]
    }
    assert env["AIPERF_DATASET_MMAP_CACHE_ENABLED"] == "false"
    assert env["AIPERF_DATASET_REMOTE_CACHE_DIR"] == "/aiperf/remote-cache"
    assert {"name": "remote-cache", "mountPath": "/aiperf/remote-cache"} in (
        pod["spec"]["containers"][0]["volumeMounts"]
    )


def test_build_manifests_keeps_results_reachable_after_completion() -> None:
    """A completed Pod cannot be exec'd into, so a holder keeps /results live."""
    _, pod = _manifests(_config(50_000))

    names = [container["name"] for container in pod["spec"]["containers"]]
    assert names == ["aiperf", "results-holder"]
    holder = pod["spec"]["containers"][1]
    assert {"name": "results", "mountPath": "/results"} in holder["volumeMounts"]


def test_build_manifests_deduplicates_user_env_by_name() -> None:
    pod_template = PodTemplateConfig(
        env=[
            {"name": "HF_HOME", "value": "/custom/hf"},
            {"name": "CUSTOM", "value": "1"},
        ]
    )

    _, pod = _manifests_with_template(_config(50_000), pod_template)

    env = pod["spec"]["containers"][0]["env"]
    names = [entry["name"] for entry in env]
    assert names.count("HF_HOME") == 1
    assert {entry["name"]: entry["value"] for entry in env}["HF_HOME"] == "/custom/hf"
    assert "CUSTOM" in names


def test_build_manifests_raises_connector_limit_for_subagent_fanout() -> None:
    """The Pod must not be capped at the 2,500 default when fanout exceeds it."""
    _, pod = _manifests(_config(50_000))

    env = {entry["name"]: entry["value"] for entry in pod["spec"]["containers"][0]["env"]}
    assert env["AIPERF_HTTP_CONNECTION_LIMIT"] == "65000"
