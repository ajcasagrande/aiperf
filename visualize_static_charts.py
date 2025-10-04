# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Publication-Quality Static Performance Visualizations
Creates high-resolution static charts using Matplotlib and Seaborn
"""

import json
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.gridspec import GridSpec

warnings.filterwarnings("ignore")

# Set publication-quality defaults
plt.style.use("seaborn-v0_8-darkgrid")
sns.set_context("paper", font_scale=1.3)
sns.set_palette("husl")

# High DPI for publication quality
DPI = 300
FIGSIZE_WIDE = (16, 6)
FIGSIZE_TALL = (12, 10)
FIGSIZE_SQUARE = (10, 10)
FIGSIZE_MEGA = (20, 12)


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

        row = {
            "request_id": metadata.get("x_request_id", f"req_{idx}"),
            "timestamp": metadata.get("timestamp_ns", 0),
            "worker_id": metadata.get("worker_id", "unknown"),
            "has_error": 1 if error else 0,
            "error_type": error.get("type") if error else None,
        }

        for key, value in metrics.items():
            if isinstance(value, dict) and "value" in value:
                row[key] = value["value"]
            elif isinstance(value, (int, float)):
                row[key] = value

        records.append(row)

    df = pd.DataFrame(records)

    if "timestamp" in df.columns:
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ns")
        df["request_number"] = range(1, len(df) + 1)

    return df


def create_latency_overview(df, output_dir):
    """Create comprehensive latency overview with violin plots"""
    fig = plt.figure(figsize=FIGSIZE_MEGA)
    gs = GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)

    # Color palette
    colors = sns.color_palette("Set2", 8)

    # 1. Request Latency Distribution (large histogram)
    ax1 = fig.add_subplot(gs[0, :2])
    if "request_latency" in df.columns:
        data = df[df["request_latency"] < 15000]["request_latency"]
        ax1.hist(data, bins=50, color=colors[0], alpha=0.7, edgecolor="black")
        ax1.axvline(
            data.mean(),
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {data.mean():.0f}ms",
        )
        ax1.axvline(
            data.median(),
            color="green",
            linestyle="--",
            linewidth=2,
            label=f"Median: {data.median():.0f}ms",
        )
        ax1.set_xlabel("Request Latency (ms)", fontsize=12, fontweight="bold")
        ax1.set_ylabel("Frequency", fontsize=12, fontweight="bold")
        ax1.set_title("Request Latency Distribution", fontsize=14, fontweight="bold")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

    # 2. Box plot comparison
    ax2 = fig.add_subplot(gs[0, 2])
    metrics_data = []
    labels = []
    if "request_latency" in df.columns:
        metrics_data.append(df[df["request_latency"] < 15000]["request_latency"] / 1000)
        labels.append("Latency\n(s)")
    if "ttft" in df.columns:
        metrics_data.append(df[df["ttft"] < 5000]["ttft"] / 1000)
        labels.append("TTFT\n(s)")

    if metrics_data:
        bp = ax2.boxplot(
            metrics_data, labels=labels, patch_artist=True, notch=True, showfliers=True
        )
        for patch, color in zip(bp["boxes"], colors, strict=False):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax2.set_ylabel("Time (seconds)", fontsize=11, fontweight="bold")
        ax2.set_title("Latency Comparison", fontsize=12, fontweight="bold")
        ax2.grid(True, alpha=0.3, axis="y")

    # 3. TTFT Distribution
    ax3 = fig.add_subplot(gs[1, 0])
    if "ttft" in df.columns:
        data = df[df["ttft"] < 5000]["ttft"]
        ax3.hist(data, bins=40, color=colors[1], alpha=0.7, edgecolor="black")
        ax3.axvline(data.mean(), color="red", linestyle="--", linewidth=2)
        ax3.set_xlabel("TTFT (ms)", fontsize=11, fontweight="bold")
        ax3.set_ylabel("Count", fontsize=11, fontweight="bold")
        ax3.set_title("Time to First Token", fontsize=12, fontweight="bold")
        ax3.grid(True, alpha=0.3)

    # 4. Inter-token Latency Distribution
    ax4 = fig.add_subplot(gs[1, 1])
    if "inter_token_latency" in df.columns:
        data = df["inter_token_latency"]
        ax4.hist(data, bins=40, color=colors[2], alpha=0.7, edgecolor="black")
        ax4.axvline(data.mean(), color="red", linestyle="--", linewidth=2)
        ax4.set_xlabel("Inter-Token Latency (ms)", fontsize=11, fontweight="bold")
        ax4.set_ylabel("Count", fontsize=11, fontweight="bold")
        ax4.set_title("Token Generation Speed", fontsize=12, fontweight="bold")
        ax4.grid(True, alpha=0.3)

    # 5. Throughput Distribution
    ax5 = fig.add_subplot(gs[1, 2])
    if "output_token_throughput_per_user" in df.columns:
        data = df["output_token_throughput_per_user"]
        ax5.hist(data, bins=40, color=colors[3], alpha=0.7, edgecolor="black")
        ax5.axvline(data.mean(), color="red", linestyle="--", linewidth=2)
        ax5.set_xlabel("Tokens/sec/user", fontsize=11, fontweight="bold")
        ax5.set_ylabel("Count", fontsize=11, fontweight="bold")
        ax5.set_title("Throughput Distribution", fontsize=12, fontweight="bold")
        ax5.grid(True, alpha=0.3)

    # 6. Violin plot for latency
    ax6 = fig.add_subplot(gs[2, :])
    violin_data = []
    violin_labels = []

    if "request_latency" in df.columns:
        violin_data.append(df[df["request_latency"] < 15000]["request_latency"])
        violin_labels.append("Request\nLatency")
    if "ttft" in df.columns:
        violin_data.append(df[df["ttft"] < 5000]["ttft"])
        violin_labels.append("TTFT")
    if "inter_token_latency" in df.columns:
        violin_data.append(df["inter_token_latency"] * 20)  # Scale for visibility
        violin_labels.append("Inter-Token\nLatency (×20)")

    if violin_data:
        parts = ax6.violinplot(
            violin_data,
            positions=range(len(violin_data)),
            showmeans=True,
            showmedians=True,
        )
        for pc, color in zip(parts["bodies"], colors, strict=False):
            pc.set_facecolor(color)
            pc.set_alpha(0.7)
        ax6.set_xticks(range(len(violin_labels)))
        ax6.set_xticklabels(violin_labels)
        ax6.set_ylabel("Latency (ms)", fontsize=12, fontweight="bold")
        ax6.set_title(
            "Latency Metrics Distribution (Violin Plot)", fontsize=14, fontweight="bold"
        )
        ax6.grid(True, alpha=0.3, axis="y")

    plt.suptitle(
        "🎯 LLM Performance Metrics Overview", fontsize=18, fontweight="bold", y=0.995
    )

    plt.savefig(output_dir / "latency_overview.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("✓ Created: latency_overview.png")


def create_performance_timeline(df, output_dir):
    """Create detailed performance timeline"""
    fig, axes = plt.subplots(4, 1, figsize=(16, 12), sharex=True)

    colors = sns.color_palette("husl", 8)

    # 1. Latency over time with moving average
    ax1 = axes[0]
    if "request_latency" in df.columns and "request_number" in df.columns:
        df_valid = df[df["request_latency"] < 15000].copy()
        window = min(10, len(df_valid) // 10)
        if window > 0:
            df_valid["ma"] = df_valid["request_latency"].rolling(window=window).mean()

        ax1.scatter(
            df_valid["request_number"],
            df_valid["request_latency"],
            alpha=0.3,
            s=30,
            color=colors[0],
            label="Individual Requests",
        )
        if window > 0 and "ma" in df_valid.columns:
            ax1.plot(
                df_valid["request_number"],
                df_valid["ma"],
                color="red",
                linewidth=2.5,
                label=f"Moving Avg (n={window})",
            )
        ax1.fill_between(
            df_valid["request_number"],
            df_valid["request_latency"].rolling(window=window).min(),
            df_valid["request_latency"].rolling(window=window).max(),
            alpha=0.2,
            color=colors[0],
        )
        ax1.set_ylabel("Latency (ms)", fontsize=11, fontweight="bold")
        ax1.set_title("Request Latency Timeline", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)

    # 2. Throughput over time
    ax2 = axes[1]
    if (
        "output_token_throughput_per_user" in df.columns
        and "request_number" in df.columns
    ):
        ax2.plot(
            df["request_number"],
            df["output_token_throughput_per_user"],
            marker="o",
            markersize=4,
            alpha=0.6,
            color=colors[2],
            linewidth=1,
        )
        ax2.axhline(
            df["output_token_throughput_per_user"].mean(),
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {df['output_token_throughput_per_user'].mean():.1f}",
        )
        ax2.set_ylabel("Tokens/sec/user", fontsize=11, fontweight="bold")
        ax2.set_title("Throughput Over Time", fontsize=12, fontweight="bold")
        ax2.legend(loc="upper right")
        ax2.grid(True, alpha=0.3)

    # 3. Token counts over time
    ax3 = axes[2]
    if "output_sequence_length" in df.columns and "reasoning_token_count" in df.columns:
        ax3.bar(
            df["request_number"],
            df["output_sequence_length"],
            alpha=0.6,
            color=colors[3],
            label="Output Tokens",
        )
        ax3.bar(
            df["request_number"],
            df["reasoning_token_count"],
            alpha=0.6,
            color=colors[4],
            label="Reasoning Tokens",
        )
        ax3.set_ylabel("Token Count", fontsize=11, fontweight="bold")
        ax3.set_title("Token Generation Pattern", fontsize=12, fontweight="bold")
        ax3.legend(loc="upper right")
        ax3.grid(True, alpha=0.3, axis="y")

    # 4. Error tracking
    ax4 = axes[3]
    if "has_error" in df.columns:
        # Cumulative error rate
        df["cum_errors"] = df["has_error"].cumsum()
        df["error_rate"] = (df["cum_errors"] / df["request_number"]) * 100

        ax4.fill_between(
            df["request_number"], 0, df["error_rate"], alpha=0.3, color="red"
        )
        ax4.plot(
            df["request_number"],
            df["error_rate"],
            color="darkred",
            linewidth=2,
            label="Cumulative Error Rate",
        )

        # Mark error points
        error_points = df[df["has_error"] == 1]
        ax4.scatter(
            error_points["request_number"],
            [df["error_rate"].max() * 1.05] * len(error_points),
            marker="x",
            s=100,
            color="red",
            alpha=0.7,
            label="Error Events",
        )

        ax4.set_xlabel("Request Number", fontsize=11, fontweight="bold")
        ax4.set_ylabel("Error Rate (%)", fontsize=11, fontweight="bold")
        ax4.set_title("Error Rate Timeline", fontsize=12, fontweight="bold")
        ax4.legend(loc="upper right")
        ax4.grid(True, alpha=0.3)

    plt.suptitle("📈 Performance Timeline Analysis", fontsize=16, fontweight="bold")
    plt.tight_layout()

    plt.savefig(output_dir / "performance_timeline.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("✓ Created: performance_timeline.png")


def create_percentile_analysis(df, output_dir):
    """Create comprehensive percentile analysis"""
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_WIDE)

    metrics = {
        "request_latency": "Request Latency (ms)",
        "ttft": "TTFT (ms)",
        "inter_token_latency": "Inter-Token Latency (ms)",
    }

    percentiles = [50, 75, 90, 95, 99]
    colors = sns.color_palette("rocket", len(metrics))

    # Left plot: Percentile comparison
    ax1 = axes[0]
    x_pos = np.arange(len(percentiles))
    width = 0.25

    for idx, (metric, label) in enumerate(metrics.items()):
        if metric in df.columns:
            values = [
                np.percentile(df[df[metric].notna()][metric], p) for p in percentiles
            ]
            ax1.bar(
                x_pos + idx * width,
                values,
                width,
                label=label,
                alpha=0.8,
                color=colors[idx],
            )

    ax1.set_xlabel("Percentile", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Latency (ms)", fontsize=12, fontweight="bold")
    ax1.set_title("Latency Percentiles", fontsize=13, fontweight="bold")
    ax1.set_xticks(x_pos + width)
    ax1.set_xticklabels([f"P{p}" for p in percentiles])
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis="y")

    # Right plot: Percentile ratios (tail latency amplification)
    ax2 = axes[1]
    for idx, (metric, label) in enumerate(metrics.items()):
        if metric in df.columns:
            data = df[df[metric].notna()][metric]
            p50 = np.percentile(data, 50)
            ratios = [np.percentile(data, p) / p50 for p in percentiles]
            ax2.plot(
                [f"P{p}" for p in percentiles],
                ratios,
                marker="o",
                markersize=8,
                linewidth=2.5,
                label=label,
                alpha=0.8,
            )

    ax2.axhline(
        y=2,
        color="orange",
        linestyle="--",
        linewidth=2,
        alpha=0.7,
        label="2x threshold",
    )
    ax2.axhline(
        y=3, color="red", linestyle="--", linewidth=2, alpha=0.7, label="3x threshold"
    )
    ax2.set_xlabel("Percentile", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Ratio to P50", fontsize=12, fontweight="bold")
    ax2.set_title("Tail Latency Amplification", fontsize=13, fontweight="bold")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.suptitle("🎯 Percentile Deep Dive", fontsize=16, fontweight="bold")
    plt.tight_layout()

    plt.savefig(output_dir / "percentile_analysis.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("✓ Created: percentile_analysis.png")


def create_correlation_matrix(df, output_dir):
    """Create beautiful correlation matrix with annotations"""
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
        return

    # Clean names for display
    name_map = {
        "request_latency": "Req Latency",
        "ttft": "TTFT",
        "inter_token_latency": "Inter-Token Lat",
        "output_token_throughput_per_user": "Throughput",
        "input_sequence_length": "Input Length",
        "output_sequence_length": "Output Length",
        "reasoning_token_count": "Reasoning Tokens",
    }

    corr_df = df[available_cols].corr()
    corr_df.index = [name_map.get(col, col) for col in corr_df.index]
    corr_df.columns = [name_map.get(col, col) for col in corr_df.columns]

    fig, ax = plt.subplots(figsize=FIGSIZE_SQUARE)

    # Create mask for upper triangle
    mask = np.triu(np.ones_like(corr_df, dtype=bool))

    # Create heatmap
    sns.heatmap(
        corr_df,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        center=0,
        square=True,
        linewidths=1,
        cbar_kws={"shrink": 0.8},
        vmin=-1,
        vmax=1,
        mask=mask,
        ax=ax,
    )

    ax.set_title(
        "🔥 Metric Correlation Heatmap", fontsize=16, fontweight="bold", pad=20
    )

    plt.tight_layout()
    plt.savefig(output_dir / "correlation_matrix.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("✓ Created: correlation_matrix.png")


def create_scatter_analysis(df, output_dir):
    """Create scatter plots for relationship analysis"""
    fig = plt.figure(figsize=FIGSIZE_MEGA)
    gs = GridSpec(2, 3, figure=fig, hspace=0.3, wspace=0.3)

    # 1. Input Length vs Latency
    ax1 = fig.add_subplot(gs[0, 0])
    if "input_sequence_length" in df.columns and "request_latency" in df.columns:
        df_valid = df[df["request_latency"] < 15000]
        scatter = ax1.scatter(
            df_valid["input_sequence_length"],
            df_valid["request_latency"],
            c=df_valid["output_sequence_length"]
            if "output_sequence_length" in df_valid
            else None,
            cmap="viridis",
            alpha=0.6,
            s=80,
            edgecolors="black",
            linewidth=0.5,
        )
        if "output_sequence_length" in df_valid:
            plt.colorbar(scatter, ax=ax1, label="Output Length")

        # Add trend line
        z = np.polyfit(
            df_valid["input_sequence_length"], df_valid["request_latency"], 1
        )
        p = np.poly1d(z)
        ax1.plot(
            df_valid["input_sequence_length"].sort_values(),
            p(df_valid["input_sequence_length"].sort_values()),
            "r--",
            linewidth=2,
            alpha=0.8,
            label="Trend",
        )

        ax1.set_xlabel("Input Sequence Length", fontweight="bold")
        ax1.set_ylabel("Request Latency (ms)", fontweight="bold")
        ax1.set_title("Input Length Impact", fontweight="bold")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

    # 2. Output Length vs Throughput
    ax2 = fig.add_subplot(gs[0, 1])
    if (
        "output_sequence_length" in df.columns
        and "output_token_throughput_per_user" in df.columns
    ):
        scatter = ax2.scatter(
            df["output_sequence_length"],
            df["output_token_throughput_per_user"],
            c=df["reasoning_token_count"] if "reasoning_token_count" in df else None,
            cmap="plasma",
            alpha=0.6,
            s=80,
            edgecolors="black",
            linewidth=0.5,
        )
        if "reasoning_token_count" in df:
            plt.colorbar(scatter, ax=ax2, label="Reasoning Tokens")

        ax2.set_xlabel("Output Sequence Length", fontweight="bold")
        ax2.set_ylabel("Throughput (tok/s/user)", fontweight="bold")
        ax2.set_title("Output Length vs Throughput", fontweight="bold")
        ax2.grid(True, alpha=0.3)

    # 3. TTFT vs Request Latency
    ax3 = fig.add_subplot(gs[0, 2])
    if "ttft" in df.columns and "request_latency" in df.columns:
        df_valid = df[(df["ttft"] < 5000) & (df["request_latency"] < 15000)]
        ax3.scatter(
            df_valid["ttft"],
            df_valid["request_latency"],
            alpha=0.6,
            s=80,
            c="coral",
            edgecolors="black",
            linewidth=0.5,
        )
        ax3.set_xlabel("TTFT (ms)", fontweight="bold")
        ax3.set_ylabel("Total Latency (ms)", fontweight="bold")
        ax3.set_title("TTFT vs Total Latency", fontweight="bold")
        ax3.grid(True, alpha=0.3)

    # 4. Reasoning Tokens vs Latency
    ax4 = fig.add_subplot(gs[1, 0])
    if "reasoning_token_count" in df.columns and "request_latency" in df.columns:
        df_valid = df[df["request_latency"] < 15000]
        ax4.scatter(
            df_valid["reasoning_token_count"],
            df_valid["request_latency"],
            alpha=0.6,
            s=80,
            c="purple",
            edgecolors="black",
            linewidth=0.5,
        )
        ax4.set_xlabel("Reasoning Token Count", fontweight="bold")
        ax4.set_ylabel("Request Latency (ms)", fontweight="bold")
        ax4.set_title("Reasoning Token Impact", fontweight="bold")
        ax4.grid(True, alpha=0.3)

    # 5. Inter-token Latency vs Throughput
    ax5 = fig.add_subplot(gs[1, 1])
    if (
        "inter_token_latency" in df.columns
        and "output_token_throughput_per_user" in df.columns
    ):
        ax5.scatter(
            df["inter_token_latency"],
            df["output_token_throughput_per_user"],
            alpha=0.6,
            s=80,
            c="teal",
            edgecolors="black",
            linewidth=0.5,
        )
        ax5.set_xlabel("Inter-Token Latency (ms)", fontweight="bold")
        ax5.set_ylabel("Throughput (tok/s/user)", fontweight="bold")
        ax5.set_title("Latency vs Throughput", fontweight="bold")
        ax5.grid(True, alpha=0.3)

    # 6. Total tokens vs Latency
    ax6 = fig.add_subplot(gs[1, 2])
    if "output_sequence_length" in df.columns and "request_latency" in df.columns:
        df_valid = df[df["request_latency"] < 15000].copy()
        if "input_sequence_length" in df_valid:
            df_valid["total_tokens"] = (
                df_valid["input_sequence_length"] + df_valid["output_sequence_length"]
            )
            ax6.scatter(
                df_valid["total_tokens"],
                df_valid["request_latency"],
                alpha=0.6,
                s=80,
                c="orange",
                edgecolors="black",
                linewidth=0.5,
            )
            ax6.set_xlabel("Total Tokens (Input + Output)", fontweight="bold")
            ax6.set_ylabel("Request Latency (ms)", fontweight="bold")
            ax6.set_title("Total Token Impact", fontweight="bold")
            ax6.grid(True, alpha=0.3)

    plt.suptitle("🔬 Performance Relationship Analysis", fontsize=18, fontweight="bold")

    plt.savefig(output_dir / "scatter_analysis.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("✓ Created: scatter_analysis.png")


def create_summary_dashboard(df, output_dir):
    """Create executive summary dashboard"""
    fig = plt.figure(figsize=(18, 10))
    gs = GridSpec(3, 4, figure=fig, hspace=0.4, wspace=0.4)

    # Define color scheme
    colors = sns.color_palette("Set2", 8)

    # Calculate key metrics
    total_requests = len(df)
    error_count = df["has_error"].sum() if "has_error" in df.columns else 0
    error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0

    # 1. KPI Cards (top row)
    kpis = []
    if "request_latency" in df.columns:
        kpis.append(
            (
                "Avg Latency",
                f"{df['request_latency'].mean():.0f} ms",
                f"P95: {np.percentile(df['request_latency'], 95):.0f} ms",
            )
        )
    if "ttft" in df.columns:
        kpis.append(
            (
                "Avg TTFT",
                f"{df['ttft'].mean():.0f} ms",
                f"P95: {np.percentile(df['ttft'], 95):.0f} ms",
            )
        )
    if "output_token_throughput_per_user" in df.columns:
        kpis.append(
            (
                "Throughput",
                f"{df['output_token_throughput_per_user'].mean():.1f} tok/s",
                f"σ: {df['output_token_throughput_per_user'].std():.1f}",
            )
        )
    kpis.append(
        ("Error Rate", f"{error_rate:.1f}%", f"{error_count}/{total_requests} requests")
    )

    for idx, (title, value, detail) in enumerate(kpis):
        ax = fig.add_subplot(gs[0, idx])
        ax.text(
            0.5,
            0.6,
            value,
            ha="center",
            va="center",
            fontsize=24,
            fontweight="bold",
            color=colors[idx],
        )
        ax.text(
            0.5, 0.3, title, ha="center", va="center", fontsize=14, fontweight="bold"
        )
        ax.text(
            0.5,
            0.1,
            detail,
            ha="center",
            va="center",
            fontsize=10,
            style="italic",
            alpha=0.7,
        )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.add_patch(
            plt.Rectangle(
                (0.05, 0.05), 0.9, 0.9, fill=False, edgecolor=colors[idx], linewidth=3
            )
        )

    # 2. Latency distribution (middle left)
    ax2 = fig.add_subplot(gs[1, :2])
    if "request_latency" in df.columns:
        data = df[df["request_latency"] < 15000]["request_latency"]
        ax2.hist(data, bins=30, color=colors[0], alpha=0.7, edgecolor="black")
        ax2.axvline(
            data.median(),
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Median: {data.median():.0f}ms",
        )
        ax2.set_xlabel("Request Latency (ms)", fontweight="bold")
        ax2.set_ylabel("Count", fontweight="bold")
        ax2.set_title("Latency Distribution", fontweight="bold", fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)

    # 3. Throughput over time (middle right)
    ax3 = fig.add_subplot(gs[1, 2:])
    if (
        "output_token_throughput_per_user" in df.columns
        and "request_number" in df.columns
    ):
        ax3.plot(
            df["request_number"],
            df["output_token_throughput_per_user"],
            color=colors[2],
            linewidth=1.5,
            alpha=0.7,
        )
        ax3.fill_between(
            df["request_number"],
            df["output_token_throughput_per_user"],
            alpha=0.3,
            color=colors[2],
        )
        ax3.set_xlabel("Request Number", fontweight="bold")
        ax3.set_ylabel("Tokens/sec/user", fontweight="bold")
        ax3.set_title("Throughput Timeline", fontweight="bold", fontsize=12)
        ax3.grid(True, alpha=0.3)

    # 4. Token analysis (bottom left)
    ax4 = fig.add_subplot(gs[2, :2])
    if "output_sequence_length" in df.columns and "reasoning_token_count" in df.columns:
        x = np.arange(min(len(df), 50))
        ax4.bar(
            x,
            df["output_sequence_length"][:50],
            alpha=0.7,
            color=colors[3],
            label="Output Tokens",
        )
        ax4.bar(
            x,
            df["reasoning_token_count"][:50],
            alpha=0.7,
            color=colors[4],
            label="Reasoning Tokens",
        )
        ax4.set_xlabel("Request Number (first 50)", fontweight="bold")
        ax4.set_ylabel("Token Count", fontweight="bold")
        ax4.set_title("Token Generation Pattern", fontweight="bold", fontsize=12)
        ax4.legend()
        ax4.grid(True, alpha=0.3, axis="y")

    # 5. Percentile bars (bottom right)
    ax5 = fig.add_subplot(gs[2, 2:])
    if "request_latency" in df.columns:
        percentiles = [50, 75, 90, 95, 99]
        values = [np.percentile(df["request_latency"], p) for p in percentiles]
        bars = ax5.bar(
            [f"P{p}" for p in percentiles],
            values,
            color=colors[5:],
            alpha=0.8,
            edgecolor="black",
        )

        # Add value labels on bars
        for bar, val in zip(bars, values, strict=False):
            height = bar.get_height()
            ax5.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{val:.0f}",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

        ax5.set_ylabel("Latency (ms)", fontweight="bold")
        ax5.set_title("Latency Percentiles", fontweight="bold", fontsize=12)
        ax5.grid(True, alpha=0.3, axis="y")

    plt.suptitle("📊 Executive Performance Summary", fontsize=20, fontweight="bold")

    plt.savefig(output_dir / "executive_summary.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("✓ Created: executive_summary.png")


def create_error_analysis(df, output_dir):
    """Create detailed error analysis charts"""
    error_df = df[df["has_error"] == 1].copy()

    if len(error_df) == 0:
        print("⚠ No errors to analyze")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Error types pie chart
    ax1 = axes[0, 0]
    if "error_type" in error_df.columns:
        error_counts = error_df["error_type"].value_counts()
        colors = sns.color_palette("Reds", len(error_counts))
        wedges, texts, autotexts = ax1.pie(
            error_counts.values,
            labels=error_counts.index,
            autopct="%1.1f%%",
            colors=colors,
            startangle=90,
        )
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontweight("bold")
        ax1.set_title("Error Types Distribution", fontweight="bold", fontsize=12)

    # 2. Errors over time
    ax2 = axes[0, 1]
    if "request_number" in error_df.columns:
        ax2.scatter(
            error_df["request_number"],
            [1] * len(error_df),
            marker="x",
            s=200,
            color="red",
            alpha=0.7,
            linewidths=2,
        )
        ax2.set_ylim(0.5, 1.5)
        ax2.set_xlabel("Request Number", fontweight="bold")
        ax2.set_title("Error Occurrence Timeline", fontweight="bold", fontsize=12)
        ax2.grid(True, alpha=0.3, axis="x")
        ax2.set_yticks([])

    # 3. Cumulative error rate
    ax3 = axes[1, 0]
    if "request_number" in df.columns and "has_error" in df.columns:
        df_sorted = df.sort_values("request_number")
        df_sorted["cum_errors"] = df_sorted["has_error"].cumsum()
        df_sorted["error_rate"] = (
            df_sorted["cum_errors"] / df_sorted["request_number"]
        ) * 100

        ax3.fill_between(
            df_sorted["request_number"],
            0,
            df_sorted["error_rate"],
            alpha=0.3,
            color="red",
        )
        ax3.plot(
            df_sorted["request_number"],
            df_sorted["error_rate"],
            color="darkred",
            linewidth=2.5,
        )
        ax3.set_xlabel("Request Number", fontweight="bold")
        ax3.set_ylabel("Error Rate (%)", fontweight="bold")
        ax3.set_title("Cumulative Error Rate", fontweight="bold", fontsize=12)
        ax3.grid(True, alpha=0.3)

    # 4. Error summary stats
    ax4 = axes[1, 1]
    ax4.axis("off")

    stats_text = f"""
    Error Analysis Summary
    ━━━━━━━━━━━━━━━━━━━━━━

    Total Errors: {len(error_df)}
    Error Rate: {len(error_df) / len(df) * 100:.1f}%
    Total Requests: {len(df)}

    First Error: Request #{error_df["request_number"].min() if "request_number" in error_df.columns else "N/A"}
    Last Error: Request #{error_df["request_number"].max() if "request_number" in error_df.columns else "N/A"}

    Error Distribution:
    {error_df["error_type"].value_counts().to_string() if "error_type" in error_df.columns else "N/A"}
    """

    ax4.text(
        0.1,
        0.5,
        stats_text,
        fontsize=11,
        family="monospace",
        verticalalignment="center",
    )

    plt.suptitle("⚠️ Error Analysis Dashboard", fontsize=16, fontweight="bold")
    plt.tight_layout()

    plt.savefig(output_dir / "error_analysis.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("✓ Created: error_analysis.png")


def create_aggregate_throughput_analysis(df, output_dir):
    """Create aggregate system throughput visualizations"""
    if "output_token_count" not in df.columns or "timestamp" not in df.columns:
        print("⚠ Skipping aggregate throughput - missing data")
        return

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    colors = sns.color_palette("husl", 8)

    # Sort by timestamp
    df_sorted = df.sort_values("timestamp").copy()
    start_time = df_sorted["timestamp"].min()
    df_sorted["elapsed_seconds"] = (df_sorted["timestamp"] - start_time) / 1e9

    # 1. Aggregate throughput over time (top left)
    ax1 = axes[0, 0]
    window_size = 10  # seconds
    df_sorted["time_bin"] = (df_sorted["elapsed_seconds"] // window_size).astype(int)

    agg_stats = (
        df_sorted.groupby("time_bin")
        .agg({"output_token_count": "sum", "elapsed_seconds": ["min", "max", "count"]})
        .reset_index()
    )

    agg_stats["aggregate_tps"] = agg_stats[("output_token_count", "sum")] / window_size
    agg_stats["time_center"] = (
        agg_stats[("elapsed_seconds", "min")] + agg_stats[("elapsed_seconds", "max")]
    ) / 2

    ax1.plot(
        agg_stats["time_center"],
        agg_stats["aggregate_tps"],
        marker="o",
        markersize=6,
        linewidth=2.5,
        color=colors[0],
        alpha=0.8,
    )
    ax1.fill_between(
        agg_stats["time_center"], agg_stats["aggregate_tps"], alpha=0.3, color=colors[0]
    )
    ax1.axhline(
        agg_stats["aggregate_tps"].mean(),
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Mean: {agg_stats['aggregate_tps'].mean():.1f} tok/s",
    )
    ax1.set_xlabel("Time (seconds)", fontweight="bold", fontsize=11)
    ax1.set_ylabel("Aggregate Throughput (tok/s)", fontweight="bold", fontsize=11)
    ax1.set_title(
        "Aggregate System Throughput Over Time", fontweight="bold", fontsize=12
    )
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Concurrent requests per time window (top right)
    ax2 = axes[0, 1]
    ax2.bar(
        agg_stats["time_bin"],
        agg_stats[("elapsed_seconds", "count")],
        color=colors[1],
        alpha=0.7,
        edgecolor="black",
    )
    ax2.set_xlabel("Time Window", fontweight="bold", fontsize=11)
    ax2.set_ylabel("Requests in Window", fontweight="bold", fontsize=11)
    ax2.set_title("Request Concurrency", fontweight="bold", fontsize=12)
    ax2.grid(True, alpha=0.3, axis="y")

    # 3. Cumulative tokens over time (bottom left)
    ax3 = axes[1, 0]
    df_sorted["cumulative_tokens"] = df_sorted["output_token_count"].cumsum()
    ax3.fill_between(
        df_sorted["elapsed_seconds"],
        df_sorted["cumulative_tokens"],
        alpha=0.5,
        color=colors[2],
    )
    ax3.plot(
        df_sorted["elapsed_seconds"],
        df_sorted["cumulative_tokens"],
        color=colors[2],
        linewidth=2,
    )
    ax3.set_xlabel("Time (seconds)", fontweight="bold", fontsize=11)
    ax3.set_ylabel("Cumulative Tokens Generated", fontweight="bold", fontsize=11)
    ax3.set_title("Total Token Generation Over Time", fontweight="bold", fontsize=12)
    ax3.grid(True, alpha=0.3)

    # Add summary stats
    total_tokens = df_sorted["output_token_count"].sum()
    total_time = df_sorted["elapsed_seconds"].max()
    overall_tps = total_tokens / total_time if total_time > 0 else 0

    ax3.text(
        0.98,
        0.98,
        f"Total: {total_tokens:,} tokens\nTime: {total_time:.1f}s\nAvg: {overall_tps:.1f} tok/s",
        transform=ax3.transAxes,
        ha="right",
        va="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        fontsize=10,
        fontweight="bold",
    )

    # 4. Per-user vs Aggregate comparison (bottom right)
    ax4 = axes[1, 1]
    if "output_token_throughput_per_user" in df_sorted.columns:
        # Rolling window for aggregate
        window = max(10, len(df_sorted) // 50)
        df_sorted["rolling_aggregate"] = (
            df_sorted["output_token_count"].rolling(window=window, min_periods=1).sum()
            / window
        )

        ax4.scatter(
            df_sorted.index,
            df_sorted["output_token_throughput_per_user"],
            alpha=0.4,
            s=30,
            color=colors[3],
            label="Per-User",
        )
        ax4.plot(
            df_sorted.index,
            df_sorted["rolling_aggregate"],
            color=colors[4],
            linewidth=2.5,
            label=f"Aggregate (window={window})",
            alpha=0.8,
        )
        ax4.set_xlabel("Request Number", fontweight="bold", fontsize=11)
        ax4.set_ylabel("Throughput (tok/s)", fontweight="bold", fontsize=11)
        ax4.set_title(
            "Per-User vs Aggregate Throughput", fontweight="bold", fontsize=12
        )
        ax4.legend()
        ax4.grid(True, alpha=0.3)

    plt.suptitle(
        "🚀 Aggregate System Throughput Analysis", fontsize=16, fontweight="bold"
    )
    plt.tight_layout()

    plt.savefig(output_dir / "aggregate_throughput.png", dpi=DPI, bbox_inches="tight")
    plt.close()
    print("✓ Created: aggregate_throughput.png")


def main():
    """Main execution"""
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

    print("🎨 Creating Publication-Quality Static Visualizations\n")
    print("Loading data...")
    print(f"File: {data_file}")
    data = load_jsonl_data(data_file)
    print(f"✓ Loaded {len(data)} records\n")

    # Extract metrics
    df = extract_metrics(data)

    # Create output directory
    output_dir = Path(__file__).parent / "performance_visualizations"
    output_dir.mkdir(exist_ok=True)

    print("Generating static visualizations...\n")

    # Generate all static visualizations
    create_summary_dashboard(df, output_dir)
    create_latency_overview(df, output_dir)
    create_performance_timeline(df, output_dir)
    create_percentile_analysis(df, output_dir)
    create_correlation_matrix(df, output_dir)
    create_scatter_analysis(df, output_dir)
    create_aggregate_throughput_analysis(df, output_dir)
    create_error_analysis(df, output_dir)

    print("\n✅ All static visualizations saved!")
    print(f"📁 Location: {output_dir}")
    print("🎨 High-resolution PNG files (300 DPI)")
    print("📄 Perfect for reports, papers, and presentations!")


if __name__ == "__main__":
    main()
