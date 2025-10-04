# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Benchmark Runner - Executes AIPerf benchmarks and streams results
"""

import asyncio
import fcntl
import json
import os
import pty
import select
import shutil
import struct
import termios
from collections.abc import Callable
from datetime import datetime
from pathlib import Path


class BenchmarkRunner:
    """Manages benchmark execution and real-time streaming"""

    def __init__(self, data_dir: str = "../data"):
        self.data_dir = Path(data_dir)
        self.active_runs = {}  # benchmark_id -> process info

    def resize_terminal(self, benchmark_id: str, rows: int, cols: int) -> bool:
        """Resize the PTY for a running benchmark"""
        if benchmark_id not in self.active_runs:
            return False

        run_info = self.active_runs[benchmark_id]
        master_fd = run_info.get("master_fd")

        if master_fd is not None:
            try:
                # Set new terminal size
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                return True
            except Exception as e:
                print(f"Failed to resize terminal: {e}")
                return False

        return False

    async def send_input(self, benchmark_id: str, data: str) -> bool:
        """Send keyboard/mouse input to the running benchmark"""
        if benchmark_id not in self.active_runs:
            return False

        run_info = self.active_runs[benchmark_id]
        master_fd = run_info.get("master_fd")

        if master_fd is not None:
            try:
                # Write input data to PTY master (goes to process stdin)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, os.write, master_fd, data.encode("utf-8")
                )
                return True
            except Exception as e:
                print(f"Failed to send input: {e}")
                return False

        return False

    async def start_benchmark(
        self, config: dict, progress_callback: Callable | None = None
    ) -> str:
        """
        Start a new benchmark run

        Args:
            config: Benchmark configuration (model, endpoint, concurrency, etc.)
            progress_callback: Async function to call with progress updates

        Returns:
            benchmark_id for tracking the run
        """
        benchmark_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        benchmark_dir = self.data_dir / benchmark_id
        benchmark_dir.mkdir(parents=True, exist_ok=True)

        # Save configuration
        config_file = benchmark_dir / "config.json"
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        # Build AIPerf command
        cmd = self._build_command(config, benchmark_dir)

        # Store run info
        self.active_runs[benchmark_id] = {
            "process": None,
            "status": "starting",
            "started_at": datetime.now().isoformat(),
            "config": config,
            "benchmark_dir": str(benchmark_dir),
            "master_fd": None,
        }

        # Start benchmark process asynchronously
        asyncio.create_task(
            self._run_benchmark(benchmark_id, cmd, benchmark_dir, progress_callback)
        )

        return benchmark_id

    def _build_command(self, config: dict, output_dir: Path) -> list:
        """Build AIPerf command from configuration"""
        # Check if aiperf is available
        aiperf_path = shutil.which("aiperf")

        if not aiperf_path:
            # For demo/testing: create mock benchmark data
            return self._build_mock_command(config, output_dir)

        cmd = ["aiperf", "profile"]

        # Model
        if config.get("model"):
            cmd.extend(["-m", config["model"]])

        # URL
        if config.get("url"):
            cmd.extend(["--url", config["url"]])

        # Endpoint type
        if config.get("endpoint_type"):
            cmd.extend(["--endpoint-type", config["endpoint_type"]])

        # Custom endpoint path (if provided)
        if config.get("custom_endpoint"):
            cmd.extend(["--endpoint", config["custom_endpoint"]])

        # Workload parameters
        if config.get("concurrency"):
            cmd.extend(["--concurrency", str(config["concurrency"])])
        if config.get("request_rate"):
            cmd.extend(["--request-rate", str(config["request_rate"])])
        if config.get("request_count"):
            cmd.extend(["--request-count", str(config["request_count"])])

        # Token parameters
        if config.get("input_tokens"):
            cmd.extend(["--synthetic-input-tokens-mean", str(config["input_tokens"])])
        if config.get("output_tokens"):
            cmd.extend(["--output-tokens-mean", str(config["output_tokens"])])

        # Additional parameters
        if config.get("num_workers"):
            cmd.extend(["--num-workers", str(config["num_workers"])])
        if config.get("max_tokens"):
            cmd.extend(["--max-tokens", str(config["max_tokens"])])

        # Streaming flag
        if config.get("streaming", True):  # Default to True
            cmd.append("--streaming")

        # Output configuration
        cmd.extend(
            [
                "--profile-export-file",
                str(output_dir / "records.jsonl"),
                "--artifact-dir",
                str(output_dir),
            ]
        )

        return cmd

    def _build_mock_command(self, config: dict, output_dir: Path) -> list:
        """Build mock command for testing when aiperf not available"""
        # Use Python to create mock benchmark data
        mock_script = f"""
import json
import time
import random

print("Mock benchmark started (aiperf not found)")
print(f"Model: {config.get("model")}")
print(f"URL: {config.get("url")}")
print(f"Endpoint type: {config.get("endpoint_type")}")
print(f"Concurrency: {config.get("concurrency")}")
print(f"Request count: {config.get("request_count")}")

output_file = "{output_dir / "records.jsonl"}"
num_prompts = {config.get("request_count", 10)}

with open(output_file, 'w') as f:
    for i in range(num_prompts):
        record = {{
            "metadata": {{
                "x_request_id": f"req_{{i}}",
                "timestamp_ns": int(time.time() * 1e9),
                "worker_id": "w1"
            }},
            "metrics": {{
                "request_latency": {{"value": random.randint(100, 2000), "unit": "ms"}},
                "ttft": {{"value": random.randint(50, 500), "unit": "ms"}},
                "output_sequence_length": {{"value": random.randint(50, 200), "unit": "tokens"}}
            }}
        }}
        f.write(json.dumps(record) + "\\n")
        print(f"Generated request {{i+1}}/{{num_prompts}} ({{int((i+1)/num_prompts*100)}}%)")
        time.sleep(0.5)

print("Mock benchmark completed successfully")
"""

        # Write mock script to temp file
        mock_script_path = output_dir / "mock_benchmark.py"
        with open(mock_script_path, "w") as f:
            f.write(mock_script)

        return ["python", str(mock_script_path)]

    async def _run_benchmark(
        self,
        benchmark_id: str,
        cmd: list,
        output_dir: Path,
        progress_callback: Callable | None,
    ):
        """Execute benchmark and stream progress with full ANSI support"""
        try:
            # Update status
            self.active_runs[benchmark_id]["status"] = "running"
            if progress_callback:
                await progress_callback(
                    {
                        "benchmark_id": benchmark_id,
                        "status": "running",
                        "message": f"Starting benchmark: {' '.join(cmd)}",
                        "ansi_data": "",
                    }
                )

            # Use PTY to capture ANSI codes from Textual
            await self._run_with_pty(benchmark_id, cmd, output_dir, progress_callback)

        except Exception as e:
            self.active_runs[benchmark_id]["status"] = "error"
            if progress_callback:
                await progress_callback(
                    {
                        "benchmark_id": benchmark_id,
                        "status": "error",
                        "message": f"Error: {str(e)}",
                        "ansi_data": f"\r\n\033[31mError: {str(e)}\033[0m\r\n",
                    }
                )

    async def _run_with_pty(
        self,
        benchmark_id: str,
        cmd: list,
        output_dir: Path,
        progress_callback: Callable | None,
    ):
        """Run command in PTY to preserve ANSI codes"""
        master_fd, slave_fd = pty.openpty()

        # Set initial terminal size (will be updated by frontend)
        # Using smaller default that matches typical terminal
        winsize = struct.pack("HHHH", 30, 120, 0, 0)  # rows, cols, xpixel, ypixel
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

        try:
            # Start process with PTY
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=str(output_dir),
                preexec_fn=os.setsid,
            )

            self.active_runs[benchmark_id]["process"] = process
            self.active_runs[benchmark_id]["master_fd"] = master_fd
            os.close(slave_fd)  # Parent doesn't need slave end

            # Make master_fd non-blocking
            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Read from PTY in chunks and stream with ANSI codes
            loop = asyncio.get_event_loop()
            while True:
                # Check if process is still running
                if process.returncode is not None:
                    break

                # Use select to wait for data
                readable, _, _ = await loop.run_in_executor(
                    None, select.select, [master_fd], [], [], 0.1
                )

                if master_fd in readable:
                    try:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break

                        # Decode and filter out terminal cleanup codes
                        decoded = data.decode("utf-8", errors="replace")

                        # Filter out ALL codes that clear/manipulate screen:
                        # Alternate screen buffer (causes full clear)
                        filtered = decoded.replace(
                            "\x1b[?1049h", ""
                        )  # Enter alt screen
                        filtered = filtered.replace(
                            "\x1b[?1049l", ""
                        )  # Exit alt screen

                        # Clear screen codes
                        filtered = filtered.replace(
                            "\x1b[2J", ""
                        )  # Clear entire screen
                        filtered = filtered.replace("\x1b[H\x1b[2J", "")  # Home + clear
                        filtered = filtered.replace(
                            "\x1b[1;1H\x1b[2J", ""
                        )  # Position + clear
                        filtered = filtered.replace(
                            "\x1b[H", ""
                        )  # Home cursor (can cause jump)

                        # Mouse tracking (not needed for display)
                        filtered = filtered.replace(
                            "\x1b[?1000h", ""
                        )  # Enable mouse tracking
                        filtered = filtered.replace(
                            "\x1b[?1000l", ""
                        )  # Disable mouse tracking
                        filtered = filtered.replace(
                            "\x1b[?1002h", ""
                        )  # Button event tracking
                        filtered = filtered.replace("\x1b[?1002l", "")
                        filtered = filtered.replace(
                            "\x1b[?1003h", ""
                        )  # Any event tracking
                        filtered = filtered.replace("\x1b[?1003l", "")
                        filtered = filtered.replace(
                            "\x1b[?1015h", ""
                        )  # Extended mouse mode
                        filtered = filtered.replace("\x1b[?1015l", "")
                        filtered = filtered.replace("\x1b[?1006h", "")  # SGR mouse mode
                        filtered = filtered.replace("\x1b[?1006l", "")

                        # Cursor hide/show (Textual uses these)
                        filtered = filtered.replace("\x1b[?25l", "")  # Hide cursor
                        filtered = filtered.replace("\x1b[?25h", "")  # Show cursor

                        # Focus events
                        filtered = filtered.replace(
                            "\x1b[?1004h", ""
                        )  # Enable focus events
                        filtered = filtered.replace(
                            "\x1b[?1004l", ""
                        )  # Disable focus events

                        # Keyboard modifiers
                        filtered = filtered.replace(
                            "\x1b[>1u", ""
                        )  # Enhanced keyboard mode

                        # Sync/async modes
                        filtered = filtered.replace(
                            "\x1b[?2026$p", ""
                        )  # Sync mode query
                        filtered = filtered.replace("\x1b[?2048$p", "")  # Query various
                        filtered = filtered.replace(
                            "\x1b[?2004h", ""
                        )  # Bracketed paste mode
                        filtered = filtered.replace("\x1b[?2004l", "")

                        # Line wrapping
                        filtered = filtered.replace("\x1b[?7l", "")  # Disable line wrap
                        filtered = filtered.replace("\x1b[?7h", "")  # Enable line wrap

                        # Send filtered ANSI data to frontend
                        if progress_callback and filtered:
                            await progress_callback(
                                {
                                    "benchmark_id": benchmark_id,
                                    "status": "running",
                                    "ansi_data": filtered,
                                }
                            )
                    except OSError:
                        break

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.05)

            # Wait for process to complete
            await process.wait()

            # Read any remaining data but DON'T send it (may contain terminal cleanup codes)
            try:
                while True:
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    # Drain buffer but don't forward - avoid terminal cleanup codes
            except OSError:
                pass

            # Update final status - DON'T send ansi_data to avoid clearing terminal
            if process.returncode == 0:
                self.active_runs[benchmark_id]["status"] = "completed"

                # Auto-import benchmark data for comparison
                stored_dir = Path(self.active_runs[benchmark_id]["benchmark_dir"])
                await self._import_benchmark_data(benchmark_id, stored_dir)

                if progress_callback:
                    await progress_callback(
                        {
                            "benchmark_id": benchmark_id,
                            "status": "completed",
                            "message": "Benchmark completed successfully",
                        }
                    )
            else:
                self.active_runs[benchmark_id]["status"] = "failed"
                if progress_callback:
                    await progress_callback(
                        {
                            "benchmark_id": benchmark_id,
                            "status": "failed",
                            "message": f"Benchmark failed with code {process.returncode}",
                        }
                    )

        finally:
            try:
                os.close(master_fd)
            except:
                pass
            if benchmark_id in self.active_runs:
                self.active_runs[benchmark_id]["master_fd"] = None

    async def _import_benchmark_data(self, benchmark_id: str, benchmark_dir: Path):
        """Import completed benchmark data into the system for comparison"""
        try:
            # Read records.jsonl
            jsonl_file = benchmark_dir / "records.jsonl"
            if not jsonl_file.exists():
                print(f"Warning: records.jsonl not found for {benchmark_id}")
                return

            with open(jsonl_file, "rb") as f:
                jsonl_data = f.read()

            # Read aggregate.json if it exists
            aggregate_file = benchmark_dir / "aggregate.json"
            aggregate_data = None
            if aggregate_file.exists():
                with open(aggregate_file, "rb") as f:
                    aggregate_data = f.read()

            # Import via data processor (gets processor from main module)
            from main import processor

            await processor.process_upload(benchmark_id, jsonl_data, aggregate_data)
            print(f"✓ Auto-imported benchmark data: {benchmark_id}")

        except Exception as e:
            print(f"Warning: Failed to auto-import benchmark data: {e}")

    def get_run_status(self, benchmark_id: str) -> dict | None:
        """Get status of a running benchmark"""
        return self.active_runs.get(benchmark_id)

    def list_active_runs(self) -> list:
        """List all active benchmark runs"""
        return [
            {
                "benchmark_id": bid,
                "status": info["status"],
                "started_at": info["started_at"],
                "config": info["config"],
            }
            for bid, info in self.active_runs.items()
        ]

    async def stop_benchmark(self, benchmark_id: str) -> bool:
        """Stop a running benchmark"""
        if benchmark_id not in self.active_runs:
            return False

        run_info = self.active_runs[benchmark_id]
        process = run_info.get("process")

        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()

            run_info["status"] = "stopped"
            return True

        return False
