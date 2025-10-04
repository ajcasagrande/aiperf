<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# CLAUDE.md

## Engineering Discipline: Parsimony and Cognitive Load

### The Core Principle
Every line of code in a diff that isn't immediately and obviously necessary for achieving the stated goal destroys the reviewer's ability to reason about the change. This is not hyperbole—it's the fundamental constraint that determines whether code review enables or blocks progress.

### The Problem: Workslop
"Workslop" is GenAI-generated content that misses the mark—output that's true-ish but misleads rather than instructs. It exists in all GenAI content and is affecting work practice globally. Generate a 100-page document in 1/1000th the time, but 15 workslop examples inside it (where the AI generated something plausible that subtly misleads) cause flow collapse in every reviewer, every time they encounter one.

In code, workslop manifests as:
- Sprawling, unfocused changes that mix the actual fix with exploratory debris
- Refactoring that wasn't requested and isn't necessary for the goal
- Comments that explain what the code does instead of protecting flow state
- Cleanup, reformatting, and tangential "improvements"
- Functions and abstractions that sound good but don't match the actual architecture

**The good news**: Unlike prose workslop, code workslop is obvious and can be eliminated with disciplined practice.

**What happens when you encounter workslop**: Your mind branches into infinite uncertainty. "What is this for? Is it part of the thing? Is it workslop? Is it accidental? Should I ask about it? How far will that rabbit hole go?" Any flow state shatters. Every single extraneous line causes this complete collapse.

### The Solution: Diff Discipline
A tight, parsimonious diff builds trust and enables rapid review. A sprawling diff burns trust and makes review nearly impossible.

**Before committing, review your own diff**. For EVERY changed line ask: "Would a reviewer immediately understand this is required for [the stated goal]?" If the answer is anything but "obviously yes," that line must be removed or moved to a separate branch.

**If you don't know what the stated goal is clearly, stop and ask**. Every modification, 100% of the time, is for the purpose of satisfying a stated, falsifiable goal.

### What Destroys Flow (Never Include in Production Diffs)
- Reformatting existing code (whitespace, alignment, line breaks)
- Renaming variables/functions not directly involved in the change
- Adding/modifying comments unless they prevent flow collapse (see Comments section below)
- Refactoring adjacent code "while you're there"
- Updating dependencies not required for the change
- Cleanup of unrelated code
- Debug statements or exploratory logging
- Value representation changes (e.g., 0.5Gi → "512Mi")
- Import reordering unless it fixes a bug

### Comments: Flow-State Protectors Only
The only comment code should have is one that protects the reader from experiencing flow collapse when they see the next line/lines. Comments exist to prevent the "What is this for?" branching uncertainty.

**When to add a comment**:
- The next lines appear incongruent with the goal
- You're taking a custom fix or alternate route that isn't obvious
- There's a surprising workaround for a known bug (e.g., "Milvus 2.4.x bug #38172: utility API returns corrupted data")

**When NOT to add a comment**:
- Explaining what the code does (the code already does that)
- Documenting function parameters (use type hints)
- Describing obvious logic
- Restating the function name in prose

### Linting: Automating the Discipline
This principle is the fundamental purpose of linting tools. Linters (black, isort, flake8, mypy, eslint, prettier) exist to:
1. **Eliminate style debates from diffs** - Automated formatting means these changes never appear in human review
2. **Catch mechanical errors pre-commit** - Type errors, unused imports, and style violations are caught before they pollute the diff
3. **Minimize cognitive load** - By enforcing consistency automatically, reviewers can focus on logic and correctness

**Always run linters before committing**. A diff that mixes functional changes with linting fixes is as harmful as any other form of workslop. If linters catch issues:
- If in files you're already changing: fix them in your branch
- If in unrelated files: create a separate "lint fixes" branch or commit

### Branch Cleanliness Protocol
1. **Do exploratory work** - Try approaches, add debug logging, experiment freely
2. **Identify the minimal solution** - Once working, determine exactly what's required
3. **Create a clean branch** - Check out from main, apply ONLY the essential changes
4. **Review your own diff** - Read it as if you know nothing about the problem
5. **Verify independently** - Run tests to prove the minimal changes work

### Commit Message Discipline
Your commit message should describe the single purpose. If you struggle to write a one-sentence description, your branch likely contains multiple concerns that should be separated.

**Good**: "Fix /jobs endpoint using Milvus REST API v2 to work around task_id=0 bug"
**Bad**: "Fix /jobs endpoint, refactor error handling, update comments, and reformat imports"

The second message describes workslop, not a shippable change.

---

## Project: NVIDIA AIPerf Dashboard v3

Full-stack LLM benchmarking dashboard: Next.js 14 frontend + FastAPI backend. Processes JSONL benchmark data, provides analytics and AI-powered insights.

## Development Commands

### Backend (Python/FastAPI)

```bash
# Setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run development server (with hot reload)
python main.py

# Backend: http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Frontend (Next.js/React)

```bash
# Setup
cd frontend
npm install

# Development
npm run dev

# Production build
npm run build
npm start

# Type checking
npm run type-check

# Linting
npm run lint

# Frontend: http://localhost:3000
```

## Architecture

### Data Flow

1. **Upload**: JSONL files → `/api/v3/benchmarks/upload` → `data/benchmark_id/records.jsonl`
2. **Processing**: `DataProcessor` parses JSONL line-by-line, computes statistics, merges aggregate data
3. **Storage**: Each benchmark gets directory with `records.jsonl`, `aggregate.json`, computed statistics
4. **Index**: `data/index.json` maintains benchmark metadata
5. **Caching**: Backend caches processed data in memory

### Critical: Aggregate vs. Record-Level Metrics

**In `backend/data_processor.py:_compute_statistics`**:
- Record-level metrics (latency, TTFT, ITL): Full percentile distributions (p1-p99)
- Aggregate metrics (throughput, goodput, request_throughput): Only `mean` values
- Method merges both sources: computes percentiles from JSONL records, then merges aggregate metrics from `aggregate.json`

**In `frontend/components/charts/ComparisonChart.tsx`**:
- Detects if metric has valid percentiles (p50/p90/p99 > 0)
- Record-level metrics: displays percentile bars
- Aggregate metrics: uses `mean` value for all bars

### State Management

**Zustand Store** (`frontend/lib/store.ts`):
- Global state: benchmarks list, selected benchmark, comparison selections
- Persists `comparisonBenchmarks` and `currentBenchmarkId` to localStorage
- Max 10 benchmarks compared simultaneously

**React Query**:
- Handles API data fetching with caching
- Keys: `['benchmarks']`, `['benchmark', id]`, `['comparison', ids, metrics]`
- Strategy: `refetchOnMount: true, staleTime: 0` (prevents stale data)

### API Structure

Backend wraps responses:
```typescript
{ "benchmarks": [...] }  // NOT unwrapped array
{ "comparison": {...} }
{ "insights": {...} }
```

API client (`frontend/lib/api.ts`) extracts nested data:
```typescript
return response.data.benchmarks  // NOT response.data
```

### Component Organization

**Comparison Page** (`frontend/app/compare/page.tsx`):
- Three views: Overview (podium/radar/heatmap), Detailed (charts/table), Statistical (deep analysis)
- Calculates performance scores: normalizes metrics 0-100 (lower=better for latency, higher=better for throughput)
- All 6 metrics selected by default

**Chart Components** (`frontend/components/charts/`):
- All include null safety guards at top
- Return "No data available" when data missing
- `RadarChart`: Normalizes metrics to 0-100 scale
- `HeatmapChart`: Color-coded performance matrix
- `MetricsTable`: Sortable, expandable rows with percentiles
- `WinnerPodium`: Olympic-style animated rankings
- `StatisticalAnalysisSection`: CV, spread analysis

## Key Files

### Backend
- `main.py`: FastAPI app, routes, WebSocket
- `data_processor.py`: Data processing, statistics, file I/O
- `ai_insights.py`: AI analysis, recommendations

### Frontend
- `app/dashboard/page.tsx`: Main benchmark dashboard
- `app/compare/page.tsx`: Multi-benchmark comparison (3 views)
- `lib/api.ts`: Axios API client (extracts nested data)
- `lib/store.ts`: Zustand global state
- `lib/utils.ts`: Helpers including `getMetricValue()` for safe extraction
- `components/charts/`: 11 chart components

## Common Issues

### "Metrics showing 0.00 despite backend having data"
- **Cause**: Aggregate metrics come from `aggregate.json`, not JSONL
- **Fix**: `_compute_statistics` merges aggregate data (implemented)

### "Comparison charts empty for throughput/goodput"
- **Cause**: Aggregate metrics have p50/p90/p99 = 0
- **Fix**: `ComparisonChart` uses `mean` value (implemented)

### "React Query serving stale data"
- **Cause**: Default caching
- **Fix**: Use `refetchOnMount: true, staleTime: 0` (implemented)

### "Cannot read properties of undefined"
- **Cause**: API response structure mismatch
- **Fix**: Extract nested data (e.g., `response.data.benchmarks`)

## Data Structure

```
data/
├── index.json
└── benchmark_20251003_223507/
    ├── records.jsonl    # Per-request metrics (one JSON/line)
    └── aggregate.json   # Aggregate metrics (throughput, goodput)
```

### JSONL Format
```json
{
  "metadata": {"x_request_id": "req1", "timestamp_ns": 1000000000},
  "metrics": {
    "request_latency": {"value": 1000, "unit": "ms"},
    "ttft": {"value": 200, "unit": "ms"}
  }
}
```

### Aggregate JSON Format
```json
{
  "records": {
    "request_throughput": {"avg": 3.65, "min": 0, "max": 10},
    "goodput": {"avg": 0.57, "min": 0, "max": 1}
  }
}
```

## Patterns

### Adding New Metrics
1. Backend: Add to `_compute_statistics()` in `data_processor.py`
2. Frontend: Add to `availableMetrics` in comparison page
3. Determine aggregate (mean only) vs. record-level (percentiles)

### Adding Chart Components
1. Create in `frontend/components/charts/`
2. Include null safety guards
3. Accept `comparison: ComparisonResult` prop
4. Export from `components/charts/index.ts`

### Safe Metric Access
```typescript
// Use optional chaining + nullish coalescing
const value = stats?.metric_name?.mean ?? 0

// Or helper:
import { getMetricValue } from '@/lib/utils'
const value = getMetricValue(stats, 'primary_name', ['alias1'], 'mean')
```

## Tech Stack

- Python 3.10+, Node.js 18+
- Next.js 14.2.0, React 18.2.0
- FastAPI 0.109.0, Pandas 2.2.0, NumPy 1.26.3

## Running Benchmarks from Dashboard

### Backend: BenchmarkRunner
(`backend/benchmark_runner.py`) - Manages benchmark execution:
- Spawns `aiperf profile` subprocess with configuration
- Falls back to mock data generator if aiperf not installed
- Streams stdout/stderr via progress callbacks
- Broadcasts updates to all WebSocket clients
- Tracks active runs with status (starting/running/completed/failed/stopped)

### API Endpoints
- `POST /api/v3/benchmarks/run` - Start benchmark with config
- `GET /api/v3/benchmarks/runs/active` - List active runs
- `POST /api/v3/benchmarks/runs/{id}/stop` - Stop running benchmark

### Frontend: Run Page
(`app/run/page.tsx`) - Live benchmark execution interface:
- Configuration form (model, endpoint, concurrency, tokens)
- WebSocket connection for real-time progress
- Terminal-style log display with auto-scroll
- Status indicators (idle/starting/running/completed/failed/stopped)
- Start/stop controls

### WebSocket Flow
1. Page connects to `ws://localhost:8000/ws/realtime`
2. Backend broadcasts progress updates as benchmark runs
3. Frontend displays logs and updates status in real-time
4. On completion, benchmark appears in dashboard automatically
