<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🚀 LLM Performance Visualization Dashboard

## Overview

This dashboard provides comprehensive, interactive visualizations of LLM inference performance metrics based on real-world profiling data. The visualizations use cutting-edge Python libraries (Plotly, Seaborn, Matplotlib) to deliver insights that matter to production systems.

## 📊 Quick Start

**Open `dashboard.html` in your browser** to view all visualizations in one place!

Individual visualizations are also available as standalone HTML files.

---

## 📈 Visualizations Explained

### 1. **Summary Statistics** (`summary_stats.html`)
**What it shows:** Key performance metrics at a glance
- Mean, median, standard deviation for all critical metrics
- P95 and P99 percentiles (crucial for SLA compliance)
- Min/max values to understand range

**Why it matters:** Quick health check of your LLM service. P95/P99 are what most users experience.

---

### 2. **Latency Distribution Analysis** (`latency_distribution.html`)
**What it shows:** Four histograms showing:
- Request Latency distribution
- Time to First Token (TTFT) distribution
- Inter-Token Latency distribution
- Throughput distribution

**Why it matters:**
- Identifies if you have bimodal distributions (indicating different request types)
- TTFT is critical for user experience - users notice delays here first
- Inter-token latency affects perceived generation speed
- Throughput shows system efficiency

**Key insights to look for:**
- Tight distributions = consistent performance
- Long tails = outliers that need investigation
- Multiple peaks = different request patterns

---

### 3. **Performance Trends Over Time** (`performance_over_time.html`)
**What it shows:** Three time-series charts:
- Request latency with moving average (to spot trends)
- Throughput over time (to see degradation)
- Cumulative error rate (to track system health)

**Why it matters:**
- Detects performance degradation over time
- Shows if system warms up or slows down
- Correlates errors with latency spikes
- Moving average reveals hidden trends in noisy data

**Red flags to watch for:**
- Increasing latency trend = resource exhaustion
- Dropping throughput = system degradation
- Rising error rate = instability

---

### 4. **Token Impact on Performance** (`token_analysis.html`)
**What it shows:** Scatter plots showing:
- How input length affects request latency (colored by output length)
- How output length affects throughput (colored by reasoning tokens)

**Why it matters:**
- Understand cost vs. performance tradeoffs
- Optimize batching strategies
- Predict latency for different request sizes
- Reasoning tokens (from models like o1) have unique performance characteristics

**Insights:**
- Linear relationship = predictable scaling
- Non-linear = bottlenecks at certain sizes
- Color patterns reveal multi-dimensional relationships

---

### 5. **Percentile Analysis** (`percentile_analysis.html`)
**What it shows:** Bar chart comparing P50, P75, P90, P95, P99 across metrics

**Why it matters:**
- P50 (median) = typical user experience
- P95/P99 = tail latency that affects SLAs
- Large P99/P50 ratio = high variance (bad for user experience)

**Best practices:**
- P95 should be < 2x P50 for good experience
- P99 should be < 3x P50
- High P99 = investigate outliers

---

### 6. **Metric Correlations** (`correlation_heatmap.html`)
**What it shows:** Heatmap of correlations between all metrics

**Why it matters:**
- Discover unexpected relationships
- Identify root causes of performance issues
- Validate assumptions about system behavior

**How to read:**
- Red = positive correlation (both increase together)
- Blue = negative correlation (one increases, other decreases)
- White/near zero = no relationship

**Expected patterns:**
- High correlation between input length and latency
- Negative correlation between sequence length and throughput
- Output tokens correlated with reasoning tokens

---

### 7. **Error Analysis** (`error_analysis.html`)
**What it shows:**
- Pie chart of error types distribution
- Timeline showing when errors occurred

**Why it matters:**
- Identifies most common failure modes
- Shows if errors cluster in time (systemic issue)
- Helps prioritize reliability improvements

**Action items:**
- Dominant error type = focus optimization there
- Clustered errors = investigate that time period
- Random errors = may be acceptable noise

---

## 🎯 Key Performance Indicators (KPIs)

Based on industry best practices, here are the metrics that matter most:

### For User Experience:
1. **TTFT (Time to First Token)** - Target: < 500ms
   - First impression of responsiveness
   - Users notice delays > 300ms

2. **Inter-Token Latency** - Target: < 50ms
   - Affects perceived "thinking speed"
   - Smoother experience with lower variance

### For System Health:
3. **P95 Request Latency** - Target: < 2x median
   - Most users' worst-case experience
   - SLA critical metric

4. **Error Rate** - Target: < 0.1%
   - System reliability indicator
   - Impact on user trust

### For Cost Optimization:
5. **Throughput** - Target: Maximize
   - Tokens per second per user
   - Directly impacts infrastructure costs
   - Higher = better GPU utilization

---

## 🔍 How to Use This Dashboard

### For Performance Engineers:
1. Start with **Summary Statistics** - are P95/P99 acceptable?
2. Check **Performance Over Time** - any degradation trends?
3. Review **Token Analysis** - where are the bottlenecks?
4. Examine **Correlation Heatmap** - what's driving latency?

### For SREs/DevOps:
1. Monitor **Error Analysis** - failure patterns?
2. Track **Performance Over Time** - stability issues?
3. Watch **Percentile Analysis** - meeting SLAs?

### For Product Managers:
1. Focus on **Latency Distribution** - user experience quality
2. Review **TTFT** metrics - first impression latency
3. Check **Error Rate** - reliability for users

### For ML Engineers:
1. Study **Token Analysis** - model efficiency
2. Examine **Reasoning Tokens** impact - new model features
3. Correlate **Input/Output Lengths** with performance

---

## 🛠️ Technical Details

### Technologies Used:
- **Plotly**: Interactive web-based visualizations with zoom, pan, hover
- **Seaborn**: Statistical visualizations with beautiful defaults
- **Pandas**: Data manipulation and analysis
- **NumPy**: Numerical computations

### Data Processing:
- Parsed JSONL format with robust error handling
- Extracted 22+ metrics per request
- Computed moving averages and percentiles
- Generated correlation matrices

### Best Practices Implemented:
- Dark theme for reduced eye strain
- Color-blind friendly palettes
- Interactive hover tooltips for data exploration
- Responsive layouts for different screen sizes
- Statistical rigor in percentile calculations

---

## 📚 Further Reading

### Understanding Latency Metrics:
- Google's "[The Tail at Scale](https://research.google/pubs/pub40801/)" paper
- AWS re:Invent talks on P99 latency
- Brendan Gregg's "[Systems Performance](https://www.brendangregg.com/systems-performance-2nd-edition-book.html)"

### LLM-Specific Performance:
- "[How to Make LLMs Go Fast](https://vgel.me/posts/faster-inference/)"
- vLLM documentation on throughput optimization
- Anthropic's research on batching strategies

### Visualization Best Practices:
- Edward Tufte's "The Visual Display of Quantitative Information"
- "[Visualization Analysis and Design](https://www.cs.ubc.ca/~tmm/vadbook/)" by Tamara Munzner
- Plotly's best practices guide

---

## 🎨 Customization

To modify visualizations, edit `visualize_performance.py`:

```python
# Change color scheme
fig.update_layout(template="plotly_white")  # Light theme

# Adjust histogram bins
nbinsx=100  # More granular

# Add custom metrics
custom_metrics = {
    'my_metric': 'My Custom Metric'
}
```

---

## 📊 Data Schema

The visualizations expect JSONL with this structure:

```json
{
  "metadata": {
    "timestamp_ns": 1234567890,
    "worker_id": "worker_123",
    "x_request_id": "req_abc"
  },
  "metrics": {
    "request_latency": {"value": 1000, "unit": "ms"},
    "ttft": {"value": 500, "unit": "ms"},
    "output_token_throughput_per_user": {"value": 25.5, "unit": "tokens/sec/user"}
  },
  "error": null
}
```

---

## 🚀 Next Steps

1. **Set up monitoring**: Schedule this script to run regularly
2. **Set alerts**: Define thresholds for P95/P99 latencies
3. **A/B testing**: Compare performance across model versions
4. **Capacity planning**: Use trends to predict scaling needs

---

## 📝 License

This visualization toolkit is part of the aiperf project.

---

## 🤝 Contributing

Suggestions for new visualizations? Open an issue or PR!

Popular requests:
- [ ] Cost per request analysis
- [ ] Comparative benchmarks across models
- [ ] Real-time streaming dashboard
- [ ] GPU utilization overlays

---

**Generated by aiperf visualization toolkit**
*Using the latest Python data visualization best practices (2024-2025)*

