<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Debugging & Profiling Quick Reference

## Launch Configurations (Press F5)

### Main AIPerf Debugging
| Configuration | Use For | Key Features |
|--------------|---------|--------------|
| `AIPerf: Debug Main Process` | Single-process debugging | max-workers: 1, DEBUG logging |
| `AIPerf: Debug with Multiprocess (Workers)` | Multi-worker debugging | subProcess: true, 2 workers |
| `AIPerf: Debug Current File` | Debug any Python file | Uses ${file} |
| `AIPerf: Debug System Controller` | Controller in isolation | system_controller module |
| `AIPerf: Debug Worker Process` | Single worker in isolation | worker module |
| `AIPerf: Debug with Config File` | Use custom config | Loads from configs/ |

### Testing
| Configuration | Use For | Key Features |
|--------------|---------|--------------|
| `Pytest: Debug All Tests` | All tests | --no-cov, verbose |
| `Pytest: Debug Current File` | Current test file | ${file} |
| `Pytest: Debug Integration Tests` | Integration tests only | -m integration |
| `Pytest: Debug Async Tests` | Async test functions | -m asyncio |
| `Pytest: Debug with Coverage` | Generate coverage | --cov=aiperf |
| `Pytest: Debug Single Test Function` | One test function | Prompts for function name |
| `Pytest: Debug Parallel Tests` | pytest-xdist tests | -n auto, subProcess: true |

### Profiling
| Configuration | Use For | Key Features |
|--------------|---------|--------------|
| `Profile: cProfile Current File` | CPU profiling | Outputs to /tmp/aiperf_profile.prof |
| `Profile: cProfile AIPerf Main` | Profile full benchmark | 10 requests, 1 worker |
| `Profile: Memory with tracemalloc` | Memory profiling | PYTHONTRACEMALLOC=1 |
| `Profile: Line Profiler` | Line-by-line profiling | Requires @profile decorator |

### Remote Debugging
| Configuration | Use For | Key Features |
|--------------|---------|--------------|
| `Remote: Attach to Process` | Local remote debugging | Port 5678 |
| `Remote: Attach to Docker Container` | Docker debugging | Path mapping to /app |
| `Remote: Attach to Worker Process` | Worker remote debug | Custom port prompt |

### ZMQ & Specialized
| Configuration | Use For | Key Features |
|--------------|---------|--------------|
| `ZMQ: Debug Communication Flow` | ZMQ message debugging | AIPERF_ZMQ_DEBUG=1 |
| `Debug: Async Workflow` | Async/await debugging | PYTHONASYNCIODEBUG=1 |
| `Debug: Performance Bottleneck Investigation` | Performance issues | tracemalloc + 100 requests |

## Tasks (Ctrl+Shift+P → "Tasks: Run Task")

### Profiling Tasks
- `Profile: View cProfile Results` - View latest cProfile output
- `Profile: py-spy Record` - Record with py-spy (no code changes needed!)
- `Profile: Scalene Current File` - CPU+Memory profiling
- `Profile: Memory with tracemalloc` - Memory profiling

### Testing Tasks
- `Test: Unit Tests` - Run unit tests (parallel)
- `Test: Integration Tests` - Run integration tests
- `Coverage: Generate Report` - Generate coverage HTML report
- `Coverage: Open HTML Report` - Open coverage in browser

### Debugging Tasks
- `Debug: Start Remote Debug Server` - Start debugpy server on port 5678

### Utility Tasks
- `Clean: Remove Caches` - Clean all Python caches
- `Workflow: Test with Coverage` - Run tests and open coverage report

## Keyboard Shortcuts

### Debugging
| Action | Shortcut | Description |
|--------|----------|-------------|
| Start/Continue | F5 | Start debugging or continue |
| Step Over | F10 | Execute current line |
| Step Into | F11 | Step into function call |
| Step Out | Shift+F11 | Step out of function |
| Toggle Breakpoint | F9 | Add/remove breakpoint |
| Stop | Shift+F5 | Stop debugging |
| Restart | Ctrl+Shift+F5 | Restart debugging |
| Show Debug Console | Ctrl+Shift+Y | Open debug console |

### Testing
| Action | Shortcut | Description |
|--------|----------|-------------|
| Run Tests | Ctrl+; A | Run all tests |
| Debug Test | - | Right-click test → Debug Test |
| Show Test Output | - | Click test in Test Explorer |

## Breakpoint Types

### Standard Breakpoint
Click in gutter (left of line numbers) or press F9

### Conditional Breakpoint
1. Right-click breakpoint
2. Edit Breakpoint → Expression
3. Enter condition: `request_id == "req_123"`

### Hit Count Breakpoint
1. Right-click breakpoint
2. Edit Breakpoint → Hit Count
3. Enter number: `10` (breaks on 10th hit)

### Logpoint
1. Right-click in gutter
2. Add Logpoint
3. Enter message: `Request {request_id} took {elapsed_time}ms`

## Common Debugging Scenarios

### Debug Main Process Only
```
Configuration: "AIPerf: Debug Main Process"
Set breakpoint in: aiperf/controller/system_controller.py
```

### Debug Worker Process
```
Configuration: "AIPerf: Debug with Multiprocess (Workers)"
Set breakpoint in: aiperf/workers/worker.py
Watch: Check Call Stack view to see all worker processes
```

### Debug Failing Test
```
1. Open test file (e.g., tests/metrics/test_ttft_metric.py)
2. Configuration: "Pytest: Debug Current File"
3. Set breakpoint in test function
4. Press F5
```

### Debug Single Test Function
```
Configuration: "Pytest: Debug Single Test Function"
When prompted, enter: test_ttft_calculation
Press F5
```

### Profile Performance
```
Configuration: "Profile: cProfile AIPerf Main"
Press F5
After run: Tasks → "Profile: View cProfile Results"
```

### Debug Remote Container
```
1. In container: python -m debugpy --listen 0.0.0.0:5678 --wait-for-client app.py
2. Expose port: docker run -p 5678:5678 ...
3. Configuration: "Remote: Attach to Docker Container"
4. Press F5
```

### Debug Async Code
```
Configuration: "Debug: Async Workflow"
Set breakpoint in async function
Press F5
Watch expressions: asyncio.all_tasks(), asyncio.current_task()
```

## Environment Variables for Debugging

| Variable | Value | Effect |
|----------|-------|--------|
| `PYTHONUNBUFFERED` | 1 | Disable Python output buffering |
| `PYTHONASYNCIODEBUG` | 1 | Enable asyncio debug mode |
| `PYTHONTRACEMALLOC` | 1-10 | Enable memory allocation tracing |
| `AIPERF_DEV_MODE` | 1 | Enable AIPerf developer mode |
| `AIPERF_ZMQ_DEBUG` | 1 | Enable ZMQ debug logging |
| `PYTEST_ADDOPTS` | --no-cov | Disable coverage during debugging |

## Watch Expressions (Add in Debug View)

### Worker Debugging
```python
len(self.workers)
self.config.max_workers
[w.status for w in self.workers]
```

### Async Debugging
```python
asyncio.all_tasks()
asyncio.current_task()
len([t for t in asyncio.all_tasks() if not t.done()])
```

### Memory Debugging
```python
import sys; sys.getsizeof(obj)
len(self._cache)
tracemalloc.get_traced_memory()
```

### Performance Debugging
```python
time.perf_counter()
len(self._pending_requests)
self.metrics.get_summary()
```

## Common Issues & Solutions

### Breakpoints Not Hit
**Problem:** Breakpoint shows as unverified or doesn't stop
**Solutions:**
- Set `"justMyCode": false` in launch.json
- Disable coverage: `"PYTEST_ADDOPTS": "--no-cov"`
- Ensure code is loaded: set breakpoint after startup
- For subprocesses: set `"subProcess": true`

### Debugger Timeout
**Problem:** "Debugger attach failed" or timeout
**Solutions:**
- Increase timeout: `"python.debugging.debugAdapterTimeout": 30000`
- Check port is not blocked: `netstat -tulpn | grep 5678`
- Verify remote host is accessible

### Coverage Breaks Debugging
**Problem:** Coverage enabled, breakpoints don't work
**Solution:** Always use `"PYTEST_ADDOPTS": "--no-cov"` when debugging

### Multiprocess Debugging Not Working
**Problem:** Child processes not showing in debugger
**Solution:** Ensure `"subProcess": true` in launch configuration

### Slow Debugging
**Problem:** Stepping through code is very slow
**Solutions:**
- Reduce workers: `"--max-workers", "1"`
- Use `"justMyCode": true`
- Reduce logging: `"--log-level", "ERROR"`
- Use conditional breakpoints instead of breaking every iteration

## Profiling Workflow

### 1. Quick CPU Profile
```bash
# Using launch configuration
F5 → "Profile: cProfile Current File"

# Or using task
Ctrl+Shift+P → Tasks: Run Task → "Profile: py-spy Record"
```

### 2. View Results
```bash
# In terminal
python -m pstats /tmp/aiperf_profile.prof
>>> sort cumtime
>>> stats 30

# Or using snakeviz (visual)
pip install snakeviz
snakeviz /tmp/aiperf_profile.prof
```

### 3. Line-by-Line Profiling
```python
# Add @profile decorator to function
@profile
def my_slow_function():
    ...

# Run line_profiler
F5 → "Profile: Line Profiler"
```

### 4. Memory Profiling
```bash
# Using tracemalloc
F5 → "Profile: Memory with tracemalloc"

# Or scalene for CPU+Memory
Ctrl+Shift+P → Tasks: Run Task → "Profile: Scalene Current File"
```

## Remote Debugging Setup

### Docker Container
```dockerfile
# In Dockerfile
RUN pip install debugpy

# In docker-compose.yml
ports:
  - "5678:5678"
```

```python
# In Python code
import debugpy
debugpy.listen(("0.0.0.0", 5678))
debugpy.wait_for_client()
```

```bash
# In VS Code
F5 → "Remote: Attach to Docker Container"
```

### SSH Remote
```bash
# Create SSH tunnel
ssh -L 5678:localhost:5678 user@remote-host

# On remote: start debugpy
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client script.py

# In VS Code
F5 → "Remote: Attach to Process"
```

## Tips & Tricks

### 1. Debug Console Evaluation
When stopped at breakpoint, use Debug Console (Ctrl+Shift+Y):
```python
# Evaluate any expression
len(records)
self.config.dict()
[w.id for w in self.workers if w.status == "busy"]
```

### 2. Conditional Breakpoint Examples
```python
# Break only for specific request
request_id == "req_123"

# Break when error occurs
error is not None

# Break after N iterations
iteration_count > 100

# Break on specific worker
worker_id == "worker_1"
```

### 3. Logpoint Examples
```
Request {request_id} - Status: {status} - Duration: {duration}ms
Worker {worker_id} processing request {req_id}
Queue size: {len(queue)} - Active workers: {len(active_workers)}
```

### 4. Test Debugging Pattern
```python
# 1. Write failing test
def test_my_feature():
    result = my_function()
    assert result == expected  # Fails here

# 2. Set breakpoint before assertion
# 3. F5 → "Pytest: Debug Current File"
# 4. Inspect variables in Debug Console
# 5. Fix code
# 6. Rerun test
```

### 5. Performance Investigation
```
1. Profile with cProfile: Find slow function
2. Profile with line_profiler: Find slow lines
3. Set breakpoints: Understand why it's slow
4. Optimize
5. Profile again: Verify improvement
```

## File Locations

| File | Purpose |
|------|---------|
| `/home/anthony/nvidia/projects/aiperf/.vscode/launch.json` | Debug configurations |
| `/home/anthony/nvidia/projects/aiperf/.vscode/tasks.json` | Task definitions |
| `/home/anthony/nvidia/projects/aiperf/.vscode/settings.json` | VS Code settings |
| `/home/anthony/nvidia/projects/aiperf/.vscode/DEBUG_GUIDE.md` | Full debugging guide |
| `/tmp/aiperf_profile.prof` | cProfile output |
| `/tmp/pyspy_profile.svg` | py-spy output |
| `/tmp/scalene_profile.html` | Scalene output |
| `htmlcov/index.html` | Coverage report |

## Additional Resources

- **VS Code Python Debugging:** https://code.visualstudio.com/docs/python/debugging
- **debugpy GitHub:** https://github.com/microsoft/debugpy
- **pytest Documentation:** https://docs.pytest.org/
- **cProfile Documentation:** https://docs.python.org/3/library/profile.html
- **py-spy GitHub:** https://github.com/benfred/py-spy
- **Scalene GitHub:** https://github.com/plasma-umass/scalene

---

**Last Updated:** October 2025
**Python Version:** 3.12+
**VS Code Version:** 1.80+
