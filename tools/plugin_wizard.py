#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
AIPerf Plugin Wizard - Following AIP-001 Specification

Creates AIPerf plugins following the official AIP-001 Plugin Architecture:
- Entry point based discovery (pyproject.toml)
- Lazy loading with importlib.metadata
- Dependency injection support
- Type-safe plugin contracts
- Zero-boilerplate authorship

Supported Plugin Types (AIP-001):
- aiperf.endpoint - API format handlers
- aiperf.transport - Communication protocols
- aiperf.data_exporter - Data exporters
- aiperf.processor - Data processors
- aiperf.metric - Performance metrics
- aiperf.collector - Data collection

Usage:
    python tools/plugin_wizard.py

    Or with VS Code extension integration (if installed):
    Ctrl+Shift+P → "AIPerf: Create Plugin"
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import re


# ANSI Colors
class C:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


@dataclass
class PluginConfig:
    """Configuration for plugin generation."""
    plugin_type: str
    plugin_name: str
    plugin_class_name: str
    display_name: str
    description: str
    package_name: str
    author: str
    email: str
    version: str
    extra_config: Dict[str, Any]


def header(text: str):
    """Print formatted header."""
    print(f"\n{C.BOLD}{C.BLUE}{'='*70}{C.END}")
    print(f"{C.BOLD}{C.BLUE}{text.center(70)}{C.END}")
    print(f"{C.BOLD}{C.BLUE}{'='*70}{C.END}\n")


def step(num: int, text: str):
    """Print step indicator."""
    print(f"\n{C.CYAN}{C.BOLD}[Step {num}]{C.END} {text}")


def success(text: str):
    """Print success message."""
    print(f"{C.GREEN}✓{C.END} {text}")


def error(text: str):
    """Print error message."""
    print(f"{C.RED}✗{C.END} {text}")


def warn(text: str):
    """Print warning message."""
    print(f"{C.YELLOW}⚠{C.END} {text}")


def ask(question: str, default: Optional[str] = None, choices: Optional[List[str]] = None) -> str:
    """Prompt for input."""
    if choices:
        print(f"\n{C.BOLD}{question}{C.END}")
        for i, choice in enumerate(choices, 1):
            print(f"  {C.CYAN}{i}.{C.END} {choice}")

        while True:
            resp = input(f"{C.YELLOW}Select (1-{len(choices)}){C.END}: ").strip()
            if resp.isdigit() and 1 <= int(resp) <= len(choices):
                return choices[int(resp) - 1]
            error(f"Enter a number between 1 and {len(choices)}")
    else:
        prompt_text = f"{C.YELLOW}{question}{C.END}"
        if default:
            prompt_text += f" {C.CYAN}[{default}]{C.END}"
        prompt_text += ": "

        resp = input(prompt_text).strip()
        return resp if resp else (default or "")


def confirm(question: str, default: bool = True) -> bool:
    """Ask yes/no question."""
    default_str = "Y/n" if default else "y/N"
    resp = input(f"{C.YELLOW}{question} [{default_str}]{C.END}: ").strip().lower()
    return resp in ('y', 'yes') if resp else default


def to_snake_case(text: str) -> str:
    """Convert to snake_case."""
    text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', text)
    text = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', text)
    return re.sub(r'[^\w]', '_', text).lower().strip('_')


def to_pascal_case(text: str) -> str:
    """Convert to PascalCase."""
    return ''.join(word.capitalize() for word in text.split('_'))


def create_plugin_package_structure(config: PluginConfig) -> Dict[str, str]:
    """
    Create complete plugin package structure following AIP-001.

    Returns:
        Dict mapping file paths to content
    """
    package_dir = f"{config.package_name}"
    files = {}

    # 1. pyproject.toml with entry points (AIP-001 requirement)
    files[f"{package_dir}/pyproject.toml"] = generate_pyproject_toml(config)

    # 2. Main plugin module
    files[f"{package_dir}/src/{config.package_name}/__init__.py"] = generate_init_py(config)
    files[f"{package_dir}/src/{config.package_name}/{config.plugin_name}.py"] = generate_plugin_module(config)

    # 3. Tests
    files[f"{package_dir}/tests/__init__.py"] = "# Test package\n"
    files[f"{package_dir}/tests/test_{config.plugin_name}.py"] = generate_test_file(config)

    # 4. Documentation
    files[f"{package_dir}/README.md"] = generate_readme(config)
    files[f"{package_dir}/LICENSE"] = generate_license()

    # 5. GitHub Actions CI
    files[f"{package_dir}/.github/workflows/test.yml"] = generate_github_actions(config)

    # 6. Pre-commit configuration
    files[f"{package_dir}/.pre-commit-config.yaml"] = generate_precommit_config()

    return files


def generate_pyproject_toml(config: PluginConfig) -> str:
    """Generate pyproject.toml with entry points (AIP-001)."""
    entry_point_group = {
        "Metric": "aiperf.metric",
        "Endpoint": "aiperf.endpoint",
        "Data Exporter": "aiperf.data_exporter",
        "Transport": "aiperf.transport",
        "Processor": "aiperf.processor",
        "Collector": "aiperf.collector",
    }.get(config.plugin_type, "aiperf.metric")

    entry_point_name = config.plugin_name
    entry_point_value = f"{config.package_name}.{config.plugin_name}:{config.plugin_class_name}"

    return f'''# SPDX-FileCopyrightText: Copyright (c) 2025 {config.author}
# SPDX-License-Identifier: Apache-2.0

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{config.package_name}"
version = "{config.version}"
description = "{config.description}"
authors = [
    {{name = "{config.author}", email = "{config.email}"}},
]
requires-python = ">=3.10"
dependencies = [
    "aiperf>=0.1.0",  # Minimum AIPerf version
]
readme = "README.md"
license = {{text = "Apache-2.0"}}

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.0.0",
    "mypy>=1.0.0",
]

# AIP-001: Entry Points for Plugin Discovery
[project.entry-points."{entry_point_group}"]
{entry_point_name} = "{entry_point_value}"

[tool.hatch.build.targets.wheel]
packages = ["src/{config.package_name}"]

[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "UP", "B", "SIM", "I"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=src/{config.package_name}"
'''


def generate_init_py(config: PluginConfig) -> str:
    """Generate package __init__.py."""
    return f'''# SPDX-FileCopyrightText: Copyright (c) 2025 {config.author}
# SPDX-License-Identifier: Apache-2.0
"""
{config.package_name} - {config.description}

This package provides a plugin for AIPerf following AIP-001 specification.
"""

from {config.package_name}.{config.plugin_name} import {config.plugin_class_name}

__version__ = "{config.version}"
__all__ = ["{config.plugin_class_name}"]
'''


def generate_plugin_module(config: PluginConfig) -> str:
    """Generate main plugin module based on type."""
    if config.plugin_type == "Metric":
        return generate_metric_plugin(config)
    elif config.plugin_type == "Endpoint":
        return generate_endpoint_plugin(config)
    elif config.plugin_type == "Data Exporter":
        return generate_exporter_plugin(config)
    else:
        return generate_generic_plugin(config)


def generate_metric_plugin(config: PluginConfig) -> str:
    """Generate metric plugin following AIP-001."""
    metric_type = config.extra_config.get('metric_type', 'record')
    value_type = config.extra_config.get('value_type', 'float')

    base_class_map = {
        'record': 'BaseRecordMetric',
        'derived': 'BaseDerivedMetric',
        'aggregate': 'BaseAggregateMetric',
        'counter': 'BaseAggregateCounterMetric',
    }

    base_class = base_class_map.get(metric_type, 'BaseRecordMetric')

    return f'''# SPDX-FileCopyrightText: Copyright (c) 2025 {config.author}
# SPDX-License-Identifier: Apache-2.0
"""
{config.display_name} - AIPerf Metric Plugin

This plugin implements {config.description}.

Plugin Type: {config.plugin_type}
Entry Point Group: aiperf.metric
AIP-001 Compliant: Yes
"""

from aiperf.common.enums import MetricFlags, GenericMetricUnit
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import {base_class}
from aiperf.metrics.metric_dicts import MetricRecordDict, MetricResultsDict


class {config.plugin_class_name}({base_class}[{value_type}]):
    """
    {config.display_name} metric.

    This is an AIPerf plugin that extends the metrics system.
    It is automatically discovered via entry points (AIP-001).

    {config.description}
    """

    # Required metadata
    tag = "{config.plugin_name}"
    header = "{config.display_name}"
    unit = GenericMetricUnit.COUNT  # TODO: Configure appropriate unit
    display_order = {config.extra_config.get('display_order', 500)}
    flags = MetricFlags.NONE  # TODO: Configure flags
    required_metrics = None  # TODO: Add dependencies if needed

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> {value_type}:
        """
        Compute metric value for a single record.

        Args:
            record: Parsed response record
            record_metrics: Previously computed metrics

        Returns:
            Computed metric value

        Raises:
            NoMetricValue: If metric cannot be computed
        """
        # TODO: Implement metric calculation
        # Example:
        # if not record.responses:
        #     raise NoMetricValue("No responses available")
        #
        # return len(record.responses)

        raise NotImplementedError("Implement metric calculation")


# Plugin metadata for AIP-001 discovery
def plugin_metadata():
    """Return plugin metadata for AIPerf discovery."""
    return {{
        "name": "{config.plugin_name}",
        "display_name": "{config.display_name}",
        "version": "{config.version}",
        "author": "{config.author}",
        "description": "{config.description}",
        "plugin_type": "metric",
        "aip_version": "001",
    }}
'''


def generate_endpoint_plugin(config: PluginConfig) -> str:
    """Generate endpoint plugin following AIP-001."""
    return f'''# SPDX-FileCopyrightText: Copyright (c) 2025 {config.author}
# SPDX-License-Identifier: Apache-2.0
"""
{config.display_name} - AIPerf Endpoint Plugin

AIP-001 Compliant Endpoint Plugin for {config.description}
"""

from typing import Dict, Any
from aiperf.clients.model_endpoint_info import ModelEndpointInfo


class {config.plugin_class_name}:
    """
    {config.display_name} endpoint implementation.

    This plugin adds support for {config.description} endpoints to AIPerf.
    Automatically discovered via entry points (AIP-001).
    """

    @staticmethod
    def endpoint_metadata():
        """Return endpoint metadata for discovery."""
        return {{
            "name": "{config.plugin_name}",
            "display_name": "{config.display_name}",
            "api_version": "v1",
            "supports_streaming": True,  # TODO: Configure
            "supported_content_types": ["application/json"],
        }}

    async def send_request(
        self,
        endpoint_info: ModelEndpointInfo,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send request to endpoint.

        Args:
            endpoint_info: Endpoint configuration
            payload: Request payload

        Returns:
            Response data
        """
        # TODO: Implement request sending
        raise NotImplementedError("Implement request sending")

    async def parse_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse endpoint response.

        Args:
            response: Raw response

        Returns:
            Parsed response data
        """
        # TODO: Implement response parsing
        raise NotImplementedError("Implement response parsing")


def plugin_metadata():
    """Return plugin metadata for AIP-001 discovery."""
    return {{
        "name": "{config.plugin_name}",
        "display_name": "{config.display_name}",
        "version": "{config.version}",
        "plugin_type": "endpoint",
        "aip_version": "001",
    }}
'''


def generate_exporter_plugin(config: PluginConfig) -> str:
    """Generate data exporter plugin following AIP-001."""
    return f'''# SPDX-FileCopyrightText: Copyright (c) 2025 {config.author}
# SPDX-License-Identifier: Apache-2.0
"""
{config.display_name} - AIPerf Data Exporter Plugin

AIP-001 Compliant Data Exporter for {config.description}
"""

from pathlib import Path
from typing import Dict, Any
from aiperf.common.models.record_models import ProfileResults


class {config.plugin_class_name}:
    """
    {config.display_name} data exporter.

    Exports AIPerf benchmark results to {config.description} format.
    """

    def __init__(self, output_dir: Path, config: Dict[str, Any]):
        """
        Initialize exporter.

        Args:
            output_dir: Directory for export files
            config: Exporter configuration
        """
        self.output_dir = output_dir
        self.config = config

    async def export(self, results: ProfileResults) -> Path:
        """
        Export benchmark results.

        Args:
            results: Benchmark results to export

        Returns:
            Path to exported file
        """
        # TODO: Implement export logic
        output_file = self.output_dir / "{config.plugin_name}_export.dat"

        # Example implementation:
        # with open(output_file, 'w') as f:
        #     # Write results
        #     pass

        raise NotImplementedError("Implement export logic")

    @staticmethod
    def get_export_info():
        """Return export metadata."""
        return {{
            "format": "{config.plugin_name}",
            "display_name": "{config.display_name}",
            "file_extension": ".dat",  # TODO: Configure
            "description": "{config.description}",
        }}


def plugin_metadata():
    """Return plugin metadata for AIP-001 discovery."""
    return {{
        "name": "{config.plugin_name}",
        "display_name": "{config.display_name}",
        "version": "{config.version}",
        "plugin_type": "data_exporter",
        "aip_version": "001",
    }}
'''


def generate_generic_plugin(config: PluginConfig) -> str:
    """Generate generic plugin template."""
    return f'''# SPDX-FileCopyrightText: Copyright (c) 2025 {config.author}
# SPDX-License-Identifier: Apache-2.0
"""
{config.display_name} - AIPerf Plugin

AIP-001 Compliant Plugin: {config.description}
"""


class {config.plugin_class_name}:
    """
    {config.display_name} plugin implementation.
    """

    def __init__(self, **kwargs):
        """Initialize plugin with dependency injection."""
        # AIP-001: Supports dependency injection
        pass


def plugin_metadata():
    """Return plugin metadata for AIP-001 discovery."""
    return {{
        "name": "{config.plugin_name}",
        "display_name": "{config.display_name}",
        "version": "{config.version}",
        "plugin_type": "{config.plugin_type.lower().replace(' ', '_')}",
        "aip_version": "001",
    }}
'''


def generate_test_file(config: PluginConfig) -> str:
    """Generate test file for plugin."""
    return f'''# SPDX-FileCopyrightText: Copyright (c) 2025 {config.author}
# SPDX-License-Identifier: Apache-2.0
"""
Tests for {config.display_name} plugin.
"""

import pytest


class Test{config.plugin_class_name}:
    """Test suite for {config.plugin_class_name}."""

    def test_plugin_metadata(self):
        """Test that plugin metadata is correctly defined."""
        from {config.package_name}.{config.plugin_name} import plugin_metadata

        metadata = plugin_metadata()
        assert metadata["name"] == "{config.plugin_name}"
        assert metadata["aip_version"] == "001"

    def test_plugin_can_be_instantiated(self):
        """Test that plugin can be created."""
        from {config.package_name}.{config.plugin_name} import {config.plugin_class_name}

        plugin = {config.plugin_class_name}()
        assert plugin is not None

    def test_plugin_implementation(self):
        """Test plugin functionality."""
        # TODO: Add comprehensive tests
        pytest.skip("Implement plugin tests")
'''


def generate_readme(config: PluginConfig) -> str:
    """Generate README for plugin package."""
    return f'''# {config.display_name}

{config.description}

## AIPerf Plugin (AIP-001 Compliant)

This package provides an AIPerf plugin following the official AIP-001 Plugin Architecture specification.

**Plugin Type**: {config.plugin_type}
**Entry Point Group**: aiperf.{config.plugin_type.lower().replace(' ', '_')}

## Installation

```bash
pip install {config.package_name}
```

## Usage

Once installed, the plugin is automatically discovered by AIPerf via entry points.

```bash
# Use AIPerf normally - your plugin will be loaded automatically
aiperf profile --model your-model --url http://localhost:8000
```

## Development

### Setup

```bash
# Clone repository
git clone <your-repo-url>
cd {config.package_name}

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src/{config.package_name}

# Run type checking
mypy src/
```

### Code Quality

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

## License

Apache-2.0

## Contributing

Contributions welcome! Please ensure:
- Tests pass
- Code is formatted (ruff format)
- Type hints are complete
- Documentation is updated

## Author

{config.author} ({config.email})

## Version

{config.version}
'''


def generate_license() -> str:
    """Generate Apache 2.0 license."""
    year = datetime.now().year
    return f'''Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

Copyright {year} - See pyproject.toml for authors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''


def generate_github_actions(config: PluginConfig) -> str:
    """Generate GitHub Actions CI workflow."""
    return f'''# SPDX-FileCopyrightText: Copyright (c) 2025 {config.author}
# SPDX-License-Identifier: Apache-2.0

name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{{{ matrix.python-version }}}}
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: |
          ruff check src/ tests/

      - name: Type check with mypy
        run: |
          mypy src/
        continue-on-error: true

      - name: Test with pytest
        run: |
          pytest --cov=src/{config.package_name} --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
'''


def generate_precommit_config() -> str:
    """Generate pre-commit configuration."""
    return '''# SPDX-FileCopyrightText: Copyright (c) 2025
# SPDX-License-Identifier: Apache-2.0

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-toml

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.13.3
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
'''


def run_wizard():
    """Run the interactive plugin creation wizard."""
    header("AIPerf Plugin Wizard (AIP-001)")

    print(f"{C.BOLD}Create AIPerf plugins following the official AIP-001 specification{C.END}")
    print("This wizard will guide you through creating a complete plugin package.\n")

    # Step 1: Plugin type
    step(1, "Plugin Type Selection")
    plugin_type = ask(
        "What type of plugin do you want to create?",
        choices=[
            "Metric - Performance metrics",
            "Endpoint - API format handlers",
            "Data Exporter - Export formats",
            "Transport - Communication protocols",
            "Processor - Data processors",
            "Collector - Data collection (e.g., Prometheus)",
        ]
    )

    plugin_type = plugin_type.split(' - ')[0]

    # Step 2: Basic information
    step(2, "Basic Information")

    display_name = ask("Plugin display name (e.g., 'My Custom Metric')")
    plugin_name = to_snake_case(display_name)
    plugin_name = ask("Plugin identifier (snake_case)", default=plugin_name)

    class_name = to_pascal_case(plugin_name)
    if not plugin_type.startswith("Metric"):
        class_name = ask("Plugin class name (PascalCase)", default=class_name)
    else:
        class_name = class_name + "Metric"

    description = ask("Brief description")

    # Step 3: Package information
    step(3, "Package Information")

    package_name = ask("Package name (for PyPI)", default=f"aiperf-{plugin_name}")
    author = ask("Author name")
    email = ask("Author email")
    version = ask("Initial version", default="0.1.0")

    # Step 4: Plugin-specific configuration
    extra_config = {}

    if plugin_type == "Metric":
        step(4, "Metric-Specific Configuration")

        metric_type = ask(
            "Metric calculation type?",
            choices=["record", "derived", "aggregate", "counter"]
        )
        extra_config['metric_type'] = metric_type

        value_type = ask(
            "Return value type?",
            choices=["int", "float", "bool", "list[int]", "list[float]"]
        )
        extra_config['value_type'] = value_type

        extra_config['display_order'] = ask("Display order (100-900)", default="500")

    # Create config object
    config = PluginConfig(
        plugin_type=plugin_type,
        plugin_name=plugin_name,
        plugin_class_name=class_name,
        display_name=display_name,
        description=description,
        package_name=package_name,
        author=author,
        email=email,
        version=version,
        extra_config=extra_config,
    )

    # Step: Generate files
    step("Final", "Generate Plugin Package")

    print(f"\n{C.BOLD}Plugin Configuration Summary:{C.END}")
    print(f"  Type: {C.CYAN}{config.plugin_type}{C.END}")
    print(f"  Name: {C.CYAN}{config.plugin_name}{C.END}")
    print(f"  Class: {C.CYAN}{config.plugin_class_name}{C.END}")
    print(f"  Package: {C.CYAN}{config.package_name}{C.END}")
    print(f"  Version: {C.CYAN}{config.version}{C.END}")

    if not confirm("\nCreate plugin package?", default=True):
        warn("Plugin creation cancelled")
        return

    # Generate files
    files = create_plugin_package_structure(config)

    # Create directory structure
    output_dir = Path.cwd() / config.package_name
    if output_dir.exists():
        if not confirm(f"\nDirectory '{config.package_name}' exists. Overwrite?", default=False):
            warn("Cancelled")
            return
        import shutil
        shutil.rmtree(output_dir)

    # Write files
    created = []
    for filepath, content in files.items():
        full_path = Path(filepath)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        created.append(filepath)
        success(f"Created {filepath}")

    # Final instructions
    header("Plugin Created Successfully!")

    print(f"{C.GREEN}{C.BOLD}Your plugin package is ready!{C.END}\n")
    print(f"{C.BOLD}Location:{C.END} {output_dir}")
    print(f"\n{C.BOLD}Next Steps:{C.END}")
    print(f"  1. cd {config.package_name}")
    print(f"  2. Implement TODOs in src/{config.package_name}/{config.plugin_name}.py")
    print(f"  3. Add tests in tests/test_{config.plugin_name}.py")
    print(f"  4. Run: {C.CYAN}pytest{C.END}")
    print(f"  5. Install: {C.CYAN}pip install -e '.[dev]'{C.END}")
    print(f"  6. Verify AIPerf discovers it: {C.CYAN}python -c 'import importlib.metadata; print(list(importlib.metadata.entry_points(group=\"aiperf.{plugin_type.lower().replace(' ', '_')}\")))){C.END}")

    print(f"\n{C.BOLD}Documentation:{C.END}")
    print(f"  • AIP-001 Spec: https://github.com/ai-dynamo/enhancements/pull/43")
    print(f"  • Plugin Guide: guidebook/chapter-47-extending-aiperf.md")
    print(f"  • Metrics Guide: guidebook/chapter-44-custom-metrics-development.md")

    print(f"\n{C.BOLD}Publishing (Optional):{C.END}")
    print(f"  1. Update README.md with examples")
    print(f"  2. Test thoroughly")
    print(f"  3. Build: {C.CYAN}python -m build{C.END}")
    print(f"  4. Publish: {C.CYAN}python -m twine upload dist/*{C.END}")


if __name__ == "__main__":
    try:
        run_wizard()
    except KeyboardInterrupt:
        print(f"\n\n{C.YELLOW}Wizard cancelled{C.END}")
        sys.exit(1)
    except Exception as e:
        error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
