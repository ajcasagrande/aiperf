<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🚀 Ultimate AIPerf Visualization Suite

**The most comprehensive LLM benchmarking visualizations powered by AIPerf metrics**

This suite provides 12 interactive visualizations covering every aspect of LLM inference performance, designed to give you deep insights into your model's behavior under load.

## 📊 Visualization Gallery

### 1. Executive Dashboard (`01_executive_dashboard.html`)
**High-level performance overview for decision makers**

- Request latency distribution with statistical summaries
- Time to First Token (TTFT) violin plots
- Output token throughput distribution
- Inter-token latency (ITL) analysis
- Latency vs token count correlation
- Throughput trends over time
- Key metrics summary table
- Reasoning vs output token breakdown
- Performance stability (coefficient of variation)

**Best for:** Quick performance assessment, stakeholder presentations

---

### 2. Latency Deep Dive (`02_latency_deep_dive.html`)
**Comprehensive latency component analysis**

- Latency breakdown: TTFT + generation time
- Distribution comparison across TTFT, TTST, and ITL
- Cumulative Distribution Function (CDF) with percentile markers
- Time vs percentile heatmap showing performance evolution

**Best for:** Understanding latency composition, identifying bottlenecks

---

### 3. Token Analysis (`03_token_analysis.html`)
**Token-centric performance metrics**

- Token distribution across input/output/reasoning types
- Throughput vs sequence length with trend analysis
- Token efficiency by output length bins
- Cumulative token generation over time with rate overlay

**Best for:** Capacity planning, understanding token generation patterns

---

### 4. Streaming Analysis (`04_streaming_analysis.html`)
**Streaming behavior and consistency**

- Inter-chunk latency distribution with statistical markers
- TTFT vs TTST scatter plot with correlation
- Chunk-by-chunk latency patterns
- Streaming stability analysis (coefficient of variation)

**Best for:** Optimizing streaming performance, detecting jitter issues

---

### 5. Time Series Analysis (`05_time_series_analysis.html`)
**Performance evolution over benchmark duration**

- Request latency over time with rolling statistics (mean, P90, P99)
- Throughput and token generation trends
- System load indicators (requests/second)

**Best for:** Detecting performance degradation, warm-up effects, load issues

---

### 6. Percentile Ladder (`06_percentile_ladder.html`)
**Comprehensive percentile distributions**

- Percentile ladder (P0, P10, P25, P50, P75, P90, P95, P99, P99.9, P100)
- Color-coded performance indicators
- Reference lines for key percentiles

**Best for:** SLA planning, understanding tail latencies

---

### 7. Correlation Matrix (`07_correlation_matrix.html`)
**Inter-metric relationships**

- Heatmap of correlations between all numeric metrics
- Identify which metrics move together
- Understand causal relationships

**Best for:** Root cause analysis, understanding system behavior

---

### 8. Reasoning Overhead Analysis (`08_reasoning_overhead.html`)
**Reasoning token impact assessment**

- Reasoning vs output token scatter
- Reasoning overhead ratio distribution
- Latency impact of reasoning tokens with trend line
- Reasoning efficiency (output tokens per reasoning token)

**Best for:** Optimizing reasoning-enabled models, cost analysis

---

### 9. Workload Characterization (`09_workload_characterization.html`)
**Understanding request patterns**

- Request size distribution
- Output length clustering
- Workload phase detection
- Request arrival pattern analysis

**Best for:** Workload modeling, capacity planning

---

### 10. SLA Compliance Dashboard (`10_sla_compliance.html`)
**Quality of service and SLA tracking**

- SLA compliance rates with traffic light indicators
- Tail latency behavior (>P90)
- SLA violation timeline
- Performance degradation detection

**Best for:** Production monitoring, SLA reporting

---

### 11. Performance Heatmaps (`11_performance_heatmaps.html`)
**Multi-dimensional performance views**

- Latency heatmap (time × worker)
- Throughput heatmap (time × output length)
- Token type distribution over time
- Performance variance heatmap

**Best for:** Identifying hot spots, load distribution analysis

---

### 12. Statistical Summary (`12_statistical_summary.html`)
**Comprehensive statistical reference**

- Benchmark overview (duration, request count, success rate)
- Detailed statistics for all metrics:
  - Count, mean, std dev, coefficient of variation
  - Min, max, and full percentile ladder (P1, P5, P25, P50, P75, P90, P95, P99, P99.9)
- Color-coded performance indicators

**Best for:** Detailed performance reporting, metric documentation

---

## 🎯 Key Metrics Explained

### Latency Metrics
- **Request Latency**: Total end-to-end time from request to final response
- **TTFT (Time to First Token)**: How quickly the model starts generating
- **TTST (Time to Second Token)**: Gap between first and second token
- **ITL (Inter Token Latency)**: Average time between consecutive tokens
- **ICL (Inter Chunk Latency)**: Time gaps between streaming chunks

### Token Metrics
- **Input Sequence Length (ISL)**: Number of prompt tokens
- **Output Token Count**: Visible output tokens (excluding reasoning)
- **Reasoning Token Count**: Internal thinking tokens
- **Output Sequence Length (OSL)**: Total completion tokens (output + reasoning)

### Throughput Metrics
- **Output Token Throughput Per User**: Individual request generation rate (excludes TTFT)
- **Request Throughput**: Overall request processing rate

### Efficiency Metrics
- **Reasoning Overhead Ratio**: Reasoning tokens / output tokens
- **Reasoning Efficiency**: Output tokens / reasoning tokens
- **Coefficient of Variation (CV)**: Stability indicator (std dev / mean)

---

## 🚀 Quick Start

### View All Visualizations
```bash
# Open all in browser
./open_all_visualizations.sh

# Or manually open the index
open index.html
```

### Generate New Visualizations
```bash
python ultimate_visualizations.py path/to/profile_export.jsonl -o output_dir
```

---

## 📈 Interpretation Guide

### Understanding Performance

#### ✅ Good Performance Indicators
- **Low CV (<0.3)**: Consistent, predictable performance
- **High SLA compliance (>95%)**: Meeting quality targets
- **Tight percentile spread**: P99/P50 ratio < 3
- **Low reasoning overhead (<1.0)**: Efficient thinking process
- **Stable throughput over time**: No degradation

#### ⚠️ Warning Signs
- **High CV (>0.5)**: Inconsistent performance, investigate variance
- **Wide percentile spread**: P99/P50 ratio > 5, indicates tail issues
- **Increasing latency over time**: Possible memory leak or resource exhaustion
- **Low throughput with high latency**: Underutilized system or bottleneck
- **High reasoning overhead (>2.0)**: Model doing excessive thinking

#### 🔥 Critical Issues
- **SLA compliance <90%**: Major quality problems
- **Bimodal distributions**: Multiple performance modes, investigate cause
- **Performance degradation**: Steady increase in latency over time
- **Extreme outliers**: P99.9 >> P99 indicates severe tail latencies
- **Variable ICL**: Jittery streaming experience

### Common Patterns

#### Warm-up Effect
- Initial requests show higher latency
- Gradually improves over first few minutes
- **Solution**: Exclude warm-up period from analysis

#### Load Saturation
- Latency increases with request rate
- Throughput plateaus despite increasing load
- **Solution**: Add capacity or optimize model

#### Batching Artifacts
- Periodic spikes in inter-chunk latency
- Sawtooth pattern in time series
- **Solution**: Tune batch size and scheduling

#### Memory/Resource Issues
- Gradual performance degradation
- Increased latency variance over time
- **Solution**: Check for memory leaks, resource limits

---

## 🎨 Customization

### Modify SLA Targets
Edit `sla_targets` in `create_sla_compliance_dashboard()`:
```python
sla_targets = {
    'ttft': 500,          # ms - your target
    'request_latency': 10000,
    'inter_token_latency': 100,
}
```

### Add Custom Visualizations
Follow the pattern in `ultimate_visualizations.py`:
```python
def create_my_custom_viz(self):
    fig = make_subplots(...)
    # Add your analysis
    fig.write_html(self.output_dir / "13_my_custom_viz.html")
```

---

## 📊 Metrics Reference

See the comprehensive [AIPerf Metrics Reference](../docs/metrics_reference.md) for detailed explanations of all metrics, their formulas, and requirements.

### Metric Categories

1. **Record Metrics**: Computed per-request (produce distributions)
   - `request_latency`, `ttft`, `inter_token_latency`, `output_token_count`, etc.

2. **Aggregate Metrics**: Single values across all requests
   - `request_count`, `total_output_tokens`, `benchmark_duration`, etc.

3. **Derived Metrics**: Computed from other metrics
   - `request_throughput`, `output_token_throughput`, etc.

### Metric Flags

- `STREAMING_ONLY`: Requires Server-Sent Events with multiple chunks
- `PRODUCES_TOKENS_ONLY`: Requires token-producing endpoints
- `SUPPORTS_REASONING`: Requires reasoning token support
- `LARGER_IS_BETTER`: Higher values indicate better performance

---

## 🔧 Technical Details

### Technology Stack
- **Plotly**: Interactive visualizations with zoom, pan, hover
- **Pandas**: Efficient data processing and analysis
- **NumPy/SciPy**: Statistical computations
- **Pydantic**: Type-safe data models

### Performance
- Handles datasets with 10K+ requests
- Generates all 12 visualizations in < 30 seconds
- Interactive HTML files (2-5 MB each)

### Browser Compatibility
- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support (some rendering differences)

---

## 📝 Best Practices

### 1. Benchmark Design
- Run for sufficient duration (5-10 minutes minimum)
- Use realistic workload patterns
- Include warm-up period
- Monitor system resources

### 2. Analysis Workflow
1. Start with **Executive Dashboard** for overview
2. Check **SLA Compliance** for quality assessment
3. Use **Time Series** to detect temporal issues
4. Dive into **Latency Deep Dive** for bottlenecks
5. Review **Percentile Ladder** for tail behavior
6. Consult **Correlation Matrix** for relationships

### 3. Reporting
- Include **Statistical Summary** for precise numbers
- Use **Executive Dashboard** screenshots for presentations
- Reference **Percentile Ladder** for SLA discussions
- Share **SLA Compliance** with stakeholders

---

## 🆘 Troubleshooting

### Missing Metrics
Some visualizations may be sparse if certain metrics aren't available:
- **Reasoning metrics**: Require reasoning-enabled models
- **Streaming metrics**: Require `--streaming` flag
- **Token metrics**: Require token-producing endpoints

### Invalid JSON Warnings
A few records may fail to parse due to:
- Very large inter-chunk latency arrays (>1000 chunks)
- Malformed JSON in rare cases
- These are safely skipped with warnings

### Visualization Performance
For very large datasets (>50K requests):
- Increase sample sizes in scatter plots
- Use aggregated views (rolling averages)
- Consider splitting analysis by time windows

---

## 🤝 Contributing

Have ideas for new visualizations? See patterns we should detect? Open an issue or PR!

### Ideas for Future Visualizations
- [ ] GPU utilization correlation
- [ ] Batch size efficiency analysis
- [ ] Model comparison dashboard
- [ ] Cost analysis (tokens × pricing)
- [ ] Concurrency impact analysis
- [ ] Queue depth visualization

---

## 📚 Additional Resources

- [AIPerf Documentation](../docs/index.md)
- [Metrics Reference](../docs/metrics_reference.md)
- [Tutorial](../docs/tutorial.md)
- [Example Scripts](../examples/)

---

## 📄 License

See [LICENSE](../LICENSE) for details.

---

**Generated by Ultimate AIPerf Visualization Suite v1.0**
*The ultimate tool for LLM benchmarking insights*

