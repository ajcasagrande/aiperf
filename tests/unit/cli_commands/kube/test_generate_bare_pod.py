# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""CLI wiring for ``aiperf kube generate --bare-pod``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import ruamel.yaml
import yaml
from pytest import param

from aiperf.cli_commands.kube import generate as generate_cmd
from aiperf.config.flags import CLIConfig
from aiperf.config.kube import KubeOptions

_BENCHMARK: dict[str, object] = {
    "models": ["test-model"],
    "endpoint": {"urls": ["http://svc:8000"]},
    "datasets": [{"name": "main", "type": "synthetic"}],
    "phases": [
        {
            "name": "profiling",
            "type": "concurrency",
            "requests": 10,
            "concurrency": 100,
        }
    ],
}


def _write_config(path: Path) -> Path:
    """Write a minimal AIPerfConfig envelope and return its path."""
    path.write_text(yaml.safe_dump({"benchmark": _BENCHMARK}, sort_keys=False))
    return path


def _cli_config(path: Path) -> CLIConfig:
    """Return CLI input with only ``--config`` explicitly set."""
    return CLIConfig(config_file=path)


def _kube_options() -> KubeOptions:
    """Return kube options that produce a self-contained single Pod."""
    return KubeOptions(
        name="bare-bench",
        namespace="aiperf-ci",
        image="aiperf:test",
        total_workers=10,
    )


@pytest.mark.asyncio
async def test_generate_bare_pod_emits_one_pod_and_one_configmap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = _write_config(tmp_path / "bench.yaml")

    await generate_cmd.generate(
        cli_config=_cli_config(config_file),
        kube_options=_kube_options(),
        bare_pod=True,
    )

    captured = capsys.readouterr()
    manifests = list(ruamel.yaml.YAML(typ="safe").load_all(captured.out))
    kinds = [manifest["kind"] for manifest in manifests]

    assert kinds.count("Pod") == 1
    assert kinds.count("ConfigMap") == 1
    assert "JobSet" not in kinds
    # The sizing summary narrates on stderr so stdout stays parseable.
    assert "Bare Pod sizing" not in captured.out
    assert "Bare Pod sizing" in captured.err


@pytest.mark.asyncio
async def test_generate_bare_pod_rejects_sweep_workload(
    tmp_path: Path,
) -> None:
    config_file = _write_config(tmp_path / "bench.yaml")
    config_file.write_text(
        yaml.safe_dump(
            {
                "benchmark": _BENCHMARK,
                "sweep": {
                    "type": "grid",
                    "parameters": {"phases.profiling.concurrency": [1, 2]},
                },
            },
            sort_keys=False,
        )
    )

    with (
        patch(
            "aiperf.cli_utils.raise_startup_error_and_exit",
            side_effect=SystemExit(1),
        ) as fail,
        pytest.raises(SystemExit),
    ):
        await generate_cmd.generate(
            cli_config=_cli_config(config_file),
            kube_options=_kube_options(),
            bare_pod=True,
        )

    message = fail.call_args.args[0]
    assert "--bare-pod" in message
    assert "parameter-sweep or multi-run" in message
    assert "aiperf kube sweep" in message


@pytest.mark.parametrize(
    ("flag", "conflicting"),
    [
        param("operator", "--operator", id="operator"),
        param("no_operator", "--no-operator", id="no-operator"),
    ],
)  # fmt: skip
@pytest.mark.asyncio
async def test_generate_bare_pod_rejects_combined_output_forms(
    flag: str, conflicting: str
) -> None:
    with (
        patch(
            "aiperf.cli_utils.raise_startup_error_and_exit",
            side_effect=SystemExit(1),
        ) as fail,
        pytest.raises(SystemExit),
    ):
        await generate_cmd.generate(
            cli_config=CLIConfig(),
            bare_pod=True,
            **{flag: True},
        )

    message = fail.call_args.args[0]
    assert "--bare-pod" in message
    assert conflicting in message


@pytest.mark.asyncio
async def test_generate_without_output_form_mentions_bare_pod() -> None:
    with (
        patch(
            "aiperf.cli_utils.raise_startup_error_and_exit",
            side_effect=SystemExit(1),
        ) as fail,
        pytest.raises(SystemExit),
    ):
        await generate_cmd.generate(cli_config=CLIConfig())

    message = fail.call_args.args[0]
    assert "--bare-pod" in message
    assert "--operator" in message
    assert "--no-operator" in message
