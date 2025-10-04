#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Ultimate AIPerf Visualization Suite

Creates comprehensive, state-of-the-art visualizations for LLM benchmarking
based on AIPerf metrics definitions and profile export data.
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


class VisualizationSuite:
    """Comprehensive visualization suite for LLM benchmarking"""

    def __init__(self, jsonl_path: Path, output_dir: Path):
        self.jsonl_path = jsonl_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.records: list[ProfileRecord] = []
        self.df = pd.DataFrame()

    def load_data(self):
        """Load and parse JSONL data"""
        print(f"Loading data from {self.jsonl_path}...")

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
        self._build_dataframe()

    def _build_dataframe(self):
        """Convert records to DataFrame for analysis"""
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
        print(f"Columns: {list(self.df.columns)}")

    def create_all_visualizations(self):
        """Generate all visualizations"""
        print("\nGenerating visualizations...")

        self.create_executive_dashboard()
        self.create_latency_deep_dive()
        self.create_token_analysis()
        self.create_streaming_analysis()
        self.create_time_series_analysis()
        self.create_percentile_ladder()
        self.create_correlation_matrix()
        self.create_reasoning_overhead_analysis()
        self.create_workload_characterization()
        self.create_sla_compliance_dashboard()
        self.create_performance_heatmaps()
        self.create_statistical_summary()

        print("\n✓ All visualizations generated!")

    def create_executive_dashboard(self):
        """High-level executive dashboard"""
        print("  Creating executive dashboard...")

        fig = make_subplots(
            rows=3,
            cols=3,
            subplot_titles=(
                "Request Latency Distribution",
                "Time to First Token (TTFT)",
                "Output Token Throughput",
                "Inter Token Latency (ITL)",
                "Latency vs Token Count",
                "Throughput Over Time",
                "Key Metrics Summary",
                "Reasoning vs Output Tokens",
                "Performance Stability",
            ),
            specs=[
                [{"type": "box"}, {"type": "violin"}, {"type": "histogram"}],
                [{"type": "box"}, {"type": "scatter"}, {"type": "scatter"}],
                [{"type": "table"}, {"type": "bar"}, {"type": "scatter"}],
            ],
            vertical_spacing=0.12,
            horizontal_spacing=0.10,
        )

        # 1. Request Latency Box Plot
        fig.add_trace(
            go.Box(
                y=self.df["request_latency"],
                name="Request Latency",
                marker_color="#3498db",
                boxmean="sd",
            ),
            row=1,
            col=1,
        )

        # 2. TTFT Violin Plot
        if "ttft" in self.df.columns:
            fig.add_trace(
                go.Violin(
                    y=self.df["ttft"],
                    name="TTFT",
                    box_visible=True,
                    meanline_visible=True,
                    marker_color="#e74c3c",
                ),
                row=1,
                col=2,
            )

        # 3. Throughput Histogram
        if "output_token_throughput_per_user" in self.df.columns:
            fig.add_trace(
                go.Histogram(
                    x=self.df["output_token_throughput_per_user"],
                    name="Throughput",
                    nbinsx=50,
                    marker_color="#2ecc71",
                ),
                row=1,
                col=3,
            )

        # 4. ITL Box Plot
        if "inter_token_latency" in self.df.columns:
            fig.add_trace(
                go.Box(
                    y=self.df["inter_token_latency"],
                    name="ITL",
                    marker_color="#f39c12",
                    boxmean="sd",
                ),
                row=2,
                col=1,
            )

        # 5. Latency vs Token Count Scatter
        if "output_sequence_length" in self.df.columns:
            fig.add_trace(
                go.Scatter(
                    x=self.df["output_sequence_length"],
                    y=self.df["request_latency"],
                    mode="markers",
                    marker=dict(
                        size=4,
                        color=self.df["request_latency"],
                        colorscale="Viridis",
                        showscale=False,
                        opacity=0.6,
                    ),
                    name="Latency vs Tokens",
                ),
                row=2,
                col=2,
            )

        # 6. Throughput Over Time
        if "output_token_throughput_per_user" in self.df.columns:
            fig.add_trace(
                go.Scatter(
                    x=self.df["timestamp_s"],
                    y=self.df["output_token_throughput_per_user"],
                    mode="markers",
                    marker=dict(size=3, color="#9b59b6", opacity=0.5),
                    name="Throughput",
                ),
                row=2,
                col=3,
            )

        # 7. Key Metrics Table
        metrics_summary = []
        for metric in [
            "request_latency",
            "ttft",
            "inter_token_latency",
            "output_token_throughput_per_user",
        ]:
            if metric in self.df.columns:
                metrics_summary.append(
                    [
                        metric.replace("_", " ").title(),
                        f"{self.df[metric].mean():.2f}",
                        f"{self.df[metric].median():.2f}",
                        f"{self.df[metric].quantile(0.90):.2f}",
                        f"{self.df[metric].quantile(0.99):.2f}",
                    ]
                )

        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Metric", "Mean", "P50", "P90", "P99"],
                    fill_color="#34495e",
                    font=dict(color="white", size=11),
                ),
                cells=dict(
                    values=list(zip(*metrics_summary, strict=False)),
                    fill_color="#ecf0f1",
                    font=dict(size=10),
                ),
            ),
            row=3,
            col=1,
        )

        # 8. Reasoning vs Output Tokens
        if (
            "reasoning_token_count" in self.df.columns
            and "output_token_count" in self.df.columns
        ):
            fig.add_trace(
                go.Bar(
                    x=["Reasoning", "Output"],
                    y=[
                        self.df["reasoning_token_count"].sum(),
                        self.df["output_token_count"].sum(),
                    ],
                    marker_color=["#e67e22", "#1abc9c"],
                    name="Token Types",
                ),
                row=3,
                col=2,
            )

        # 9. Performance Stability (CV over time windows)
        if "request_latency" in self.df.columns:
            window_size = max(50, len(self.df) // 20)
            cv = (
                self.df["request_latency"].rolling(window=window_size).std()
                / self.df["request_latency"].rolling(window=window_size).mean()
            )
            fig.add_trace(
                go.Scatter(
                    x=self.df["timestamp_s"],
                    y=cv,
                    mode="lines",
                    name="Coeff of Variation",
                    line=dict(color="#c0392b", width=2),
                ),
                row=3,
                col=3,
            )

        fig.update_layout(
            title_text="AIPerf Executive Dashboard - Performance at a Glance",
            title_font_size=20,
            showlegend=False,
            height=1400,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "01_executive_dashboard.html")

    def create_latency_deep_dive(self):
        """Comprehensive latency analysis"""
        print("  Creating latency deep dive...")

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Latency Components Breakdown",
                "TTFT vs TTST vs ITL Distribution",
                "Request Latency CDF",
                "Latency Heatmap (Time vs Percentile)",
            ),
            specs=[
                [{"type": "bar"}, {"type": "box"}],
                [{"type": "scatter"}, {"type": "heatmap"}],
            ],
        )

        # 1. Latency Components Stacked Bar
        if all(
            k in self.df.columns
            for k in ["ttft", "inter_token_latency", "output_sequence_length"]
        ):
            sample_size = min(100, len(self.df))
            sample_df = self.df.sample(sample_size).sort_values("request_latency")

            generation_time = sample_df["inter_token_latency"] * (
                sample_df["output_sequence_length"] - 1
            )

            fig.add_trace(
                go.Bar(
                    x=sample_df.index,
                    y=sample_df["ttft"],
                    name="TTFT",
                    marker_color="#3498db",
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Bar(
                    x=sample_df.index,
                    y=generation_time,
                    name="Generation",
                    marker_color="#2ecc71",
                ),
                row=1,
                col=1,
            )

        # 2. Distribution Comparison
        latency_metrics = ["ttft", "ttst", "inter_token_latency"]
        for metric in latency_metrics:
            if metric in self.df.columns:
                fig.add_trace(
                    go.Box(y=self.df[metric], name=metric.upper(), boxmean="sd"),
                    row=1,
                    col=2,
                )

        # 3. CDF Plot
        sorted_latency = np.sort(self.df["request_latency"])
        cdf = np.arange(1, len(sorted_latency) + 1) / len(sorted_latency)

        fig.add_trace(
            go.Scatter(
                x=sorted_latency,
                y=cdf * 100,
                mode="lines",
                name="CDF",
                line=dict(width=3, color="#e74c3c"),
            ),
            row=2,
            col=1,
        )

        # Add percentile lines
        for p, color in [(50, "green"), (90, "orange"), (99, "red")]:
            val = np.percentile(self.df["request_latency"], p)
            fig.add_vline(
                x=val,
                line_dash="dash",
                line_color=color,
                annotation_text=f"P{p}",
                row=2,
                col=1,
            )

        # 4. Time vs Percentile Heatmap
        time_buckets = pd.cut(self.df["timestamp_s"], bins=20)
        percentiles = [50, 75, 90, 95, 99, 99.9]
        heatmap_data = []

        for bucket in time_buckets.cat.categories:
            mask = time_buckets == bucket
            bucket_data = self.df[mask]["request_latency"]
            if len(bucket_data) > 0:
                heatmap_data.append(
                    [np.percentile(bucket_data, p) for p in percentiles]
                )

        if heatmap_data:
            fig.add_trace(
                go.Heatmap(
                    z=np.array(heatmap_data).T,
                    x=list(range(len(heatmap_data))),
                    y=[f"P{p}" for p in percentiles],
                    colorscale="RdYlGn_r",
                    showscale=True,
                ),
                row=2,
                col=2,
            )

        fig.update_xaxes(title_text="Sample Index", row=1, col=1)
        fig.update_xaxes(title_text="Latency (ms)", row=2, col=1)
        fig.update_xaxes(title_text="Time Window", row=2, col=2)
        fig.update_yaxes(title_text="Latency (ms)", row=1, col=1)
        fig.update_yaxes(title_text="Latency (ms)", row=1, col=2)
        fig.update_yaxes(title_text="Cumulative %", row=2, col=1)

        fig.update_layout(
            title_text="Latency Deep Dive Analysis",
            height=1000,
            showlegend=True,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "02_latency_deep_dive.html")

    def create_token_analysis(self):
        """Token-based metrics analysis"""
        print("  Creating token analysis...")

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Token Distribution (Input/Output/Reasoning)",
                "Throughput vs Output Sequence Length",
                "Token Efficiency (Tokens per Second)",
                "Cumulative Token Generation Over Time",
            ),
        )

        # 1. Token Type Distribution
        if all(
            k in self.df.columns
            for k in [
                "input_sequence_length",
                "output_token_count",
                "reasoning_token_count",
            ]
        ):
            fig.add_trace(
                go.Histogram(
                    x=self.df["input_sequence_length"],
                    name="Input",
                    marker_color="#3498db",
                    opacity=0.7,
                    nbinsx=30,
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Histogram(
                    x=self.df["output_token_count"],
                    name="Output",
                    marker_color="#2ecc71",
                    opacity=0.7,
                    nbinsx=30,
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Histogram(
                    x=self.df["reasoning_token_count"],
                    name="Reasoning",
                    marker_color="#e74c3c",
                    opacity=0.7,
                    nbinsx=30,
                ),
                row=1,
                col=1,
            )

        # 2. Throughput vs Sequence Length
        if (
            "output_token_throughput_per_user" in self.df.columns
            and "output_sequence_length" in self.df.columns
        ):
            fig.add_trace(
                go.Scatter(
                    x=self.df["output_sequence_length"],
                    y=self.df["output_token_throughput_per_user"],
                    mode="markers",
                    marker=dict(
                        size=5,
                        color=self.df["output_token_throughput_per_user"],
                        colorscale="Plasma",
                        showscale=True,
                        colorbar=dict(x=0.46, len=0.4),
                        opacity=0.6,
                    ),
                    name="Throughput",
                ),
                row=1,
                col=2,
            )

            # Add trend line
            z = np.polyfit(
                self.df["output_sequence_length"],
                self.df["output_token_throughput_per_user"],
                2,
            )
            p = np.poly1d(z)
            x_trend = np.linspace(
                self.df["output_sequence_length"].min(),
                self.df["output_sequence_length"].max(),
                100,
            )
            fig.add_trace(
                go.Scatter(
                    x=x_trend,
                    y=p(x_trend),
                    mode="lines",
                    name="Trend",
                    line=dict(color="red", width=3, dash="dash"),
                ),
                row=1,
                col=2,
            )

        # 3. Token Efficiency Box Plot
        if "output_token_throughput_per_user" in self.df.columns:
            # Bin by output length
            self.df["length_bin"] = pd.cut(self.df["output_sequence_length"], bins=5)
            for bin_val in self.df["length_bin"].cat.categories:
                mask = self.df["length_bin"] == bin_val
                fig.add_trace(
                    go.Box(
                        y=self.df[mask]["output_token_throughput_per_user"],
                        name=f"{bin_val.left:.0f}-{bin_val.right:.0f}",
                        boxmean="sd",
                    ),
                    row=2,
                    col=1,
                )

        # 4. Cumulative Tokens Over Time
        if "output_sequence_length" in self.df.columns:
            sorted_df = self.df.sort_values("timestamp_s")
            cumulative_tokens = sorted_df["output_sequence_length"].cumsum()

            fig.add_trace(
                go.Scatter(
                    x=sorted_df["timestamp_s"],
                    y=cumulative_tokens,
                    mode="lines",
                    fill="tozeroy",
                    name="Cumulative Tokens",
                    line=dict(color="#9b59b6", width=2),
                ),
                row=2,
                col=2,
            )

            # Add generation rate
            if len(sorted_df) > 10:
                window = max(10, len(sorted_df) // 50)
                rate = (
                    sorted_df["output_sequence_length"].rolling(window).sum()
                    / sorted_df["timestamp_s"].diff().rolling(window).sum()
                )

                fig.add_trace(
                    go.Scatter(
                        x=sorted_df["timestamp_s"],
                        y=rate,
                        mode="lines",
                        name="Rate (tokens/s)",
                        line=dict(color="#e67e22", width=2),
                        yaxis="y2",
                    ),
                    row=2,
                    col=2,
                )

        fig.update_xaxes(title_text="Token Count", row=1, col=1)
        fig.update_xaxes(title_text="Output Sequence Length", row=1, col=2)
        fig.update_xaxes(title_text="Output Length Bin", row=2, col=1)
        fig.update_xaxes(title_text="Time (s)", row=2, col=2)

        fig.update_yaxes(title_text="Frequency", row=1, col=1)
        fig.update_yaxes(title_text="Throughput (tok/s)", row=1, col=2)
        fig.update_yaxes(title_text="Throughput (tok/s)", row=2, col=1)
        fig.update_yaxes(title_text="Cumulative Tokens", row=2, col=2)

        fig.update_layout(
            title_text="Token Analysis Dashboard",
            height=1000,
            showlegend=True,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "03_token_analysis.html")

    def create_streaming_analysis(self):
        """Streaming behavior analysis"""
        print("  Creating streaming analysis...")

        # Collect all inter-chunk latencies
        all_icl = []
        for record in self.records:
            if "inter_chunk_latency" in record.metrics:
                icl_data = record.metrics["inter_chunk_latency"].value
                if isinstance(icl_data, list):
                    all_icl.extend(icl_data)

        if not all_icl:
            print("    ⚠ No inter-chunk latency data available")
            return

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Inter-Chunk Latency Distribution",
                "TTFT vs TTST Scatter",
                "Chunk Latency Pattern (First 200 chunks)",
                "Streaming Stability Analysis",
            ),
        )

        # 1. ICL Distribution
        fig.add_trace(
            go.Histogram(
                x=all_icl,
                nbinsx=100,
                marker_color="#3498db",
                name="Inter-Chunk Latency",
            ),
            row=1,
            col=1,
        )

        # Add statistical markers
        mean_icl = np.mean(all_icl)
        median_icl = np.median(all_icl)
        fig.add_vline(
            x=mean_icl,
            line_dash="dash",
            line_color="red",
            annotation_text="Mean",
            row=1,
            col=1,
        )
        fig.add_vline(
            x=median_icl,
            line_dash="dash",
            line_color="green",
            annotation_text="Median",
            row=1,
            col=1,
        )

        # 2. TTFT vs TTST
        if "ttft" in self.df.columns and "ttst" in self.df.columns:
            fig.add_trace(
                go.Scatter(
                    x=self.df["ttft"],
                    y=self.df["ttst"],
                    mode="markers",
                    marker=dict(
                        size=6,
                        color=self.df["request_latency"],
                        colorscale="Viridis",
                        showscale=True,
                        colorbar=dict(x=0.46, len=0.4),
                        opacity=0.6,
                    ),
                    name="TTFT vs TTST",
                ),
                row=1,
                col=2,
            )

            # Add diagonal reference line
            max_val = max(self.df["ttft"].max(), self.df["ttst"].max())
            fig.add_trace(
                go.Scatter(
                    x=[0, max_val],
                    y=[0, max_val],
                    mode="lines",
                    name="y=x",
                    line=dict(dash="dash", color="gray"),
                ),
                row=1,
                col=2,
            )

        # 3. Pattern Analysis (first request with many chunks)
        for record in self.records:
            if "inter_chunk_latency" in record.metrics:
                icl_data = record.metrics["inter_chunk_latency"].value
                if isinstance(icl_data, list) and len(icl_data) >= 50:
                    chunk_data = icl_data[:200]
                    fig.add_trace(
                        go.Scatter(
                            y=chunk_data,
                            mode="lines+markers",
                            marker=dict(size=4),
                            line=dict(width=1),
                            name="ICL Pattern",
                            opacity=0.7,
                        ),
                        row=2,
                        col=1,
                    )
                    break

        # 4. Streaming Stability (CV by request)
        if (
            "inter_chunk_latency_std" in self.df.columns
            and "inter_chunk_latency_mean" in self.df.columns
        ):
            cv = (
                self.df["inter_chunk_latency_std"] / self.df["inter_chunk_latency_mean"]
            )
            fig.add_trace(
                go.Histogram(
                    x=cv,
                    nbinsx=50,
                    marker_color="#e74c3c",
                    name="Coefficient of Variation",
                ),
                row=2,
                col=2,
            )

        fig.update_xaxes(title_text="Latency (ms)", row=1, col=1)
        fig.update_xaxes(title_text="TTFT (ms)", row=1, col=2)
        fig.update_xaxes(title_text="Chunk Index", row=2, col=1)
        fig.update_xaxes(title_text="Coefficient of Variation", row=2, col=2)

        fig.update_yaxes(title_text="Frequency", row=1, col=1)
        fig.update_yaxes(title_text="TTST (ms)", row=1, col=2)
        fig.update_yaxes(title_text="Latency (ms)", row=2, col=1)
        fig.update_yaxes(title_text="Frequency", row=2, col=2)

        fig.update_layout(
            title_text="Streaming Behavior Analysis",
            height=1000,
            showlegend=True,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "04_streaming_analysis.html")

    def create_time_series_analysis(self):
        """Performance over time analysis"""
        print("  Creating time series analysis...")

        sorted_df = self.df.sort_values("timestamp_s")

        fig = make_subplots(
            rows=3,
            cols=1,
            subplot_titles=(
                "Request Latency Over Time (with rolling statistics)",
                "Throughput and Token Generation Over Time",
                "System Load and Concurrency Indicators",
            ),
            vertical_spacing=0.12,
        )

        # 1. Latency Over Time with Rolling Stats
        window = max(20, len(sorted_df) // 100)

        fig.add_trace(
            go.Scatter(
                x=sorted_df["timestamp_s"],
                y=sorted_df["request_latency"],
                mode="markers",
                marker=dict(size=3, color="lightblue", opacity=0.5),
                name="Individual Requests",
            ),
            row=1,
            col=1,
        )

        rolling_mean = sorted_df["request_latency"].rolling(window).mean()
        rolling_p90 = sorted_df["request_latency"].rolling(window).quantile(0.9)
        rolling_p99 = sorted_df["request_latency"].rolling(window).quantile(0.99)

        fig.add_trace(
            go.Scatter(
                x=sorted_df["timestamp_s"],
                y=rolling_mean,
                mode="lines",
                name="Rolling Mean",
                line=dict(color="blue", width=3),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=sorted_df["timestamp_s"],
                y=rolling_p90,
                mode="lines",
                name="Rolling P90",
                line=dict(color="orange", width=2),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=sorted_df["timestamp_s"],
                y=rolling_p99,
                mode="lines",
                name="Rolling P99",
                line=dict(color="red", width=2, dash="dash"),
            ),
            row=1,
            col=1,
        )

        # 2. Throughput and Token Generation
        if "output_token_throughput_per_user" in sorted_df.columns:
            rolling_tput = (
                sorted_df["output_token_throughput_per_user"].rolling(window).mean()
            )
            fig.add_trace(
                go.Scatter(
                    x=sorted_df["timestamp_s"],
                    y=rolling_tput,
                    mode="lines",
                    name="Avg Throughput",
                    line=dict(color="green", width=3),
                ),
                row=2,
                col=1,
            )

        if "output_sequence_length" in sorted_df.columns:
            rolling_tokens = sorted_df["output_sequence_length"].rolling(window).mean()
            fig.add_trace(
                go.Scatter(
                    x=sorted_df["timestamp_s"],
                    y=rolling_tokens,
                    mode="lines",
                    name="Avg Output Length",
                    line=dict(color="purple", width=2),
                    yaxis="y2",
                ),
                row=2,
                col=1,
            )

        # 3. System Load Indicators
        # Requests per second in sliding window
        time_window = 5.0  # seconds
        rps = []
        timestamps = []
        for i in range(len(sorted_df)):
            current_time = sorted_df.iloc[i]["timestamp_s"]
            window_start = current_time - time_window
            count = (
                (sorted_df["timestamp_s"] >= window_start)
                & (sorted_df["timestamp_s"] <= current_time)
            ).sum()
            rps.append(count / time_window)
            timestamps.append(current_time)

        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=rps,
                mode="lines",
                name="Requests/sec",
                line=dict(color="#e74c3c", width=2),
                fill="tozeroy",
            ),
            row=3,
            col=1,
        )

        fig.update_xaxes(title_text="Time (s)", row=3, col=1)
        fig.update_yaxes(title_text="Latency (ms)", row=1, col=1)
        fig.update_yaxes(title_text="Throughput (tok/s)", row=2, col=1)
        fig.update_yaxes(
            title_text="Output Length (tokens)", row=2, col=1, secondary_y=True
        )
        fig.update_yaxes(title_text="Request Rate", row=3, col=1)

        fig.update_layout(
            title_text="Time Series Performance Analysis",
            height=1200,
            showlegend=True,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "05_time_series_analysis.html")

    def create_percentile_ladder(self):
        """Percentile ladder visualization"""
        print("  Creating percentile ladder...")

        metrics_to_analyze = [
            "request_latency",
            "ttft",
            "ttst",
            "inter_token_latency",
            "output_token_throughput_per_user",
        ]

        percentiles = [0, 10, 25, 50, 75, 90, 95, 99, 99.9, 100]

        fig = make_subplots(
            rows=len([m for m in metrics_to_analyze if m in self.df.columns]),
            cols=1,
            subplot_titles=[
                m.replace("_", " ").title()
                for m in metrics_to_analyze
                if m in self.df.columns
            ],
            vertical_spacing=0.08,
        )

        row = 1
        for metric in metrics_to_analyze:
            if metric not in self.df.columns:
                continue

            values = [np.percentile(self.df[metric], p) for p in percentiles]
            colors = ["green"] * 4 + ["yellow"] * 3 + ["orange"] * 2 + ["red"]

            fig.add_trace(
                go.Bar(
                    x=[f"P{p}" for p in percentiles],
                    y=values,
                    marker_color=colors,
                    text=[f"{v:.2f}" for v in values],
                    textposition="outside",
                    name=metric,
                ),
                row=row,
                col=1,
            )

            # Add horizontal lines for key percentiles
            for p, color in [(50, "blue"), (90, "orange"), (99, "red")]:
                val = np.percentile(self.df[metric], p)
                fig.add_hline(
                    y=val,
                    line_dash="dash",
                    line_color=color,
                    line_width=1,
                    row=row,
                    col=1,
                )

            row += 1

        fig.update_layout(
            title_text="Percentile Ladder - Distribution Analysis",
            height=300 * row,
            showlegend=False,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "06_percentile_ladder.html")

    def create_correlation_matrix(self):
        """Correlation analysis between metrics"""
        print("  Creating correlation matrix...")

        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        # Filter out timestamp and binary columns
        metric_cols = [
            c
            for c in numeric_cols
            if not c.startswith("timestamp") and c not in ["has_error", "worker_id"]
        ]

        if len(metric_cols) < 2:
            print("    ⚠ Not enough metrics for correlation analysis")
            return

        corr_data = self.df[metric_cols].corr()

        fig = go.Figure(
            data=go.Heatmap(
                z=corr_data.values,
                x=corr_data.columns,
                y=corr_data.columns,
                colorscale="RdBu",
                zmid=0,
                text=corr_data.values,
                texttemplate="%{text:.2f}",
                textfont={"size": 8},
                colorbar=dict(title="Correlation"),
            )
        )

        fig.update_layout(
            title_text="Metric Correlation Matrix",
            height=max(800, len(metric_cols) * 40),
            width=max(800, len(metric_cols) * 40),
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "07_correlation_matrix.html")

    def create_reasoning_overhead_analysis(self):
        """Analyze reasoning token overhead"""
        print("  Creating reasoning overhead analysis...")

        if (
            "reasoning_token_count" not in self.df.columns
            or "output_token_count" not in self.df.columns
        ):
            print("    ⚠ Reasoning metrics not available")
            return

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Reasoning vs Output Token Count",
                "Reasoning Overhead Ratio",
                "Latency Impact of Reasoning Tokens",
                "Reasoning Efficiency",
            ),
        )

        # 1. Scatter: Reasoning vs Output
        fig.add_trace(
            go.Scatter(
                x=self.df["output_token_count"],
                y=self.df["reasoning_token_count"],
                mode="markers",
                marker=dict(
                    size=6,
                    color=self.df["request_latency"],
                    colorscale="Viridis",
                    showscale=True,
                    colorbar=dict(x=1.15, len=0.4),
                    opacity=0.6,
                ),
                name="Reasoning vs Output",
            ),
            row=1,
            col=1,
        )

        # 2. Overhead Ratio Distribution
        self.df["reasoning_overhead_ratio"] = (
            self.df["reasoning_token_count"]
            / (self.df["output_token_count"] + 1)  # avoid div by zero
        )

        fig.add_trace(
            go.Histogram(
                x=self.df["reasoning_overhead_ratio"],
                nbinsx=50,
                marker_color="#e67e22",
                name="Overhead Ratio",
            ),
            row=1,
            col=2,
        )

        # 3. Latency Impact
        fig.add_trace(
            go.Scatter(
                x=self.df["reasoning_token_count"],
                y=self.df["request_latency"],
                mode="markers",
                marker=dict(size=5, color="#e74c3c", opacity=0.5),
                name="Latency Impact",
            ),
            row=2,
            col=1,
        )

        # Add trend line
        if len(self.df) > 10:
            z = np.polyfit(
                self.df["reasoning_token_count"], self.df["request_latency"], 1
            )
            p = np.poly1d(z)
            x_trend = np.linspace(
                self.df["reasoning_token_count"].min(),
                self.df["reasoning_token_count"].max(),
                100,
            )
            fig.add_trace(
                go.Scatter(
                    x=x_trend,
                    y=p(x_trend),
                    mode="lines",
                    name="Trend",
                    line=dict(color="blue", width=3, dash="dash"),
                ),
                row=2,
                col=1,
            )

        # 4. Efficiency: Output per reasoning token
        self.df["reasoning_efficiency"] = self.df["output_token_count"] / (
            self.df["reasoning_token_count"] + 1
        )

        fig.add_trace(
            go.Box(
                y=self.df["reasoning_efficiency"],
                marker_color="#2ecc71",
                name="Efficiency",
                boxmean="sd",
            ),
            row=2,
            col=2,
        )

        fig.update_xaxes(title_text="Output Tokens", row=1, col=1)
        fig.update_xaxes(title_text="Overhead Ratio", row=1, col=2)
        fig.update_xaxes(title_text="Reasoning Tokens", row=2, col=1)

        fig.update_yaxes(title_text="Reasoning Tokens", row=1, col=1)
        fig.update_yaxes(title_text="Frequency", row=1, col=2)
        fig.update_yaxes(title_text="Latency (ms)", row=2, col=1)
        fig.update_yaxes(title_text="Output/Reasoning", row=2, col=2)

        fig.update_layout(
            title_text="Reasoning Token Overhead Analysis",
            height=1000,
            showlegend=True,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "08_reasoning_overhead.html")

    def create_workload_characterization(self):
        """Characterize workload patterns"""
        print("  Creating workload characterization...")

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Request Size Distribution",
                "Output Length Clustering",
                "Workload Phases (K-Means)",
                "Request Arrival Pattern",
            ),
            specs=[
                [{"type": "histogram"}, {"type": "scatter"}],
                [{"type": "scatter"}, {"type": "scatter"}],
            ],
        )

        # 1. Request Size Distribution
        if "input_sequence_length" in self.df.columns:
            fig.add_trace(
                go.Histogram(
                    x=self.df["input_sequence_length"],
                    nbinsx=50,
                    marker_color="#3498db",
                    name="Input Length",
                ),
                row=1,
                col=1,
            )

        # 2. Output Length Clustering
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
                        size=6,
                        color=self.df["output_token_throughput_per_user"]
                        if "output_token_throughput_per_user" in self.df.columns
                        else "blue",
                        colorscale="Viridis",
                        showscale=True,
                        colorbar=dict(x=0.46, len=0.4),
                        opacity=0.6,
                    ),
                    name="Length vs Latency",
                ),
                row=1,
                col=2,
            )

        # 3. Workload Phases (simple binning by time)
        sorted_df = self.df.sort_values("timestamp_s")
        sorted_df["phase"] = pd.cut(sorted_df["timestamp_s"], bins=5, labels=False)

        for phase in sorted_df["phase"].unique():
            phase_data = sorted_df[sorted_df["phase"] == phase]
            fig.add_trace(
                go.Scatter(
                    x=phase_data["output_sequence_length"]
                    if "output_sequence_length" in phase_data.columns
                    else phase_data["request_latency"],
                    y=phase_data["request_latency"],
                    mode="markers",
                    marker=dict(size=5, opacity=0.6),
                    name=f"Phase {phase}",
                ),
                row=2,
                col=1,
            )

        # 4. Request Arrival Pattern
        sorted_df["inter_arrival"] = sorted_df["timestamp_s"].diff()

        fig.add_trace(
            go.Scatter(
                x=sorted_df["timestamp_s"],
                y=sorted_df["inter_arrival"],
                mode="markers",
                marker=dict(size=3, color="#e74c3c", opacity=0.5),
                name="Inter-arrival Time",
            ),
            row=2,
            col=2,
        )

        # Add moving average
        window = max(20, len(sorted_df) // 50)
        ma = sorted_df["inter_arrival"].rolling(window).mean()
        fig.add_trace(
            go.Scatter(
                x=sorted_df["timestamp_s"],
                y=ma,
                mode="lines",
                line=dict(color="blue", width=3),
                name="Moving Average",
            ),
            row=2,
            col=2,
        )

        fig.update_xaxes(title_text="Input Length (tokens)", row=1, col=1)
        fig.update_xaxes(title_text="Output Length (tokens)", row=1, col=2)
        fig.update_xaxes(title_text="Metric Value", row=2, col=1)
        fig.update_xaxes(title_text="Time (s)", row=2, col=2)

        fig.update_yaxes(title_text="Frequency", row=1, col=1)
        fig.update_yaxes(title_text="Latency (ms)", row=1, col=2)
        fig.update_yaxes(title_text="Latency (ms)", row=2, col=1)
        fig.update_yaxes(title_text="Inter-arrival (s)", row=2, col=2)

        fig.update_layout(
            title_text="Workload Characterization",
            height=1000,
            showlegend=True,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "09_workload_characterization.html")

    def create_sla_compliance_dashboard(self):
        """SLA compliance and quality of service"""
        print("  Creating SLA compliance dashboard...")

        # Define SLA targets
        sla_targets = {
            "ttft": 500,  # ms
            "request_latency": 10000,  # ms
            "inter_token_latency": 100,  # ms
        }

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "SLA Compliance Rates",
                "Latency Tail Behavior",
                "SLA Violation Timeline",
                "Performance Degradation Detection",
            ),
            specs=[
                [{"type": "bar"}, {"type": "box"}],
                [{"type": "scatter"}, {"type": "scatter"}],
            ],
        )

        # 1. SLA Compliance Rates
        compliance_rates = []
        metric_names = []

        for metric, target in sla_targets.items():
            if metric in self.df.columns:
                compliant = (self.df[metric] <= target).sum()
                rate = compliant / len(self.df) * 100
                compliance_rates.append(rate)
                metric_names.append(metric.replace("_", " ").title())

        colors = [
            "green" if r >= 95 else "orange" if r >= 90 else "red"
            for r in compliance_rates
        ]

        fig.add_trace(
            go.Bar(
                x=metric_names,
                y=compliance_rates,
                marker_color=colors,
                text=[f"{r:.1f}%" for r in compliance_rates],
                textposition="outside",
                name="SLA Compliance",
            ),
            row=1,
            col=1,
        )

        fig.add_hline(
            y=95,
            line_dash="dash",
            line_color="green",
            annotation_text="95% Target",
            row=1,
            col=1,
        )

        # 2. Tail Behavior
        tail_metrics = ["request_latency", "ttft", "inter_token_latency"]
        for metric in tail_metrics:
            if metric in self.df.columns:
                # Only show values above 90th percentile
                p90 = self.df[metric].quantile(0.90)
                tail_data = self.df[self.df[metric] > p90][metric]

                fig.add_trace(
                    go.Box(
                        y=tail_data, name=metric.replace("_", " ").title(), boxmean="sd"
                    ),
                    row=1,
                    col=2,
                )

        # 3. SLA Violation Timeline
        sorted_df = self.df.sort_values("timestamp_s")

        for metric, target in sla_targets.items():
            if metric in sorted_df.columns:
                violations = sorted_df[sorted_df[metric] > target]
                fig.add_trace(
                    go.Scatter(
                        x=violations["timestamp_s"],
                        y=violations[metric],
                        mode="markers",
                        marker=dict(size=8, symbol="x"),
                        name=f"{metric} violations",
                    ),
                    row=2,
                    col=1,
                )

                # Add SLA line
                fig.add_hline(
                    y=target,
                    line_dash="dash",
                    annotation_text=f"{metric} SLA",
                    row=2,
                    col=1,
                )

        # 4. Performance Degradation
        window = max(50, len(sorted_df) // 50)
        degradation_score = []

        for i in range(window, len(sorted_df)):
            window_data = sorted_df.iloc[i - window : i]["request_latency"]
            baseline = sorted_df.iloc[:window]["request_latency"].median()
            current_median = window_data.median()
            degradation = ((current_median - baseline) / baseline) * 100
            degradation_score.append(degradation)

        fig.add_trace(
            go.Scatter(
                x=sorted_df.iloc[window:]["timestamp_s"],
                y=degradation_score,
                mode="lines",
                line=dict(color="#e74c3c", width=2),
                fill="tozeroy",
                name="Degradation %",
            ),
            row=2,
            col=2,
        )

        fig.add_hline(y=0, line_dash="solid", line_color="black", row=2, col=2)
        fig.add_hline(
            y=20,
            line_dash="dash",
            line_color="red",
            annotation_text="20% Threshold",
            row=2,
            col=2,
        )

        fig.update_yaxes(title_text="Compliance %", row=1, col=1)
        fig.update_yaxes(title_text="Latency (ms)", row=1, col=2)
        fig.update_yaxes(title_text="Latency (ms)", row=2, col=1)
        fig.update_yaxes(title_text="Degradation %", row=2, col=2)

        fig.update_xaxes(title_text="Time (s)", row=2, col=1)
        fig.update_xaxes(title_text="Time (s)", row=2, col=2)

        fig.update_layout(
            title_text="SLA Compliance & Quality of Service Dashboard",
            height=1000,
            showlegend=True,
            template="plotly_white",
        )

        fig.write_html(self.output_dir / "10_sla_compliance.html")

    def create_performance_heatmaps(self):
        """Performance heatmaps"""
        print("  Creating performance heatmaps...")

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Latency Heatmap (Time x Worker)",
                "Throughput Heatmap (Time x Output Length)",
                "Token Type Distribution Over Time",
                "Performance Variance Heatmap",
            ),
            specs=[
                [{"type": "heatmap"}, {"type": "heatmap"}],
                [{"type": "heatmap"}, {"type": "heatmap"}],
            ],
        )

        # 1. Latency by Time and Worker
        time_bins = pd.cut(self.df["timestamp_s"], bins=20)
        workers = sorted(self.df["worker_id"].unique())[:20]  # Limit to 20 workers

        latency_matrix = np.zeros((len(workers), 20))
        for i, worker in enumerate(workers):
            for j, time_bin in enumerate(time_bins.cat.categories):
                mask = (self.df["worker_id"] == worker) & (time_bins == time_bin)
                if mask.sum() > 0:
                    latency_matrix[i, j] = self.df[mask]["request_latency"].mean()

        fig.add_trace(
            go.Heatmap(
                z=latency_matrix,
                x=[f"T{i}" for i in range(20)],
                y=[f"W{i}" for i in range(len(workers))],
                colorscale="RdYlGn_r",
                showscale=True,
                colorbar=dict(x=0.46, len=0.4),
            ),
            row=1,
            col=1,
        )

        # 2. Throughput by Time and Output Length
        if (
            "output_sequence_length" in self.df.columns
            and "output_token_throughput_per_user" in self.df.columns
        ):
            length_bins = pd.cut(self.df["output_sequence_length"], bins=15)

            throughput_matrix = np.zeros((15, 20))
            for i, length_bin in enumerate(length_bins.cat.categories):
                for j, time_bin in enumerate(time_bins.cat.categories):
                    mask = (length_bins == length_bin) & (time_bins == time_bin)
                    if mask.sum() > 0:
                        throughput_matrix[i, j] = self.df[mask][
                            "output_token_throughput_per_user"
                        ].mean()

            fig.add_trace(
                go.Heatmap(
                    z=throughput_matrix,
                    x=[f"T{i}" for i in range(20)],
                    y=[f"L{i}" for i in range(15)],
                    colorscale="Viridis",
                    showscale=True,
                    colorbar=dict(x=1.15, len=0.4),
                ),
                row=1,
                col=2,
            )

        # 3. Token Type Distribution Over Time
        if all(
            k in self.df.columns
            for k in ["output_token_count", "reasoning_token_count"]
        ):
            token_matrix = []
            for time_bin in time_bins.cat.categories:
                mask = time_bins == time_bin
                if mask.sum() > 0:
                    token_matrix.append(
                        [
                            self.df[mask]["output_token_count"].sum(),
                            self.df[mask]["reasoning_token_count"].sum(),
                        ]
                    )

            if token_matrix:
                fig.add_trace(
                    go.Heatmap(
                        z=np.array(token_matrix).T,
                        x=[f"T{i}" for i in range(len(token_matrix))],
                        y=["Output", "Reasoning"],
                        colorscale="Plasma",
                        showscale=True,
                        colorbar=dict(x=0.46, y=0.25, len=0.3),
                    ),
                    row=2,
                    col=1,
                )

        # 4. Variance Heatmap
        variance_metrics = ["request_latency", "ttft", "inter_token_latency"]
        variance_matrix = []

        for time_bin in time_bins.cat.categories:
            mask = time_bins == time_bin
            row_data = []
            for metric in variance_metrics:
                if metric in self.df.columns and mask.sum() > 0:
                    cv = self.df[mask][metric].std() / (
                        self.df[mask][metric].mean() + 1e-6
                    )
                    row_data.append(cv)
                else:
                    row_data.append(0)
            variance_matrix.append(row_data)

        if variance_matrix:
            fig.add_trace(
                go.Heatmap(
                    z=np.array(variance_matrix).T,
                    x=[f"T{i}" for i in range(len(variance_matrix))],
                    y=[
                        m.replace("_", " ").title()
                        for m in variance_metrics
                        if m in self.df.columns
                    ],
                    colorscale="RdYlGn_r",
                    showscale=True,
                    colorbar=dict(x=1.15, y=0.25, len=0.3),
                ),
                row=2,
                col=2,
            )

        fig.update_layout(
            title_text="Performance Heatmaps", height=1000, template="plotly_white"
        )

        fig.write_html(self.output_dir / "11_performance_heatmaps.html")

    def create_statistical_summary(self):
        """Comprehensive statistical summary"""
        print("  Creating statistical summary...")

        # Generate detailed statistics
        stats_dict = {}
        key_metrics = [
            "request_latency",
            "ttft",
            "ttst",
            "inter_token_latency",
            "output_token_throughput_per_user",
            "output_token_count",
            "reasoning_token_count",
            "output_sequence_length",
            "input_sequence_length",
        ]

        for metric in key_metrics:
            if metric not in self.df.columns:
                continue

            data = self.df[metric].dropna()
            if len(data) == 0:
                continue

            stats_dict[metric] = {
                "count": len(data),
                "mean": data.mean(),
                "std": data.std(),
                "min": data.min(),
                "p01": data.quantile(0.01),
                "p05": data.quantile(0.05),
                "p25": data.quantile(0.25),
                "p50": data.quantile(0.50),
                "p75": data.quantile(0.75),
                "p90": data.quantile(0.90),
                "p95": data.quantile(0.95),
                "p99": data.quantile(0.99),
                "p999": data.quantile(0.999),
                "max": data.max(),
                "cv": data.std() / (data.mean() + 1e-6),
            }

        # Create comprehensive table
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AIPerf Statistical Summary</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background: #f5f7fa; }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 30px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                th {{ background: #3498db; color: white; padding: 12px; text-align: left; font-weight: 600; }}
                td {{ padding: 10px; border-bottom: 1px solid #ecf0f1; }}
                tr:hover {{ background: #f8f9fa; }}
                .metric-name {{ font-weight: 600; color: #2c3e50; }}
                .good {{ color: #27ae60; font-weight: 600; }}
                .warning {{ color: #f39c12; font-weight: 600; }}
                .bad {{ color: #e74c3c; font-weight: 600; }}
                .summary-box {{ background: white; padding: 20px; margin: 20px 0; border-left: 4px solid #3498db; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            </style>
        </head>
        <body>
            <h1>🚀 AIPerf Statistical Summary Report</h1>
            <div class="summary-box">
                <h2>Benchmark Overview</h2>
                <p><strong>Total Requests:</strong> {total_requests}</p>
                <p><strong>Success Rate:</strong> {success_rate}%</p>
                <p><strong>Duration:</strong> {duration:.2f} seconds</p>
                <p><strong>Average Request Rate:</strong> {avg_rate:.2f} requests/second</p>
            </div>
        """

        html_content = html_template.format(
            total_requests=len(self.df),
            success_rate=((~self.df["has_error"]).sum() / len(self.df) * 100)
            if "has_error" in self.df.columns
            else 100,
            duration=(self.df["timestamp_ns"].max() - self.df["timestamp_ns"].min())
            / 1e9,
            avg_rate=len(self.df)
            / ((self.df["timestamp_ns"].max() - self.df["timestamp_ns"].min()) / 1e9),
        )

        html_content += "<h2>Detailed Metrics Statistics</h2>"

        for metric, stats in stats_dict.items():
            html_content += f"""
            <h3>{metric.replace("_", " ").title()}</h3>
            <table>
                <tr>
                    <th>Statistic</th>
                    <th>Value</th>
                    <th>Statistic</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td class="metric-name">Count</td><td>{stats["count"]}</td>
                    <td class="metric-name">Mean</td><td>{stats["mean"]:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-name">Std Dev</td><td>{stats["std"]:.2f}</td>
                    <td class="metric-name">CV</td><td>{stats["cv"]:.3f}</td>
                </tr>
                <tr>
                    <td class="metric-name">Min</td><td>{stats["min"]:.2f}</td>
                    <td class="metric-name">Max</td><td>{stats["max"]:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-name">P1</td><td>{stats["p01"]:.2f}</td>
                    <td class="metric-name">P5</td><td>{stats["p05"]:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-name">P25</td><td>{stats["p25"]:.2f}</td>
                    <td class="metric-name">P50 (Median)</td><td class="good">{stats["p50"]:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-name">P75</td><td>{stats["p75"]:.2f}</td>
                    <td class="metric-name">P90</td><td class="warning">{stats["p90"]:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-name">P95</td><td class="warning">{stats["p95"]:.2f}</td>
                    <td class="metric-name">P99</td><td class="bad">{stats["p99"]:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-name">P99.9</td><td class="bad">{stats["p999"]:.2f}</td>
                    <td></td><td></td>
                </tr>
            </table>
            """

        html_content += """
        </body>
        </html>
        """

        with open(self.output_dir / "12_statistical_summary.html", "w") as f:
            f.write(html_content)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ultimate AIPerf Visualization Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "jsonl_file", type=Path, help="Path to profile_export JSONL file"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("ultimate_visualizations"),
        help="Output directory for visualizations (default: ultimate_visualizations/)",
    )

    args = parser.parse_args()

    if not args.jsonl_file.exists():
        print(f"❌ Error: File not found: {args.jsonl_file}")
        return 1

    print("=" * 70)
    print(" " * 15 + "🎨 ULTIMATE AIPERF VISUALIZATION SUITE")
    print("=" * 70)

    suite = VisualizationSuite(args.jsonl_file, args.output_dir)
    suite.load_data()
    suite.create_all_visualizations()

    print("\n" + "=" * 70)
    print(f"✨ All visualizations saved to: {args.output_dir}")
    print("=" * 70)
    print("\nGenerated visualizations:")
    for html_file in sorted(args.output_dir.glob("*.html")):
        print(f"  • {html_file.name}")

    return 0


if __name__ == "__main__":
    exit(main())
