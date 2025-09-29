# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CLI commands for managing plugins."""

import json
from pathlib import Path

import click

from aiperf.common.enums import EndpointType

from .hybrid_factory import get_hybrid_factory
from .manager import get_plugin_manager


@click.group(name="plugins")
def plugins_cli():
    """Plugin management commands."""
    pass


@plugins_cli.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def list_plugins(output_format: str):
    """List all registered plugins."""
    manager = get_plugin_manager()
    plugins_info = manager.list_plugins()

    if output_format == "json":
        # Convert EndpointType enums to strings for JSON serialization
        json_data = []
        for name, endpoint_types in plugins_info:
            json_data.append(
                {"name": name, "endpoint_types": [str(et) for et in endpoint_types]}
            )
        click.echo(json.dumps(json_data, indent=2))
    else:
        if not plugins_info:
            click.echo("No plugins registered.")
            return

        click.echo("Registered Plugins:")
        click.echo("=" * 50)
        for name, endpoint_types in plugins_info:
            click.echo(f"Plugin: {name}")
            if endpoint_types:
                click.echo(f"  Supports: {', '.join(str(et) for et in endpoint_types)}")
            else:
                click.echo("  Supports: No endpoint types")
            click.echo()


@plugins_cli.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def list_supported_types(output_format: str):
    """List all supported endpoint types from both plugin systems."""
    factory = get_hybrid_factory()
    supported_types = factory.list_all_supported_types()

    if output_format == "json":
        # Convert EndpointType enums to strings for JSON serialization
        json_data = {}
        for system, types in supported_types.items():
            json_data[system] = [str(et) for et in types]
        click.echo(json.dumps(json_data, indent=2))
    else:
        click.echo("Supported Endpoint Types:")
        click.echo("=" * 30)

        for system, types in supported_types.items():
            click.echo(f"{system.title()} System:")
            if types:
                for endpoint_type in types:
                    click.echo(f"  - {endpoint_type}")
            else:
                click.echo("  - No types supported")
            click.echo()


@plugins_cli.command()
@click.argument("endpoint_type")
def test_endpoint(endpoint_type: str):
    """Test which system can handle a specific endpoint type."""
    try:
        et = EndpointType(endpoint_type)
    except ValueError:
        click.echo(f"Invalid endpoint type: {endpoint_type}")
        click.echo(f"Valid types: {', '.join(str(et) for et in EndpointType)}")
        return

    factory = get_hybrid_factory()

    # Test pluggy system
    pluggy_can_handle = factory.pluggy_factory.can_handle_endpoint_type(et)

    # Test original system
    original_can_handle = False
    try:
        from aiperf.common.factories import RequestConverterFactory

        RequestConverterFactory.create_instance(et)
        original_can_handle = True
    except Exception:
        original_can_handle = False

    click.echo(f"Endpoint Type: {endpoint_type}")
    click.echo("=" * 30)
    click.echo(f"Pluggy System: {'✓' if pluggy_can_handle else '✗'}")
    click.echo(f"Original System: {'✓' if original_can_handle else '✗'}")

    if pluggy_can_handle or original_can_handle:
        click.echo("\n✓ This endpoint type is supported!")
    else:
        click.echo("\n✗ This endpoint type is not supported by either system.")


@plugins_cli.command()
@click.option(
    "--plugin-dir",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Additional directories to scan for plugins",
)
def discover_plugins(plugin_dir: list[Path]):
    """Discover and load plugins from directories."""
    manager = get_plugin_manager()

    if plugin_dir:
        click.echo(f"Discovering plugins in: {', '.join(str(p) for p in plugin_dir)}")
        manager.discover_and_load_plugins(list(plugin_dir))
    else:
        click.echo("Discovering plugins in default locations...")
        manager.discover_and_load_plugins()

    plugins_info = manager.list_plugins()
    click.echo(f"Discovered {len(plugins_info)} plugins:")

    for name, endpoint_types in plugins_info:
        click.echo(
            f"  - {name} (supports: {', '.join(str(et) for et in endpoint_types)})"
        )


@plugins_cli.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def system_info(output_format: str):
    """Show detailed information about both plugin systems."""
    factory = get_hybrid_factory()
    info = factory.get_detailed_info()

    if output_format == "json":
        # Convert complex objects to JSON-serializable format
        json_data = {
            "pluggy_plugins": [],
            "original_classes": [],
            "supported_types": {},
        }

        # Convert pluggy plugins
        for name, endpoint_types in info.get("pluggy_plugins", []):
            json_data["pluggy_plugins"].append(
                {"name": name, "endpoint_types": [str(et) for et in endpoint_types]}
            )

        # Convert original classes
        for cls, endpoint_type in info.get("original_classes", []):
            json_data["original_classes"].append(
                {"class_name": cls.__name__, "endpoint_type": str(endpoint_type)}
            )

        # Convert supported types
        for system, types in info.get("supported_types", {}).items():
            json_data["supported_types"][system] = [str(et) for et in types]

        click.echo(json.dumps(json_data, indent=2))
    else:
        click.echo("Plugin System Information")
        click.echo("=" * 40)

        # Show pluggy plugins
        click.echo("\nPluggy Plugins:")
        pluggy_plugins = info.get("pluggy_plugins", [])
        if pluggy_plugins:
            for name, endpoint_types in pluggy_plugins:
                click.echo(f"  - {name}")
                if endpoint_types:
                    click.echo(
                        f"    Supports: {', '.join(str(et) for et in endpoint_types)}"
                    )
        else:
            click.echo("  No pluggy plugins registered")

        # Show original classes
        click.echo("\nOriginal Factory Classes:")
        original_classes = info.get("original_classes", [])
        if original_classes:
            for cls, endpoint_type in original_classes:
                click.echo(f"  - {cls.__name__} -> {endpoint_type}")
        else:
            click.echo("  No original factory classes registered")

        # Show supported types summary
        click.echo("\nSupported Types Summary:")
        supported_types = info.get("supported_types", {})
        for system, types in supported_types.items():
            click.echo(f"  {system.title()}: {len(types)} types")


if __name__ == "__main__":
    plugins_cli()
