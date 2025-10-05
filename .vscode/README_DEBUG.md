<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf VS Code Debugging & Profiling - Getting Started

## Quick Navigation

📋 **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Start here for quick cheat sheet
📖 **[DEBUG_GUIDE.md](DEBUG_GUIDE.md)** - Comprehensive debugging guide
📊 **[SUMMARY.md](SUMMARY.md)** - Complete configuration overview
⚙️  **[launch.json](launch.json)** - Debug configurations (29 configs)
🔧 **[tasks.json](tasks.json)** - VS Code tasks with profiling
🎯 **[settings.json](settings.json)** - VS Code settings

## 5-Minute Quick Start

### 1. Install Required Tools
```bash
# Install debugging and profiling packages
pip install debugpy pytest pytest-cov pytest-asyncio

# Optional profiling tools
pip install py-spy scalene line-profiler memory-profiler
```

### 2. Open AIPerf in VS Code
```bash
code /home/anthony/nvidia/projects/aiperf
```

### 3. Start Debugging

#### Debug AIPerf Main Process
1. Press `F5` or click Run & Debug icon
2. Select: **"AIPerf: Debug Main Process"**
3. Set breakpoints by clicking line numbers
4. Press `F5` to start

#### Debug a Test
1. Open a test file: `tests/metrics/test_ttft_metric.py`
2. Press `F5`
3. Select: **"Pytest: Debug Current File"**
4. Set breakpoint in test function
5. Press `F5` to start

#### Debug Worker Processes
1. Press `F5`
2. Select: **"AIPerf: Debug with Multiprocess (Workers)"**
3. Set breakpoint in `aiperf/workers/worker.py`
4. When hit, check **Call Stack** view to see all workers

### 4. Profile Performance
```bash
# Quick CPU profile
F5 → "Profile: cProfile AIPerf Main"

# View results
Ctrl+Shift+P → Tasks: Run Task → "Profile: View cProfile Results"

# Or use py-spy (no code changes!)
Ctrl+Shift+P → Tasks: Run Task → "Profile: py-spy Record"
```

### 5. Common Keyboard Shortcuts
| Action | Key |
|--------|-----|
| Start/Continue | F5 |
| Step Over | F10 |
| Step Into | F11 |
| Toggle Breakpoint | F9 |
| Debug Console | Ctrl+Shift+Y |

## What You Get

### 29 Debug Configurations
- 6 AIPerf configurations (main process, workers, system controller, etc.)
- 7 Testing configurations (all tests, current file, integration, async, etc.)
- 4 Profiling configurations (cProfile, memory, line profiler)
- 3 Remote debugging configurations (Docker, SSH, custom port)
- 2 ZMQ debugging configurations
- 4 Specialized configurations (async workflow, performance investigation)
- 3 Example script configurations

### Advanced Features
- ✅ Multiprocess debugging with subprocess attachment
- ✅ Async/await debugging
- ✅ Conditional breakpoints
- ✅ Logpoints (no code changes!)
- ✅ Watch expressions
- ✅ Remote debugging (Docker, SSH)
- ✅ ZMQ communication debugging
- ✅ Performance profiling (cProfile, py-spy, scalene)
- ✅ Memory profiling (tracemalloc, memory_profiler)
- ✅ Coverage debugging

## Common Scenarios

### Scenario 1: Debug a Bug in Main Logic
```
1. Set breakpoint in aiperf/controller/system_controller.py
2. F5 → "AIPerf: Debug Main Process"
3. Step through code with F10/F11
4. Inspect variables in Variables view or Debug Console
```

### Scenario 2: Debug Worker Communication Issue
```
1. Set breakpoint in aiperf/workers/worker.py
2. F5 → "AIPerf: Debug with Multiprocess (Workers)"
3. When breakpoint hits, see all worker processes in Call Stack
4. Switch between workers to inspect state
```

### Scenario 3: Find Performance Bottleneck
```
1. F5 → "Profile: cProfile AIPerf Main"
2. Wait for completion
3. Ctrl+Shift+P → Tasks: Run Task → "Profile: View cProfile Results"
4. Identify slow functions
5. Set breakpoints to understand why
```

### Scenario 4: Debug Failing Test
```
1. Open test file with failing test
2. Set breakpoint before assertion
3. F5 → "Pytest: Debug Current File"
4. Inspect variables when breakpoint hits
5. Find the bug, fix it, rerun
```

### Scenario 5: Debug in Docker Container
```
1. Add to Dockerfile: RUN pip install debugpy
2. In code: debugpy.listen(("0.0.0.0", 5678)); debugpy.wait_for_client()
3. Expose port: docker run -p 5678:5678 ...
4. F5 → "Remote: Attach to Docker Container"
```

## Tips for Success

1. **Start Simple:** Use single-process debugging first
2. **Use Conditional Breakpoints:** Break only when needed
3. **Try Logpoints:** Log without stopping execution
4. **Debug Tests:** Tests are easier to debug than full app
5. **Profile First:** Find bottlenecks before optimizing

## Troubleshooting

### Breakpoints Not Hit?
- Set `"justMyCode": false` in configuration
- For tests: ensure `"PYTEST_ADDOPTS": "--no-cov"`
- For workers: use `"subProcess": true`

### Debugger Slow?
- Use `--max-workers 1`
- Set `"justMyCode": true`
- Reduce logging: `--log-level ERROR`

### Coverage Breaks Debugging?
- Always use `--no-cov` when debugging
- Use separate "Debug with Coverage" configuration

## Documentation

### Quick Reference
**File:** [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
**Contents:** All 29 configurations, keyboard shortcuts, common scenarios, tips

### Full Guide
**File:** [DEBUG_GUIDE.md](DEBUG_GUIDE.md)
**Contents:** Comprehensive guide with:
- Quick start
- All configuration details
- Advanced features (conditional breakpoints, logpoints, watch expressions)
- Async/await debugging
- Profiling workflows
- Remote debugging setup
- ZMQ debugging
- Troubleshooting
- Best practices

### Configuration Summary
**File:** [SUMMARY.md](SUMMARY.md)
**Contents:** Complete overview of all configurations, features, and statistics

## Available Configurations

### Main AIPerf
- AIPerf: Debug Main Process
- AIPerf: Debug with Multiprocess (Workers)
- AIPerf: Debug Current File
- AIPerf: Debug System Controller
- AIPerf: Debug Worker Process
- AIPerf: Debug with Config File

### Testing
- Pytest: Debug All Tests
- Pytest: Debug Current File
- Pytest: Debug Integration Tests
- Pytest: Debug Async Tests
- Pytest: Debug with Coverage
- Pytest: Debug Single Test Function
- Pytest: Debug Parallel Tests

### Profiling
- Profile: cProfile Current File
- Profile: cProfile AIPerf Main
- Profile: Memory with tracemalloc
- Profile: Line Profiler

### Remote Debugging
- Remote: Attach to Process
- Remote: Attach to Docker Container
- Remote: Attach to Worker Process

### Specialized
- ZMQ: Debug Communication Flow
- ZMQ: Debug Message Bus
- Debug: Async Workflow
- Debug: Performance Bottleneck Investigation
- Debug: Critical Test Suite

### Examples
- Example: Simple Benchmark
- Example: Streaming Benchmark
- Example: Trace Replay

## Available Tasks

### Profiling Tasks
- Profile: View cProfile Results
- Profile: py-spy Record
- Profile: Scalene Current File
- Profile: Memory with tracemalloc

### Testing Tasks
- Test: Unit Tests
- Test: Integration Tests
- Coverage: Generate Report
- Coverage: Open HTML Report

### Debugging Tasks
- Debug: Start Remote Debug Server

### Utility Tasks
- Clean: Remove Caches
- Workflow: Test with Coverage

## Environment Variables

Useful environment variables for debugging:

```bash
# Disable Python output buffering
PYTHONUNBUFFERED=1

# Enable asyncio debug mode
PYTHONASYNCIODEBUG=1

# Enable memory allocation tracing
PYTHONTRACEMALLOC=10

# Enable AIPerf developer mode
AIPERF_DEV_MODE=1

# Enable ZMQ debug logging
AIPERF_ZMQ_DEBUG=1

# Disable coverage during pytest debugging
PYTEST_ADDOPTS=--no-cov
```

## Breakpoint Types

### Standard Breakpoint
Click in gutter or press F9

### Conditional Breakpoint
Right-click breakpoint → Edit Breakpoint → Expression
```python
request_id == "req_123"
worker_id == "worker_1" and len(queue) > 100
```

### Logpoint
Right-click in gutter → Add Logpoint
```
Request {request_id} took {elapsed_time}ms
```

### Hit Count Breakpoint
Right-click breakpoint → Edit Breakpoint → Hit Count
```
10  # Breaks on 10th hit
```

## Watch Expressions

Add to Watch view during debugging:

```python
# Worker debugging
len(self.workers)
[w.status for w in self.workers]

# Async debugging
asyncio.all_tasks()
asyncio.current_task()

# Memory debugging
tracemalloc.get_traced_memory()
sys.getsizeof(obj)
```

## Resources

### Official Documentation
- [VS Code Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [debugpy GitHub](https://github.com/microsoft/debugpy)
- [pytest Documentation](https://docs.pytest.org/)

### Profiling Tools
- [cProfile Docs](https://docs.python.org/3/library/profile.html)
- [py-spy GitHub](https://github.com/benfred/py-spy)
- [Scalene GitHub](https://github.com/plasma-umass/scalene)
- [memory_profiler GitHub](https://github.com/pythonprofilers/memory_profiler)

### AIPerf
- Project: `/home/anthony/nvidia/projects/aiperf`
- Examples: `examples/`
- Tests: `tests/`

## Support

If you run into issues:

1. Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for common solutions
2. Read [DEBUG_GUIDE.md](DEBUG_GUIDE.md) for detailed information
3. Review [SUMMARY.md](SUMMARY.md) for configuration overview
4. Check VS Code Python debugging documentation
5. Review debugpy GitHub issues

## Next Steps

1. **Try it now:** Press F5 and select a configuration
2. **Read Quick Reference:** [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
3. **Learn Advanced Features:** [DEBUG_GUIDE.md](DEBUG_GUIDE.md)
4. **Customize:** Edit `launch.json` to add your own configurations

---

**Happy Debugging! 🐛🔍**

**Last Updated:** October 2025
**Python Version:** 3.12+
**VS Code Version:** 1.80+
