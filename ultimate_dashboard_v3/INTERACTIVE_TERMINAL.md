<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Interactive Terminal Implementation

## Overview

Fully bidirectional terminal integration allowing complete keyboard and mouse interaction with the aiperf Textual dashboard through the web interface.

## Architecture

```
Frontend (xterm.js)
    ↓ keyboard/mouse events
WebSocket (bidirectional)
    ↓ input data
Backend (FastAPI)
    ↓ os.write()
PTY Master FD
    ↓ slave FD
AIPerf Process (Textual UI)
    ↓ ANSI output
PTY Master FD
    ↓ os.read()
Backend (FastAPI)
    ↓ ansi_data
WebSocket
    ↓
Frontend (xterm.js display)
```

## Components

### Frontend (TerminalViewer.tsx)

**Input Capture:**
- `disableStdin: false` - Enable keyboard input
- `terminal.onData()` - Capture all keyboard events
- Mouse tracking enabled via ANSI sequences:
  - `\x1b[?1000h` - Basic mouse tracking
  - `\x1b[?1002h` - Button event tracking
  - `\x1b[?1003h` - Any event tracking (movement)
  - `\x1b[?1006h` - SGR extended mode (supports larger terminals)

**Terminal Configuration:**
- `scrollback: 0` - Static size, no scrolling
- `convertEol: false` - Preserve ANSI sequences
- `cursorStyle: 'block'` - Visible cursor
- `fontSize: 13` - Optimal density

**Focus Management:**
- Auto-focus on mount
- Click to focus
- Focus after benchmark starts

### Frontend (app/run/page.tsx)

**WebSocket Communication:**

```typescript
// Send keyboard/mouse input
{
  type: 'input',
  benchmark_id: string,
  data: string  // Raw input data (keys, escape sequences)
}

// Send terminal resize
{
  type: 'resize',
  benchmark_id: string,
  rows: number,
  cols: number
}

// Receive ANSI output
{
  benchmark_id: string,
  status: string,
  ansi_data: string  // Raw ANSI with control codes
}
```

### Backend (main.py)

**WebSocket Handler:**

```python
elif data.get("type") == "input":
    benchmark_id = data.get("benchmark_id")
    input_data = data.get("data")
    await benchmark_runner.send_input(benchmark_id, input_data)
```

### Backend (benchmark_runner.py)

**Input Handling:**

```python
async def send_input(self, benchmark_id: str, data: str) -> bool:
    """Send keyboard/mouse input to running benchmark"""
    master_fd = self.active_runs[benchmark_id]["master_fd"]

    # Write to PTY master (process reads from slave)
    await loop.run_in_executor(
        None,
        os.write,
        master_fd,
        data.encode('utf-8')
    )
```

**PTY Setup:**
- Initial size: 30 rows × 120 cols
- Non-blocking I/O on master FD
- `preexec_fn=os.setsid` - New session for process group

## Supported Interactions

### Keyboard

- **Arrow Keys**: Navigate Textual UI
- **Enter**: Activate buttons/selections
- **Tab/Shift+Tab**: Focus navigation
- **Space**: Toggle/activate
- **Escape**: Cancel/back
- **Letters/Numbers**: Text input in fields
- **Ctrl+C**: Signal interrupt (handled by aiperf)
- **Function Keys**: F1-F12 if mapped

### Mouse

- **Click**: Button activation, selection
- **Drag**: Selection (if supported by Textual widget)
- **Scroll**: Not enabled (scrollback: 0)
- **Hover**: Visual feedback (if widget supports)

### Special Sequences

xterm.js automatically encodes:
- Arrow keys → `\x1b[A` (up), `\x1b[B` (down), etc.
- Enter → `\r` or `\n`
- Tab → `\t`
- Backspace → `\x7f` or `\b`
- Mouse clicks → SGR format: `\x1b[<b;x;yM` (press), `\x1b[<b;x;ym` (release)

## Data Flow Examples

### Keyboard Input Example

1. User presses **Enter** key
2. xterm.js `onData()` fires with `\r`
3. Frontend sends: `{ type: 'input', benchmark_id: 'bench_123', data: '\r' }`
4. Backend receives via WebSocket
5. Backend calls `os.write(master_fd, b'\r')`
6. AIPerf reads from slave FD, processes Enter key
7. Textual updates UI, sends ANSI output
8. Backend reads from master FD
9. Backend broadcasts: `{ ansi_data: '\x1b[2J\x1b[H...' }` (clear + redraw)
10. Frontend `terminal.write()` displays updated UI

### Mouse Click Example

1. User clicks at column 50, row 10
2. xterm.js encodes as `\x1b[<0;50;10M` (button 0, press)
3. Frontend sends: `{ type: 'input', benchmark_id: 'bench_123', data: '\x1b[<0;50;10M' }`
4. Backend writes to PTY master
5. Textual processes mouse event at (50, 10)
6. Button widget activates, triggers action
7. UI updates, ANSI output returned
8. Frontend displays result

## Testing Interactive Features

### Manual Test Plan

1. **Start Benchmark**:
   - Click "Start Benchmark" button
   - Verify terminal shows "Interactive Terminal" message
   - Verify cursor is visible and blinking

2. **Keyboard Navigation**:
   - Press **Tab** - focus should move between widgets
   - Press **Arrow Keys** - navigate through options
   - Press **Enter** - activate focused element

3. **Mouse Interaction**:
   - Click buttons in Textual UI
   - Click tabs/panels
   - Verify click coordinates match visual position

4. **Terminal Resize**:
   - Resize browser window
   - Verify Textual UI adjusts layout
   - Check console for resize messages

5. **Text Input** (if applicable):
   - Type in text fields
   - Backspace to delete
   - Verify characters appear correctly

## Troubleshooting

### Input Not Working

**Check:**
- Is benchmark running? (Only works with active PTY)
- Is terminal focused? (Click terminal area)
- Check browser console for WebSocket errors
- Verify backend logs show `send_input()` calls

### Mouse Clicks Not Registering

**Check:**
- Mouse tracking sequences sent? (Look for `\x1b[?1000h` in terminal init)
- SGR mode enabled? (`\x1b[?1006h`)
- Click coordinates within terminal bounds?
- Textual widget supports mouse input?

### Keyboard Shortcuts Not Working

**Possible causes:**
- Browser capturing shortcut (Ctrl+T, Ctrl+W, etc.)
- Terminal not focused
- Special key not encoded correctly

**Solutions:**
- Use browser that allows override (electron, etc.)
- Implement custom key handlers for blocked shortcuts
- Check xterm.js key encoding

## Performance Considerations

- **Input Latency**: ~5-50ms (WebSocket + PTY + encoding)
- **Throughput**: Handles hundreds of events/second
- **Buffering**: Backend uses 4096-byte chunks for output
- **Non-blocking**: Async I/O prevents UI freeze

## Security Notes

- PTY isolated per benchmark
- No shell access (process runs aiperf only)
- Input sanitization via UTF-8 encoding
- WebSocket behind same-origin policy
- No arbitrary command execution

## Future Enhancements

- [ ] Copy/paste support (`\x1b[200~` bracketed paste)
- [ ] Terminal search (Ctrl+F)
- [ ] Save/export terminal session
- [ ] Replay mode for completed benchmarks
- [ ] Multi-user collaborative viewing
- [ ] Screen recording to GIF/video

## Related Files

- `frontend/components/TerminalViewer.tsx` - xterm.js wrapper
- `frontend/app/run/page.tsx` - Run page with WebSocket
- `backend/benchmark_runner.py` - PTY management
- `backend/main.py` - WebSocket handler
