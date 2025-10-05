<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf VS Code Debugging & Profiling Configuration Summary

## Overview

This VS Code workspace has been configured with comprehensive debugging and profiling support for Python development in 2025, specifically tailored for the AIPerf project.

## What's Included

### 1. Launch Configurations (`launch.json`)
**29 debugging configurations** covering:
- ✅ Main AIPerf process debugging
- ✅ Multiprocess worker debugging with subprocess attachment
- ✅ Async/await Python code debugging
- ✅ Unit test debugging (pytest)
- ✅ Integration test debugging
- ✅ Performance profiling (cProfile, memory_profiler, line_profiler)
- ✅ Remote debugging (Docker containers, SSH)
- ✅ ZMQ communication debugging
- ✅ Coverage debugging

**File:** `/home/anthony/nvidia/projects/aiperf/.vscode/launch.json` (666 lines)

### 2. Comprehensive Debug Guide (`DEBUG_GUIDE.md`)
**Full documentation** with:
- Quick start instructions
- Configuration descriptions
- Advanced debugging features (conditional breakpoints, logpoints, watch expressions)
- Async/await debugging techniques
- Profiling workflows (cProfile, py-spy, scalene, memory_profiler)
- Remote debugging setup (Docker, SSH)
- ZMQ communication debugging
- Troubleshooting guide
- Best practices

**File:** `/home/anthony/nvidia/projects/aiperf/.vscode/DEBUG_GUIDE.md` (749 lines)

### 3. Quick Reference (`QUICK_REFERENCE.md`)
**Cheat sheet** with:
- All 29 launch configurations in tables
- Common debugging scenarios
- Keyboard shortcuts
- Breakpoint types and examples
- Watch expression examples
- Environment variables
- Common issues & solutions
- Profiling workflow
- Remote debugging setup

**File:** `/home/anthony/nvidia/projects/aiperf/.vscode/QUICK_REFERENCE.md` (398 lines)

### 4. VS Code Settings (`settings.json`)
**Enhanced with:**
- Debugging configuration (timeout: 30s)
- Coverage gutters configuration
- Python testing setup
- Linting and formatting (Ruff)
- File exclusions for better performance

**File:** `/home/anthony/nvidia/projects/aiperf/.vscode/settings.json`

### 5. Tasks Configuration (`tasks.json`)
**Extended with profiling tasks:**
- Profile: View cProfile Results
- Profile: py-spy Record
- Profile: Scalene Current File
- Profile: Memory with tracemalloc
- Debug: Start Remote Debug Server

**File:** `/home/anthony/nvidia/projects/aiperf/.vscode/tasks.json`

## Key Features Implemented

### Modern Python Debugging (2025)
- ✅ Uses `debugpy` (latest Python debugger)
- ✅ Type: "debugpy" (not deprecated "python")
- ✅ Subprocess debugging with `"subProcess": true`
- ✅ Async debugging with `PYTHONASYNCIODEBUG=1`
- ✅ Coverage debugging with proper `--no-cov` handling

### AIPerf-Specific Configurations

#### 1. Debug Main Process
```json
{
    "name": "AIPerf: Debug Main Process",
    "module": "aiperf.cli",
    "args": ["profile", "-m", "gpt2", "--max-workers", "1"]
}
```
**Use for:** Single-process debugging, understanding core logic

#### 2. Debug with Multiprocess Workers
```json
{
    "name": "AIPerf: Debug with Multiprocess (Workers)",
    "subProcess": true,
    "args": ["profile", "-m", "gpt2", "--max-workers", "2"]
}
```
**Use for:** Debugging worker processes, ZMQ communication

#### 3. Debug Tests
Multiple test configurations:
- All tests
- Current file
- Integration tests
- Async tests
- Single test function
- With coverage
- Parallel tests

#### 4. Profiling
Multiple profiling approaches:
- cProfile (CPU profiling)
- tracemalloc (memory profiling)
- line_profiler (line-by-line)
- py-spy (sampling profiler, no code changes!)
- Scalene (CPU+GPU+memory)

#### 5. Remote Debugging
Configurations for:
- Local process attachment
- Docker container debugging
- Worker process attachment with custom port

#### 6. ZMQ Debugging
Special configurations with:
- `AIPERF_ZMQ_DEBUG=1` environment variable
- Subprocess debugging enabled
- Log to file enabled

## Research-Based Implementation

All configurations are based on 2025 best practices from:

### VS Code Python Debugging
- Official VS Code documentation (September 2025 updates)
- Python Debugger extension features
- debugpy latest capabilities

### Multiprocess Debugging
- `subProcess: true` for automatic subprocess attachment
- Call Stack view for switching between processes
- Worker PID tracking

### Async Debugging
- `PYTHONASYNCIODEBUG=1` for asyncio debug mode
- Watch expressions for `asyncio.all_tasks()`
- Proper handling of unawaited coroutines

### Remote Debugging
- debugpy listen/wait_for_client pattern
- Docker port mapping (5678)
- Path mappings for container/remote debugging

### Profiling Integration
- cProfile with pstats/snakeviz visualization
- py-spy for production-like profiling
- Scalene for comprehensive CPU+memory analysis
- tracemalloc for built-in memory profiling

### Coverage Debugging
- `PYTEST_ADDOPTS: --no-cov` to disable coverage when debugging
- Separate configuration for coverage generation
- Coverage Gutters extension integration

## Usage Examples

### Quick Start: Debug Main Process
1. Open VS Code in AIPerf directory
2. Press F5
3. Select "AIPerf: Debug Main Process"
4. Set breakpoints in controller/worker code
5. Debug!

### Debug Failing Test
1. Open test file: `tests/metrics/test_ttft_metric.py`
2. Set breakpoint in test function
3. Press F5, select "Pytest: Debug Current File"
4. Inspect variables when breakpoint hits

### Debug Worker Communication
1. Set breakpoint in `aiperf/workers/worker.py`
2. Press F5, select "AIPerf: Debug with Multiprocess (Workers)"
3. When breakpoint hits, check Call Stack view
4. Switch between worker processes

### Profile Performance
1. Press F5, select "Profile: cProfile AIPerf Main"
2. Let it run (10 requests)
3. Run task: "Profile: View cProfile Results"
4. Analyze top functions by cumulative time

### Debug in Docker
1. In Dockerfile: `RUN pip install debugpy`
2. In code: `debugpy.listen(("0.0.0.0", 5678)); debugpy.wait_for_client()`
3. Expose port: `docker run -p 5678:5678 ...`
4. Press F5, select "Remote: Attach to Docker Container"

## Advanced Features

### Conditional Breakpoints
```python
# Break only when:
request_id == "req_123"
worker_id == "worker_1" and len(queue) > 100
error is not None
```

### Logpoints (No Code Changes!)
```
Request {request_id} took {elapsed_time}ms
Worker {worker_id} - Status: {status}
```

### Watch Expressions
```python
len(self.workers)
asyncio.all_tasks()
[w.status for w in self.workers]
tracemalloc.get_traced_memory()
```

### Debug Console Evaluation
When stopped at breakpoint:
```python
len(records)
self.config.dict()
import json; json.dumps(data, indent=2)
```

## Performance Considerations

### Debugging Performance
- Single worker for faster debugging: `--max-workers 1`
- `justMyCode: true` to skip library code
- Reduce logging: `--log-level ERROR`
- Use conditional breakpoints

### Profiling Performance
- py-spy: Minimal overhead, production-safe
- cProfile: Low overhead, good for development
- line_profiler: Higher overhead, use on specific functions
- Scalene: Comprehensive, some overhead

## Troubleshooting

### Common Issues

**Breakpoints not hit:**
- Set `"justMyCode": false`
- Add `"PYTEST_ADDOPTS": "--no-cov"` for tests
- Use `"subProcess": true` for workers

**Debugger timeout:**
- Increase `"python.debugging.debugAdapterTimeout": 30000`
- Check firewall/port availability

**Coverage breaks debugging:**
- Always use `--no-cov` when debugging
- Separate configurations for coverage generation

**Slow debugging:**
- Reduce workers
- Use `justMyCode: true`
- Disable verbose logging
- Use conditional breakpoints

## File Organization

```
.vscode/
├── launch.json              # 29 debug configurations
├── tasks.json               # Enhanced with profiling tasks
├── settings.json            # Debugging settings
├── DEBUG_GUIDE.md          # Comprehensive guide (749 lines)
├── QUICK_REFERENCE.md      # Quick cheat sheet (398 lines)
└── SUMMARY.md              # This file
```

## Keyboard Shortcuts Reference

| Action | Shortcut | Description |
|--------|----------|-------------|
| Start/Continue | F5 | Start debugging or continue |
| Step Over | F10 | Execute current line |
| Step Into | F11 | Step into function call |
| Step Out | Shift+F11 | Step out of function |
| Toggle Breakpoint | F9 | Add/remove breakpoint |
| Stop | Shift+F5 | Stop debugging |
| Restart | Ctrl+Shift+F5 | Restart debugging |
| Debug Console | Ctrl+Shift+Y | Open debug console |
| Run Task | Ctrl+Shift+P | "Tasks: Run Task" |

## Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `PYTHONUNBUFFERED` | 1 | Disable output buffering |
| `PYTHONASYNCIODEBUG` | 1 | Enable asyncio debug mode |
| `PYTHONTRACEMALLOC` | 1-10 | Memory allocation tracing |
| `AIPERF_DEV_MODE` | 1 | AIPerf developer mode |
| `AIPERF_ZMQ_DEBUG` | 1 | ZMQ debug logging |
| `PYTEST_ADDOPTS` | --no-cov | Disable coverage during debug |

## Testing Integration

### Pytest Configuration
- Auto-discovery enabled
- Asyncio mode: auto
- Default args: `-m "not integration" --no-cov`
- Parallel execution with pytest-xdist

### Test Markers Supported
- `@pytest.mark.asyncio` - Async tests
- `@pytest.mark.integration` - Integration tests
- Custom markers as defined in pytest.ini

### Coverage Integration
- pytest-cov plugin
- HTML reports: `htmlcov/index.html`
- XML reports: `coverage.xml`
- Coverage Gutters extension for real-time feedback

## Profiling Workflow

1. **Quick Profile:** py-spy (no code changes)
   ```bash
   Task: "Profile: py-spy Record"
   ```

2. **Detailed Profile:** cProfile
   ```bash
   F5 → "Profile: cProfile AIPerf Main"
   Task: "Profile: View cProfile Results"
   ```

3. **Line-by-Line:** line_profiler
   ```python
   @profile  # Add decorator
   F5 → "Profile: Line Profiler"
   ```

4. **Memory:** tracemalloc
   ```bash
   F5 → "Profile: Memory with tracemalloc"
   ```

5. **Comprehensive:** Scalene
   ```bash
   Task: "Profile: Scalene Current File"
   ```

## Best Practices

1. **Start Simple**
   - Begin with single-process debugging
   - Add multiprocess only when needed

2. **Use Conditional Breakpoints**
   - Don't break on every iteration
   - Break only on interesting cases

3. **Leverage Logpoints**
   - No code changes needed
   - Easy to enable/disable

4. **Debug Tests First**
   - Tests are isolated
   - Easier to reproduce bugs

5. **Profile Before Optimizing**
   - Find actual bottlenecks
   - Don't guess

6. **Version Control**
   - launch.json can be committed
   - Uses workspace variables
   - No personal paths

## Additional Resources

### Documentation
- VS Code Python Debugging: https://code.visualstudio.com/docs/python/debugging
- debugpy: https://github.com/microsoft/debugpy
- pytest: https://docs.pytest.org/

### Profiling Tools
- cProfile: https://docs.python.org/3/library/profile.html
- py-spy: https://github.com/benfred/py-spy
- Scalene: https://github.com/plasma-umass/scalene
- memory_profiler: https://github.com/pythonprofilers/memory_profiler

### AIPerf
- Project: `/home/anthony/nvidia/projects/aiperf`
- Examples: `/home/anthony/nvidia/projects/aiperf/examples/`
- Tests: `/home/anthony/nvidia/projects/aiperf/tests/`

## Configuration Statistics

- **Debug Configurations:** 29
- **Configuration Groups:** 7
  - AIPerf: 6 configs
  - Examples: 3 configs
  - Testing: 7 configs
  - Profiling: 4 configs
  - Remote: 3 configs
  - ZMQ: 2 configs
  - Specialized: 4 configs
- **Input Variables:** 2 (testFunction, debugPort)
- **Profiling Tasks:** 5
- **Total Lines:** 1,813 (across all files)

## Technology Stack

- **Python:** 3.12+
- **VS Code:** 1.80+
- **debugpy:** 1.8+
- **pytest:** 7.0+
- **pytest-asyncio:** Latest
- **pytest-cov:** Latest
- **pytest-xdist:** 3.8+

## Maintenance

This configuration is based on 2025 best practices and should be maintained:
- Update debugpy version as needed
- Review VS Code Python extension updates
- Add new configurations as AIPerf evolves
- Keep documentation in sync with code changes

## Support

For issues or questions:
1. Check `DEBUG_GUIDE.md` for detailed information
2. Check `QUICK_REFERENCE.md` for quick solutions
3. Review VS Code Python debugging documentation
4. Check debugpy GitHub issues

---

**Created:** October 2025
**Last Updated:** October 2025
**Python Version:** 3.12.10
**Platform:** Linux (Arch Linux 6.14.9-arch1-1)
**Workspace:** /home/anthony/nvidia/projects/aiperf
