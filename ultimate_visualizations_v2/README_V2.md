<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 🚀 Ultimate AIPerf Visualization Suite v2.0

## What's New in v2?

**v2.0** combines aggregate summary metrics with per-record data for the **ultimate** LLM benchmarking experience!

### Key Enhancements Over v1

✨ **Dual Data Source Integration**
- Combines JSONL per-record data with aggregate JSON summary
- Leverages pre-computed statistics for faster insights
- Access to benchmark configuration and metadata

🎯 **New Executive Features**
- Supreme Executive Dashboard with 12 KPI indicators
- Overall Performance Score (composite metric)
- Beautiful benchmark configuration overview
- Real-time quality metrics

💰 **Cost Analysis**
- Token-based cost breakdown
- Cost per request tracking
- ROI analysis and efficiency metrics
- Hourly cost projections

✅ **Goodput Analysis** (NEW!)
- SLA compliance tracking
- Quality-adjusted throughput
- Request classification (good vs exceeding SLA)
- Compliance trends over time

🚀 **Efficiency Scorecards**
- Tokens per request
- Time per token
- Reasoning overhead ratios
- Goodput efficiency percentage
- Visual progress bars

---

## 📊 Complete Visualization List (13 Total)

| # | Visualization | Size | What's Special |
|---|---------------|------|----------------|
| 00 | **Master Dashboard** | 4.4 KB | Navigation hub with key stats |
| 01 | **Supreme Executive Dashboard** | 4.8 MB | 12 KPI indicators + composite score |
| 02 | **Benchmark Overview** | 9.9 KB | Beautiful config card |
| 03 | **Goodput Analysis** | 4.7 MB | SLA compliance & quality metrics |
| 04 | **Efficiency Scorecard** | 6.7 KB | Comprehensive efficiency breakdown |
| 05 | **Cost Analysis** | 4.7 MB | Token-based cost tracking |
| 06 | **Performance Matrix** | 4.7 MB | Multi-percentile comparison |
| 07 | **Advanced Latency** | 4.7 MB | Deep latency decomposition |
| 08 | **Token Economics** | 4.7 MB | Token usage & throughput |
| 09 | **Quality Metrics** | 4.7 MB | Quality & reliability |
| 10 | **System Health** | 4.7 MB | Health monitoring |
| 11 | **Comparative Analysis** | 4.7 MB | Multi-run comparison (placeholder) |
| 12 | **Predictive Insights** | 4.7 MB | Forecasting (placeholder) |

---

## 🎯 Feature Highlights

### 1. Supreme Executive Dashboard
The crown jewel of v2! Features:
- **6 KPI Indicators**: Throughput, Token Rate, Latency, Goodput, Quality Rate, TTFT
- **Gauge Charts**: Visual progress meters for key metrics
- **Performance Score**: Composite metric (0-100) combining throughput, latency, quality, TTFT
- **Live Trends**: Real-time latency and throughput trends
- **Distribution Comparisons**: Side-by-side metric analysis

### 2. Benchmark Overview Card
Beautiful presentation of:
- Model configuration (name, type, streaming, concurrency)
- Target duration vs actual duration
- Complete CLI command used
- Benchmark timeline (start, end, status)
- Key performance summary

### 3. Goodput Analysis (⭐ NEW!)
Deep dive into quality metrics:
- **Goodput vs Total Throughput**: Visual comparison
- **SLA Compliance Over Time**: Rolling compliance percentage
- **Request Classification**: Pie chart of good vs bad requests
- **Latency Distribution**: Histogram showing SLA threshold

**Goodput** = requests meeting SLA / time

### 4. Efficiency Scorecard (⭐ NEW!)
Comprehensive efficiency dashboard:
- **Tokens Per Request**: Average workload size
- **Time Per Token**: Generation efficiency (ms/token)
- **Reasoning Overhead**: Thinking vs output ratio
- **Goodput Efficiency**: Quality throughput percentage
- **Visual Progress Bars**: For each efficiency metric
- **Overall Efficiency Rating**: 0-100 composite score

### 5. Cost Analysis (⭐ NEW!)
Token-based cost tracking:
- **Cost Breakdown**: Pie chart by token type (input/output/reasoning)
- **Cost Per Request**: Over time with rolling average
- **Token Volume**: Bar chart showing token distribution
- **Cost Per Quality Request**: Gauge showing $/good request
- **Hourly Cost**: Projected cost per hour of operation

### 6. Performance Matrix
Multi-dimensional comparison:
- P50, P90, P99 across all latency metrics
- Interactive line chart for easy comparison
- Identifies where tail latencies appear

---

## 💡 New Metrics Explained

### Goodput
**Quality-adjusted throughput** measuring requests that meet SLA.

```
Goodput = Good Requests / Benchmark Duration
```

Where "Good Request" = request_latency ≤ SLA target

**Why it matters**: Total throughput can be misleading if many requests exceed SLA. Goodput shows *usable* throughput.

### Efficiency Scores

**Tokens Per Request**
```
Avg tokens generated per request
Higher = more content per request
```

**Time Per Token**
```
(Total duration × 1000) / Total tokens
Lower = faster generation
```

**Reasoning Overhead**
```
Reasoning tokens / Output tokens
Lower = more efficient thinking
< 1.0 = efficient
> 2.0 = excessive overhead
```

**Goodput Efficiency**
```
(Goodput / Total Throughput) × 100%
Higher = better quality rate
> 95% = excellent
90-95% = good
< 90% = needs improvement
```

### Overall Performance Score
Composite metric combining:
- Throughput score (30%)
- Latency score (30%)
- Quality score (20%)
- TTFT score (20%)

Each component normalized to 0-100, then averaged.

---

## 🚀 Quick Start

### Generate v2 Visualizations
```bash
cd /home/anthony/nvidia/projects/aiperf9
source .venv/bin/activate

python ultimate_visualizations_v2.py \
    artifacts/openai_gpt-oss-20b-openai-chat-concurrency100/profile_export_5min.jsonl \
    artifacts/openai_gpt-oss-20b-openai-chat-concurrency100/profile_export_aiperf_5min.json \
    -o ultimate_visualizations_v2
```

### View Visualizations
```bash
cd ultimate_visualizations_v2

# Start with the master dashboard
xdg-open v2_00_master_dashboard.html

# Or go straight to supreme executive dashboard
xdg-open v2_01_supreme_executive_dashboard.html
```

---

## 📈 Recommended Analysis Workflow

### Executive Review (5 minutes)
1. **Master Dashboard** - Get oriented
2. **Supreme Executive** - See KPIs and performance score
3. **Benchmark Overview** - Understand configuration

### Quality Assessment (10 minutes)
4. **Goodput Analysis** - Check SLA compliance
5. **Quality Metrics** - Assess reliability
6. **Efficiency Scorecard** - Evaluate efficiency

### Deep Dive (20 minutes)
7. **Cost Analysis** - Understand economics
8. **Token Economics** - Token usage patterns
9. **Performance Matrix** - Multi-percentile view
10. **Advanced Latency** - Detailed latency breakdown

---

## 🎨 Visual Design Philosophy

### Color Coding
- **Blue (#3498db)**: Neutral metrics, latency
- **Green (#2ecc71)**: Good performance, throughput, success
- **Red (#e74c3c)**: Warnings, errors, critical issues
- **Orange (#f39c12)**: Caution, cost-related
- **Purple (#9b59b6)**: Special metrics (goodput, efficiency)

### Gauge Interpretations
- **Green Zone**: Excellent performance (>95%)
- **Yellow Zone**: Acceptable (90-95%)
- **Red Zone**: Needs attention (<90%)

### Progress Bars
- Full bar (100%): Optimal
- 75-99%: Good
- 50-74%: Fair
- <50%: Poor

---

## 📊 Key Differences from v1

| Feature | v1 | v2 |
|---------|----|----|
| Data Sources | JSONL only | JSONL + Aggregate JSON |
| Dashboards | 12 | 13 |
| Executive Summary | Basic | Supreme with KPIs |
| Goodput Analysis | ❌ | ✅ |
| Cost Analysis | ❌ | ✅ |
| Efficiency Scorecard | ❌ | ✅ |
| Benchmark Config | Text | Beautiful card |
| Performance Score | ❌ | ✅ Composite metric |
| SLA Tracking | Basic | Advanced with trends |

---

## 🔬 Technical Details

### Data Pipeline
```
JSONL (per-record) ──┐
                      ├──> Pydantic Models ──> Pandas ──> Analysis ──> Plotly
JSON (aggregate)   ──┘
```

### Performance
- **Generation Time**: ~30 seconds
- **Total Size**: ~47 MB (13 files)
- **Records Processed**: 1200
- **Aggregate Metrics**: 22

### Requirements
- Python 3.10+
- Plotly, Pandas, NumPy, Pydantic
- Modern web browser

---

## 💡 Pro Tips

### Tip 1: Start with Master Dashboard
Navigate from `v2_00_master_dashboard.html` for easy access to all visualizations.

### Tip 2: Focus on Goodput
Don't just look at total throughput. **Goodput** shows quality-adjusted performance.

### Tip 3: Watch Efficiency Scores
Key efficiency metrics:
- Tokens/request: Understand workload
- Time/token: Generation speed
- Reasoning overhead: Model efficiency
- Goodput efficiency: Quality rate

### Tip 4: Use Performance Score
The composite score (0-100) in Supreme Executive Dashboard gives you a single metric to track improvements.

### Tip 5: Cost Analysis
Use cost dashboard to:
- Understand token economics
- Identify expensive request patterns
- Project operational costs

---

## 🆕 Future v2 Enhancements

Planned features:
- [ ] Multi-run comparison (v2_11)
- [ ] Predictive insights with ML (v2_12)
- [ ] Real-time monitoring mode
- [ ] Automated anomaly detection
- [ ] Custom threshold configuration
- [ ] PDF report generation
- [ ] Benchmark comparison matrix
- [ ] Historical trend analysis

---

## 📞 Questions & Support

### Common Questions

**Q: Do I need v1 if I have v2?**
A: No, v2 is a superset. But v1 has some different visualizations you might find useful.

**Q: Can I customize SLA targets?**
A: Yes! SLA targets are pulled from the aggregate JSON (`input_config.goodput`).

**Q: Why are some visualizations placeholders?**
A: v2_11 (comparative) and v2_12 (predictive) are designed for future multi-run analysis.

**Q: How do I interpret the performance score?**
A:
- 90-100: Excellent
- 80-90: Good
- 70-80: Fair
- <70: Needs improvement

---

## 🎯 Summary

**Ultimate AIPerf Visualization Suite v2.0** represents the next generation of LLM benchmarking visualization:

✅ **Comprehensive**: 13 visualizations covering all aspects
✅ **Executive-Friendly**: Beautiful KPI dashboards
✅ **Quality-Focused**: Goodput and SLA tracking
✅ **Cost-Aware**: Token-based cost analysis
✅ **Efficient**: Scorecard for quick assessment
✅ **Actionable**: Clear insights for optimization

---

**Version**: 2.0
**Generated**: 2025-10-04
**Total Visualizations**: 13
**Total Size**: ~47 MB

🚀 **The Ultimate Tool for Ultimate LLM Benchmarking!**

