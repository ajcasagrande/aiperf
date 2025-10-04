<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🎨 Ultimate AIPerf Visualization Suite - Complete Guide

## Overview

The **Ultimate AIPerf Visualization Suite** is a comprehensive, state-of-the-art visualization system designed specifically for LLM benchmarking. It transforms AIPerf's rich performance data into 12 interactive, publication-quality visualizations that provide deep insights into every aspect of LLM inference performance.

## 🌟 Key Features

### Comprehensive Coverage
- **12 specialized visualizations** covering all AIPerf metrics
- **Interactive HTML dashboards** with zoom, pan, and hover capabilities
- **Publication-ready** charts with professional styling
- **Statistical rigor** with percentiles, distributions, and correlations

### Metric-Driven Design
Built around AIPerf's three metric types:
- **Record Metrics**: Per-request distributions (latency, tokens, etc.)
- **Aggregate Metrics**: Cross-request totals and counts
- **Derived Metrics**: Computed throughput and efficiency

### Performance at Scale
- Handles **10,000+ requests** efficiently
- Generates all visualizations in **<30 seconds**
- Lightweight HTML files (**2-5 MB each**)
- Browser-based, no server required

## 📊 Visualization Portfolio

### 1️⃣ Executive Dashboard
**Purpose**: High-level overview for decision makers

**Contains**:
- Request latency distribution (box plot with statistics)
- TTFT violin plot with density estimation
- Output token throughput histogram
- Inter-token latency (ITL) box plot
- Latency vs token count scatter with color-coding
- Throughput trends over time
- Key metrics summary table (mean, P50, P90, P99)
- Reasoning vs output token breakdown
- Performance stability (coefficient of variation)

**Best For**:
- Quick assessment meetings
- Stakeholder presentations
- Performance snapshots

---

### 2️⃣ Latency Deep Dive
**Purpose**: Understand latency composition and bottlenecks

**Contains**:
- Stacked bar chart: TTFT + generation time breakdown
- Distribution comparison: TTFT, TTST, ITL side-by-side
- Cumulative Distribution Function (CDF) with P50/P90/P99 markers
- Time × percentile heatmap showing evolution

**Best For**:
- Root cause analysis
- Optimization targeting
- Identifying bottlenecks

**Key Insights**:
- What dominates latency: prompt processing or generation?
- How consistent is performance across requests?
- Are tail latencies problematic?

---

### 3️⃣ Token Analysis
**Purpose**: Token-centric performance and efficiency

**Contains**:
- Overlapping histograms: input/output/reasoning token distributions
- Throughput vs sequence length scatter with polynomial trend
- Token efficiency box plots by output length bins
- Cumulative token generation over time with rate overlay

**Best For**:
- Capacity planning
- Understanding generation patterns
- Token budget analysis

**Key Insights**:
- How does throughput scale with sequence length?
- What's the typical token workload?
- Is generation rate consistent?

---

### 4️⃣ Streaming Analysis
**Purpose**: Streaming behavior and consistency

**Contains**:
- Inter-chunk latency distribution with mean/median markers
- TTFT vs TTST scatter (correlation analysis)
- Chunk-by-chunk latency pattern (first 200 chunks)
- Streaming stability (coefficient of variation histogram)

**Best For**:
- Optimizing streaming UX
- Detecting jitter issues
- Understanding chunk delivery

**Key Insights**:
- Is streaming consistent or variable?
- What's the relationship between TTFT and TTST?
- Are there batching artifacts?

---

### 5️⃣ Time Series Analysis
**Purpose**: Performance evolution over benchmark duration

**Contains**:
- Request latency over time (individual + rolling mean/P90/P99)
- Throughput and token generation trends (dual axis)
- System load indicator (requests/second with moving average)

**Best For**:
- Detecting degradation
- Warm-up analysis
- Load pattern identification

**Key Insights**:
- Does performance degrade over time?
- Are there warm-up effects?
- How does load vary?

---

### 6️⃣ Percentile Ladder
**Purpose**: Complete percentile distributions

**Contains**:
- Bar charts for each metric showing P0, P10, P25, P50, P75, P90, P95, P99, P99.9, P100
- Color-coded zones (green=good, yellow=warning, red=critical)
- Reference lines for key percentiles

**Best For**:
- SLA planning
- Understanding tail behavior
- Setting performance targets

**Key Insights**:
- Where are the performance cliffs?
- What's the P99/P50 ratio?
- Are outliers extreme?

---

### 7️⃣ Correlation Matrix
**Purpose**: Inter-metric relationships

**Contains**:
- Heatmap showing correlations between all numeric metrics
- Color scale: red (negative) → white (zero) → blue (positive)
- Annotated correlation coefficients

**Best For**:
- Understanding system behavior
- Root cause analysis
- Finding predictive relationships

**Key Insights**:
- Which metrics move together?
- What drives latency increases?
- Are there unexpected correlations?

---

### 8️⃣ Reasoning Overhead Analysis
**Purpose**: Reasoning token impact assessment

**Contains**:
- Reasoning vs output token scatter (colored by latency)
- Reasoning overhead ratio distribution
- Latency impact with linear trend line
- Reasoning efficiency box plot (output/reasoning ratio)

**Best For**:
- Optimizing reasoning-enabled models
- Cost analysis
- Understanding thinking overhead

**Key Insights**:
- How much overhead does reasoning add?
- Is reasoning efficient?
- Does reasoning scale linearly?

---

### 9️⃣ Workload Characterization
**Purpose**: Understanding request patterns

**Contains**:
- Input sequence length distribution
- Output length vs latency clustering (colored by throughput)
- Workload phase detection (5 temporal phases)
- Request arrival pattern with moving average

**Best For**:
- Workload modeling
- Capacity planning
- Load pattern analysis

**Key Insights**:
- What's the typical request profile?
- Are there distinct workload phases?
- Is arrival rate consistent?

---

### 🔟 SLA Compliance Dashboard
**Purpose**: Quality of service and SLA tracking

**Contains**:
- SLA compliance rate bar chart (color-coded: green=95%+, orange=90-95%, red=<90%)
- Tail latency behavior (>P90 box plots)
- SLA violation timeline with threshold lines
- Performance degradation detection (% change from baseline)

**Best For**:
- Production monitoring
- SLA reporting
- Quality assurance

**Key Insights**:
- Are SLAs being met?
- Where do violations occur?
- Is performance degrading?

**Default SLA Targets** (customizable):
- TTFT: 500ms
- Request Latency: 10,000ms
- Inter-Token Latency: 100ms

---

### 1️⃣1️⃣ Performance Heatmaps
**Purpose**: Multi-dimensional performance views

**Contains**:
- Latency heatmap: time × worker (identify hot workers)
- Throughput heatmap: time × output length (identify sweet spots)
- Token type distribution over time (output vs reasoning)
- Performance variance heatmap (CV across time)

**Best For**:
- Identifying hot spots
- Load distribution analysis
- Finding performance patterns

**Key Insights**:
- Are some workers slower?
- How does performance vary over time?
- Is variance increasing?

---

### 1️⃣2️⃣ Statistical Summary
**Purpose**: Comprehensive statistical reference

**Contains**:
- Benchmark overview: duration, request count, success rate, avg rate
- Detailed statistics for each metric:
  - Central tendency: count, mean, median
  - Spread: std dev, min, max, CV
  - Percentiles: P1, P5, P25, P50, P75, P90, P95, P99, P99.9
- Color-coded performance indicators

**Best For**:
- Detailed reporting
- Metric documentation
- Performance archiving

---

## 🎯 Usage

### Generate Visualizations
```bash
python ultimate_visualizations.py path/to/profile_export.jsonl -o output_dir
```

### View Results
```bash
# Open index page
cd output_dir && open index.html

# Or use helper script to open all
./open_all.sh
```

### Customize
Edit `ultimate_visualizations.py`:
- Modify SLA targets in `create_sla_compliance_dashboard()`
- Adjust colors, themes, and styles
- Add custom visualizations following the pattern

## 📈 Interpretation Framework

### Performance Health Checklist

#### ✅ Healthy System
- [ ] SLA compliance > 95%
- [ ] CV < 0.3 for key metrics
- [ ] P99/P50 ratio < 3
- [ ] Stable throughput over time
- [ ] No performance degradation trend
- [ ] Reasoning overhead < 1.0

#### ⚠️ Warning Signs
- [ ] SLA compliance 90-95%
- [ ] CV 0.3-0.5
- [ ] P99/P50 ratio 3-5
- [ ] Variable throughput
- [ ] Slight degradation (<20%)
- [ ] Reasoning overhead 1.0-2.0

#### 🔥 Critical Issues
- [ ] SLA compliance < 90%
- [ ] CV > 0.5
- [ ] P99/P50 ratio > 5
- [ ] Throughput collapse
- [ ] Severe degradation (>20%)
- [ ] Reasoning overhead > 2.0

### Common Performance Patterns

#### Pattern 1: Warm-up Effect
**Symptoms**:
- High latency in first few minutes
- Gradual improvement over time
- Stabilizes after warm-up period

**Visible In**:
- Time Series Analysis: Decreasing latency trend
- SLA Compliance: Violations clustered at start

**Action**:
- Exclude warm-up from analysis
- Pre-warm in production

---

#### Pattern 2: Load Saturation
**Symptoms**:
- Increasing latency with request rate
- Throughput plateau despite increasing load
- Queue buildup

**Visible In**:
- Time Series: Latency increases with RPS
- Workload Characterization: Request arrival spikes
- Performance Heatmaps: Increasing variance

**Action**:
- Add capacity
- Optimize bottlenecks
- Implement load shedding

---

#### Pattern 3: Batching Artifacts
**Symptoms**:
- Periodic spikes in inter-chunk latency
- Sawtooth pattern in streaming
- Bimodal distributions

**Visible In**:
- Streaming Analysis: ICL pattern shows spikes
- Latency Deep Dive: Bimodal distribution

**Action**:
- Tune batch size
- Adjust scheduling parameters

---

#### Pattern 4: Memory/Resource Leak
**Symptoms**:
- Gradual performance degradation
- Increasing latency variance
- Growing tail latencies

**Visible In**:
- Time Series: Upward trend in rolling stats
- SLA Compliance: Degradation detector shows increase
- Performance Heatmaps: Increasing variance over time

**Action**:
- Check for memory leaks
- Monitor resource utilization
- Restart workers periodically

---

#### Pattern 5: Worker Imbalance
**Symptoms**:
- Some workers consistently slower
- Uneven load distribution
- High variance across workers

**Visible In**:
- Performance Heatmaps: Latency heatmap shows hot workers
- Correlation Matrix: Worker ID correlates with latency

**Action**:
- Investigate slow workers
- Balance load distribution
- Check for resource contention

---

## 🔬 Advanced Analysis Techniques

### Percentile Analysis
```
P50: Typical user experience
P90: Good performance target
P95: SLA boundary
P99: Acceptable tail
P99.9: Investigate if >> P99
```

### Coefficient of Variation (CV)
```
CV < 0.1: Very consistent
CV 0.1-0.3: Acceptable variance
CV 0.3-0.5: High variance
CV > 0.5: Investigate instability
```

### Throughput Analysis
```
Ideal: Linear scaling with concurrency
Saturation: Throughput plateau
Overload: Throughput decline
```

### Correlation Insights
```
Strong positive (>0.7): Metrics move together
Strong negative (<-0.7): Inverse relationship
Weak (±0.3): Little relationship
```

## 🛠️ Technical Architecture

### Data Pipeline
```
JSONL Records → Pydantic Models → Pandas DataFrame → Analysis → Plotly/HTML
```

### Key Technologies
- **Plotly**: Interactive visualizations
- **Pandas**: Efficient data processing
- **NumPy/SciPy**: Statistical computations
- **Pydantic**: Type-safe data models

### Design Principles
1. **Metric-driven**: Built around AIPerf metric definitions
2. **Interactive**: All charts support zoom, pan, hover
3. **Self-contained**: Single HTML files, no dependencies
4. **Scalable**: Efficient for 1K-100K requests
5. **Extensible**: Easy to add new visualizations

## 📊 Metrics Coverage

### Latency Metrics ✅
- Request Latency
- TTFT (Time to First Token)
- TTST (Time to Second Token)
- ITL (Inter Token Latency)
- ICL (Inter Chunk Latency)

### Token Metrics ✅
- Input Sequence Length
- Output Token Count
- Reasoning Token Count
- Output Sequence Length (OSL)
- Total counts (aggregate)

### Throughput Metrics ✅
- Output Token Throughput Per User
- Request Throughput
- Request Rate

### Efficiency Metrics ✅
- Reasoning Overhead Ratio
- Reasoning Efficiency
- Coefficient of Variation
- Token generation rate

### Quality Metrics ✅
- SLA Compliance Rate
- Error Rate
- Performance Stability
- Degradation Detection

## 🚀 Best Practices

### Benchmark Design
1. **Duration**: Run for 5-10 minutes minimum
2. **Warm-up**: Include and identify warm-up period
3. **Load**: Use realistic concurrency and patterns
4. **Monitoring**: Track system resources

### Analysis Workflow
1. Start with **Executive Dashboard** (overview)
2. Check **SLA Compliance** (quality)
3. Review **Time Series** (temporal patterns)
4. Dive into **Latency Deep Dive** (bottlenecks)
5. Examine **Percentile Ladder** (tail behavior)
6. Consult **Correlation Matrix** (relationships)
7. Generate **Statistical Summary** (report)

### Reporting
- **Executives**: Executive Dashboard + SLA Compliance
- **Engineers**: Latency Deep Dive + Correlation Matrix
- **Capacity Planning**: Token Analysis + Workload Characterization
- **Documentation**: Statistical Summary + Percentile Ladder

## 🎓 Learning Resources

### Understanding Metrics
- See `METRICS_REFERENCE.md` for detailed metric definitions
- Each metric includes: formula, requirements, notes
- Understand Record vs Aggregate vs Derived metrics

### Visualization Techniques
- **Box plots**: Show distribution + outliers
- **Violin plots**: Show density + distribution
- **CDF plots**: Show percentile behavior
- **Heatmaps**: Show 2D patterns
- **Time series**: Show temporal evolution

### Statistical Concepts
- **Percentiles**: Value below which X% of data falls
- **Coefficient of Variation**: Normalized measure of spread
- **Correlation**: Linear relationship between variables
- **Rolling statistics**: Smooth temporal trends

## 🔮 Future Enhancements

### Planned Features
- [ ] GPU utilization correlation
- [ ] Batch size efficiency analysis
- [ ] Model comparison dashboard
- [ ] Cost analysis (tokens × pricing)
- [ ] Concurrency impact analysis
- [ ] Queue depth visualization
- [ ] Real-time monitoring mode
- [ ] Automated anomaly detection
- [ ] PDF report generation
- [ ] Custom metric definitions

### Community Ideas
Open to suggestions! See existing issues or create new ones.

## 📄 File Structure

```
ultimate_visualizations/
├── index.html                        # Landing page
├── README.md                         # Detailed documentation
├── open_all.sh                       # Helper script
├── 01_executive_dashboard.html       # Overview
├── 02_latency_deep_dive.html        # Latency analysis
├── 03_token_analysis.html           # Token metrics
├── 04_streaming_analysis.html       # Streaming behavior
├── 05_time_series_analysis.html     # Temporal trends
├── 06_percentile_ladder.html        # Percentile distributions
├── 07_correlation_matrix.html       # Metric relationships
├── 08_reasoning_overhead.html       # Reasoning analysis
├── 09_workload_characterization.html # Workload patterns
├── 10_sla_compliance.html           # SLA tracking
├── 11_performance_heatmaps.html     # Multi-dimensional views
└── 12_statistical_summary.html      # Comprehensive stats
```

## 🤝 Contributing

Contributions welcome! Areas for contribution:
- New visualization types
- Statistical analysis techniques
- Performance optimizations
- Documentation improvements
- Bug fixes

## 📞 Support

For issues, questions, or feature requests:
1. Check the README
2. Review existing issues
3. Create a new issue with details

## 🙏 Acknowledgments

Built with:
- **AIPerf**: LLM benchmarking framework
- **Plotly**: Interactive visualization library
- **Pandas**: Data analysis library
- **Pydantic**: Data validation library

---

**The Ultimate AIPerf Visualization Suite**
*Transforming benchmark data into actionable insights*

Version 1.0 | Created with ❤️ for the LLM benchmarking community

