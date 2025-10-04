<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🎨 Ultimate AIPerf Visualizations - Quick Start

## 🚀 5-Minute Quick Start

### 1. Generate Visualizations
```bash
cd /home/anthony/nvidia/projects/aiperf9

# Activate environment
source .venv/bin/activate

# Run visualization suite
python ultimate_visualizations.py \
    artifacts/openai_gpt-oss-20b-openai-chat-concurrency100/profile_export_5min.jsonl \
    -o ultimate_visualizations
```

### 2. View Results
```bash
# Option A: Open index page
cd ultimate_visualizations
xdg-open index.html  # Linux
# open index.html    # macOS

# Option B: Use helper script (opens all)
./open_all.sh
```

### 3. Explore Visualizations

**Start Here**:
1. **Executive Dashboard** (`01_executive_dashboard.html`) - Get the big picture
2. **SLA Compliance** (`10_sla_compliance.html`) - Check quality
3. **Time Series** (`05_time_series_analysis.html`) - See trends

**Dive Deeper**:
- **Latency issues?** → `02_latency_deep_dive.html`
- **Token efficiency?** → `03_token_analysis.html`
- **Streaming problems?** → `04_streaming_analysis.html`
- **Need statistics?** → `12_statistical_summary.html`

---

## 📊 What You Get

### 12 Interactive Visualizations (63 MB total)

| # | Visualization | Size | Purpose |
|---|---------------|------|---------|
| 01 | Executive Dashboard | 4.8 MB | High-level overview |
| 02 | Latency Deep Dive | 4.7 MB | Latency analysis |
| 03 | Token Analysis | 4.8 MB | Token metrics |
| 04 | Streaming Analysis | 16 MB | Streaming behavior |
| 05 | Time Series | 4.8 MB | Performance over time |
| 06 | Percentile Ladder | 4.7 MB | Percentile distributions |
| 07 | Correlation Matrix | 4.7 MB | Metric relationships |
| 08 | Reasoning Overhead | 4.7 MB | Reasoning analysis |
| 09 | Workload Characterization | 4.8 MB | Workload patterns |
| 10 | SLA Compliance | 4.7 MB | Quality tracking |
| 11 | Performance Heatmaps | 4.7 MB | Multi-dimensional views |
| 12 | Statistical Summary | 18 KB | Comprehensive stats |

Plus:
- `index.html` - Beautiful landing page
- `README.md` - Detailed documentation
- `open_all.sh` - Helper script

---

## 🎯 Common Use Cases

### Use Case 1: Performance Review
```bash
# Generate visualizations
python ultimate_visualizations.py profile_export.jsonl

# Open these for review meeting:
- 01_executive_dashboard.html      # Overview
- 10_sla_compliance.html            # Quality
- 12_statistical_summary.html      # Details
```

### Use Case 2: Optimization
```bash
# Identify bottlenecks
- 02_latency_deep_dive.html         # Where is time spent?
- 07_correlation_matrix.html        # What drives latency?
- 05_time_series_analysis.html      # Any degradation?
```

### Use Case 3: Capacity Planning
```bash
# Understand workload
- 03_token_analysis.html             # Token patterns
- 09_workload_characterization.html  # Request patterns
- 11_performance_heatmaps.html       # Load distribution
```

### Use Case 4: Streaming Optimization
```bash
# Improve streaming
- 04_streaming_analysis.html         # Chunk behavior
- 02_latency_deep_dive.html          # TTFT breakdown
- 05_time_series_analysis.html       # Consistency
```

---

## 📈 Interpretation Cheat Sheet

### Reading Executive Dashboard
- **Box plots**: Wider = more variance (bad)
- **P90/P99 lines**: Higher = worse tail latency
- **CV (Coeff of Variation)**: >0.5 = inconsistent performance

### Reading Latency Deep Dive
- **CDF steep**: Consistent performance ✅
- **CDF flat**: High variance ⚠️
- **P99 >> P90**: Tail latency problem 🔥

### Reading SLA Compliance
- **Green bars (>95%)**: Meeting SLA ✅
- **Orange bars (90-95%)**: At risk ⚠️
- **Red bars (<90%)**: Missing SLA 🔥

### Reading Time Series
- **Stable lines**: Good performance ✅
- **Upward trend**: Degradation ⚠️
- **Spikes**: Investigate cause 🔥

---

## 🛠️ Customization

### Change SLA Targets
Edit `ultimate_visualizations.py`, line ~1039:
```python
sla_targets = {
    'ttft': 1000,           # Change from 500ms to 1000ms
    'request_latency': 15000,  # Change from 10000ms to 15000ms
    'inter_token_latency': 150,  # Change from 100ms to 150ms
}
```

### Custom Output Directory
```bash
python ultimate_visualizations.py input.jsonl -o my_custom_output/
```

---

## 🐛 Troubleshooting

### "Invalid JSON" Warnings
**Normal**: A few records may have parsing issues (corrupted data)
**Action**: If <5% of records fail, ignore. If >5%, investigate input file.

### Missing Metrics
**Cause**: Not all metrics available in all modes
- `ttft`, `ttst`, `inter_chunk_latency` → Require `--streaming`
- `reasoning_token_count` → Require reasoning-enabled model

**Action**: Visualizations adapt automatically, showing only available metrics.

### Large File Sizes
**Cause**: Streaming analysis includes all inter-chunk latency data
**Action**: Normal. The interactive charts need the full data for zoom/pan.

### Slow Generation
**Cause**: Very large datasets (>50K requests)
**Action**: Still completes in <2 minutes. Be patient.

---

## 📚 Documentation

### Full Documentation
- **Complete Guide**: `ULTIMATE_VISUALIZATIONS_GUIDE.md` (detailed reference)
- **Suite README**: `ultimate_visualizations/README.md` (in-depth explanations)
- **Metrics Reference**: Full metrics definitions in your original doc

### Key Concepts
- **Record Metrics**: Per-request (create distributions)
- **Aggregate Metrics**: Totals across all requests
- **Derived Metrics**: Computed from other metrics

### Metric Types
- **Latency**: request_latency, ttft, ttst, inter_token_latency
- **Tokens**: input_sequence_length, output_token_count, reasoning_token_count
- **Throughput**: output_token_throughput_per_user, request_throughput

---

## 🎓 Learning Path

### Beginner (First 10 minutes)
1. Open **Executive Dashboard** - understand the metrics
2. Open **Statistical Summary** - see the numbers
3. Read **percentile values** - understand P50/P90/P99

### Intermediate (Next 20 minutes)
4. Open **Latency Deep Dive** - understand components
5. Open **Time Series** - see temporal patterns
6. Open **SLA Compliance** - check quality

### Advanced (Next 30 minutes)
7. Open **Correlation Matrix** - find relationships
8. Open **Performance Heatmaps** - multi-dimensional view
9. Open **Workload Characterization** - understand patterns
10. Study **interpretation patterns** in full guide

---

## 🚀 Next Steps

### Share Results
```bash
# Zip visualizations for sharing
cd ultimate_visualizations
zip -r ../visualizations.zip .
```

### Continuous Monitoring
```bash
# Create visualization for each benchmark
python ultimate_visualizations.py run1.jsonl -o viz_run1/
python ultimate_visualizations.py run2.jsonl -o viz_run2/
# Compare across directories
```

### Integration
```bash
# Add to CI/CD pipeline
python ultimate_visualizations.py ${BENCHMARK_OUTPUT} -o ${ARTIFACT_DIR}/viz/

# Archive with artifacts
tar -czf benchmark_results.tar.gz profile_export.jsonl ultimate_visualizations/
```

---

## 💡 Pro Tips

### Tip 1: Use the Index
Start with `index.html` - it has:
- Beautiful landing page
- Quick navigation
- Links to all visualizations
- Category organization

### Tip 2: Hover for Details
All interactive charts support:
- **Hover**: See exact values
- **Zoom**: Box select to zoom in
- **Pan**: Drag to pan around
- **Reset**: Double-click to reset view

### Tip 3: Compare Runs
Generate visualizations in separate directories:
```bash
python ultimate_visualizations.py baseline.jsonl -o viz_baseline/
python ultimate_visualizations.py optimized.jsonl -o viz_optimized/
# Open both and compare side-by-side
```

### Tip 4: Focus on Percentiles
- **P50**: Typical experience
- **P90**: Good target
- **P99**: Acceptable tail
- **P99/P50 ratio**: Quality indicator (<3 is good)

### Tip 5: Watch the CV
Coefficient of Variation = std / mean
- CV < 0.3: Stable ✅
- CV 0.3-0.5: Variable ⚠️
- CV > 0.5: Unstable 🔥

---

## 📞 Getting Help

1. **Documentation**: Read `ULTIMATE_VISUALIZATIONS_GUIDE.md`
2. **Examples**: See visualization descriptions in `README.md`
3. **Metrics**: Review original metrics reference doc
4. **Issues**: Check existing issues or create new one

---

## ✨ Summary

You now have:
- ✅ 12 interactive visualizations
- ✅ Comprehensive statistical analysis
- ✅ Professional documentation
- ✅ Easy sharing and navigation

**Total visualization time**: ~30 seconds
**Total file size**: ~63 MB
**Browser required**: Any modern browser
**Dependencies**: None (self-contained HTML)

---

**Happy benchmarking!** 🚀

*The Ultimate AIPerf Visualization Suite - Making LLM performance visible*

