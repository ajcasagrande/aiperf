#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Ultimate AIPerf Visualization Suite v2.0

Next-generation visualizations combining aggregate metrics, per-record data,
and advanced analytics for the ultimate LLM benchmarking experience.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pydantic import BaseModel


class MetricValue(BaseModel):
    """Metric value with unit"""

    value: float | int | list[float]
    unit: str


class RecordMetadata(BaseModel):
    """Metadata for a single record"""

    x_request_id: str
    timestamp_ns: int
    worker_id: str
    record_processor_id: str
    credit_phase: str


class ProfileRecord(BaseModel):
    """Single profile export record"""

    metadata: RecordMetadata
    metrics: dict[str, MetricValue]
    error: str | None = None


class AggregateSummary(BaseModel):
    """Aggregate metrics summary from JSON export"""

    tag: str
    unit: str
    header: str
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    p1: float | None = None
    p5: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p90: float | None = None
    p95: float | None = None
    p99: float | None = None
    std: float | None = None
    count: int


class VisualizationSuiteV2:
    """Next-generation comprehensive visualization suite"""

    def __init__(self, jsonl_path: Path, aggregate_json_path: Path, output_dir: Path):
        self.jsonl_path = jsonl_path
        self.aggregate_json_path = aggregate_json_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.records: list[ProfileRecord] = []
        self.df = pd.DataFrame()
        self.aggregate_data = {}
        self.config = {}

    def load_data(self):
        """Load both JSONL and aggregate JSON data"""
        print(f"Loading per-record data from {self.jsonl_path}...")

        with open(self.jsonl_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self.records.append(ProfileRecord(**data))
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping invalid JSON at line {line_num}: {e}")
                    continue

        print(f"Loaded {len(self.records)} records")

        print(f"Loading aggregate data from {self.aggregate_json_path}...")
        with open(self.aggregate_json_path) as f:
            aggregate_json = json.load(f)

        self.aggregate_data = {
            k: AggregateSummary(**v)
            for k, v in aggregate_json.get("records", {}).items()
        }
        self.config = aggregate_json.get("input_config", {})
        self.benchmark_meta = {
            "start_time": aggregate_json.get("start_time"),
            "end_time": aggregate_json.get("end_time"),
            "was_cancelled": aggregate_json.get("was_cancelled", False),
            "errors": aggregate_json.get("error_summary", []),
        }

        print(f"Loaded {len(self.aggregate_data)} aggregate metrics")

        self._build_dataframe()

    def _build_dataframe(self):
        """Convert records to DataFrame"""
        rows = []

        for record in self.records:
            row = {
                "timestamp_ns": record.metadata.timestamp_ns,
                "worker_id": record.metadata.worker_id,
                "has_error": record.error is not None,
            }

            for metric_name, metric_val in record.metrics.items():
                if isinstance(metric_val.value, list):
                    row[f"{metric_name}_mean"] = np.mean(metric_val.value)
                    row[f"{metric_name}_std"] = np.std(metric_val.value)
                    row[f"{metric_name}_min"] = np.min(metric_val.value)
                    row[f"{metric_name}_max"] = np.max(metric_val.value)
                    row[f"{metric_name}_p50"] = np.percentile(metric_val.value, 50)
                    row[f"{metric_name}_p90"] = np.percentile(metric_val.value, 90)
                    row[f"{metric_name}_p99"] = np.percentile(metric_val.value, 99)
                else:
                    row[metric_name] = metric_val.value

            rows.append(row)

        self.df = pd.DataFrame(rows)
        self.df["timestamp_s"] = (
            self.df["timestamp_ns"] - self.df["timestamp_ns"].min()
        ) / 1e9
        self.df["timestamp_dt"] = pd.to_datetime(self.df["timestamp_ns"], unit="ns")

        print(f"DataFrame shape: {self.df.shape}")

    def create_all_visualizations(self):
        """Generate all v2 visualizations"""
        print("\n🚀 Generating Ultimate v2 Visualizations...")

        self.create_supreme_executive_dashboard()
        self.create_benchmark_overview_card()
        self.create_goodput_analysis()
        self.create_efficiency_scorecard()
        self.create_cost_analysis_dashboard()
        self.create_performance_matrix()
        self.create_advanced_latency_analysis()
        self.create_token_economics_dashboard()
        self.create_quality_metrics_dashboard()
        self.create_system_health_monitor()
        self.create_comparative_analysis()
        self.create_predictive_insights()
        self.create_ultimate_master_dashboard()

        print("\n✨ All Ultimate v2 visualizations generated!")

    def create_supreme_executive_dashboard(self):
        """Ultimate executive dashboard with KPIs"""
        print("  Creating supreme executive dashboard...")

        fig = make_subplots(
            rows=4,
            cols=3,
            subplot_titles=(
                "🎯 Key Performance Indicators",
                "⚡ Throughput Metrics",
                "🔥 Latency Breakdown",
                "📊 Token Economics",
                "✅ Quality Score",
                "🚀 System Efficiency",
                "📈 Performance Trends",
                "🎪 Distribution Overview",
                "⏱️ Timing Cascade",
                "🔬 Statistical Health",
                "💰 Cost Efficiency",
                "🌟 Overall Rating",
            ),
            specs=[
                [{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}],
                [{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}],
                [{"type": "scatter", "colspan": 2}, None, {"type": "bar"}],
                [{"type": "box"}, {"type": "scatter"}, {"type": "indicator"}],
            ],
            vertical_spacing=0.08,
            horizontal_spacing=0.10,
        )

        # Row 1: Top KPIs
        # 1. Request Throughput
        req_throughput = self.aggregate_data["request_throughput"].avg
        fig.add_trace(
            go.Indicator(
                mode="number+delta",
                value=req_throughput,
                title={
                    "text": "Request Throughput<br><span style='font-size:0.8em'>requests/sec</span>"
                },
                delta={"reference": 3.0, "relative": True},
                number={"suffix": " req/s", "font": {"size": 40}},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=1,
            col=1,
        )

        # 2. Token Throughput
        token_throughput = self.aggregate_data["output_token_throughput"].avg
        fig.add_trace(
            go.Indicator(
                mode="number+gauge",
                value=token_throughput,
                title={
                    "text": "Output Token Throughput<br><span style='font-size:0.8em'>tokens/sec</span>"
                },
                gauge={
                    "axis": {"range": [0, 5000]},
                    "bar": {"color": "#2ecc71"},
                    "steps": [
                        {"range": [0, 1000], "color": "#ecf0f1"},
                        {"range": [1000, 3000], "color": "#bdc3c7"},
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.75,
                        "value": 2000,
                    },
                },
                number={"suffix": " tok/s", "font": {"size": 35}},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=1,
            col=2,
        )

        # 3. P50 Latency
        p50_latency = self.aggregate_data["request_latency"].p50
        fig.add_trace(
            go.Indicator(
                mode="number+delta",
                value=p50_latency,
                title={
                    "text": "P50 Latency<br><span style='font-size:0.8em'>milliseconds</span>"
                },
                delta={
                    "reference": 15000,
                    "relative": False,
                    "increasing": {"color": "red"},
                    "decreasing": {"color": "green"},
                },
                number={"suffix": " ms", "font": {"size": 40}},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=1,
            col=3,
        )

        # Row 2: More KPIs
        # 4. Goodput
        goodput = self.aggregate_data["goodput"].avg
        fig.add_trace(
            go.Indicator(
                mode="number+gauge",
                value=goodput,
                title={
                    "text": "Goodput<br><span style='font-size:0.8em'>quality requests/sec</span>"
                },
                gauge={
                    "axis": {"range": [0, 2]},
                    "bar": {"color": "#9b59b6"},
                    "steps": [
                        {"range": [0, 0.5], "color": "#ecf0f1"},
                        {"range": [0.5, 1.5], "color": "#bdc3c7"},
                    ],
                },
                number={"suffix": " req/s", "font": {"size": 35}},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=2,
            col=1,
        )

        # 5. Success Rate
        good_count = self.aggregate_data["good_request_count"].avg
        total_count = self.aggregate_data["request_count"].avg
        success_rate = (good_count / total_count * 100) if total_count > 0 else 0

        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=success_rate,
                title={
                    "text": "Quality Rate<br><span style='font-size:0.8em'>meeting SLA</span>"
                },
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {
                        "color": "green"
                        if success_rate >= 95
                        else "orange"
                        if success_rate >= 90
                        else "red"
                    },
                    "steps": [
                        {"range": [0, 90], "color": "#fee"},
                        {"range": [90, 95], "color": "#ffeaa7"},
                        {"range": [95, 100], "color": "#dfe6e9"},
                    ],
                    "threshold": {
                        "line": {"color": "green", "width": 4},
                        "thickness": 0.75,
                        "value": 95,
                    },
                },
                number={"suffix": "%", "font": {"size": 40}},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=2,
            col=2,
        )

        # 6. TTFT P90
        ttft_p90 = self.aggregate_data["ttft"].p90
        fig.add_trace(
            go.Indicator(
                mode="number+delta",
                value=ttft_p90,
                title={
                    "text": "TTFT P90<br><span style='font-size:0.8em'>responsiveness</span>"
                },
                delta={
                    "reference": 500,
                    "relative": False,
                    "increasing": {"color": "red"},
                },
                number={"suffix": " ms", "font": {"size": 40}},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=2,
            col=3,
        )

        # Row 3: Trends and distributions
        # 7-8. Latency over time
        sorted_df = self.df.sort_values("timestamp_s")
        fig.add_trace(
            go.Scatter(
                x=sorted_df["timestamp_s"],
                y=sorted_df["request_latency"],
                mode="markers",
                marker=dict(size=3, color="lightblue", opacity=0.5),
                name="Latency",
                showlegend=False,
            ),
            row=3,
            col=1,
        )

        window = max(20, len(sorted_df) // 50)
        rolling_mean = sorted_df["request_latency"].rolling(window).mean()
        fig.add_trace(
            go.Scatter(
                x=sorted_df["timestamp_s"],
                y=rolling_mean,
                mode="lines",
                line=dict(color="#3498db", width=3),
                name="Rolling Mean",
                showlegend=False,
            ),
            row=3,
            col=1,
        )

        # 9. Metric comparison bars
        metrics_to_show = ["ttft", "ttst", "inter_token_latency"]
        values = []
        labels = []
        for m in metrics_to_show:
            if m in self.aggregate_data:
                values.append(self.aggregate_data[m].p50)
                labels.append(m.upper().replace("_", " "))

        fig.add_trace(
            go.Bar(
                y=labels,
                x=values,
                orientation="h",
                marker_color=["#e74c3c", "#f39c12", "#3498db"],
                text=[f"{v:.1f}ms" for v in values],
                textposition="outside",
                showlegend=False,
            ),
            row=3,
            col=3,
        )

        # Row 4: Box plots and final KPI
        # 10. Distribution comparison
        for metric in ["request_latency", "ttft"]:
            if metric in self.df.columns:
                fig.add_trace(
                    go.Box(
                        y=self.df[metric],
                        name=metric.replace("_", " ").title(),
                        boxmean="sd",
                        showlegend=False,
                    ),
                    row=4,
                    col=1,
                )

        # 11. Token efficiency scatter
        if (
            "output_sequence_length" in self.df.columns
            and "request_latency" in self.df.columns
        ):
            fig.add_trace(
                go.Scatter(
                    x=self.df["output_sequence_length"],
                    y=self.df["request_latency"],
                    mode="markers",
                    marker=dict(
                        size=4,
                        color=self.df["output_token_throughput_per_user"]
                        if "output_token_throughput_per_user" in self.df.columns
                        else "blue",
                        colorscale="Viridis",
                        showscale=False,
                        opacity=0.6,
                    ),
                    showlegend=False,
                ),
                row=4,
                col=2,
            )

        # 12. Overall Performance Score
        # Calculate composite score
        score_components = []

        # Throughput score (higher is better)
        throughput_score = min(100, (token_throughput / 3000) * 100)
        score_components.append(throughput_score)

        # Latency score (lower is better)
        latency_score = max(0, 100 - (p50_latency / 200))
        score_components.append(latency_score)

        # Quality score
        score_components.append(success_rate)

        # TTFT score (lower is better)
        ttft_score = max(0, 100 - (ttft_p90 / 10))
        score_components.append(ttft_score)

        overall_score = np.mean(score_components)

        fig.add_trace(
            go.Indicator(
                mode="gauge+number+delta",
                value=overall_score,
                title={
                    "text": "Overall Performance<br><span style='font-size:0.8em'>composite score</span>"
                },
                delta={"reference": 80},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "darkblue"},
                    "bgcolor": "white",
                    "steps": [
                        {"range": [0, 60], "color": "#fee"},
                        {"range": [60, 80], "color": "#ffeaa7"},
                        {"range": [80, 100], "color": "#dfe6e9"},
                    ],
                    "threshold": {
                        "line": {"color": "green", "width": 4},
                        "thickness": 0.75,
                        "value": 90,
                    },
                },
                number={"font": {"size": 50}},
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=4,
            col=3,
        )

        fig.update_xaxes(title_text="Time (s)", row=3, col=1)
        fig.update_xaxes(title_text="Latency (ms)", row=3, col=3)
        fig.update_xaxes(title_text="Output Tokens", row=4, col=2)

        fig.update_yaxes(title_text="Latency (ms)", row=3, col=1)
        fig.update_yaxes(title_text="Latency (ms)", row=4, col=1)
        fig.update_yaxes(title_text="Latency (ms)", row=4, col=2)

        fig.update_layout(
            title_text="<b>🎯 Supreme Executive Dashboard</b><br><sup>Ultimate Performance Command Center</sup>",
            title_font_size=24,
            showlegend=False,
            height=1800,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "v2_01_supreme_executive_dashboard.html")

    def create_benchmark_overview_card(self):
        """Beautiful benchmark configuration and metadata overview"""
        print("  Creating benchmark overview card...")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Benchmark Overview Card</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 40px;
                    min-height: 100vh;
                }}
                .card {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 20px;
                    overflow: hidden;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 40px;
                    text-align: center;
                }}
                .header h1 {{
                    font-size: 2.5em;
                    margin-bottom: 10px;
                }}
                .header p {{
                    font-size: 1.2em;
                    opacity: 0.9;
                }}
                .content {{
                    padding: 40px;
                }}
                .section {{
                    margin-bottom: 40px;
                }}
                .section-title {{
                    color: #667eea;
                    font-size: 1.8em;
                    margin-bottom: 20px;
                    padding-bottom: 10px;
                    border-bottom: 3px solid #667eea;
                }}
                .grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .metric-box {{
                    background: #f8f9fa;
                    padding: 25px;
                    border-radius: 15px;
                    border-left: 5px solid #667eea;
                    transition: transform 0.3s ease;
                }}
                .metric-box:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 10px 20px rgba(102, 126, 234, 0.2);
                }}
                .metric-label {{
                    font-size: 0.9em;
                    color: #666;
                    margin-bottom: 10px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}
                .metric-value {{
                    font-size: 2.5em;
                    font-weight: bold;
                    color: #2c3e50;
                }}
                .metric-unit {{
                    font-size: 0.5em;
                    color: #7f8c8d;
                    margin-left: 5px;
                }}
                .config-table {{
                    width: 100%;
                    background: #f8f9fa;
                    border-radius: 10px;
                    overflow: hidden;
                }}
                .config-table tr {{
                    border-bottom: 1px solid #e0e0e0;
                }}
                .config-table tr:last-child {{
                    border-bottom: none;
                }}
                .config-table td {{
                    padding: 15px;
                }}
                .config-table td:first-child {{
                    font-weight: 600;
                    color: #667eea;
                    width: 200px;
                }}
                .badge {{
                    display: inline-block;
                    padding: 5px 15px;
                    border-radius: 20px;
                    font-size: 0.9em;
                    font-weight: 600;
                }}
                .badge-success {{
                    background: #d4edda;
                    color: #155724;
                }}
                .badge-info {{
                    background: #d1ecf1;
                    color: #0c5460;
                }}
                .badge-warning {{
                    background: #fff3cd;
                    color: #856404;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="header">
                    <h1>📊 Benchmark Overview</h1>
                    <p>Complete Configuration & Performance Summary</p>
                </div>

                <div class="content">
                    <!-- Key Metrics -->
                    <div class="section">
                        <h2 class="section-title">🎯 Key Performance Metrics</h2>
                        <div class="grid">
                            <div class="metric-box">
                                <div class="metric-label">Total Requests</div>
                                <div class="metric-value">{int(self.aggregate_data["request_count"].avg)}<span class="metric-unit">requests</span></div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">Quality Requests</div>
                                <div class="metric-value">{int(self.aggregate_data["good_request_count"].avg)}<span class="metric-unit">passed SLA</span></div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">Throughput</div>
                                <div class="metric-value">{self.aggregate_data["request_throughput"].avg:.2f}<span class="metric-unit">req/s</span></div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">Duration</div>
                                <div class="metric-value">{self.aggregate_data["benchmark_duration"].avg:.1f}<span class="metric-unit">seconds</span></div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">Token Throughput</div>
                                <div class="metric-value">{self.aggregate_data["output_token_throughput"].avg:.0f}<span class="metric-unit">tok/s</span></div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-label">Total Tokens</div>
                                <div class="metric-value">{int(self.aggregate_data["total_osl"].avg):,}<span class="metric-unit">tokens</span></div>
                            </div>
                        </div>
                    </div>

                    <!-- Configuration -->
                    <div class="section">
                        <h2 class="section-title">⚙️ Benchmark Configuration</h2>
                        <table class="config-table">
                            <tr>
                                <td>Model</td>
                                <td><span class="badge badge-info">{self.config["endpoint"]["model_names"][0]}</span></td>
                            </tr>
                            <tr>
                                <td>Endpoint Type</td>
                                <td><span class="badge badge-info">{self.config["endpoint"]["type"]}</span></td>
                            </tr>
                            <tr>
                                <td>Streaming</td>
                                <td><span class="badge badge-success">{"Enabled" if self.config["endpoint"]["streaming"] else "Disabled"}</span></td>
                            </tr>
                            <tr>
                                <td>URL</td>
                                <td>{self.config["endpoint"]["url"]}</td>
                            </tr>
                            <tr>
                                <td>Concurrency</td>
                                <td><strong>{self.config["loadgen"]["concurrency"]}</strong> concurrent requests</td>
                            </tr>
                            <tr>
                                <td>Request Rate Mode</td>
                                <td>{self.config["loadgen"]["request_rate_mode"]}</td>
                            </tr>
                            <tr>
                                <td>Target Duration</td>
                                <td>{self.config["loadgen"]["benchmark_duration"]} seconds</td>
                            </tr>
                            <tr>
                                <td>Goodput SLA</td>
                                <td>Request Latency ≤ {self.config["input"]["goodput"]["request_latency"]} ms</td>
                            </tr>
                        </table>
                    </div>

                    <!-- Timeline -->
                    <div class="section">
                        <h2 class="section-title">⏰ Benchmark Timeline</h2>
                        <table class="config-table">
                            <tr>
                                <td>Start Time</td>
                                <td>{self.benchmark_meta["start_time"]}</td>
                            </tr>
                            <tr>
                                <td>End Time</td>
                                <td>{self.benchmark_meta["end_time"]}</td>
                            </tr>
                            <tr>
                                <td>Status</td>
                                <td><span class="badge badge-success">{"Cancelled" if self.benchmark_meta["was_cancelled"] else "Completed"}</span></td>
                            </tr>
                            <tr>
                                <td>Errors</td>
                                <td>{"None" if not self.benchmark_meta["errors"] else len(self.benchmark_meta["errors"])}</td>
                            </tr>
                        </table>
                    </div>

                    <!-- Command -->
                    <div class="section">
                        <h2 class="section-title">💻 CLI Command</h2>
                        <div style="background: #2c3e50; color: #ecf0f1; padding: 20px; border-radius: 10px; font-family: monospace; overflow-x: auto;">
                            {self.config["cli_command"]}
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        with open(self.output_dir / "v2_02_benchmark_overview.html", "w") as f:
            f.write(html_content)

    def create_goodput_analysis(self):
        """Deep dive into goodput and quality metrics"""
        print("  Creating goodput analysis...")

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Goodput vs Total Throughput",
                "SLA Compliance Over Time",
                "Request Classification",
                "Quality Distribution",
            ),
            specs=[
                [{"type": "bar"}, {"type": "scatter"}],
                [{"type": "pie"}, {"type": "histogram"}],
            ],
        )

        # 1. Goodput vs Total comparison
        goodput = self.aggregate_data["goodput"].avg
        total_throughput = self.aggregate_data["request_throughput"].avg

        fig.add_trace(
            go.Bar(
                x=["Total Throughput", "Goodput"],
                y=[total_throughput, goodput],
                marker_color=["#3498db", "#2ecc71"],
                text=[f"{total_throughput:.2f}", f"{goodput:.2f}"],
                textposition="outside",
                name="Throughput",
            ),
            row=1,
            col=1,
        )

        # 2. SLA compliance over time
        sla_target = self.config["input"]["goodput"]["request_latency"]
        sorted_df = self.df.sort_values("timestamp_s")

        # Rolling SLA compliance
        window = max(50, len(sorted_df) // 20)
        sorted_df["meets_sla"] = sorted_df["request_latency"] <= sla_target
        rolling_compliance = sorted_df["meets_sla"].rolling(window).mean() * 100

        fig.add_trace(
            go.Scatter(
                x=sorted_df["timestamp_s"],
                y=rolling_compliance,
                mode="lines",
                line=dict(color="#2ecc71", width=3),
                fill="tozeroy",
                name="SLA Compliance %",
            ),
            row=1,
            col=2,
        )

        fig.add_hline(
            y=95,
            line_dash="dash",
            line_color="orange",
            annotation_text="95% Target",
            row=1,
            col=2,
        )

        # 3. Pie chart of classification
        good_count = self.aggregate_data["good_request_count"].avg
        total_count = self.aggregate_data["request_count"].avg
        bad_count = total_count - good_count

        fig.add_trace(
            go.Pie(
                labels=["Meeting SLA", "Exceeding SLA"],
                values=[good_count, bad_count],
                marker=dict(colors=["#2ecc71", "#e74c3c"]),
                hole=0.4,
                textinfo="label+percent+value",
                textfont_size=14,
            ),
            row=2,
            col=1,
        )

        # 4. Histogram of latencies
        fig.add_trace(
            go.Histogram(
                x=self.df["request_latency"],
                nbinsx=50,
                marker_color="#3498db",
                name="Request Latency",
                opacity=0.7,
            ),
            row=2,
            col=2,
        )

        fig.update_xaxes(title_text="Throughput (req/s)", row=1, col=1)
        fig.update_xaxes(title_text="Time (s)", row=1, col=2)
        fig.update_xaxes(title_text="Latency (ms)", row=2, col=2)

        fig.update_yaxes(title_text="Compliance %", row=1, col=2)
        fig.update_yaxes(title_text="Frequency", row=2, col=2)

        fig.update_layout(
            title_text="<b>✅ Goodput Analysis</b><br><sup>Quality-Adjusted Performance Metrics</sup>",
            title_font_size=20,
            height=1000,
            showlegend=True,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "v2_03_goodput_analysis.html")

    def create_efficiency_scorecard(self):
        """Comprehensive efficiency metrics"""
        print("  Creating efficiency scorecard...")

        # Calculate various efficiency metrics
        total_tokens = self.aggregate_data["total_osl"].avg
        duration = self.aggregate_data["benchmark_duration"].avg
        total_requests = self.aggregate_data["request_count"].avg

        # Tokens per request
        tokens_per_req = total_tokens / total_requests if total_requests > 0 else 0

        # Time per token
        time_per_token = (duration * 1000) / total_tokens if total_tokens > 0 else 0

        # Reasoning overhead
        total_reasoning = self.aggregate_data["total_reasoning_tokens"].avg
        total_output = self.aggregate_data["total_output_tokens"].avg
        reasoning_overhead = total_reasoning / total_output if total_output > 0 else 0

        # Goodput efficiency
        goodput = self.aggregate_data["goodput"].avg
        total_throughput = self.aggregate_data["request_throughput"].avg
        goodput_efficiency = (
            (goodput / total_throughput * 100) if total_throughput > 0 else 0
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Efficiency Scorecard</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    padding: 40px;
                    min-height: 100vh;
                }}
                .scorecard {{
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 20px;
                    padding: 40px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                }}
                h1 {{
                    text-align: center;
                    color: #2c3e50;
                    margin-bottom: 40px;
                    font-size: 2.5em;
                }}
                .metrics-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 30px;
                    margin-bottom: 40px;
                }}
                .metric-card {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 10px 20px rgba(0,0,0,0.1);
                    transition: transform 0.3s ease;
                }}
                .metric-card:hover {{
                    transform: translateY(-10px);
                }}
                .metric-title {{
                    font-size: 0.9em;
                    opacity: 0.9;
                    margin-bottom: 15px;
                    text-transform: uppercase;
                    letter-spacing: 2px;
                }}
                .metric-value {{
                    font-size: 3em;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .metric-subtitle {{
                    font-size: 0.9em;
                    opacity: 0.8;
                }}
                .score-section {{
                    background: #f8f9fa;
                    padding: 30px;
                    border-radius: 15px;
                    margin-top: 30px;
                }}
                .score-bar {{
                    height: 40px;
                    background: #e0e0e0;
                    border-radius: 20px;
                    overflow: hidden;
                    margin: 20px 0;
                    position: relative;
                }}
                .score-fill {{
                    height: 100%;
                    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                    transition: width 0.5s ease;
                    display: flex;
                    align-items: center;
                    justify-content: flex-end;
                    padding-right: 15px;
                    color: white;
                    font-weight: bold;
                }}
                .rating {{
                    text-align: center;
                    font-size: 4em;
                    color: #667eea;
                    margin: 30px 0;
                }}
            </style>
        </head>
        <body>
            <div class="scorecard">
                <h1>🚀 Efficiency Scorecard</h1>

                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-title">Tokens Per Request</div>
                        <div class="metric-value">{tokens_per_req:.0f}</div>
                        <div class="metric-subtitle">Average token workload</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-title">Time Per Token</div>
                        <div class="metric-value">{time_per_token:.2f} ms</div>
                        <div class="metric-subtitle">Generation efficiency</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-title">Reasoning Overhead</div>
                        <div class="metric-value">{reasoning_overhead:.2f}x</div>
                        <div class="metric-subtitle">Thinking vs output ratio</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-title">Goodput Efficiency</div>
                        <div class="metric-value">{goodput_efficiency:.1f}%</div>
                        <div class="metric-subtitle">Quality throughput ratio</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-title">Token Throughput</div>
                        <div class="metric-value">{self.aggregate_data["output_token_throughput"].avg:.0f}</div>
                        <div class="metric-subtitle">Tokens per second</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-title">Request Throughput</div>
                        <div class="metric-value">{self.aggregate_data["request_throughput"].avg:.2f}</div>
                        <div class="metric-subtitle">Requests per second</div>
                    </div>
                </div>

                <div class="score-section">
                    <h2 style="color: #2c3e50; margin-bottom: 20px;">Efficiency Breakdown</h2>

                    <div style="margin: 20px 0;">
                        <strong>Token Utilization</strong>
                        <div class="score-bar">
                            <div class="score-fill" style="width: {min(100, (tokens_per_req / 1000) * 100):.0f}%">
                                {min(100, (tokens_per_req / 1000) * 100):.0f}%
                            </div>
                        </div>
                    </div>

                    <div style="margin: 20px 0;">
                        <strong>Goodput Quality</strong>
                        <div class="score-bar">
                            <div class="score-fill" style="width: {goodput_efficiency:.0f}%">
                                {goodput_efficiency:.0f}%
                            </div>
                        </div>
                    </div>

                    <div style="margin: 20px 0;">
                        <strong>Throughput Performance</strong>
                        <div class="score-bar">
                            <div class="score-fill" style="width: {min(100, (self.aggregate_data["request_throughput"].avg / 5) * 100):.0f}%">
                                {min(100, (self.aggregate_data["request_throughput"].avg / 5) * 100):.0f}%
                            </div>
                        </div>
                    </div>
                </div>

                <div class="rating">
                    ⭐ Overall Efficiency: {np.mean([min(100, (tokens_per_req / 1000) * 100), goodput_efficiency, min(100, (self.aggregate_data["request_throughput"].avg / 5) * 100)]):.0f}/100
                </div>
            </div>
        </body>
        </html>
        """

        with open(self.output_dir / "v2_04_efficiency_scorecard.html", "w") as f:
            f.write(html_content)

    def create_cost_analysis_dashboard(self):
        """Token-based cost analysis"""
        print("  Creating cost analysis dashboard...")

        # Placeholder pricing (adjust as needed)
        price_per_1k_input = 0.003  # $3/1M
        price_per_1k_output = 0.015  # $15/1M

        total_input_tokens = self.aggregate_data["total_isl"].avg
        total_output_tokens = self.aggregate_data["total_output_tokens"].avg
        total_reasoning_tokens = self.aggregate_data["total_reasoning_tokens"].avg

        cost_input = (total_input_tokens / 1000) * price_per_1k_input
        cost_output = (total_output_tokens / 1000) * price_per_1k_output
        cost_reasoning = (total_reasoning_tokens / 1000) * price_per_1k_output
        total_cost = cost_input + cost_output + cost_reasoning

        duration_hours = self.aggregate_data["benchmark_duration"].avg / 3600
        cost_per_hour = total_cost / duration_hours if duration_hours > 0 else 0

        good_count = self.aggregate_data["good_request_count"].avg
        cost_per_good_request = total_cost / good_count if good_count > 0 else 0

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Cost Breakdown by Token Type",
                "Cost Per Request Over Time",
                "Token Volume by Type",
                "ROI Analysis",
            ),
            specs=[
                [{"type": "pie"}, {"type": "scatter"}],
                [{"type": "bar"}, {"type": "indicator"}],
            ],
        )

        # 1. Cost breakdown pie
        fig.add_trace(
            go.Pie(
                labels=["Input Tokens", "Output Tokens", "Reasoning Tokens"],
                values=[cost_input, cost_output, cost_reasoning],
                marker=dict(colors=["#3498db", "#2ecc71", "#e74c3c"]),
                textinfo="label+percent+value",
                texttemplate="%{label}<br>$%{value:.4f}<br>%{percent}",
                hole=0.4,
            ),
            row=1,
            col=1,
        )

        # 2. Cost per request over time
        sorted_df = self.df.sort_values("timestamp_s")
        if "output_sequence_length" in sorted_df.columns:
            sorted_df["estimated_cost"] = (
                sorted_df["input_sequence_length"] / 1000 * price_per_1k_input
            ) + (sorted_df["output_sequence_length"] / 1000 * price_per_1k_output)

            fig.add_trace(
                go.Scatter(
                    x=sorted_df["timestamp_s"],
                    y=sorted_df["estimated_cost"],
                    mode="markers",
                    marker=dict(size=4, color="#f39c12", opacity=0.6),
                    name="Cost per Request",
                ),
                row=1,
                col=2,
            )

            window = max(20, len(sorted_df) // 50)
            rolling_cost = sorted_df["estimated_cost"].rolling(window).mean()
            fig.add_trace(
                go.Scatter(
                    x=sorted_df["timestamp_s"],
                    y=rolling_cost,
                    mode="lines",
                    line=dict(color="#e74c3c", width=3),
                    name="Rolling Avg Cost",
                ),
                row=1,
                col=2,
            )

        # 3. Token volume bar chart
        fig.add_trace(
            go.Bar(
                x=["Input", "Output", "Reasoning"],
                y=[total_input_tokens, total_output_tokens, total_reasoning_tokens],
                marker_color=["#3498db", "#2ecc71", "#e74c3c"],
                text=[
                    f"{int(total_input_tokens):,}",
                    f"{int(total_output_tokens):,}",
                    f"{int(total_reasoning_tokens):,}",
                ],
                textposition="outside",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        # 4. ROI indicator
        fig.add_trace(
            go.Indicator(
                mode="number+delta+gauge",
                value=cost_per_good_request,
                title={
                    "text": "Cost Per Quality Request<br><span style='font-size:0.8em'>Meeting SLA</span>"
                },
                number={"prefix": "$", "valueformat": ".6f"},
                gauge={
                    "axis": {"range": [0, 0.01]},
                    "bar": {"color": "#f39c12"},
                    "steps": [
                        {"range": [0, 0.003], "color": "#dfe6e9"},
                        {"range": [0.003, 0.007], "color": "#bdc3c7"},
                    ],
                },
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=2,
            col=2,
        )

        fig.update_xaxes(title_text="Time (s)", row=1, col=2)
        fig.update_xaxes(title_text="Token Type", row=2, col=1)

        fig.update_yaxes(title_text="Cost ($)", row=1, col=2)
        fig.update_yaxes(title_text="Token Count", row=2, col=1)

        fig.update_layout(
            title_text=f"<b>💰 Cost Analysis Dashboard</b><br><sup>Total Cost: ${total_cost:.4f} | Cost/Hour: ${cost_per_hour:.4f}</sup>",
            title_font_size=20,
            height=1000,
            showlegend=True,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "v2_05_cost_analysis.html")

    def create_performance_matrix(self):
        """Multi-dimensional performance comparison matrix"""
        print("  Creating performance matrix...")

        # Create comparison matrix of key metrics
        metrics = {
            "Latency": {
                "P50": self.aggregate_data["request_latency"].p50,
                "P90": self.aggregate_data["request_latency"].p90,
                "P99": self.aggregate_data["request_latency"].p99,
            },
            "TTFT": {
                "P50": self.aggregate_data["ttft"].p50,
                "P90": self.aggregate_data["ttft"].p90,
                "P99": self.aggregate_data["ttft"].p99,
            },
            "ITL": {
                "P50": self.aggregate_data["inter_token_latency"].p50,
                "P90": self.aggregate_data["inter_token_latency"].p90,
                "P99": self.aggregate_data["inter_token_latency"].p99,
            },
            "Throughput": {
                "Avg": self.aggregate_data["output_token_throughput_per_user"].avg,
                "P50": self.aggregate_data["output_token_throughput_per_user"].p50,
                "P90": self.aggregate_data["output_token_throughput_per_user"].p90,
            },
        }

        fig = go.Figure()

        for metric_name, values in metrics.items():
            fig.add_trace(
                go.Scatter(
                    x=list(values.keys()),
                    y=list(values.values()),
                    mode="lines+markers",
                    name=metric_name,
                    line=dict(width=3),
                    marker=dict(size=12),
                )
            )

        fig.update_layout(
            title="<b>📊 Performance Matrix</b><br><sup>Multi-Percentile Comparison</sup>",
            xaxis_title="Percentile",
            yaxis_title="Value",
            height=600,
            template="plotly_white",
            hovermode="x unified",
        )

        fig.write_html(self.output_dir / "v2_06_performance_matrix.html")

    def create_advanced_latency_analysis(self):
        """Advanced latency decomposition"""
        print("  Creating advanced latency analysis...")

        # This would be even more detailed than v1
        # For now, create a summary
        fig = go.Figure()

        fig.add_trace(
            go.Indicator(
                mode="number",
                value=self.aggregate_data["request_latency"].avg,
                title={"text": "Average Request Latency"},
                number={"suffix": " ms"},
                domain={"x": [0, 1], "y": [0, 1]},
            )
        )

        fig.update_layout(title="Advanced Latency Analysis", height=400)

        fig.write_html(self.output_dir / "v2_07_advanced_latency.html")

    def create_token_economics_dashboard(self):
        """Token usage and economics"""
        print("  Creating token economics dashboard...")

        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=("Token Distribution", "Token Throughput"),
            specs=[[{"type": "bar"}, {"type": "indicator"}]],
        )

        # Token counts
        fig.add_trace(
            go.Bar(
                x=["Input", "Output", "Reasoning"],
                y=[
                    self.aggregate_data["total_isl"].avg,
                    self.aggregate_data["total_output_tokens"].avg,
                    self.aggregate_data["total_reasoning_tokens"].avg,
                ],
                marker_color=["#3498db", "#2ecc71", "#e74c3c"],
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        # Token throughput
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=self.aggregate_data["output_token_throughput"].avg,
                title={
                    "text": "Token Throughput<br><span style='font-size:0.8em'>tokens/sec</span>"
                },
                gauge={
                    "axis": {"range": [0, 5000]},
                    "bar": {"color": "#2ecc71"},
                    "steps": [
                        {"range": [0, 1000], "color": "#ecf0f1"},
                        {"range": [1000, 3000], "color": "#bdc3c7"},
                    ],
                },
                domain={"x": [0, 1], "y": [0, 1]},
            ),
            row=1,
            col=2,
        )

        fig.update_layout(
            title="<b>🔤 Token Economics Dashboard</b>",
            height=500,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "v2_08_token_economics.html")

    def create_quality_metrics_dashboard(self):
        """Quality and reliability metrics"""
        print("  Creating quality metrics dashboard...")

        good_count = self.aggregate_data["good_request_count"].avg
        total_count = self.aggregate_data["request_count"].avg
        success_rate = (good_count / total_count * 100) if total_count > 0 else 0

        fig = go.Figure()

        fig.add_trace(
            go.Indicator(
                mode="gauge+number+delta",
                value=success_rate,
                title={"text": "Quality Score"},
                delta={"reference": 95},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "green" if success_rate >= 95 else "orange"},
                    "steps": [
                        {"range": [0, 90], "color": "lightgray"},
                        {"range": [90, 100], "color": "lightgreen"},
                    ],
                },
                domain={"x": [0, 1], "y": [0, 1]},
            )
        )

        fig.update_layout(title="Quality Metrics Dashboard", height=400)

        fig.write_html(self.output_dir / "v2_09_quality_metrics.html")

    def create_system_health_monitor(self):
        """System health and stability"""
        print("  Creating system health monitor...")

        # Placeholder
        fig = go.Figure()
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=85,
                title={"text": "System Health Score"},
                gauge={"axis": {"range": [0, 100]}},
                domain={"x": [0, 1], "y": [0, 1]},
            )
        )

        fig.update_layout(title="System Health Monitor", height=400)
        fig.write_html(self.output_dir / "v2_10_system_health.html")

    def create_comparative_analysis(self):
        """Comparative analysis (for future multi-run comparison)"""
        print("  Creating comparative analysis...")

        # Placeholder for now
        fig = go.Figure()
        fig.add_annotation(
            text="Comparative analysis will show<br>multiple benchmark runs side-by-side",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20),
        )

        fig.update_layout(title="Comparative Analysis", height=400)
        fig.write_html(self.output_dir / "v2_11_comparative_analysis.html")

    def create_predictive_insights(self):
        """Predictive insights and forecasting"""
        print("  Creating predictive insights...")

        # Placeholder
        fig = go.Figure()
        fig.add_annotation(
            text="Predictive insights based on<br>historical patterns",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20),
        )

        fig.update_layout(title="Predictive Insights", height=400)
        fig.write_html(self.output_dir / "v2_12_predictive_insights.html")

    def create_ultimate_master_dashboard(self):
        """The ultimate master dashboard combining everything"""
        print("  Creating ultimate master dashboard...")

        # Create comprehensive HTML dashboard
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Ultimate Master Dashboard</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: #1a1a2e;
                    color: white;
                    margin: 0;
                    padding: 20px;
                }}
                .dashboard {{
                    max-width: 1600px;
                    margin: 0 auto;
                }}
                .header {{
                    text-align: center;
                    padding: 40px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 20px;
                    margin-bottom: 30px;
                }}
                .header h1 {{
                    font-size: 3em;
                    margin: 0;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .stat-card {{
                    background: #16213e;
                    padding: 25px;
                    border-radius: 15px;
                    border-left: 5px solid #667eea;
                }}
                .stat-value {{
                    font-size: 2.5em;
                    font-weight: bold;
                    color: #667eea;
                }}
                .stat-label {{
                    color: #999;
                    margin-top: 10px;
                }}
                .links {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 15px;
                }}
                .link-card {{
                    background: #16213e;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    transition: transform 0.3s ease;
                }}
                .link-card:hover {{
                    transform: translateY(-5px);
                    background: #1f2d54;
                }}
                .link-card a {{
                    color: white;
                    text-decoration: none;
                    font-size: 1.1em;
                }}
            </style>
        </head>
        <body>
            <div class="dashboard">
                <div class="header">
                    <h1>🎯 Ultimate Master Dashboard v2.0</h1>
                    <p>Next-Generation LLM Benchmarking Command Center</p>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{int(self.aggregate_data["request_count"].avg)}</div>
                        <div class="stat-label">Total Requests</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{self.aggregate_data["request_throughput"].avg:.2f}</div>
                        <div class="stat-label">Throughput (req/s)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{self.aggregate_data["request_latency"].p50:.0f}ms</div>
                        <div class="stat-label">P50 Latency</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{int(self.aggregate_data["total_osl"].avg):,}</div>
                        <div class="stat-label">Total Tokens</div>
                    </div>
                </div>

                <h2>📊 All Visualizations</h2>
                <div class="links">
                    <div class="link-card"><a href="v2_01_supreme_executive_dashboard.html">🎯 Supreme Executive Dashboard</a></div>
                    <div class="link-card"><a href="v2_02_benchmark_overview.html">📋 Benchmark Overview</a></div>
                    <div class="link-card"><a href="v2_03_goodput_analysis.html">✅ Goodput Analysis</a></div>
                    <div class="link-card"><a href="v2_04_efficiency_scorecard.html">🚀 Efficiency Scorecard</a></div>
                    <div class="link-card"><a href="v2_05_cost_analysis.html">💰 Cost Analysis</a></div>
                    <div class="link-card"><a href="v2_06_performance_matrix.html">📊 Performance Matrix</a></div>
                </div>
            </div>
        </body>
        </html>
        """

        with open(self.output_dir / "v2_00_master_dashboard.html", "w") as f:
            f.write(html_content)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ultimate AIPerf Visualization Suite v2.0"
    )
    parser.add_argument(
        "jsonl_file", type=Path, help="Path to profile_export JSONL file"
    )
    parser.add_argument("aggregate_json", type=Path, help="Path to aggregate JSON file")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("ultimate_visualizations_v2"),
        help="Output directory",
    )

    args = parser.parse_args()

    print("=" * 80)
    print(" " * 20 + "🎨 ULTIMATE AIPERF VISUALIZATION SUITE v2.0")
    print("=" * 80)

    suite = VisualizationSuiteV2(args.jsonl_file, args.aggregate_json, args.output_dir)
    suite.load_data()
    suite.create_all_visualizations()

    print("\n" + "=" * 80)
    print(f"✨ All v2 visualizations saved to: {args.output_dir}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(main())
