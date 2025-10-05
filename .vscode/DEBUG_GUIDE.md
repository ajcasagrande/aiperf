<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf VS Code Debugging and Profiling Guide (2025)

This guide provides comprehensive instructions for debugging and profiling AIPerf using VS Code with the latest Python debugging features.

## Table of Contents

- [Quick Start](#quick-start)
- [Debugging Configurations](#debugging-configurations)
- [Advanced Features](#advanced-features)
- [Profiling](#profiling)
- [Remote Debugging](#remote-debugging)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## Quick Start

### Prerequisites

1. **Install VS Code Python Extension**
   ```bash
   # The Python Debugger extension is automatically installed with the Python extension
   code --install-extension ms-python.python
   ```

2. **Install Required Python Packages**
   ```bash
   pip install debugpy pytest pytest-cov pytest-asyncio

   # Optional profiling tools
   pip install line-profiler memory-profiler py-spy scalene
   ```

3. **Open AIPerf Project in VS Code**
   ```bash
   code /home/anthony/nvidia/projects/aiperf
   ```

### Running Your First Debug Session

1. Open the Run and Debug view (Ctrl+Shift+D or Cmd+Shift+D)
2. Select "AIPerf: Debug Main Process" from the dropdown
3. Press F5 or click the green play button
4. Set breakpoints by clicking in the gutter next to line numbers

---

## Debugging Configurations

### Main AIPerf Configurations

#### 1. Debug Main Process
**Use when:** Debugging the main AIPerf entry point without worker processes

**Configuration:** `AIPerf: Debug Main Process`

**Features:**
- Single-process debugging (max-workers: 1)
- Full control over execution flow
- Ideal for understanding core logic

**Example Usage:**
```python
# Set a breakpoint in aiperf/cli.py or aiperf/controller/system_controller.py
# Press F5 with "AIPerf: Debug Main Process" selected
```

#### 2. Debug with Multiprocess (Workers)
**Use when:** Debugging worker processes and multiprocess communication

**Configuration:** `AIPerf: Debug with Multiprocess (Workers)`

**Features:**
- Enables subprocess debugging with `subProcess: true`
- Debugger attaches to all spawned worker processes
- Can switch between processes in VS Code's Call Stack view

**Important Notes:**
- When a breakpoint hits in a subprocess, VS Code will show it in the Call Stack view
- You can select which process to inspect from the dropdown
- All processes are listed with their PIDs

**Example Workflow:**
```python
# 1. Set breakpoint in aiperf/workers/worker.py in the request handling code
# 2. Run "AIPerf: Debug with Multiprocess (Workers)"
# 3. When breakpoint hits, check Call Stack view to see which worker process
# 4. Switch between worker processes using the dropdown
```

#### 3. Debug System Controller
**Use when:** Debugging the system controller in isolation

**Configuration:** `AIPerf: Debug System Controller`

**Module:** `aiperf.controller.system_controller`

#### 4. Debug Worker Process
**Use when:** Debugging a single worker in isolation

**Configuration:** `AIPerf: Debug Worker Process`

**Module:** `aiperf.workers.worker`

### Example Scripts Debugging

Debug AIPerf example scripts directly:

- **Simple Benchmark:** `examples/basic/simple_benchmark.py`
- **Streaming Benchmark:** `examples/basic/streaming_benchmark.py`
- **Trace Replay:** `examples/advanced/trace_replay.py`

### Testing Configurations

#### Debugging All Tests
```json
Configuration: "Pytest: Debug All Tests"
```
Runs all tests with debugging enabled and coverage disabled.

#### Debugging Current Test File
```json
Configuration: "Pytest: Debug Current File"
```
**Usage:**
1. Open a test file (e.g., `tests/metrics/test_ttft_metric.py`)
2. Select "Pytest: Debug Current File"
3. Press F5

#### Debugging Single Test Function
```json
Configuration: "Pytest: Debug Single Test Function"
```
**Usage:**
1. Open a test file
2. Select "Pytest: Debug Single Test Function"
3. When prompted, enter the test function name (e.g., `test_ttft_calculation`)
4. Press F5

#### Debugging Async Tests
```json
Configuration: "Pytest: Debug Async Tests"
```
Specifically for debugging async/await test functions with `@pytest.mark.asyncio`.

**Environment Variables:**
- `PYTHONASYNCIODEBUG=1` enables asyncio debug mode
- Helps catch common async issues like unawaited coroutines

#### Debugging Integration Tests
```json
Configuration: "Pytest: Debug Integration Tests"
```
Runs tests marked with `@pytest.mark.integration`.

#### Debugging with Coverage
```json
Configuration: "Pytest: Debug with Coverage"
```

**Important:** When debugging with coverage, breakpoints may not work properly. Use this configuration only when you need to generate coverage reports while debugging is less important.

**To disable coverage during debugging:**
```json
"env": {
    "PYTEST_ADDOPTS": "--no-cov"
}
```

#### Debugging Parallel Tests
```json
Configuration: "Pytest: Debug Parallel Tests"
```
Enables subprocess debugging for pytest-xdist parallel test execution.

---

## Advanced Features

### Conditional Breakpoints

Set breakpoints that only trigger when a condition is met:

1. Right-click on a breakpoint
2. Select "Edit Breakpoint"
3. Choose "Expression" or "Hit Count"

**Examples:**

```python
# Expression breakpoint - only break when request_id == 42
request_id == 42

# Hit count breakpoint - break on the 10th iteration
10

# Complex condition
worker_id == "worker_1" and len(queue) > 100
```

### Logpoints

Log messages without stopping execution:

1. Right-click in the gutter where you'd set a breakpoint
2. Select "Add Logpoint"
3. Enter a message with curly braces for expressions

**Example:**
```
Request {request_id} took {elapsed_time}ms
```

### Watch Expressions

Monitor variables and expressions:

1. In the Debug view, find the "Watch" section
2. Click "+" to add an expression
3. The expression updates automatically as you step through code

**Useful Watch Expressions:**
```python
len(self.workers)
self.config.max_workers
sum(r.duration for r in records)
asyncio.all_tasks()
```

### Debug Console

Evaluate expressions during debugging:

1. When stopped at a breakpoint, open Debug Console (Ctrl+Shift+Y)
2. Type Python expressions to evaluate

**Examples:**
```python
# Inspect variables
print(self.config)
len(records)

# Call methods
self.get_status()

# Import and use modules
import json; json.dumps(config.dict(), indent=2)

# For async code (note: await doesn't work directly in debug console)
# You need to use the async workflow debugging configuration
```

### Async/Await Debugging

**Configuration:** `Debug: Async Workflow`

**Environment Variable:** `PYTHONASYNCIODEBUG=1`

This enables asyncio debug mode which helps detect:
- Unawaited coroutines
- Tasks that take too long
- Resources not properly closed

**Common Async Debugging Scenarios:**

1. **Inspecting running tasks:**
   ```python
   # Add to watch expressions
   asyncio.all_tasks()
   asyncio.current_task()
   ```

2. **Finding deadlocks:**
   - Set breakpoints in coroutines
   - Check the call stack to see what each task is waiting for
   - Look for circular waits

3. **Memory leaks in async code:**
   - Use `PYTHONTRACEMALLOC=1`
   - Monitor task creation/completion
   - Check for tasks that never complete

---

## Profiling

### cProfile Integration

#### Profile Current File
**Configuration:** `Profile: cProfile Current File`

Runs cProfile on the current file and saves output to `/tmp/aiperf_profile.prof`.

**View Results:**
```bash
# Using pstats
python -m pstats /tmp/aiperf_profile.prof
# Then type: sort cumtime, stats 20

# Using snakeviz (install: pip install snakeviz)
snakeviz /tmp/aiperf_profile.prof

# Using gprof2dot (install: pip install gprof2dot)
gprof2dot -f pstats /tmp/aiperf_profile.prof | dot -Tpng -o profile.png
```

#### Profile AIPerf Main
**Configuration:** `Profile: cProfile AIPerf Main`

Profiles a complete AIPerf benchmark run.

### Memory Profiling

#### Using tracemalloc
**Configuration:** `Profile: Memory with tracemalloc`

**Environment:** `PYTHONTRACEMALLOC=1`

**In your code:**
```python
import tracemalloc

tracemalloc.start()

# Your code here

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("[ Top 10 memory allocations ]")
for stat in top_stats[:10]:
    print(stat)
```

#### Using memory_profiler
**Install:**
```bash
pip install memory-profiler
```

**Decorate functions:**
```python
from memory_profiler import profile

@profile
def my_function():
    # Your code here
    pass
```

**Run:**
```bash
python -m memory_profiler your_script.py
```

### Line Profiler

**Configuration:** `Profile: Line Profiler`

**Install:**
```bash
pip install line-profiler
```

**Decorate functions to profile:**
```python
@profile
def bottleneck_function():
    # Your code here
    pass
```

**Run the configuration and view detailed line-by-line timing.**

### Advanced Profiling Tools

#### py-spy (Sampling Profiler)
**No code changes required!**

```bash
# Install
pip install py-spy

# Profile a running AIPerf process
py-spy record -o profile.svg --pid <PID>

# Or start AIPerf with py-spy
py-spy record -o profile.svg -- python -m aiperf.cli profile -m gpt2

# Top-like view
py-spy top --pid <PID>
```

#### Scalene (CPU + Memory Profiler)
**Install VS Code Extension:** `Scalene` by Emery Berger

```bash
# Install
pip install scalene

# Run
scalene your_script.py

# Or use the VS Code extension
# It adds a "Profile with Scalene" button to the UI
```

---

## Remote Debugging

### Debugging in Docker Containers

#### 1. Add debugpy to Your Container

**Dockerfile:**
```dockerfile
RUN pip install debugpy
```

#### 2. Start Your Application with debugpy

**Command line method:**
```bash
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m aiperf.cli profile -m gpt2
```

**Code method:**
```python
import debugpy

# Enable debugging
debugpy.listen(("0.0.0.0", 5678))
print("Waiting for debugger attach...")
debugpy.wait_for_client()
print("Debugger attached!")

# Your code continues here
```

#### 3. Expose Debug Port

**docker-compose.yml:**
```yaml
services:
  aiperf:
    ports:
      - "5678:5678"  # Debug port
      - "8000:8000"  # Application port
```

**docker run:**
```bash
docker run -p 5678:5678 -p 8000:8000 your-image
```

#### 4. Attach VS Code Debugger

**Configuration:** `Remote: Attach to Docker Container`

Press F5 with this configuration selected.

**Path Mappings:**
Update the `pathMappings` in launch.json to match your container:
```json
"pathMappings": [
    {
        "localRoot": "${workspaceFolder}",
        "remoteRoot": "/app"  // Change this to your container's app path
    }
]
```

### Debugging Worker Processes Remotely

To debug a specific worker process:

1. **Modify worker startup to listen for debugger:**
   ```python
   import debugpy
   import os

   worker_id = os.environ.get("WORKER_ID", "0")
   debug_port = 5678 + int(worker_id)

   debugpy.listen(("0.0.0.0", debug_port))
   ```

2. **Use configuration:** `Remote: Attach to Worker Process`

3. **When prompted, enter the debug port** (e.g., 5678, 5679, etc.)

### Debugging Over SSH

1. **SSH tunnel to remote machine:**
   ```bash
   ssh -L 5678:localhost:5678 user@remote-host
   ```

2. **Start debugpy on remote machine:**
   ```bash
   python -m debugpy --listen 0.0.0.0:5678 --wait-for-client your_script.py
   ```

3. **Use configuration:** `Remote: Attach to Process`

---

## ZMQ Communication Debugging

AIPerf uses ZeroMQ for inter-process communication. Debugging ZMQ flows can be challenging.

### Configuration
**Use:** `ZMQ: Debug Communication Flow`

**Features:**
- Enables subprocess debugging
- Sets `AIPERF_ZMQ_DEBUG=1` environment variable
- Enables `logToFile` for detailed logging

### Debugging Tips

1. **Enable ZMQ debug logging in code:**
   ```python
   import logging
   logging.getLogger("zmq").setLevel(logging.DEBUG)
   ```

2. **Monitor message patterns:**
   Set breakpoints in:
   - `aiperf/zmq/zmq_base_client.py`
   - `aiperf/common/base_comms.py`
   - Message handler methods

3. **Watch expressions for ZMQ:**
   ```python
   self._socket.closed
   self._context.closed
   len(self._pending_messages)
   ```

4. **Common ZMQ Issues:**
   - **Deadlock:** Check send/recv patterns
   - **Lost messages:** Check socket types (PUSH/PULL, PUB/SUB, etc.)
   - **Connection issues:** Verify ports and addresses

---

## Troubleshooting

### Breakpoints Not Being Hit

**Possible Causes:**

1. **Coverage is enabled:**
   - **Solution:** Add `"PYTEST_ADDOPTS": "--no-cov"` to env

2. **Code hasn't been loaded yet:**
   - **Solution:** Use conditional breakpoints or set them after startup

3. **Subprocess not attached:**
   - **Solution:** Set `"subProcess": true` in configuration

4. **justMyCode is true:**
   - **Solution:** Set `"justMyCode": false` to debug into libraries

### Debugger Timing Out

**For remote debugging:**
- Increase timeout in settings:
  ```json
  "python.debugging.debugAdapterTimeout": 30000
  ```

### Multiple Python Versions

Ensure VS Code uses the correct Python interpreter:
1. Press Ctrl+Shift+P (Cmd+Shift+P on Mac)
2. Type "Python: Select Interpreter"
3. Choose the interpreter with AIPerf installed

### Slow Debugging Performance

1. **Disable logging:**
   ```json
   "env": {
       "AIPERF_LOG_LEVEL": "ERROR"
   }
   ```

2. **Use justMyCode:**
   ```json
   "justMyCode": true
   ```

3. **Reduce worker count:**
   ```json
   "args": ["--max-workers", "1"]
   ```

---

## Best Practices

### 1. Start Simple
- Begin with single-process debugging
- Use `AIPerf: Debug Main Process` first
- Add multiprocess debugging only when needed

### 2. Use Conditional Breakpoints
- Don't break on every iteration
- Set conditions to break only on interesting cases
- Example: `request_id == "req_123" and error is not None`

### 3. Leverage Logpoints
- Use logpoints instead of print statements
- They don't require code changes
- Easier to enable/disable than print statements

### 4. Organize Your Breakpoints
- Use the Breakpoints view to manage all breakpoints
- Disable/enable groups of breakpoints
- Save breakpoint configurations

### 5. Debug Tests First
- Tests are isolated and easier to debug
- Write a failing test to reproduce your bug
- Debug the test using `Pytest: Debug Current File`

### 6. Profile Before Optimizing
- Use cProfile to find actual bottlenecks
- Don't guess at performance issues
- Profile realistic workloads

### 7. Memory Profiling Strategy
- Start with tracemalloc (built-in)
- Use memory_profiler for line-by-line analysis
- Check for memory leaks with repeated operations

### 8. Remote Debugging Workflow
- Develop locally when possible
- Use remote debugging for environment-specific issues
- Keep path mappings updated

### 9. Version Control
- Don't commit launch.json with personal paths
- Use workspace variables like `${workspaceFolder}`
- Share useful configurations with team

### 10. Learn Keyboard Shortcuts
- **F5:** Start debugging
- **F9:** Toggle breakpoint
- **F10:** Step over
- **F11:** Step into
- **Shift+F11:** Step out
- **Shift+F5:** Stop debugging
- **Ctrl+Shift+F5:** Restart debugging

---

## Additional Resources

### VS Code Documentation
- [Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [Debugging](https://code.visualstudio.com/docs/editor/debugging)
- [Python Testing](https://code.visualstudio.com/docs/python/testing)

### Python Debugging Tools
- [debugpy](https://github.com/microsoft/debugpy) - Python debugger
- [pdb](https://docs.python.org/3/library/pdb.html) - Python debugger
- [ipdb](https://github.com/gotcha/ipdb) - IPython debugger

### Profiling Tools
- [cProfile](https://docs.python.org/3/library/profile.html) - Built-in profiler
- [line_profiler](https://github.com/pyutils/line_profiler) - Line-by-line profiler
- [memory_profiler](https://github.com/pythonprofilers/memory_profiler) - Memory profiler
- [py-spy](https://github.com/benfred/py-spy) - Sampling profiler
- [Scalene](https://github.com/plasma-umass/scalene) - CPU+GPU+memory profiler

### AIPerf-Specific
- AIPerf Documentation: Check project README
- Example Scripts: `/home/anthony/nvidia/projects/aiperf/examples/`
- Test Suite: `/home/anthony/nvidia/projects/aiperf/tests/`

---

## Configuration Reference

All configurations are defined in `/home/anthony/nvidia/projects/aiperf/.vscode/launch.json`

**Configuration Groups:**
1. **aiperf** - Main AIPerf debugging
2. **examples** - Example script debugging
3. **testing** - Test debugging
4. **profiling** - Performance profiling
5. **remote** - Remote debugging
6. **zmq** - ZMQ communication debugging
7. **specialized** - Advanced scenarios

**Key Configuration Options:**

| Option | Description | Values |
|--------|-------------|--------|
| `type` | Debugger type | `debugpy` |
| `request` | Launch or attach | `launch`, `attach` |
| `module` | Python module to run | `aiperf.cli`, `pytest`, etc. |
| `program` | Python file to run | `${file}`, absolute path |
| `args` | Command-line arguments | Array of strings |
| `console` | Console to use | `integratedTerminal`, `internalConsole` |
| `justMyCode` | Debug only user code | `true`, `false` |
| `subProcess` | Attach to subprocesses | `true`, `false` |
| `env` | Environment variables | Object with key-value pairs |
| `pathMappings` | Remote path mappings | Array of local/remote pairs |

---

## Quick Reference Card

### Most Common Configurations

| Task | Configuration | Shortcut |
|------|--------------|----------|
| Debug main AIPerf | `AIPerf: Debug Main Process` | - |
| Debug with workers | `AIPerf: Debug with Multiprocess (Workers)` | - |
| Debug current test | `Pytest: Debug Current File` | - |
| Debug single test | `Pytest: Debug Single Test Function` | - |
| Profile current file | `Profile: cProfile Current File` | - |
| Attach to container | `Remote: Attach to Docker Container` | - |

### Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|---------------|-------|
| Start/Continue | F5 | F5 |
| Step Over | F10 | F10 |
| Step Into | F11 | F11 |
| Step Out | Shift+F11 | Shift+F11 |
| Toggle Breakpoint | F9 | F9 |
| Stop | Shift+F5 | Shift+F5 |
| Restart | Ctrl+Shift+F5 | Cmd+Shift+F5 |
| Show Debug Console | Ctrl+Shift+Y | Cmd+Shift+Y |

---

**Last Updated:** October 2025
**Python Version:** 3.12+
**VS Code Version:** 1.80+
**debugpy Version:** 1.8+
