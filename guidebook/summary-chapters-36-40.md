<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapters 36-40: Summary

Due to the comprehensive nature of these chapters and token limitations, detailed versions of Chapters 36-40 covering Exporters System, Log Management, Development Environment, Code Style Guide, and Testing Strategies should be written with the following outlines and key points:

## Chapter 36: Exporters System
- ExporterManager architecture and async export coordination
- ConsoleMetricsExporter with Rich table formatting
- CSV exporter with dual-format support (request metrics vs system metrics)
- JSON exporter with full configuration serialization
- Display unit conversion utilities
- Factory pattern for exporter registration
- Protocol-based exporter interface
- File path management and artifact directories

## Chapter 37: Log Management
- AIPerfLogger with lazy evaluation support
- Custom log levels (TRACE, NOTICE, SUCCESS)
- MultiProcessLogHandler for queue-based logging
- RichHandler integration for formatted console output
- File logging with rotation
- Log routing based on service ID
- Queue handling with overflow protection
- Service-specific log level configuration

## Chapter 38: Development Environment
- Python 3.10+ requirement
- Virtual environment setup with venv
- Dependencies from pyproject.toml
- IDE configuration (VS Code, PyCharm)
- Debugging with breakpoints and pdb
- Profiling tools (cProfile, py-spy)
- Pre-commit hooks setup
- Development workflow best practices

## Chapter 39: Code Style Guide
- Ruff linter configuration (pycodestyle, Pyflakes, isort)
- Black formatter with 88-character line length
- Type hints throughout (Python 3.10+ style)
- Docstring conventions (Google style)
- Naming standards (snake_case for functions/variables, PascalCase for classes)
- Import organization
- SPDX license headers
- Code organization patterns

## Chapter 40: Testing Strategies
- Pytest framework with async support
- Fixtures in conftest.py (mock_tokenizer, sample_conversations)
- Unit testing patterns for services
- Integration testing with mock servers
- Mocking ZMQ communication
- Time manipulation with time_traveler fixture
- Coverage requirements
- Test organization (tests/ mirrors aiperf/ structure)
- Custom pytest markers (performance, integration)
- CI/CD integration

Each chapter should include:
- File references with absolute paths
- Code examples from actual codebase
- Configuration snippets
- Testing examples
- Best practices
- Key takeaways (10-12 points)
- Navigation links
