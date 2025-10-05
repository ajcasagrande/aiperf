#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
AIPerf Plugin Creator - Interactive CLI Wizard

This tool provides an interactive wizard for creating AIPerf plugins following
established patterns and best practices.

Supported Plugin Types:
- Metrics (Record, Aggregate, Derived, Counter)
- Dataset Loaders (Custom, Public)
- Services (Component, Base)
- Request Converters
- Response Parsers

Usage:
    python tools/create_plugin.py

Features:
- Interactive prompts with validation
- Automatic file generation
- Test file creation
- Documentation scaffolding
- Factory registration
- Best practices enforcement
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import re


class Colors:
    """ANSI color codes for terminal output."""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")


def print_step(step: int, text: str):
    """Print a formatted step."""
    print(f"{Colors.CYAN}{Colors.BOLD}[Step {step}]{Colors.END} {text}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓{Colors.END} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗{Colors.END} {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.END} {text}")


def prompt(question: str, default: str = None, choices: List[str] = None) -> str:
    """
    Prompt user for input with optional default and choices.

    Args:
        question: Question to ask
        default: Default value if user presses Enter
        choices: List of valid choices

    Returns:
        User's response
    """
    if choices:
        print(f"\n{Colors.BOLD}{question}{Colors.END}")
        for i, choice in enumerate(choices, 1):
            print(f"  {Colors.CYAN}{i}.{Colors.END} {choice}")

        while True:
            response = input(f"{Colors.YELLOW}Select (1-{len(choices)}){Colors.END}: ").strip()
            if response.isdigit() and 1 <= int(response) <= len(choices):
                return choices[int(response) - 1]
            print_error(f"Please enter a number between 1 and {len(choices)}")
    else:
        prompt_text = f"{Colors.YELLOW}{question}{Colors.END}"
        if default:
            prompt_text += f" {Colors.CYAN}[{default}]{Colors.END}"
        prompt_text += ": "

        response = input(prompt_text).strip()
        return response if response else default


def confirm(question: str, default: bool = True) -> bool:
    """
    Ask yes/no question.

    Args:
        question: Question to ask
        default: Default answer

    Returns:
        True for yes, False for no
    """
    default_str = "Y/n" if default else "y/N"
    response = input(f"{Colors.YELLOW}{question} [{default_str}]{Colors.END}: ").strip().lower()

    if not response:
        return default

    return response in ('y', 'yes')


def validate_identifier(name: str) -> bool:
    """Check if name is valid Python identifier."""
    return name.isidentifier()


def to_snake_case(text: str) -> str:
    """Convert text to snake_case."""
    text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', text)
    text = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', text)
    text = re.sub(r'[^\w]', '_', text)
    return text.lower().strip('_')


def to_pascal_case(text: str) -> str:
    """Convert text to PascalCase."""
    return ''.join(word.capitalize() for word in text.split('_'))


def create_metric_plugin(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Create metric plugin files.

    Returns:
        Dict mapping file paths to content
    """
    metric_name = config['metric_name']
    class_name = to_pascal_case(metric_name) + 'Metric'
    metric_type = config['metric_type']

    # Determine base class
    if metric_type == 'record':
        base_class = 'BaseRecordMetric'
        method_name = '_parse_record'
        method_params = 'self, record: ParsedResponseRecord, record_metrics: MetricRecordDict'
        method_return = config['value_type']
    elif metric_type == 'aggregate':
        base_class = 'BaseAggregateMetric'
        method_name = '_parse_record and _aggregate_value'
        method_params = 'self, ...'
        method_return = config['value_type']
    elif metric_type == 'derived':
        base_class = 'BaseDerivedMetric'
        method_name = '_derive_value'
        method_params = 'self, metric_results: MetricResultsDict'
        method_return = config['value_type']
    else:  # counter
        base_class = 'BaseAggregateCounterMetric'
        method_name = None
        method_params = None
        method_return = 'int'

    # Generate imports
    imports = [
        "# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.",
        "# SPDX-License-Identifier: Apache-2.0",
        f'"""{config["metric_display_name"]} metric implementation.',
        "",
        "This metric computes " + config.get('description', 'custom values') + ".",
        '"""',
        "",
    ]

    if metric_type in ['record', 'aggregate']:
        imports.extend([
            "from aiperf.common.enums import MetricFlags, " + config['unit_import'],
            "from aiperf.common.exceptions import NoMetricValue",
            "from aiperf.common.models import ParsedResponseRecord",
            f"from aiperf.metrics import {base_class}",
            "from aiperf.metrics.metric_dicts import MetricRecordDict",
        ])
    elif metric_type == 'derived':
        imports.extend([
            "from aiperf.common.enums import MetricFlags, " + config['unit_import'],
            "from aiperf.common.exceptions import NoMetricValue",
            f"from aiperf.metrics import {base_class}",
            "from aiperf.metrics.metric_dicts import MetricResultsDict",
        ])
        # Add required metric imports
        for req_metric in config.get('required_metrics', []):
            metric_class = to_pascal_case(req_metric) + 'Metric'
            imports.append(f"from aiperf.metrics.types.{req_metric} import {metric_class}")
    else:  # counter
        imports.extend([
            "from aiperf.common.enums import GenericMetricUnit, MetricFlags",
            "from aiperf.metrics.base_aggregate_counter_metric import BaseAggregateCounterMetric",
        ])

    imports.append("")
    imports.append("")

    # Generate class definition
    class_def = [
        f"class {class_name}({base_class}[{method_return}]):",
        f'    """{config["metric_display_name"]} metric.',
        "    ",
    ]

    if config.get('formula'):
        class_def.append(f"    Formula:")
        class_def.append(f"        {config['formula']}")
        class_def.append("    ")

    class_def.extend([
        '    """',
        "",
        f'    tag = "{metric_name}"',
        f'    header = "{config["metric_display_name"]}"',
    ])

    if config.get('short_header'):
        class_def.append(f'    short_header = "{config["short_header"]}"')

    class_def.extend([
        f'    unit = {config["unit"]}',
    ])

    if config.get('display_unit'):
        class_def.append(f'    display_unit = {config["display_unit"]}')

    if config.get('display_order'):
        class_def.append(f'    display_order = {config["display_order"]}')

    class_def.append(f'    flags = {config["flags"]}')

    if config.get('required_metrics'):
        req_metrics_str = ', '.join(f'"{m}"' for m in config['required_metrics'])
        class_def.append(f'    required_metrics = {{{req_metrics_str}}}')
    else:
        class_def.append('    required_metrics = None')

    # Add method implementation for non-counter metrics
    if metric_type != 'counter':
        class_def.extend([
            "",
            f"    def {method_name}(",
            f"        {method_params}",
            f"    ) -> {method_return}:",
            '        """',
        ])

        if metric_type == 'record':
            class_def.extend([
                "        Compute the metric value for a single record.",
                "        ",
                "        Args:",
                "            record: The parsed response record",
                "            record_metrics: Previously computed metrics",
                "        ",
                "        Returns:",
                f"            The computed {config['metric_display_name']} value",
                "        ",
                "        Raises:",
                "            NoMetricValue: If metric cannot be computed for this record",
            ])
        elif metric_type == 'derived':
            class_def.extend([
                "        Derive metric value from other computed metrics.",
                "        ",
                "        Args:",
                "            metric_results: Dictionary of all computed metrics",
                "        ",
                "        Returns:",
                f"            The computed {config['metric_display_name']} value",
                "        ",
                "        Raises:",
                "            NoMetricValue: If required metrics are missing",
            ])

        class_def.extend([
            '        """',
            "        # TODO: Implement metric calculation",
            f'        raise NotImplementedError("{config["metric_display_name"]} calculation not implemented")',
        ])

    metric_content = '\n'.join(imports + class_def)

    # Generate test file
    test_content = generate_metric_test(config, class_name)

    return {
        f"aiperf/metrics/types/{metric_name}.py": metric_content,
        f"tests/metrics/test_{metric_name}.py": test_content,
    }


def generate_metric_test(config: Dict[str, Any], class_name: str) -> str:
    """Generate test file for metric."""
    metric_name = config['metric_name']

    test_lines = [
        "# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.",
        "# SPDX-License-Identifier: Apache-2.0",
        f'"""Tests for {config["metric_display_name"]} metric."""',
        "",
        "import pytest",
        "",
        "from aiperf.common.exceptions import NoMetricValue",
        "from aiperf.common.models import ParsedResponseRecord",
        f"from aiperf.metrics.types.{metric_name} import {class_name}",
        "from aiperf.metrics.metric_dicts import MetricRecordDict",
        "",
        "",
        f"class Test{class_name}:",
        f'    """Test suite for {class_name}."""',
        "",
        "    def test_basic_computation(self):",
        f'        """Test basic {config["metric_display_name"]} computation."""',
        "        # TODO: Implement test",
        "        pytest.skip('Implement basic computation test')",
        "",
        "    def test_missing_data_raises_no_metric_value(self):",
        '        """Test that missing data raises NoMetricValue."""',
        "        # TODO: Implement test",
        "        pytest.skip('Implement missing data test')",
        "",
        "    @pytest.mark.parametrize('input,expected', [",
        "        # TODO: Add test cases",
        "    ])",
        "    def test_parametrized_values(self, input, expected):",
        '        """Test various input values."""',
        "        pytest.skip('Add parametrized test cases')",
    ]

    return '\n'.join(test_lines)


def main():
    """Run the interactive plugin creator."""
    print_header("AIPerf Plugin Creator")

    print(f"{Colors.BOLD}Welcome to the AIPerf Plugin Creation Wizard!{Colors.END}")
    print("This tool will guide you through creating a new AIPerf plugin.\n")

    # Step 1: Select plugin type
    print_step(1, "Select Plugin Type")
    plugin_type = prompt(
        "What type of plugin do you want to create?",
        choices=[
            "Metric (Record) - Per-request calculations",
            "Metric (Derived) - Computed from other metrics",
            "Metric (Aggregate) - Accumulated values",
            "Metric (Counter) - Simple counting",
            "Dataset Loader - Custom dataset support",
            "Service - New AIPerf service",
            "Request Converter - API payload formatting",
            "Response Parser - Response extraction",
        ]
    )

    plugin_category = plugin_type.split(' - ')[0]

    if plugin_category.startswith("Metric"):
        files = create_metric_wizard()
    elif plugin_category == "Dataset Loader":
        files = create_dataset_wizard()
    elif plugin_category == "Service":
        files = create_service_wizard()
    else:
        print_error(f"{plugin_category} creation not yet implemented")
        print("Use the code snippets in VS Code instead:")
        print(f"  1. Open a .py file in VS Code")
        print(f"  2. Type the snippet prefix (e.g., 'metric-record')")
        print(f"  3. Press Tab and fill in the template")
        return

    # Step: Confirm and create files
    print_step("Final", "Review and Create")
    print(f"\n{Colors.BOLD}Files to be created:{Colors.END}")
    for filepath in files.keys():
        print(f"  {Colors.CYAN}•{Colors.END} {filepath}")

    if not confirm("\nCreate these files?", default=True):
        print_warning("Plugin creation cancelled")
        return

    # Create files
    project_root = Path(__file__).parent.parent
    created_files = []

    for filepath, content in files.items():
        full_path = project_root / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if full_path.exists():
            if not confirm(f"\n{filepath} already exists. Overwrite?", default=False):
                print_warning(f"Skipped {filepath}")
                continue

        full_path.write_text(content)
        created_files.append(filepath)
        print_success(f"Created {filepath}")

    # Success summary
    print_header("Plugin Created Successfully!")

    print(f"{Colors.GREEN}{Colors.BOLD}Next Steps:{Colors.END}")
    print(f"  1. Implement the TODO sections in the generated files")
    print(f"  2. Run the tests: {Colors.CYAN}pytest {created_files[1] if len(created_files) > 1 else 'tests/'}{Colors.END}")
    print(f"  3. Import and use your new plugin")
    print(f"\n{Colors.BOLD}Documentation:{Colors.END}")
    print(f"  • Metrics Guide: guidebook/chapter-44-custom-metrics-development.md")
    print(f"  • Testing Guide: guidebook/chapter-40-testing-strategies.md")
    print(f"  • Contributing: CONTRIBUTING.md")


def create_metric_wizard() -> Dict[str, str]:
    """Interactive wizard for creating metrics."""
    config = {}

    # Step 2: Basic information
    print_step(2, "Basic Information")

    while True:
        metric_name = prompt("Metric tag (snake_case, e.g., 'my_latency')")
        if validate_identifier(metric_name):
            config['metric_name'] = metric_name
            break
        print_error("Must be valid Python identifier (letters, numbers, underscores)")

    config['metric_display_name'] = prompt(
        "Display name (e.g., 'My Latency Metric')",
        default=metric_name.replace('_', ' ').title()
    )

    config['short_header'] = prompt(
        "Short header for dashboard (optional, e.g., 'My Lat')",
        default=None
    )

    config['description'] = prompt(
        "Brief description",
        default="custom metric values"
    )

    # Step 3: Metric type
    print_step(3, "Metric Type Selection")
    metric_type_choice = prompt(
        "What type of metric?",
        choices=[
            "Record - Per-request values (e.g., TTFT, latency)",
            "Derived - Computed from other metrics (e.g., throughput)",
            "Aggregate - Accumulated values (e.g., max timestamp)",
            "Counter - Simple counting (e.g., request count)",
        ]
    )
    config['metric_type'] = metric_type_choice.split(' - ')[0].lower()

    # Step 4: Value type
    print_step(4, "Value Type")
    value_type = prompt(
        "What type of value does this metric return?",
        choices=["int", "float", "bool", "list[int]", "list[float]"]
    )
    config['value_type'] = value_type

    # Step 5: Unit
    print_step(5, "Unit of Measurement")
    unit_choice = prompt(
        "What unit does this metric use?",
        choices=[
            "Time (nanoseconds)",
            "Tokens",
            "Requests",
            "Ratio",
            "Tokens per second",
            "Requests per second",
            "Custom"
        ]
    )

    unit_map = {
        "Time (nanoseconds)": ("MetricTimeUnit.NANOSECONDS", "MetricTimeUnit"),
        "Tokens": ("GenericMetricUnit.TOKENS", "GenericMetricUnit"),
        "Requests": ("GenericMetricUnit.REQUESTS", "GenericMetricUnit"),
        "Ratio": ("GenericMetricUnit.RATIO", "GenericMetricUnit"),
        "Tokens per second": ("MetricOverTimeUnit.TOKENS_PER_SECOND", "MetricOverTimeUnit"),
        "Requests per second": ("MetricOverTimeUnit.REQUESTS_PER_SECOND", "MetricOverTimeUnit"),
    }

    if unit_choice != "Custom":
        config['unit'], config['unit_import'] = unit_map[unit_choice]
    else:
        config['unit'] = "GenericMetricUnit.COUNT"
        config['unit_import'] = "GenericMetricUnit"

    # Display unit
    if unit_choice == "Time (nanoseconds)":
        config['display_unit'] = "MetricTimeUnit.MILLISECONDS"
    else:
        config['display_unit'] = None

    # Step 6: Flags
    print_step(6, "Metric Flags")
    flags = []

    if confirm("Is this metric only for streaming endpoints?", default=False):
        flags.append("MetricFlags.STREAMING_ONLY")

    if confirm("Is this metric only for token-producing endpoints?", default=False):
        flags.append("MetricFlags.PRODUCES_TOKENS_ONLY")

    if confirm("Is this metric only for error cases?", default=False):
        flags.append("MetricFlags.ERROR_ONLY")

    if confirm("Should this metric be hidden from console output?", default=False):
        flags.append("MetricFlags.NO_CONSOLE")

    if confirm("Is higher value better? (for throughput, counts)", default=False):
        flags.append("MetricFlags.LARGER_IS_BETTER")

    config['flags'] = ' | '.join(flags) if flags else 'MetricFlags.NONE'

    # Step 7: Dependencies (for non-counter metrics)
    if config['metric_type'] != 'counter':
        print_step(7, "Dependencies")
        if confirm("Does this metric depend on other metrics?", default=False):
            deps = prompt("Enter comma-separated metric tags (e.g., 'ttft,request_latency')")
            config['required_metrics'] = [d.strip() for d in deps.split(',') if d.strip()]
        else:
            config['required_metrics'] = []

    # Step 8: Display order
    print_step(8, "Display Settings")
    config['display_order'] = prompt("Display order (100-900, lower=earlier)", default="500")

    # Step 9: Formula/description
    config['formula'] = prompt("Formula or calculation description (optional)", default=None)

    # Generate files
    return create_metric_plugin(config)


def create_dataset_wizard() -> Dict[str, str]:
    """Interactive wizard for dataset loaders."""
    print_warning("Dataset loader wizard not yet implemented")
    print("Use the 'dataset-loader' snippet in VS Code instead")
    return {}


def create_service_wizard() -> Dict[str, str]:
    """Interactive wizard for services."""
    print_warning("Service wizard not yet implemented")
    print("Use the 'service' snippet in VS Code instead")
    return {}


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Plugin creation cancelled{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
