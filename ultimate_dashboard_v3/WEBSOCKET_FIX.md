<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# WebSocket Connection Fix

## Problem

WebSocket error on page load:
```
readyState: 3 (CLOSED)
type: "error"
```

The WebSocket was trying to connect immediately when the page loaded, but there was no benchmark running yet, causing connection failures.

## Solution

### 1. Lazy Connection (Only When Needed)

**Before:**
```typescript
useEffect(() => {
  const ws = apiClient.createWebSocket()  // ❌ Connects immediately
  // ...
}, [benchmarkId])
```

**After:**
```typescript
useEffect(() => {
  // Don't connect if no benchmark is running
  if (!benchmarkId || status === 'idle') {
    return  // ✅ Skip connection
  }

  const ws = apiClient.createWebSocket()  // ✅ Only connects when needed
  // ...
}, [benchmarkId, isRunning, status])
```

### 2. Automatic Reconnection

Added exponential backoff reconnection logic:

```typescript
ws.onclose = (event) => {
  if (isRunning && reconnectAttempts < maxReconnectAttempts) {
    reconnectAttempts++
    setTimeout(() => {
      setStatus((prev) => prev)  // Trigger reconnect
    }, 2000 * reconnectAttempts)  // 2s, 4s, 6s delays
  }
}
```

**Features:**
- Max 3 reconnection attempts
- Exponential backoff (2s → 4s → 6s)
- Only reconnects if benchmark is still running
- User-friendly toast notifications

### 3. Subscription Message

When WebSocket connects, it now subscribes to the specific benchmark:

```typescript
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    benchmark_id: benchmarkId
  }))
}
```

### 4. Better Error Handling

All WebSocket operations now have try-catch blocks:

```typescript
try {
  wsRef.current.send(JSON.stringify({
    type: 'input',
    benchmark_id: benchmarkId,
    data: data,
  }))
} catch (error) {
  console.warn('Failed to send input:', error)
}
```

### 5. Proper Cleanup

```typescript
return () => {
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout)  // Clear pending reconnects
  }
  if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
    ws.close()  // Close active connections
  }
  wsRef.current = null
}
```

## How It Works Now

### Connection Flow

1. **Page Load**
   - No WebSocket connection attempted
   - User sees "Waiting for benchmark to start..."

2. **User Clicks "Start Benchmark"**
   - Benchmark ID created
   - Status changes to "starting" → "running"
   - WebSocket connects automatically

3. **WebSocket Opens**
   - Sends subscription message
   - Ready to receive ANSI data
   - Ready to send input (keyboard/mouse)

4. **If Connection Drops**
   - Shows toast: "Connection lost. Attempting to reconnect..."
   - Tries 3 times with exponential backoff
   - If all fail: "Connection lost. Please refresh the page."

5. **Benchmark Completes**
   - WebSocket closes gracefully
   - No reconnection attempts

## Testing the Fix

### Manual Test

1. **Start Backend**
   ```bash
   cd backend
   python main.py
   ```

2. **Start Frontend**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Navigate to Run Page**
   - Open http://localhost:3000/run
   - Check browser console: Should see NO WebSocket errors

4. **Start a Benchmark**
   - Fill in configuration
   - Click "Start Benchmark"
   - Console should show: `"Connecting WebSocket for benchmark: benchmark_..."` then `"✓ WebSocket connected"`

5. **Interact with Terminal**
   - Type keys → should see input sent
   - Click terminal → should see mouse events
   - Resize window → should see resize messages

6. **Test Reconnection**
   - Restart backend while benchmark running
   - Should see: "Connection lost. Attempting to reconnect..."
   - When backend comes back, should reconnect automatically

## WebSocket Message Types

### Client → Server

```typescript
// Subscribe to benchmark
{
  type: 'subscribe',
  benchmark_id: string
}

// Terminal resize
{
  type: 'resize',
  benchmark_id: string,
  rows: number,
  cols: number
}

// Keyboard/mouse input
{
  type: 'input',
  benchmark_id: string,
  data: string  // Raw input data
}

// Ping (keep-alive)
{
  type: 'ping'
}
```

### Server → Client

```typescript
// ANSI output
{
  benchmark_id: string,
  status: 'running' | 'completed' | 'failed',
  ansi_data: string  // Raw ANSI with escape codes
}

// Status message (fallback)
{
  benchmark_id: string,
  status: string,
  message: string
}

// Pong (keep-alive response)
{
  type: 'pong'
}
```

## Console Output Examples

### Successful Connection

```
Connecting WebSocket for benchmark: benchmark_20251004_112730
✓ WebSocket connected
✓ Sent terminal resize: 30x120
```

### Receiving ANSI Data

```
Received ANSI data: 247 bytes
Received ANSI data: 1834 bytes
Received ANSI data: 512 bytes
```

### Keyboard Input

```
Sent input: "\x1b[A" (arrow up)
Sent input: "\r" (enter)
Sent input: "q" (quit)
```

### Mouse Click

```
Sent input: "\x1b[<0;45;12M" (mouse press at col 45, row 12)
Sent input: "\x1b[<0;45;12m" (mouse release)
```

### Reconnection

```
WebSocket error: Event {...}
Connection lost. Attempting to reconnect...
Reconnection attempt 1/3
Attempting to reconnect...
Connecting WebSocket for benchmark: benchmark_20251004_112730
✓ WebSocket connected
```

## Troubleshooting

### Still Getting WebSocket Errors?

**Check:**
1. Backend running? `ps aux | grep "python main.py"`
2. Port 8000 free? `lsof -i :8000`
3. CORS enabled? (already configured in main.py)
4. Browser console shows connection attempts?

**Solutions:**
- Restart backend: `cd backend && python main.py`
- Clear browser cache
- Check firewall/antivirus blocking WebSocket
- Try different port (update both backend and frontend)

### Input Not Working After Reconnect?

The reconnection sends a new subscription message, so input should work. If not:
1. Check console for "WebSocket not connected" warnings
2. Verify `wsRef.current` is set
3. Look for `readyState: 1` (OPEN) in console

### Terminal Showing Old Data After Reconnect?

This is expected - the terminal keeps history. If you want a fresh view:
1. Restart the benchmark (creates new WebSocket)
2. Refresh the page
3. Clear terminal manually with Ctrl+L (if aiperf supports it)

## Related Files

- `frontend/app/run/page.tsx` - WebSocket connection logic (line 42-156)
- `backend/main.py` - WebSocket endpoint (line 297-338)
- `frontend/lib/api.ts` - WebSocket factory (line 146-149)
