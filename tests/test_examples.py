# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Example Validation Tests

Validates that all example files are syntactically correct and importable.
Does not execute the examples (which would require running servers).
"""

import ast
from pathlib import Path

import pytest


class TestExampleValidity:
    """Test that examples are valid Python and well-structured."""

    @pytest.fixture
    def examples_dir(self):
        """Get examples directory path."""
        return Path(__file__).parent.parent / "examples"

    def test_all_examples_have_shebang(self, examples_dir):
        """Test that all example Python files have proper shebang."""
        for example in examples_dir.rglob("*.py"):
            with open(example) as f:
                first_line = f.readline()
                assert first_line.startswith("#!"), f"{example} missing shebang"
                assert "python" in first_line, f"{example} shebang not Python"

    def test_all_examples_have_docstring(self, examples_dir):
        """Test that all examples have module docstrings."""
        for example in examples_dir.rglob("*.py"):
            with open(example) as f:
                tree = ast.parse(f.read(), filename=str(example))
                docstring = ast.get_docstring(tree)
                assert docstring is not None, f"{example} missing module docstring"
                assert "Usage:" in docstring, f"{example} docstring missing usage"

    def test_all_examples_syntactically_valid(self, examples_dir):
        """Test that all examples are syntactically valid Python."""
        for example in examples_dir.rglob("*.py"):
            with open(example) as f:
                try:
                    ast.parse(f.read(), filename=str(example))
                except SyntaxError as e:
                    pytest.fail(f"Syntax error in {example}: {e}")

    def test_all_examples_have_main_guard(self, examples_dir):
        """Test that all examples have if __name__ == '__main__' guard."""
        for example in examples_dir.rglob("*.py"):
            with open(example) as f:
                content = f.read()
                assert (
                    '__name__ == "__main__"' in content
                    or "__name__ == '__main__'" in content
                ), f"{example} missing main guard"

    def test_examples_use_correct_imports(self, examples_dir):
        """Test that examples import from aiperf correctly."""
        for example in examples_dir.rglob("*.py"):
            with open(example) as f:
                content = f.read()

                # Examples should manipulate sys.path for imports
                # Look for the pattern: sys.path.insert(0, ...)
                has_path_insert = "sys.path.insert" in content

                # Examples should manipulate sys.path or they won't import
                assert has_path_insert, f"{example.name} should add parent to sys.path"

    @pytest.mark.parametrize(
        "example_name",
        [
            "basic/simple_benchmark.py",
            "basic/streaming_benchmark.py",
            "basic/request_rate_test.py",
            "advanced/trace_replay.py",
            "advanced/goodput_measurement.py",
            "advanced/request_cancellation.py",
            "custom-metrics/custom_record_metric.py",
            "custom-metrics/custom_derived_metric.py",
            "custom-datasets/custom_single_turn.py",
            "custom-datasets/custom_multi_turn.py",
            "integration/vllm_integration.py",
            "integration/tgi_integration.py",
            "integration/multimodal_benchmark.py",
            "integration/openai_compatible.py",
        ],
    )
    def test_example_exists_and_valid(self, examples_dir, example_name):
        """Test that each documented example exists and is valid."""
        example_path = examples_dir / example_name
        assert example_path.exists(), f"Example not found: {example_name}"

        # Test it's valid Python
        with open(example_path) as f:
            try:
                ast.parse(f.read(), filename=example_name)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {example_name}: {e}")
