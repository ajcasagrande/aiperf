# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Display helpers for the ``aiperf env`` CLI command."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings
from rich import box
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from aiperf.common.environment import Environment

console = Console()

_CONSTRAINT_SYMBOLS: dict[str, str] = {
    "ge": ">=",
    "le": "<=",
    "gt": ">",
    "lt": "<",
    "min_length": "min length:",
    "max_length": "max length:",
}


@dataclass(slots=True)
class _SubsystemInfo:
    """Resolved subsystem: attribute name, env_prefix, and the live settings instance."""

    attr: str
    prefix: str
    instance: BaseSettings


def _get_subsystems() -> list[_SubsystemInfo]:
    """Return all subsystems from the Environment singleton."""
    results: list[_SubsystemInfo] = []
    for attr, _field_info in Environment.model_fields.items():
        instance = getattr(Environment, attr)
        if isinstance(instance, BaseSettings):
            prefix = instance.model_config.get("env_prefix", f"AIPERF_{attr}_")
            results.append(_SubsystemInfo(attr=attr, prefix=prefix, instance=instance))
    return results


def _resolve_subsystem(name: str) -> _SubsystemInfo | None:
    """Find a subsystem by case-insensitive name match."""
    upper = name.upper().replace("-", "_")
    for info in _get_subsystems():
        if info.attr == upper:
            return info
    return None


def _format_value(value: object) -> str:
    """Format a field value for display."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,}"
    return str(value)


def _get_constraints(field_info: FieldInfo) -> str:
    """Extract human-readable constraints from field metadata."""
    parts: list[str] = []
    for meta in field_info.metadata:
        for attr, symbol in _CONSTRAINT_SYMBOLS.items():
            val = getattr(meta, attr, None)
            if val is not None:
                parts.append(f"{symbol} {val}")
    return ", ".join(parts) if parts else ""


def _resolve_subsystems(subsystem: str | None) -> list[_SubsystemInfo] | None:
    """Resolve subsystem filter, printing error on invalid name. Returns None on error."""
    if subsystem:
        info = _resolve_subsystem(subsystem)
        if info is None:
            available = ", ".join(s.attr.lower() for s in _get_subsystems())
            console.print(f"[red]Unknown subsystem:[/red] {subsystem}")
            console.print(f"[dim]Available: {available}[/dim]")
            return None
        return [info]
    return _get_subsystems()


def _subsystem_title(info: _SubsystemInfo) -> str:
    """Format subsystem name for section headers."""
    return info.attr.replace("_", " ")


def _make_table(title: str | None = None) -> Table:
    """Create a consistently styled table."""
    return Table(
        title=title,
        title_style="bold",
        box=box.SIMPLE_HEAVY,
        pad_edge=False,
    )


def show_env_vars(
    *,
    subsystem: str | None = None,
    show_all: bool = False,
    describe: bool = False,
) -> None:
    """Show environment variables, optionally filtered to a subsystem.

    By default only shows vars that differ from their defaults (i.e. are set
    via the process environment). ``--all`` shows every var, grouped by subsystem.
    """
    subsystems = _resolve_subsystems(subsystem)
    if subsystems is None:
        return

    if show_all:
        _show_all_grouped(subsystems)
    else:
        _show_overridden(subsystems, subsystem=subsystem, describe=describe)


def _show_overridden(
    subsystems: list[_SubsystemInfo],
    *,
    subsystem: str | None,
    describe: bool,
) -> None:
    """Show only env vars that have been explicitly set."""
    table = _make_table()
    table.add_column("Env Variable", style="cyan", no_wrap=True)
    table.add_column("Value", style="green", justify="right")
    if describe:
        table.add_column("Description", style="dim")

    row_count = 0
    for info in subsystems:
        fields_set = info.instance.model_fields_set
        for field_name, field_info in info.instance.model_fields.items():
            if field_name not in fields_set:
                continue

            current = getattr(info.instance, field_name)
            row: list[str] = [
                f"{info.prefix}{field_name}",
                _format_value(current),
            ]
            if describe:
                row.append(field_info.description or "")
            table.add_row(*row)
            row_count += 1

    if row_count == 0:
        prefix = subsystems[0].prefix if subsystem else "AIPERF_"
        all_flag = f"--all {subsystem}" if subsystem else "--all"
        console.print(f"[dim]No {prefix}* environment variables are set.[/dim]")
        console.print(
            f"[dim]Use {all_flag} to see all variables with their defaults.[/dim]"
        )
        return

    console.print(table)
    all_flag = f"--all {subsystem}" if subsystem else "--all"
    console.print(
        f"\n[dim]{row_count} variable(s) overridden. Use {all_flag} to see all.[/dim]"
    )


def _show_all_grouped(subsystems: list[_SubsystemInfo]) -> None:
    """Show all env vars grouped by subsystem."""
    for info in subsystems:
        fields_set = info.instance.model_fields_set
        console.print(
            Rule(f"{_subsystem_title(info)} ({info.prefix}*)", characters="━")
        )
        table = _make_table()
        table.add_column("Env Variable", style="cyan", no_wrap=True)
        table.add_column("Value", justify="right")

        for field_name in info.instance.model_fields:
            current = getattr(info.instance, field_name)
            value_str = _format_value(current)

            if field_name in fields_set:
                value_str = f"[bold green]{value_str}[/bold green]"
            else:
                value_str = f"[dim]{value_str}[/dim]"

            table.add_row(f"{info.prefix}{field_name}", value_str)

        console.print(table)


def show_defaults(*, subsystem: str | None = None) -> None:
    """Show a reference table of all env vars with defaults, constraints, and descriptions."""
    subsystems = _resolve_subsystems(subsystem)
    if subsystems is None:
        return

    for info in subsystems:
        console.print(
            Rule(f"{_subsystem_title(info)} ({info.prefix}*)", characters="━")
        )

        for field_name, field_info in info.instance.model_fields.items():
            default = _format_value(field_info.default)
            constraints = _get_constraints(field_info)
            desc = field_info.description or ""

            console.print(f"  [cyan]{info.prefix}{field_name}[/cyan]")
            parts = [f"    default: {default}"]
            if constraints:
                parts.append(f"  [yellow]({constraints})[/yellow]")
            console.print("".join(parts))
            if desc:
                console.print(f"    [dim]{desc}[/dim]")
        console.print()
