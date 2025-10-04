#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
NVIDIA AIPerf Dashboard v3 - Backend API Server
Powered by FastAPI for blazing-fast performance
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from ai_insights import AIInsightsEngine
from benchmark_runner import BenchmarkRunner
from data_processor import DataProcessor
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Initialize FastAPI app
app = FastAPI(
    title="NVIDIA AIPerf Dashboard v3",
    description="Next-generation LLM performance benchmarking dashboard",
    version="3.0.0",
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
processor = DataProcessor()
ai_engine = AIInsightsEngine()
benchmark_runner = BenchmarkRunner()
active_connections: list[WebSocket] = []


# Models
class BenchmarkQuery(BaseModel):
    """Query parameters for benchmark data"""

    metric: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    filters: dict[str, Any] | None = None


class ComparisonRequest(BaseModel):
    """Request to compare multiple benchmarks"""

    benchmark_ids: list[str]
    metrics: list[str]


class InsightRequest(BaseModel):
    """Request for AI-powered insights"""

    benchmark_id: str
    focus_area: str | None = None


class BenchmarkRunRequest(BaseModel):
    """Request to start a new benchmark run"""

    model: str
    url: str = "http://localhost:8000"
    endpoint_type: str = "chat"
    custom_endpoint: str | None = None
    concurrency: int | None = 1
    request_rate: float | None = None
    request_count: int | None = 100
    input_tokens: int | None = 256
    output_tokens: int | None = 128


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            print("⚠️  No active WebSocket connections to broadcast to")
            return

        print(
            f"📡 Broadcasting to {len(self.active_connections)} connection(s): {list(message.keys())}"
        )
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"❌ Failed to send to connection: {e}")


manager = ConnectionManager()


# API Endpoints


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "NVIDIA AIPerf Dashboard v3",
        "status": "operational",
        "version": "3.0.0",
        "powered_by": ["FastAPI", "NVIDIA", "AIPerf"],
    }


@app.get("/api/v3/benchmarks")
async def list_benchmarks():
    """List all available benchmarks"""
    benchmarks = await processor.list_benchmarks()
    return {"benchmarks": benchmarks}


@app.get("/api/v3/benchmarks/{benchmark_id}")
async def get_benchmark(benchmark_id: str):
    """Get detailed benchmark data"""
    try:
        data = await processor.get_benchmark_data(benchmark_id)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Benchmark not found")


@app.post("/api/v3/benchmarks/upload")
async def upload_benchmark(
    jsonl_file: UploadFile = File(...), aggregate_file: UploadFile | None = File(None)
):
    """Upload new benchmark data"""
    try:
        # Validate file types
        if not jsonl_file.filename.endswith(".jsonl"):
            raise HTTPException(
                status_code=400, detail="JSONL file must have .jsonl extension"
            )

        if aggregate_file and not aggregate_file.filename.endswith(".json"):
            raise HTTPException(
                status_code=400, detail="Aggregate file must have .json extension"
            )

        # Save uploaded files
        benchmark_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        jsonl_data = await jsonl_file.read()
        aggregate_data = await aggregate_file.read() if aggregate_file else None

        # Validate JSONL data size
        if len(jsonl_data) == 0:
            raise HTTPException(status_code=400, detail="JSONL file is empty")

        # Process data
        result = await processor.process_upload(
            benchmark_id, jsonl_data, aggregate_data
        )

        return {"benchmark_id": benchmark_id, "status": "success", "summary": result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Data validation error: {str(e)}")
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/api/v3/query")
async def query_metrics(query: BenchmarkQuery):
    """Query specific metrics with filters"""
    try:
        results = await processor.query_metrics(
            metric=query.metric,
            start_time=query.start_time,
            end_time=query.end_time,
            filters=query.filters,
        )
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v3/compare")
async def compare_benchmarks(request: ComparisonRequest):
    """Compare multiple benchmarks side-by-side"""
    try:
        comparison = await processor.compare_benchmarks(
            request.benchmark_ids, request.metrics
        )
        return {"comparison": comparison}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v3/insights")
async def get_ai_insights(request: InsightRequest):
    """Get AI-powered insights and recommendations"""
    try:
        # Get benchmark data
        data = await processor.get_benchmark_data(request.benchmark_id)

        # Generate insights
        insights = await ai_engine.analyze(data, focus_area=request.focus_area)

        return {
            "benchmark_id": request.benchmark_id,
            "insights": insights,
            "generated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/stats/summary")
async def get_summary_stats():
    """Get high-level summary statistics"""
    try:
        summary = await processor.get_summary_stats()
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/export/{benchmark_id}/{format}")
async def export_data(benchmark_id: str, format: str):
    """Export benchmark data in various formats"""
    supported_formats = ["json", "csv", "parquet"]

    if format not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Format must be one of: {', '.join(supported_formats)}",
        )

    try:
        data = await processor.export_benchmark(benchmark_id, format)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v3/benchmarks/run")
async def run_benchmark(request: BenchmarkRunRequest):
    """Start a new benchmark run with real-time streaming"""
    try:
        print(f"🚀 Starting benchmark with config: {request.model}")

        # Start benchmark with progress callback that broadcasts to WebSocket
        async def progress_callback(update: dict):
            print(f"📤 Progress callback called with keys: {list(update.keys())}")
            await manager.broadcast(update)

        benchmark_id = await benchmark_runner.start_benchmark(
            config=request.dict(), progress_callback=progress_callback
        )

        return {
            "benchmark_id": benchmark_id,
            "status": "started",
            "message": "Benchmark started successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start benchmark: {str(e)}"
        )


@app.get("/api/v3/benchmarks/runs/active")
async def list_active_runs():
    """List all currently active benchmark runs"""
    runs = benchmark_runner.list_active_runs()
    return {"active_runs": runs}


@app.post("/api/v3/benchmarks/runs/{benchmark_id}/stop")
async def stop_benchmark_run(benchmark_id: str):
    """Stop a running benchmark"""
    success = await benchmark_runner.stop_benchmark(benchmark_id)

    if not success:
        raise HTTPException(
            status_code=404, detail="Benchmark not found or already stopped"
        )

    return {
        "benchmark_id": benchmark_id,
        "status": "stopped",
        "message": "Benchmark stopped successfully",
    }


@app.post("/api/v3/configs/save")
async def save_config(request: dict):
    """Save a benchmark configuration"""
    config_name = request.get("name")
    config_data = request.get("config")

    if not config_name or not config_data:
        raise HTTPException(status_code=400, detail="Missing name or config")

    configs_dir = Path("../data/configs")
    configs_dir.mkdir(parents=True, exist_ok=True)

    config_file = configs_dir / f"{config_name}.json"
    with open(config_file, "w") as f:
        json.dump(config_data, f, indent=2)

    return {
        "status": "success",
        "name": config_name,
        "message": f"Configuration '{config_name}' saved successfully",
    }


@app.get("/api/v3/configs")
async def list_configs():
    """List all saved configurations"""
    configs_dir = Path("../data/configs")
    configs_dir.mkdir(parents=True, exist_ok=True)

    configs = []
    for config_file in configs_dir.glob("*.json"):
        try:
            with open(config_file) as f:
                config_data = json.load(f)
            configs.append({"name": config_file.stem, "config": config_data})
        except Exception as e:
            print(f"Warning: Failed to load config {config_file}: {e}")

    return {"configs": configs}


@app.delete("/api/v3/configs/{config_name}")
async def delete_config(config_name: str):
    """Delete a saved configuration"""
    configs_dir = Path("../data/configs")
    config_file = configs_dir / f"{config_name}.json"

    if not config_file.exists():
        raise HTTPException(status_code=404, detail="Configuration not found")

    config_file.unlink()
    return {
        "status": "success",
        "message": f"Configuration '{config_name}' deleted successfully",
    }


# WebSocket for real-time updates
@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time metric streaming"""
    await manager.connect(websocket)
    print(
        f"✓ WebSocket client connected. Total connections: {len(manager.active_connections)}"
    )

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()

            if data.get("type") == "subscribe":
                benchmark_id = data.get("benchmark_id")
                # Start streaming updates for this benchmark
                await manager.broadcast(
                    {"type": "status", "message": f"Subscribed to {benchmark_id}"}
                )

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            elif data.get("type") == "resize":
                # Handle terminal resize
                benchmark_id = data.get("benchmark_id")
                rows = data.get("rows")
                cols = data.get("cols")

                if benchmark_id and rows and cols:
                    success = benchmark_runner.resize_terminal(benchmark_id, rows, cols)
                    if success:
                        print(f"Resized terminal for {benchmark_id} to {rows}x{cols}")

            elif data.get("type") == "input":
                # Handle terminal input (keyboard/mouse)
                benchmark_id = data.get("benchmark_id")
                input_data = data.get("data")

                if benchmark_id and input_data:
                    await benchmark_runner.send_input(benchmark_id, input_data)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(
            f"✗ WebSocket client disconnected. Total connections: {len(manager.active_connections)}"
        )


@app.get("/api/v3/leaderboard")
async def get_leaderboard():
    """Get performance leaderboard across all benchmarks"""
    try:
        leaderboard = await processor.get_leaderboard()
        return {"leaderboard": leaderboard}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/trends/{metric}")
async def get_trends(metric: str, window: int = 30):
    """Get historical trends for a metric"""
    try:
        trends = await processor.get_metric_trends(metric, window)
        return {"metric": metric, "trends": trends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print("=" * 80)
    print("🚀 NVIDIA AIPerf Dashboard v3 - Backend Server")
    print("=" * 80)
    print("\n🔥 Powered by:")
    print("   • FastAPI - High-performance async framework")
    print("   • NVIDIA AIPerf - Advanced benchmarking")
    print("   • AI-Dynamo - Intelligent insights")
    print("\n📡 Starting server on http://localhost:8000")
    print("📊 API docs available at http://localhost:8000/docs")
    print("🔌 WebSocket endpoint: ws://localhost:8000/ws/realtime")
    print("=" * 80)
    print()

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
