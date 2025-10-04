# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Advanced Performance Visualization Dashboard
Analyzes LLM inference metrics with interactive charts using Plotly and Seaborn
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
from plotly.subplots import make_subplots

# Set style for static plots
sns.set_theme(style="darkgrid", palette="husl")
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["font.size"] = 10


def load_jsonl_data(filepath):
    """Load and parse JSONL performance data"""
    data = []
    with open(filepath) as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                data.append(record)
            except json.JSONDecodeError:
                continue
    return data


def extract_metrics(data):
    """Extract key metrics from records into a DataFrame"""
    records = []

    for idx, record in enumerate(data):
        metadata = record.get("metadata", {})
        metrics = record.get("metrics", {})
        error = record.get("error")

        # Extract scalar values from metric objects
        row = {
            "request_id": metadata.get("x_request_id", f"req_{idx}"),
            "timestamp": metadata.get("timestamp_ns", 0),
            "worker_id": metadata.get("worker_id", "unknown"),
            "has_error": 1 if error else 0,
            "error_type": error.get("type") if error else None,
        }

        # Extract metric values
        for key, value in metrics.items():
            if isinstance(value, dict) and "value" in value:
                row[key] = value["value"]
            elif isinstance(value, (int, float)):
                row[key] = value

        records.append(row)

    df = pd.DataFrame(records)

    # Convert timestamp to datetime
    if "timestamp" in df.columns:
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ns")
        df["request_number"] = range(1, len(df) + 1)

    return df


def create_latency_distribution(df):
    """Create interactive latency distribution visualization"""
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Request Latency Distribution",
            "Time to First Token (TTFT)",
            "Inter-Token Latency",
            "Throughput Distribution",
        ),
        specs=[
            [{"type": "histogram"}, {"type": "histogram"}],
            [{"type": "histogram"}, {"type": "histogram"}],
        ],
    )

    # Request Latency
    if "request_latency" in df.columns:
        fig.add_trace(
            go.Histogram(
                x=df[df["request_latency"] < 15000]["request_latency"],
                name="Request Latency",
                nbinsx=50,
                marker_color="#636EFA",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    # TTFT
    if "ttft" in df.columns:
        fig.add_trace(
            go.Histogram(
                x=df[df["ttft"] < 5000]["ttft"],
                name="TTFT",
                nbinsx=50,
                marker_color="#EF553B",
                showlegend=False,
            ),
            row=1,
            col=2,
        )

    # Inter-token latency
    if "inter_token_latency" in df.columns:
        fig.add_trace(
            go.Histogram(
                x=df["inter_token_latency"],
                name="Inter-Token Latency",
                nbinsx=50,
                marker_color="#00CC96",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    # Throughput
    if "output_token_throughput_per_user" in df.columns:
        fig.add_trace(
            go.Histogram(
                x=df["output_token_throughput_per_user"],
                name="Throughput",
                nbinsx=50,
                marker_color="#AB63FA",
                showlegend=False,
            ),
            row=2,
            col=2,
        )

    fig.update_xaxes(title_text="Latency (ms)", row=1, col=1)
    fig.update_xaxes(title_text="TTFT (ms)", row=1, col=2)
    fig.update_xaxes(title_text="Inter-Token Latency (ms)", row=2, col=1)
    fig.update_xaxes(title_text="Tokens/sec/user", row=2, col=2)

    fig.update_yaxes(title_text="Count", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=1, col=2)
    fig.update_yaxes(title_text="Count", row=2, col=1)
    fig.update_yaxes(title_text="Count", row=2, col=2)

    fig.update_layout(
        title_text="Performance Metrics Distribution",
        height=800,
        showlegend=False,
        template="plotly_dark",
    )

    return fig


def create_performance_over_time(df):
    """Create time-series performance visualization"""
    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=(
            "Request Latency Over Time",
            "Throughput Over Time",
            "Error Rate Over Time",
        ),
        shared_xaxes=True,
        vertical_spacing=0.1,
    )

    # Latency over time with moving average
    if "request_latency" in df.columns and "request_number" in df.columns:
        df_valid = df[df["request_latency"] < 15000].copy()
        window_size = min(10, len(df_valid) // 10)
        if window_size > 0:
            df_valid["latency_ma"] = (
                df_valid["request_latency"].rolling(window=window_size).mean()
            )

        fig.add_trace(
            go.Scatter(
                x=df_valid["request_number"],
                y=df_valid["request_latency"],
                mode="markers",
                name="Latency",
                marker=dict(size=4, opacity=0.5),
                showlegend=True,
            ),
            row=1,
            col=1,
        )

        if window_size > 0 and "latency_ma" in df_valid.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_valid["request_number"],
                    y=df_valid["latency_ma"],
                    mode="lines",
                    name="Moving Avg",
                    line=dict(color="red", width=2),
                ),
                row=1,
                col=1,
            )

    # Throughput over time
    if (
        "output_token_throughput_per_user" in df.columns
        and "request_number" in df.columns
    ):
        fig.add_trace(
            go.Scatter(
                x=df["request_number"],
                y=df["output_token_throughput_per_user"],
                mode="markers",
                name="Throughput",
                marker=dict(size=4, color="green", opacity=0.5),
                showlegend=True,
            ),
            row=2,
            col=1,
        )

    # Error rate (cumulative)
    if "has_error" in df.columns and "request_number" in df.columns:
        df["cumulative_error_rate"] = (
            df["has_error"].cumsum() / df["request_number"]
        ) * 100
        fig.add_trace(
            go.Scatter(
                x=df["request_number"],
                y=df["cumulative_error_rate"],
                mode="lines",
                name="Error Rate %",
                line=dict(color="red", width=2),
                fill="tozeroy",
                showlegend=True,
            ),
            row=3,
            col=1,
        )

    fig.update_xaxes(title_text="Request Number", row=3, col=1)
    fig.update_yaxes(title_text="Latency (ms)", row=1, col=1)
    fig.update_yaxes(title_text="Tokens/sec/user", row=2, col=1)
    fig.update_yaxes(title_text="Error Rate (%)", row=3, col=1)

    fig.update_layout(
        title_text="Performance Metrics Over Time", height=900, template="plotly_dark"
    )

    return fig


def create_percentile_chart(df):
    """Create percentile analysis for latency metrics"""
    metrics_to_analyze = {
        "request_latency": "Request Latency (ms)",
        "ttft": "Time to First Token (ms)",
        "inter_token_latency": "Inter-Token Latency (ms)",
    }

    percentiles = [50, 75, 90, 95, 99]
    results = []

    for metric, label in metrics_to_analyze.items():
        if metric in df.columns:
            valid_data = df[df[metric].notna()][metric]
            for p in percentiles:
                value = np.percentile(valid_data, p)
                results.append({"Metric": label, "Percentile": f"P{p}", "Value": value})

    if not results:
        return None

    results_df = pd.DataFrame(results)

    fig = px.bar(
        results_df,
        x="Percentile",
        y="Value",
        color="Metric",
        barmode="group",
        title="Latency Percentiles Analysis",
        labels={"Value": "Latency (ms)"},
        template="plotly_dark",
    )

    fig.update_layout(height=500)

    return fig


def create_correlation_heatmap(df):
    """Create correlation heatmap for key metrics"""
    numeric_cols = [
        "request_latency",
        "ttft",
        "inter_token_latency",
        "output_token_throughput_per_user",
        "input_sequence_length",
        "output_sequence_length",
        "reasoning_token_count",
    ]

    available_cols = [col for col in numeric_cols if col in df.columns]

    if len(available_cols) < 2:
        return None

    corr_df = df[available_cols].corr()

    fig = go.Figure(
        data=go.Heatmap(
            z=corr_df.values,
            x=corr_df.columns,
            y=corr_df.columns,
            colorscale="RdBu_r",
            zmid=0,
            text=np.round(corr_df.values, 2),
            texttemplate="%{text}",
            textfont={"size": 10},
            colorbar=dict(title="Correlation"),
        )
    )

    fig.update_layout(
        title="Metric Correlation Matrix", height=600, template="plotly_dark"
    )

    return fig


def create_token_analysis(df):
    """Analyze relationship between tokens and performance"""
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Latency vs Input Length", "Throughput vs Output Length"),
    )

    # Latency vs Input
    if "input_sequence_length" in df.columns and "request_latency" in df.columns:
        df_valid = df[(df["request_latency"] < 15000) & (df["request_latency"].notna())]
        fig.add_trace(
            go.Scatter(
                x=df_valid["input_sequence_length"],
                y=df_valid["request_latency"],
                mode="markers",
                name="Input vs Latency",
                marker=dict(
                    size=8,
                    color=df_valid["output_sequence_length"]
                    if "output_sequence_length" in df_valid
                    else None,
                    colorscale="Viridis",
                    showscale=True,
                    colorbar=dict(title="Output<br>Length", x=0.46),
                ),
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    # Throughput vs Output
    if (
        "output_sequence_length" in df.columns
        and "output_token_throughput_per_user" in df.columns
    ):
        df_valid = df[df["output_token_throughput_per_user"].notna()]
        fig.add_trace(
            go.Scatter(
                x=df_valid["output_sequence_length"],
                y=df_valid["output_token_throughput_per_user"],
                mode="markers",
                name="Output vs Throughput",
                marker=dict(
                    size=8,
                    color=df_valid["reasoning_token_count"]
                    if "reasoning_token_count" in df_valid
                    else None,
                    colorscale="Plasma",
                    showscale=True,
                    colorbar=dict(title="Reasoning<br>Tokens", x=1.02),
                ),
                showlegend=False,
            ),
            row=1,
            col=2,
        )

    fig.update_xaxes(title_text="Input Sequence Length", row=1, col=1)
    fig.update_xaxes(title_text="Output Sequence Length", row=1, col=2)
    fig.update_yaxes(title_text="Request Latency (ms)", row=1, col=1)
    fig.update_yaxes(title_text="Throughput (tokens/sec/user)", row=1, col=2)

    fig.update_layout(
        title_text="Token Length Impact on Performance",
        height=500,
        template="plotly_dark",
    )

    return fig


def create_summary_stats(df):
    """Generate summary statistics table"""
    stats = []

    metrics = {
        "request_latency": "Request Latency (ms)",
        "ttft": "TTFT (ms)",
        "inter_token_latency": "Inter-Token Latency (ms)",
        "output_token_throughput_per_user": "Throughput (tok/s/user)",
        "output_sequence_length": "Output Tokens",
        "reasoning_token_count": "Reasoning Tokens",
    }

    for metric, label in metrics.items():
        if metric in df.columns:
            data = df[df[metric].notna()][metric]
            if len(data) > 0:
                stats.append(
                    {
                        "Metric": label,
                        "Mean": f"{data.mean():.2f}",
                        "Median": f"{data.median():.2f}",
                        "Std Dev": f"{data.std():.2f}",
                        "Min": f"{data.min():.2f}",
                        "Max": f"{data.max():.2f}",
                        "P95": f"{np.percentile(data, 95):.2f}",
                        "P99": f"{np.percentile(data, 99):.2f}",
                    }
                )

    if not stats:
        return None

    stats_df = pd.DataFrame(stats)

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=list(stats_df.columns),
                    fill_color="#1f77b4",
                    align="left",
                    font=dict(color="white", size=12),
                ),
                cells=dict(
                    values=[stats_df[col] for col in stats_df.columns],
                    fill_color="#2c3e50",
                    align="left",
                    font=dict(color="white", size=11),
                ),
            )
        ]
    )

    fig.update_layout(
        title="Performance Summary Statistics", height=300, template="plotly_dark"
    )

    return fig


def create_error_analysis(df):
    """Analyze error patterns"""
    error_df = df[df["has_error"] == 1].copy()

    if len(error_df) == 0:
        print("No errors found in the data")
        return None

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Error Types Distribution", "Errors Over Time"),
        specs=[[{"type": "pie"}, {"type": "scatter"}]],
    )

    # Error types pie chart
    if "error_type" in error_df.columns:
        error_counts = error_df["error_type"].value_counts()
        fig.add_trace(
            go.Pie(
                labels=error_counts.index,
                values=error_counts.values,
                name="Error Types",
            ),
            row=1,
            col=1,
        )

    # Errors over time
    if "request_number" in error_df.columns:
        fig.add_trace(
            go.Scatter(
                x=error_df["request_number"],
                y=[1] * len(error_df),
                mode="markers",
                name="Error Occurrence",
                marker=dict(size=10, color="red", symbol="x"),
            ),
            row=1,
            col=2,
        )

    fig.update_layout(
        title_text=f"Error Analysis (Total: {len(error_df)} errors, {len(error_df) / len(df) * 100:.1f}%)",
        height=400,
        template="plotly_dark",
    )

    return fig


def compute_aggregate_throughput(df):
    """Compute aggregate system throughput over time"""
    df_sorted = df.sort_values("timestamp").copy()

    # Calculate time windows
    if len(df_sorted) > 0 and "timestamp" in df_sorted.columns:
        start_time = df_sorted["timestamp"].min()
        df_sorted["elapsed_seconds"] = (df_sorted["timestamp"] - start_time) / 1e9

        # Rolling window aggregate throughput
        window_size = max(10, len(df_sorted) // 50)

        def calc_window_throughput(window_df):
            if len(window_df) < 2:
                return 0

            time_span = (
                window_df["timestamp"].max() - window_df["timestamp"].min()
            ) / 1e9
            if time_span == 0:
                return 0

            total_tokens = (
                window_df["output_token_count"].sum()
                if "output_token_count" in window_df
                else 0
            )
            return total_tokens / time_span if time_span > 0 else 0

        df_sorted["aggregate_throughput"] = df_sorted.rolling(
            window=window_size, min_periods=1
        )["output_token_count"].apply(
            lambda x: x.sum() / window_size if len(x) > 0 else 0, raw=False
        )

    return df_sorted


def create_aggregate_throughput_chart(df):
    """Create aggregate system throughput visualization"""
    if "output_token_count" not in df.columns or "timestamp" not in df.columns:
        return None

    df_sorted = compute_aggregate_throughput(df)

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=(
            "Aggregate System Throughput (tokens/sec)",
            "Per-User vs System Throughput Comparison",
        ),
        vertical_spacing=0.15,
    )

    # Compute aggregate throughput over time windows
    window_size = 10  # seconds
    df_sorted["time_bin"] = (df_sorted["elapsed_seconds"] // window_size).astype(int)

    agg_stats = (
        df_sorted.groupby("time_bin")
        .agg({"output_token_count": "sum", "elapsed_seconds": ["min", "max"]})
        .reset_index()
    )

    if len(agg_stats) > 0:
        agg_stats["time_window_duration"] = (
            agg_stats[("elapsed_seconds", "max")]
            - agg_stats[("elapsed_seconds", "min")]
        )
        agg_stats["aggregate_tps"] = (
            agg_stats[("output_token_count", "sum")] / window_size
        )
        agg_stats["time_center"] = (
            agg_stats[("elapsed_seconds", "min")]
            + agg_stats[("elapsed_seconds", "max")]
        ) / 2

        # Plot aggregate throughput
        fig.add_trace(
            go.Scatter(
                x=agg_stats["time_center"],
                y=agg_stats["aggregate_tps"],
                mode="lines+markers",
                name="Aggregate Throughput",
                line=dict(color="#00CC96", width=3),
                marker=dict(size=8),
                fill="tozeroy",
                fillcolor="rgba(0, 204, 150, 0.3)",
            ),
            row=1,
            col=1,
        )

        # Add mean line
        mean_tps = agg_stats["aggregate_tps"].mean()
        fig.add_hline(
            y=mean_tps,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Mean: {mean_tps:.1f} tok/s",
            row=1,
            col=1,
        )

    # Comparison plot
    if (
        "output_token_throughput_per_user" in df_sorted.columns
        and "request_number" in df_sorted.columns
    ):
        # Calculate system throughput (sum of all concurrent requests)
        fig.add_trace(
            go.Scatter(
                x=df_sorted["request_number"],
                y=df_sorted["output_token_throughput_per_user"],
                mode="markers",
                name="Per-User Throughput",
                marker=dict(size=5, opacity=0.6, color="#636EFA"),
            ),
            row=2,
            col=1,
        )

        # Show aggregate as line
        if "aggregate_throughput" in df_sorted.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_sorted["request_number"],
                    y=df_sorted["aggregate_throughput"],
                    mode="lines",
                    name="Aggregate System Throughput",
                    line=dict(color="#00CC96", width=2),
                ),
                row=2,
                col=1,
            )

    fig.update_xaxes(title_text="Time (seconds)", row=1, col=1)
    fig.update_xaxes(title_text="Request Number", row=2, col=1)
    fig.update_yaxes(title_text="Tokens/Second", row=1, col=1)
    fig.update_yaxes(title_text="Throughput", row=2, col=1)

    fig.update_layout(
        title_text="Aggregate System Throughput Analysis",
        height=800,
        template="plotly_dark",
    )

    return fig


def main():
    """Main execution function"""
    import sys

    # Allow command line argument for data file
    if len(sys.argv) > 1:
        data_file = Path(sys.argv[1])
    else:
        data_file = (
            Path(__file__).parent
            / "artifacts"
            / "openai_gpt-oss-20b-openai-chat-concurrency100"
            / "profile_export_5min.jsonl"
        )

    print("Loading performance data...")
    print(f"File: {data_file}")
    data = load_jsonl_data(data_file)
    print(f"Loaded {len(data)} records")

    # Extract metrics into DataFrame
    print("Extracting metrics...")
    df = extract_metrics(data)
    print(f"Extracted {len(df)} records with {len(df.columns)} features")

    # Create output directory
    output_dir = Path(__file__).parent / "performance_visualizations"
    output_dir.mkdir(exist_ok=True)

    print("\nGenerating visualizations...")

    # Generate all visualizations
    visualizations = [
        ("summary_stats", create_summary_stats(df)),
        ("latency_distribution", create_latency_distribution(df)),
        ("performance_over_time", create_performance_over_time(df)),
        ("percentile_analysis", create_percentile_chart(df)),
        ("correlation_heatmap", create_correlation_heatmap(df)),
        ("token_analysis", create_token_analysis(df)),
        ("error_analysis", create_error_analysis(df)),
        ("aggregate_throughput", create_aggregate_throughput_chart(df)),
    ]

    # Save visualizations
    for name, fig in visualizations:
        if fig is not None:
            output_file = output_dir / f"{name}.html"
            fig.write_html(str(output_file))
            print(f"✓ Created: {output_file.name}")

    # Create combined dashboard
    print("\nCreating combined dashboard...")
    create_combined_dashboard(df, output_dir)

    print(f"\n✅ All visualizations saved to: {output_dir}")
    print("\n📊 Open 'dashboard.html' in your browser to view the complete analysis!")


def create_combined_dashboard(df, output_dir):
    """Create a single HTML page with all visualizations"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LLM Performance Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #1a1a1a;
                color: #ffffff;
            }
            .header {
                text-align: center;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px;
                margin-bottom: 30px;
            }
            h1 {
                margin: 0;
                font-size: 2.5em;
            }
            .subtitle {
                margin-top: 10px;
                font-size: 1.2em;
                opacity: 0.9;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .viz-section {
                margin-bottom: 40px;
                background-color: #2c2c2c;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }
            iframe {
                width: 100%;
                border: none;
                background-color: #1a1a1a;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 LLM Performance Analytics Dashboard</h1>
                <div class="subtitle">Real-time Performance Metrics & Analysis</div>
            </div>
    """

    sections = [
        ("summary_stats.html", "Performance Summary", "300px"),
        ("latency_distribution.html", "Latency Distribution Analysis", "850px"),
        ("performance_over_time.html", "Performance Trends Over Time", "950px"),
        (
            "aggregate_throughput.html",
            "Aggregate System Throughput (Computed)",
            "850px",
        ),
        ("token_analysis.html", "Token Impact on Performance", "550px"),
        ("percentile_analysis.html", "Percentile Analysis", "550px"),
        ("correlation_heatmap.html", "Metric Correlations", "650px"),
        ("error_analysis.html", "Error Analysis", "450px"),
    ]

    for filename, title, height in sections:
        filepath = output_dir / filename
        if filepath.exists():
            html_content += f"""
            <div class="viz-section">
                <h2>{title}</h2>
                <iframe src="{filename}" height="{height}"></iframe>
            </div>
            """

    html_content += """
        </div>
    </body>
    </html>
    """

    dashboard_file = output_dir / "dashboard.html"
    with open(dashboard_file, "w") as f:
        f.write(html_content)

    print("✓ Created: dashboard.html")


if __name__ == "__main__":
    main()
