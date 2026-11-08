# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for `aiperf kube profile --bare-pod`.

Covers the CLI mutual-exclusion guard and the deploy path's create ordering,
name-collision fence, and terminal-phase reporting. Every test fakes the
Kubernetes client; none contacts a cluster.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aiperf.cli_commands.kube.profile import profile
from aiperf.cli_commands.kube.profile_deploy_bare import deploy_bare_pod
from aiperf.config.kube import KubeOptions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(*, workers: int | None = None) -> Any:
    """Build a validated AIPerfConfig for bare-Pod rendering."""
    from aiperf.config import AIPerfConfig

    runtime = {"workers": workers} if workers is not None else {}
    return AIPerfConfig.model_validate(
        {
            "benchmark": {
                "models": ["test-model"],
                "endpoint": {"urls": ["http://svc:8000"]},
                "datasets": [{"name": "main", "type": "synthetic"}],
                "phases": [
                    {
                        "name": "profiling",
                        "type": "concurrency",
                        "requests": 8,
                        "concurrency": 8,
                    }
                ],
                "runtime": runtime,
            }
        }
    )


@asynccontextmanager
async def _fake_k8s_client(**_kw: Any):
    yield MagicMock(name="ApiClient")


class _RecordingCore:
    """Fake ``CoreV1Api`` that records create order and serves a fixed exit."""

    def __init__(
        self,
        *,
        exit_code: int = 0,
        phase: str = "Running",
        pod_create_error: BaseException | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.created: dict[str, dict[str, Any]] = {}
        self.exit_code = exit_code
        self.phase = phase
        self.pod_create_error = pod_create_error

    async def create_namespaced_config_map(
        self, *, namespace: str, body: dict[str, Any]
    ) -> None:
        self.calls.append("ConfigMap")
        self.created["ConfigMap"] = body

    async def create_namespaced_pod(
        self, *, namespace: str, body: dict[str, Any]
    ) -> None:
        self.calls.append("Pod")
        if self.pod_create_error is not None:
            raise self.pod_create_error
        self.created["Pod"] = body

    async def read_namespaced_pod(self, *, name: str, namespace: str) -> Any:
        from aiperf.kubernetes.bare_pod import BARE_POD_CONTAINER_NAME

        main = MagicMock()
        main.name = BARE_POD_CONTAINER_NAME
        main.state.terminated.exit_code = self.exit_code
        status = MagicMock()
        status.phase = self.phase
        status.container_statuses = [main]
        pod = MagicMock()
        pod.status = status
        return pod

    async def read_namespaced_pod_log(self, **_kwargs: Any) -> str:
        return "benchmark log line\n"


def _deploy_patches(core: _RecordingCore):
    """Patch the k8s client, the CoreV1Api factory, and last-benchmark state."""
    client = MagicMock(side_effect=lambda **_kw: _fake_k8s_client())
    core_factory = MagicMock(return_value=core)
    return (
        patch("aiperf.kubernetes.client.k8s_client", new=client),
        patch("kubernetes_asyncio.client.CoreV1Api", new=core_factory),
        patch("aiperf.kubernetes.console.save_last_benchmark"),
    )


# ---------------------------------------------------------------------------
# CLI flag routing
# ---------------------------------------------------------------------------


class TestBarePodFlag:
    """`--bare-pod` is mutually exclusive with the operator flags."""

    @pytest.mark.asyncio
    async def test_bare_pod_with_operator_errors_naming_both_flags(self) -> None:
        messages: list[str] = []

        def _fail(message: str, **_kwargs: Any) -> None:
            messages.append(message)
            raise SystemExit(1)

        with (
            patch("aiperf.cli_utils.raise_startup_error_and_exit", side_effect=_fail),
            pytest.raises(SystemExit),
        ):
            await profile(
                cli_config=MagicMock(),
                kube_options=KubeOptions(namespace="bench-ns"),
                bare_pod=True,
                operator=True,
            )

        assert messages
        assert "--bare-pod" in messages[0]
        assert "--operator" in messages[0]

    @pytest.mark.asyncio
    async def test_bare_pod_with_no_operator_errors_naming_both_flags(self) -> None:
        messages: list[str] = []

        def _fail(message: str, **_kwargs: Any) -> None:
            messages.append(message)
            raise SystemExit(1)

        with (
            patch("aiperf.cli_utils.raise_startup_error_and_exit", side_effect=_fail),
            pytest.raises(SystemExit),
        ):
            await profile(
                cli_config=MagicMock(),
                kube_options=KubeOptions(namespace="bench-ns"),
                bare_pod=True,
                no_operator=True,
            )

        assert messages
        assert "--bare-pod" in messages[0]
        assert "--no-operator" in messages[0]


# ---------------------------------------------------------------------------
# deploy_bare_pod
# ---------------------------------------------------------------------------


class TestDeployBarePod:
    """Render, apply, and follow the single Pod."""

    @pytest.mark.asyncio
    async def test_dry_run_prints_manifests_and_creates_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        client_patch, core_patch, save_patch = _deploy_patches(_RecordingCore())

        with client_patch as fake_client, core_patch as fake_core, save_patch:
            await deploy_bare_pod(
                _make_config(),
                KubeOptions(namespace="bench-ns", image="aiperf:test"),
                "bench",
                "bench-ns",
                dry_run=True,
                detach=False,
                no_wait=False,
            )

        fake_client.assert_not_called()
        fake_core.assert_not_called()
        out = capsys.readouterr().out
        assert "kind: ConfigMap" in out
        assert "kind: Pod" in out

    @pytest.mark.asyncio
    async def test_creates_configmap_before_pod(self) -> None:
        core = _RecordingCore()
        client_patch, core_patch, save_patch = _deploy_patches(core)

        with client_patch, core_patch, save_patch:
            await deploy_bare_pod(
                _make_config(),
                KubeOptions(namespace="bench-ns", image="aiperf:test"),
                "bench",
                "bench-ns",
                dry_run=False,
                detach=True,
                no_wait=False,
            )

        assert core.calls == ["ConfigMap", "Pod"]
        assert core.created["ConfigMap"]["kind"] == "ConfigMap"
        assert core.created["Pod"]["kind"] == "Pod"

    @pytest.mark.asyncio
    async def test_pod_already_exists_fails_closed_naming_the_resource(self) -> None:
        from kubernetes_asyncio.client.exceptions import ApiException

        core = _RecordingCore(
            pod_create_error=ApiException(status=409, reason="AlreadyExists")
        )
        client_patch, core_patch, save_patch = _deploy_patches(core)

        with (
            client_patch,
            core_patch,
            save_patch,
            pytest.raises(RuntimeError, match=r"Pod/bench-ns/aiperf-bench"),
        ):
            await deploy_bare_pod(
                _make_config(),
                KubeOptions(namespace="bench-ns", image="aiperf:test"),
                "bench",
                "bench-ns",
                dry_run=False,
                detach=True,
                no_wait=False,
            )

    @pytest.mark.asyncio
    async def test_succeeded_prints_log_tail_and_results_hint(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        core = _RecordingCore(exit_code=0)
        client_patch, core_patch, save_patch = _deploy_patches(core)

        with (
            client_patch,
            core_patch,
            save_patch,
            patch("sys.stdout.isatty", return_value=True),
        ):
            await deploy_bare_pod(
                _make_config(),
                KubeOptions(namespace="bench-ns", image="aiperf:test"),
                "bench",
                "bench-ns",
                dry_run=False,
                detach=False,
                no_wait=False,
            )

        out = capsys.readouterr().out
        assert "benchmark log line" in out
        assert "kubectl cp bench-ns/aiperf-bench:/results ./results" in out
        assert "results-holder" in out

    @pytest.mark.asyncio
    async def test_failed_pod_exits_non_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        core = _RecordingCore(exit_code=1)
        client_patch, core_patch, save_patch = _deploy_patches(core)

        with (
            client_patch,
            core_patch,
            save_patch,
            patch("sys.stdout.isatty", return_value=True),
            pytest.raises(SystemExit) as exc_info,
        ):
            await deploy_bare_pod(
                _make_config(),
                KubeOptions(namespace="bench-ns", image="aiperf:test"),
                "bench",
                "bench-ns",
                dry_run=False,
                detach=False,
                no_wait=False,
            )

        assert exc_info.value.code != 0
        out = capsys.readouterr().out
        assert "benchmark log line" in out

    @pytest.mark.asyncio
    async def test_runtime_workers_override_wins_over_total_workers(self) -> None:
        """An explicit benchmark.runtime.workers drives the Pod topology."""
        from aiperf.cli_commands.kube.profile_deploy_bare import (
            _resolve_total_workers,
        )

        assert _resolve_total_workers(_make_config(workers=4), KubeOptions()) == 4
        assert _resolve_total_workers(_make_config(), KubeOptions(total_workers=7)) == 7
