<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Debugging Guide - No Terminal Output

## Problem
Terminal events (keyboard/mouse) are working, but no ANSI output is showing in the terminal.

## Debug Steps

### 1. Check Backend Logs

The backend now has verbose logging. Check the terminal where backend is running or check `backend.log`:

```bash
cd backend
tail -f backend.log
```

**Expected Output When Starting Benchmark:**
```
🚀 Starting benchmark with config: openai/gpt-oss-20b
✓ WebSocket client connected. Total connections: 1
📤 Progress callback called with keys: ['benchmark_id', 'status', 'message', 'ansi_data']
📡 Broadcasting to 1 connection(s): ['benchmark_id', 'status', 'message', 'ansi_data']
```

**Problem Indicators:**
- `⚠️  No active WebSocket connections to broadcast to` → Frontend not connected
- `❌ Failed to send to connection: ...` → WebSocket broken
- No `📤 Progress callback` messages → Benchmark not sending data

### 2. Check Frontend Console

Open browser DevTools (F12) and check console:

**Expected Output:**
```
Setting up WebSocket connection
✓ WebSocket connected
Subscribing to benchmark: benchmark_20251004_...
WebSocket message received: data running
Writing ANSI data to terminal: 247 bytes
Writing ANSI data to terminal: 1834 bytes
```

**Problem Indicators:**
- `WebSocket error: ...` → Connection issue
- `Received ANSI data but terminal not ready` → Terminal initialization issue
- No `"WebSocket message received"` → Backend not sending or connection broken
- No `"Writing ANSI data"` → Data not reaching terminal write

### 3. Check WebSocket Connection

In browser console, check:
```javascript
// After page loads
wsRef.current  // Should be WebSocket object
wsRef.current.readyState  // Should be 1 (OPEN)
```

**ReadyState Values:**
- 0 = CONNECTING
- 1 = OPEN ✓
- 2 = CLOSING
- 3 = CLOSED ❌

### 4. Test Backend Directly

Test if backend is running the benchmark correctly:

```bash
cd backend
python -c "
import asyncio
from benchmark_runner import BenchmarkRunner

async def test():
    runner = BenchmarkRunner()

    received_data = []
    async def callback(data):
        received_data.append(data)
        print(f'Received: {list(data.keys())}')
        if 'ansi_data' in data:
            print(f'  ANSI data: {len(data[\"ansi_data\"])} bytes')

    config = {
        'model': 'test',
        'url': 'http://localhost:8000',
        'endpoint_type': 'chat',
        'request_count': 5,
        'concurrency': 1,
        'input_tokens': 10,
        'output_tokens': 10
    }

    bench_id = await runner.start_benchmark(config, callback)
    print(f'Benchmark started: {bench_id}')

    # Wait for completion
    await asyncio.sleep(10)

    print(f'\\nTotal callbacks: {len(received_data)}')
    for i, data in enumerate(received_data[:5]):
        print(f'{i+1}. {list(data.keys())}')

asyncio.run(test())
"
```

**Expected Output:**
```
Benchmark started: benchmark_...
Received: ['benchmark_id', 'status', 'message', 'ansi_data']
  ANSI data: 247 bytes
Received: ['benchmark_id', 'status', 'ansi_data']
  ANSI data: 1834 bytes
...
```

### 5. Check Terminal Object

In browser console after terminal loads:
```javascript
// Check terminal exists
window.xterm
// Should show: Terminal {element: div.xterm, ...}

// Test writing directly
window.xterm.write('\\x1b[32mTest\\x1b[0m\\r\\n')
// Should see green "Test" in terminal

// Check terminal is ready
window.xterm.rows  // Should be number > 0
window.xterm.cols  // Should be number > 0
```

## Common Issues & Fixes

### Issue 1: No WebSocket Connections

**Symptom:** Backend logs show `⚠️  No active WebSocket connections`

**Cause:** Frontend WebSocket not connecting

**Fix:**
1. Check frontend console for WebSocket errors
2. Verify backend is running on port 8000
3. Check CORS settings in backend
4. Try refreshing the page

### Issue 2: Progress Callback Not Called

**Symptom:** No `📤 Progress callback` messages in backend logs

**Cause:** Benchmark not starting or PTY issue

**Fix:**
1. Check if `aiperf` is installed: `which aiperf`
2. If not, it should use mock benchmark (check logs)
3. Check for errors in backend logs
4. Verify PTY creation isn't failing

### Issue 3: Terminal Not Ready

**Symptom:** Frontend logs show `Received ANSI data but terminal not ready`

**Cause:** Terminal initialization race condition

**Fix:**
1. Wait a few seconds after page load
2. Check `window.xterm` exists in console
3. Try clicking on terminal area to ensure focus
4. Refresh page and wait for terminal to fully load

### Issue 4: Data Received But Not Displayed

**Symptom:** Logs show data received but nothing in terminal

**Cause:** Terminal write failing silently

**Fix:**
1. Check browser console for errors
2. Try writing test data: `window.xterm.write('test\\r\\n')`
3. Check if terminal is hidden (CSS issue)
4. Verify terminal container has proper dimensions

### Issue 5: WebSocket Closes Immediately

**Symptom:** WebSocket connects then immediately closes

**Cause:** Backend endpoint error or connection rejected

**Fix:**
1. Check backend logs for errors
2. Verify WebSocket endpoint: `ws://localhost:8000/ws/realtime`
3. Check for firewall/proxy blocking WebSocket
4. Test with: `websocat ws://localhost:8000/ws/realtime`

## Manual Test Procedure

1. **Start Backend:**
   ```bash
   cd backend
   python main.py
   ```
   Watch for: `📡 Starting server on http://localhost:8000`

2. **Start Frontend:**
   ```bash
   cd frontend
   npm run dev
   ```
   Open: http://localhost:3000/run

3. **Open Browser Console** (F12)

4. **Check Initial State:**
   - Should see: `Setting up WebSocket connection`
   - Should see: `✓ WebSocket connected`

5. **Start Benchmark:**
   - Fill in config
   - Click "Start Benchmark"
   - Watch both backend logs AND browser console

6. **Expected Flow:**
   - Backend: `🚀 Starting benchmark...`
   - Frontend: `Subscribing to benchmark: ...`
   - Backend: `📤 Progress callback...`
   - Backend: `📡 Broadcasting...`
   - Frontend: `WebSocket message received...`
   - Frontend: `Writing ANSI data to terminal: X bytes`
   - Terminal: Should show aiperf output

## Logging Cheat Sheet

### Backend Logs (Terminal/backend.log)
- 🚀 = Benchmark starting
- ✓ = WebSocket connected
- ✗ = WebSocket disconnected
- 📤 = Progress callback triggered
- 📡 = Broadcasting data
- ⚠️  = Warning (no connections)
- ❌ = Error sending data

### Frontend Console
- "Setting up" = Initializing connection
- "✓ WebSocket connected" = Connection established
- "Subscribing" = Sending subscription
- "WebSocket message received" = Data received
- "Writing ANSI data" = Writing to terminal
- "Terminal input" = Keyboard/mouse event

## Quick Diagnostic Commands

```bash
# Check backend running
curl http://localhost:8000/

# Check WebSocket (requires websocat)
echo '{"type":"ping"}' | websocat ws://localhost:8000/ws/realtime

# Watch backend logs
tail -f backend/backend.log

# Check processes
ps aux | grep -E "python main.py|npm run dev"

# Check ports
lsof -i :8000  # Backend
lsof -i :3000  # Frontend
```

## If All Else Fails

1. **Restart Everything:**
   ```bash
   pkill -f "python main.py"
   pkill -f "npm run dev"
   cd backend && python main.py &
   cd frontend && npm run dev
   ```

2. **Clear Browser Cache:**
   - Hard refresh: Ctrl+Shift+R (Cmd+Shift+R on Mac)
   - Or clear all browser data

3. **Check Versions:**
   ```bash
   python --version  # Should be 3.10+
   node --version    # Should be 18+
   ```

4. **Reinstall Dependencies:**
   ```bash
   cd backend && pip install -r requirements.txt
   cd frontend && rm -rf node_modules && npm install
   ```
