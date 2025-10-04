# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Create Beautiful Infographic-Style Summary
Perfect for social media, blog posts, and quick sharing
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import FancyBboxPatch

# High quality settings
DPI = 300
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]


def load_data(data_file=None):
    """Load and process data"""
    if data_file is None:
        data_file = (
            Path(__file__).parent
            / "artifacts"
            / "openai_gpt-oss-20b-openai-chat-concurrency100"
            / "profile_export_5min.jsonl"
        )

    data = []
    with open(data_file) as f:
        for line in f:
            try:
                data.append(json.loads(line.strip()))
            except:
                continue

    records = []
    for record in data:
        row = {}
        metadata = record.get("metadata", {})
        metrics = record.get("metrics", {})
        error = record.get("error")

        row["has_error"] = 1 if error else 0
        for key, value in metrics.items():
            if isinstance(value, dict) and "value" in value:
                row[key] = value["value"]

        records.append(row)

    return pd.DataFrame(records)


def create_infographic(df):
    """Create stunning one-page infographic"""
    fig = plt.figure(figsize=(16, 20), facecolor="#0f0f1e")

    # Color palette - modern and vibrant
    colors = {
        "primary": "#6366f1",  # Indigo
        "success": "#10b981",  # Green
        "warning": "#f59e0b",  # Amber
        "danger": "#ef4444",  # Red
        "info": "#06b6d4",  # Cyan
        "purple": "#8b5cf6",  # Purple
        "pink": "#ec4899",  # Pink
        "text": "#e5e7eb",  # Light gray
        "bg_dark": "#1f2937",  # Dark gray
    }

    # Calculate key metrics
    total_requests = len(df)
    errors = df["has_error"].sum()
    error_rate = errors / total_requests * 100

    successful = df[df["has_error"] == 0]

    metrics = {}
    if len(successful) > 0:
        for col in [
            "request_latency",
            "ttft",
            "inter_token_latency",
            "output_token_throughput_per_user",
            "output_sequence_length",
        ]:
            if col in successful.columns:
                data = successful[col]
                metrics[col] = {
                    "mean": data.mean(),
                    "median": data.median(),
                    "p95": np.percentile(data, 95),
                    "p99": np.percentile(data, 99),
                    "min": data.min(),
                    "max": data.max(),
                }

    # Title section
    fig.text(
        0.5,
        0.97,
        "LLM PERFORMANCE",
        ha="center",
        fontsize=48,
        fontweight="bold",
        color=colors["primary"],
    )
    fig.text(
        0.5,
        0.94,
        "ANALYTICS REPORT",
        ha="center",
        fontsize=36,
        fontweight="bold",
        color=colors["text"],
    )
    fig.text(0.5, 0.915, "━" * 50, ha="center", fontsize=14, color=colors["info"])
    fig.text(
        0.5,
        0.89,
        f"Analysis of {total_requests} inference requests",
        ha="center",
        fontsize=14,
        color=colors["text"],
        style="italic",
    )

    # KPI Cards Section
    y_start = 0.82
    kpi_height = 0.12
    kpi_data = []

    if "request_latency" in metrics:
        kpi_data.append(
            {
                "title": "AVG LATENCY",
                "value": f"{metrics['request_latency']['mean'] / 1000:.2f}s",
                "detail": f"P95: {metrics['request_latency']['p95'] / 1000:.2f}s",
                "color": colors["primary"],
            }
        )

    if "ttft" in metrics:
        kpi_data.append(
            {
                "title": "TIME TO FIRST TOKEN",
                "value": f"{metrics['ttft']['mean']:.0f}ms",
                "detail": f"P95: {metrics['ttft']['p95']:.0f}ms",
                "color": colors["info"],
            }
        )

    if "output_token_throughput_per_user" in metrics:
        kpi_data.append(
            {
                "title": "THROUGHPUT",
                "value": f"{metrics['output_token_throughput_per_user']['mean']:.1f}",
                "detail": "tokens/sec/user",
                "color": colors["success"],
            }
        )

    kpi_data.append(
        {
            "title": "ERROR RATE",
            "value": f"{error_rate:.1f}%",
            "detail": f"{errors}/{total_requests} requests",
            "color": colors["danger"] if error_rate > 5 else colors["success"],
        }
    )

    # Draw KPI cards
    for idx, kpi in enumerate(kpi_data):
        x = 0.1 + (idx * 0.22)

        # Card background
        fancy_box = FancyBboxPatch(
            (x, y_start - kpi_height),
            0.18,
            kpi_height,
            boxstyle="round,pad=0.01",
            facecolor=colors["bg_dark"],
            edgecolor=kpi["color"],
            linewidth=3,
            transform=fig.transFigure,
            clip_on=False,
        )
        fig.add_artist(fancy_box)

        # KPI content
        fig.text(
            x + 0.09,
            y_start - 0.03,
            kpi["title"],
            ha="center",
            fontsize=10,
            fontweight="bold",
            color=colors["text"],
        )
        fig.text(
            x + 0.09,
            y_start - 0.07,
            kpi["value"],
            ha="center",
            fontsize=22,
            fontweight="bold",
            color=kpi["color"],
        )
        fig.text(
            x + 0.09,
            y_start - 0.10,
            kpi["detail"],
            ha="center",
            fontsize=9,
            color=colors["text"],
            alpha=0.8,
        )

    # Create subplots for visualizations
    ax1 = plt.subplot2grid((20, 2), (5, 0), rowspan=4, colspan=1, fig=fig)
    ax2 = plt.subplot2grid((20, 2), (5, 1), rowspan=4, colspan=1, fig=fig)
    ax3 = plt.subplot2grid((20, 2), (10, 0), rowspan=4, colspan=1, fig=fig)
    ax4 = plt.subplot2grid((20, 2), (10, 1), rowspan=4, colspan=1, fig=fig)
    ax5 = plt.subplot2grid((20, 2), (15, 0), rowspan=4, colspan=2, fig=fig)

    # Set dark background for all subplots
    for ax in [ax1, ax2, ax3, ax4, ax5]:
        ax.set_facecolor("#1a1a2e")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color(colors["text"])
        ax.spines["left"].set_color(colors["text"])
        ax.tick_params(colors=colors["text"])
        ax.xaxis.label.set_color(colors["text"])
        ax.yaxis.label.set_color(colors["text"])

    # 1. Latency Distribution (top left)
    if "request_latency" in metrics:
        data = successful["request_latency"]
        ax1.hist(data, bins=25, color=colors["primary"], alpha=0.8, edgecolor="white")
        ax1.axvline(
            metrics["request_latency"]["median"],
            color=colors["warning"],
            linestyle="--",
            linewidth=2.5,
            label="Median",
        )
        ax1.axvline(
            metrics["request_latency"]["p95"],
            color=colors["danger"],
            linestyle="--",
            linewidth=2.5,
            label="P95",
        )
        ax1.set_xlabel("Latency (ms)", fontweight="bold", fontsize=11)
        ax1.set_ylabel("Frequency", fontweight="bold", fontsize=11)
        ax1.set_title(
            "📊 LATENCY DISTRIBUTION",
            fontweight="bold",
            color=colors["text"],
            fontsize=12,
            pad=10,
        )
        ax1.legend(facecolor=colors["bg_dark"], edgecolor=colors["text"])
        ax1.grid(True, alpha=0.2, color=colors["text"])

    # 2. Throughput gauge (top right)
    if "output_token_throughput_per_user" in metrics:
        throughput_mean = metrics["output_token_throughput_per_user"]["mean"]
        throughput_max = 50  # Expected max

        # Create gauge
        theta = np.linspace(0, np.pi, 100)
        r = np.ones_like(theta)

        # Background arc
        ax2.fill_between(theta, 0, r, color=colors["bg_dark"], alpha=0.3)

        # Filled arc based on value
        fill_theta = np.linspace(0, (throughput_mean / throughput_max) * np.pi, 100)
        ax2.fill_between(fill_theta, 0, r[0], color=colors["success"], alpha=0.8)

        # Add value text
        ax2.text(
            np.pi / 2,
            0.3,
            f"{throughput_mean:.1f}",
            ha="center",
            va="center",
            fontsize=32,
            fontweight="bold",
            color=colors["success"],
        )
        ax2.text(
            np.pi / 2,
            -0.1,
            "tokens/sec/user",
            ha="center",
            va="center",
            fontsize=11,
            color=colors["text"],
        )

        ax2.set_xlim(0, np.pi)
        ax2.set_ylim(-0.3, 1.2)
        ax2.axis("off")
        ax2.set_title(
            "⚡ THROUGHPUT",
            fontweight="bold",
            color=colors["text"],
            fontsize=12,
            pad=10,
        )

    # 3. Percentile comparison (middle left)
    if "request_latency" in metrics and "ttft" in metrics:
        percentiles = [50, 95, 99]
        x = np.arange(len(percentiles))
        width = 0.35

        latency_vals = [
            metrics["request_latency"][f"p{p}" if p > 50 else "median"]
            for p in percentiles
        ]
        ttft_vals = [
            metrics["ttft"][f"p{p}" if p > 50 else "median"] for p in percentiles
        ]

        bars1 = ax3.bar(
            x - width / 2,
            latency_vals,
            width,
            label="Latency",
            color=colors["primary"],
            alpha=0.8,
            edgecolor="white",
            linewidth=1.5,
        )
        bars2 = ax3.bar(
            x + width / 2,
            ttft_vals,
            width,
            label="TTFT",
            color=colors["info"],
            alpha=0.8,
            edgecolor="white",
            linewidth=1.5,
        )

        ax3.set_ylabel("Time (ms)", fontweight="bold", fontsize=11)
        ax3.set_title(
            "🎯 PERCENTILES",
            fontweight="bold",
            color=colors["text"],
            fontsize=12,
            pad=10,
        )
        ax3.set_xticks(x)
        ax3.set_xticklabels([f"P{p}" for p in percentiles])
        ax3.legend(facecolor=colors["bg_dark"], edgecolor=colors["text"])
        ax3.grid(True, alpha=0.2, axis="y", color=colors["text"])

    # 4. Token analysis (middle right)
    if "output_sequence_length" in successful.columns:
        data = successful["output_sequence_length"]

        # Create violin plot manually with filled area
        parts = ax4.violinplot(
            [data], positions=[0], widths=0.7, showmeans=True, showmedians=True
        )

        for pc in parts["bodies"]:
            pc.set_facecolor(colors["purple"])
            pc.set_alpha(0.8)
            pc.set_edgecolor("white")
            pc.set_linewidth(2)

        for partname in ("cbars", "cmins", "cmaxes", "cmedians", "cmeans"):
            if partname in parts:
                vp = parts[partname]
                vp.set_edgecolor("white")
                vp.set_linewidth(2)

        ax4.set_ylabel("Token Count", fontweight="bold", fontsize=11)
        ax4.set_title(
            "🎲 OUTPUT TOKENS",
            fontweight="bold",
            color=colors["text"],
            fontsize=12,
            pad=10,
        )
        ax4.set_xticks([])
        ax4.grid(True, alpha=0.2, axis="y", color=colors["text"])

        # Add stats text
        ax4.text(
            0,
            data.max() * 1.05,
            f"Mean: {data.mean():.0f}",
            ha="center",
            fontsize=10,
            color=colors["text"],
            fontweight="bold",
        )

    # 5. Performance timeline (bottom - wide)
    if "request_latency" in successful.columns:
        x = range(len(successful))
        y = successful["request_latency"].values

        # Create gradient effect
        ax5.fill_between(x, y, alpha=0.3, color=colors["primary"])
        ax5.plot(x, y, color=colors["primary"], linewidth=2, alpha=0.9)

        # Add rolling average
        window = 10
        if len(successful) >= window:
            rolling_avg = pd.Series(y).rolling(window=window).mean()
            ax5.plot(
                x,
                rolling_avg,
                color=colors["warning"],
                linewidth=3,
                linestyle="--",
                label=f"{window}-request avg",
                alpha=0.9,
            )

        ax5.set_xlabel("Request Number", fontweight="bold", fontsize=12)
        ax5.set_ylabel("Latency (ms)", fontweight="bold", fontsize=12)
        ax5.set_title(
            "📈 PERFORMANCE OVER TIME",
            fontweight="bold",
            color=colors["text"],
            fontsize=14,
            pad=15,
        )
        ax5.legend(facecolor=colors["bg_dark"], edgecolor=colors["text"], fontsize=10)
        ax5.grid(True, alpha=0.2, color=colors["text"])

    # Footer with key insights
    footer_y = 0.02

    insights = []
    if "request_latency" in metrics:
        p99_p50_ratio = (
            metrics["request_latency"]["p99"] / metrics["request_latency"]["median"]
        )
        insights.append(f"P99/P50 Ratio: {p99_p50_ratio:.2f}x")

    if "output_token_throughput_per_user" in metrics:
        tp_std = successful["output_token_throughput_per_user"].std()
        tp_mean = metrics["output_token_throughput_per_user"]["mean"]
        cv = (tp_std / tp_mean) * 100
        insights.append(f"Throughput CV: {cv:.1f}%")

    insights.append(
        f"Success Rate: {((total_requests - errors) / total_requests * 100):.1f}%"
    )

    fig.text(
        0.5,
        footer_y,
        " | ".join(insights),
        ha="center",
        fontsize=11,
        color=colors["text"],
        style="italic",
        alpha=0.8,
    )

    fig.text(
        0.5, footer_y - 0.01, "━" * 80, ha="center", fontsize=10, color=colors["info"]
    )

    fig.text(
        0.05,
        footer_y - 0.025,
        "🚀 Generated by aiperf visualization toolkit",
        fontsize=9,
        color=colors["text"],
        alpha=0.6,
    )
    fig.text(
        0.95,
        footer_y - 0.025,
        "October 2025",
        ha="right",
        fontsize=9,
        color=colors["text"],
        alpha=0.6,
    )

    plt.tight_layout(rect=[0, 0.03, 1, 0.88])

    return fig


def create_comparison_chart(df, output_dir):
    """Create side-by-side comparison chart"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    successful = df[df["has_error"] == 0]
    colors_palette = sns.color_palette("husl", 8)

    # Calculate metrics for this function
    total_requests = len(df)
    errors = df["has_error"].sum()
    error_rate = errors / total_requests * 100

    # 1. Latency breakdown
    ax1 = axes[0]
    if "ttft" in successful.columns and "request_latency" in successful.columns:
        # Calculate time after first token
        successful_copy = successful.copy()
        successful_copy["after_first_token"] = (
            successful_copy["request_latency"] - successful_copy["ttft"]
        )

        categories = ["TTFT", "Generation\nTime"]
        values = [
            successful_copy["ttft"].mean(),
            successful_copy["after_first_token"].mean(),
        ]

        bars = ax1.barh(
            categories,
            values,
            color=[colors_palette[0], colors_palette[2]],
            alpha=0.8,
            edgecolor="black",
            linewidth=2,
        )

        # Add value labels
        for bar, val in zip(bars, values, strict=False):
            width = bar.get_width()
            ax1.text(
                width,
                bar.get_y() + bar.get_height() / 2,
                f" {val:.0f}ms",
                ha="left",
                va="center",
                fontweight="bold",
                fontsize=12,
            )

        ax1.set_xlabel("Time (ms)", fontweight="bold", fontsize=12)
        ax1.set_title("⏱️ Latency Breakdown", fontweight="bold", fontsize=14)
        ax1.grid(True, alpha=0.3, axis="x")

    # 2. Token comparison
    ax2 = axes[1]
    if (
        "output_sequence_length" in successful.columns
        and "reasoning_token_count" in successful.columns
    ):
        token_types = ["Output\nTokens", "Reasoning\nTokens"]
        token_values = [
            successful["output_sequence_length"].mean(),
            successful["reasoning_token_count"].mean(),
        ]

        bars = ax2.bar(
            token_types,
            token_values,
            color=[colors_palette[3], colors_palette[4]],
            alpha=0.8,
            edgecolor="black",
            linewidth=2,
        )

        for bar, val in zip(bars, token_values, strict=False):
            height = bar.get_height()
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                height,
                f"{val:.0f}",
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=12,
            )

        ax2.set_ylabel("Average Token Count", fontweight="bold", fontsize=12)
        ax2.set_title("🎯 Token Generation", fontweight="bold", fontsize=14)
        ax2.grid(True, alpha=0.3, axis="y")

    # 3. Performance grade
    ax3 = axes[2]

    # Calculate performance score
    score_components = []

    if "request_latency" in successful.columns:
        # Lower is better, normalize to 0-100
        latency_score = max(0, 100 - (successful["request_latency"].mean() / 100))
        score_components.append(("Latency", latency_score))

    if "output_token_throughput_per_user" in successful.columns:
        # Higher is better
        throughput_score = min(
            100, (successful["output_token_throughput_per_user"].mean() / 50) * 100
        )
        score_components.append(("Throughput", throughput_score))

    # Error score
    error_score = 100 - error_rate
    score_components.append(("Reliability", error_score))

    # Create radar-style bar chart
    categories = [comp[0] for comp in score_components]
    scores = [comp[1] for comp in score_components]

    bars = ax3.barh(
        categories,
        scores,
        color=colors_palette[: len(scores)],
        alpha=0.8,
        edgecolor="black",
        linewidth=2,
    )

    for bar, score in zip(bars, scores, strict=False):
        width = bar.get_width()
        ax3.text(
            width,
            bar.get_y() + bar.get_height() / 2,
            f" {score:.0f}",
            ha="left",
            va="center",
            fontweight="bold",
            fontsize=12,
        )

    ax3.set_xlim(0, 110)
    ax3.set_xlabel("Score (0-100)", fontweight="bold", fontsize=12)
    ax3.set_title("📊 Performance Scores", fontweight="bold", fontsize=14)
    ax3.grid(True, alpha=0.3, axis="x")

    plt.suptitle(
        "🔥 Performance Comparison Dashboard", fontsize=18, fontweight="bold", y=0.98
    )

    plt.tight_layout()
    plt.savefig(output_dir / "comparison_chart.png", dpi=DPI, bbox_inches="tight")
    plt.close()

    print("✓ Created: comparison_chart.png")


if __name__ == "__main__":
    import sys

    output_dir = Path(__file__).parent / "performance_visualizations"
    output_dir.mkdir(exist_ok=True)

    # Allow command line argument
    data_file = None
    if len(sys.argv) > 1:
        data_file = Path(sys.argv[1])

    print("🎨 Creating Infographic Visualizations...\n")

    df = load_data(data_file)

    # Create infographic
    fig = create_infographic(df)
    plt.savefig(
        output_dir / "performance_infographic.png",
        dpi=DPI,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close()
    print("✓ Created: performance_infographic.png")

    # Create comparison chart
    create_comparison_chart(df, output_dir)

    print("\n✅ Infographic visualizations complete!")
    print("📸 Perfect for sharing and presentations!")
