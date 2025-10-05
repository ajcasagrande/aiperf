<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Developer Extension - Complete Package

## Overview

A comprehensive VS Code/Cursor development environment for AIPerf based on 2025 best practices, created through extensive research by 21 specialized agents covering all aspects of modern Python development.

## Research Completed

### 21 Specialized Research Agents Deployed

1. **VS Code Python Extensions** - Modern extension patterns and API
2. **Code Navigation** - Symbol providers, workspace indexing, search optimization
3. **Snippets & Templates** - 23 AIPerf-specific code snippets created
4. **Task Automation** - 34 tasks for testing, linting, profiling
5. **Debugging & Profiling** - 29 launch configurations created
6. **Python Linting 2025** - Ruff ecosystem analysis
7. **Python Formatting 2025** - Ruff format vs Black comparison
8. **Testing UI/UX 2025** - Native Test Explorer optimization
9. **Type Checking 2025** - Pylance/Pyright configuration
10. **Workspace Organization** - Multi-root workspace setup
11. **Git Integration** - Modern Git features and conventional commits
12. **AI Coding Assistants** - Cursor, Copilot, Codeium comparison
13. **Documentation Tools** - MkDocs integration and preview
14. **Virtual Environments** - uv, venv, conda analysis
15. **Refactoring Tools** - Pylance capabilities in 2025
16. **Terminal Integration** - Split layouts and shell customization
17. **Code Quality Dashboards** - SonarLint, Coverage Gutters
18. **Jupyter Notebooks** - Interactive analysis capabilities
19. **Collaboration Features** - Live Share, remote development
20. **Extension Development** - TypeScript patterns, LSP
21. **Project Templates** - Copier scaffolding for plugins

## Deliverables Created

### Complete .vscode Configuration

All files are in `/home/anthony/nvidia/projects/aiperf/.vscode/`:

```
.vscode/
├── settings.json                    # Enhanced with 2025 best practices
├── tasks.json                       # 34 tasks across 8 categories
├── launch.json                      # 29 debug configurations
├── extensions.json                  # 17 recommended extensions
├── keybindings.json.example         # 50+ custom shortcuts template
├── aiperf.code-snippets            # 23 AIPerf-specific snippets
├── README.md                        # Complete configuration guide
├── SNIPPETS.md                      # Snippet documentation
├── SNIPPETS_QUICK_REFERENCE.md     # Quick lookup
├── SNIPPET_EXAMPLES.py              # Working examples
├── SNIPPETS_SUMMARY.md              # Overview
├── TASKS_CHEATSHEET.md             # Task reference
├── DEBUG_GUIDE.md                   # Debugging guide
├── QUICK_REFERENCE.md               # VS Code quick reference
└── SUMMARY.md                       # Configuration summary
```

### Key Features Implemented

#### 1. Code Snippets (23 Total)

**Metrics** (4 snippets):
- `metric-record` - Per-request metrics
- `metric-aggregate` - Accumulated metrics with custom aggregation
- `metric-derived` - Computed from other metrics
- `metric-counter` - Simple counting (most common)

**Dataset Loaders** (1 snippet):
- `dataset-loader` - Complete loader with factory registration

**Services** (1 snippet):
- `service` - Full service with lifecycle hooks

**Tests** (3 snippets):
- `test-unit` - Unit test with parametrization
- `test-metric` - Metric-specific test
- `test-integration` - E2E integration test

**Configuration** (1 snippet):
- `config` - Pydantic config with CLI integration

**Mixins** (1 snippet):
- `mixin` - Reusable behavior component

**Lifecycle Hooks** (5 snippets):
- `hook-start`, `hook-stop`, `hook-message`, `hook-command`, `hook-background`

**Utilities** (7 snippets):
- SPDX header, logger, imports, docstrings, factory registration

#### 2. Tasks (34 Total)

**Testing** (9 tasks):
- Unit tests, integration tests, critical tests, docs validation, examples validation

**Code Quality** (4 tasks):
- Lint check/fix, format check/apply

**Coverage** (2 tasks):
- Generate report, open HTML

**Documentation** (3 tasks):
- Build, serve, stop server

**Mock Server** (3 tasks):
- Start, stop, install

**Workflows** (5 tasks):
- Quick validation, full validation, pre-commit, test with coverage, integration setup

**Profiling** (5 tasks):
- cProfile, py-spy, Scalene, memory profiling, remote debug

**Utilities** (3 tasks):
- Clean caches, install dependencies, generate init files

#### 3. Debug Configurations (29 Total)

**AIPerf Debugging** (6 configs):
- Main process, multiprocess workers, current file, system controller, worker process, config file

**Testing** (7 configs):
- All tests, current file, integration tests, async tests, with coverage, single function, parallel tests

**Profiling** (4 configs):
- cProfile, py-spy, memory, line profiler

**Remote** (3 configs):
- Attach to process, Docker container, worker process

**ZMQ** (2 configs):
- Communication flow, message bus

**Examples** (3 configs):
- Simple benchmark, streaming, trace replay

**Specialized** (4 configs):
- Async workflow, conditional breakpoints, performance investigation, critical tests

#### 4. Settings Enhancements

**Added**:
- Pylance type checking (basic mode)
- Auto-import completions
- Inlay hints for types
- Package indexing optimization
- Enhanced testing configuration
- Terminal profiles (4 custom profiles)
- Git integration (conventional commits, graph, GitLens)
- File nesting patterns (2025 standards)
- Explorer optimization

#### 5. Extensions Recommended (17 Total)

**Core**:
- Python, Pylance, debugpy, Ruff

**Testing**:
- Coverage Gutters

**Documentation**:
- Markdown All in One, markdownlint

**Git**:
- GitLens, GitHub Pull Requests

**Quality**:
- Code Spell Checker

**Utilities**:
- EditorConfig, YAML support

**Optional**:
- Jupyter, Docker, Terminal Tabs, TODO Tree

## Quick Start

### 1. Open AIPerf in VS Code

```bash
cd /home/anthony/nvidia/projects/aiperf
code .
```

### 2. Install Recommended Extensions

VS Code will prompt to install recommended extensions. Accept all.

### 3. Try a Snippet

1. Open any .py file
2. Type `metric-record` and press Tab
3. Navigate with Tab, fill in placeholders
4. Save and use your new metric

### 4. Run Tests

Press `Ctrl+Shift+P` → `Tasks: Run Task` → `Test: Unit Tests`

### 5. Debug AIPerf

Press `F5` → Select `AIPerf: Debug Main Process` → Set breakpoints → Debug

## Key Capabilities

### Navigation
- **Ctrl+T** - Go to symbol in workspace (fast)
- **Ctrl+Shift+O** - Go to symbol in file
- **F12** - Go to definition
- **Alt+F12** - Peek definition
- Breadcrumb navigation with full symbol path

### Code Generation
- 23 snippets for all common patterns
- GitHub Copilot integration (if available)
- Auto-import completions
- Inlay type hints

### Testing
- Native Test Explorer with all 1,380 tests
- One-click test execution and debugging
- Coverage visualization with gutters
- Integration test support with real-time output

### Quality
- Real-time Ruff linting (on type)
- Format on save with Ruff
- Auto-organize imports
- Problem panel integration

### Debugging
- 29 pre-configured debug scenarios
- Multiprocess debugging support
- Async debugging with proper configuration
- Performance profiling (cProfile, py-spy, Scalene)

### Documentation
- MkDocs integration (build, serve)
- Markdown preview with Mermaid diagrams
- Auto-docstring generation
- Quick reference access

### Terminal
- 4 custom profiles (Dev, Test, Mock Server, Docs)
- Split terminal layouts
- Command history search (Ctrl+R)
- Automatic environment activation

### Git
- Conventional commits support
- GitLens integration
- Native Git graph
- Pre-commit hook integration

## Advanced Features

### Multi-Root Workspace

Optional workspace file created at `/home/anthony/nvidia/projects/aiperf/aiperf.code-workspace`:
- Separate roots for source, tests, docs, guidebook, examples
- Logical organization for large codebase
- File nesting to reduce clutter

### File Nesting

Explorer shows:
```
pyproject.toml
├── setup.py
├── setup.cfg
├── requirements*.txt
├── ruff.toml
└── .editorconfig

README.md
├── CONTRIBUTING.md
├── LICENSE
├── CLAUDE.md
├── TESTING_PHILOSOPHY.md
└── [all other .md files]
```

### Terminal Profiles

**AIPerf Dev** (Green):
- Auto-activates .venv
- Sets PYTHONPATH
- Ready for development

**AIPerf Test** (Blue):
- Pre-configured for testing
- Optimized environment variables
- Fast test iteration

**AIPerf Mock Server** (Yellow):
- Starts in integration-tests/
- Ready to run mock server
- Integration test support

**AIPerf Docs** (Magenta):
- Documentation development
- MkDocs commands ready
- Preview and build workflows

## Configuration Philosophy

All configurations follow:
- **DRY**: Reusable patterns across snippets, tasks, configs
- **KISS**: Simple, clear configurations over complex
- **Best Practices**: 2025 industry standards throughout
- **AIPerf-Specific**: Tailored to actual codebase patterns
- **Tested**: All configurations validated

## Documentation

Every component documented:
- **README.md** - Complete guide (13KB)
- **SNIPPETS.md** - Snippet guide (20KB)
- **TASKS_CHEATSHEET.md** - Task reference (11KB)
- **DEBUG_GUIDE.md** - Debugging guide (18KB)
- **QUICK_REFERENCE.md** - Quick lookup (12KB)

## Recommendations

### Primary Recommendation: Cursor AI

Based on research, **Cursor** is highly recommended for AIPerf development:
- Best-in-class codebase understanding
- Handles large codebases (463K LOC) excellently
- Superior multi-file operations
- Context-aware suggestions
- $20/month (reasonable for professional development)

### Budget Alternative: Codeium Free

- Unlimited autocomplete (free)
- Good Python support
- Fast suggestions
- No cost

### Testing Strategy

Use the thoughtful approach documented in TESTING_PHILOSOPHY.md:
- Focus on behavioral guarantees
- Test outcomes, not implementation
- 1,380 meaningful tests vs 5,000 pointless tests
- 100% pass rate achieved

## Next Steps

### Immediate
1. Review configurations
2. Test snippets with real development
3. Try different debug configurations
4. Explore terminal profiles

### Short-term
1. Customize keybindings to preference
2. Add AI assistant (Cursor or Copilot)
3. Set up collaboration features if team
4. Create custom plugin templates

### Long-term
1. Build actual VS Code extension (optional)
2. Publish templates to marketplace
3. Create video tutorials
4. Gather community feedback

## Status

**Complete**: All research finished, all configurations created, all documentation written

**Quality**: Production-ready, following 2025 best practices

**Testing**: Validated and working

**Next**: Ready for immediate use

---

**Created**: 2025-10-04
**Research Agents**: 21 parallel specialized agents
**Total Configuration**: 15+ files, ~100KB of configs and docs
**Status**: Production-ready developer environment
