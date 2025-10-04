<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# 📊 Complete Visualization Index

## Quick Access Guide

This directory contains **15 comprehensive visualizations** analyzing LLM inference performance:

---

## 🎨 Static Charts (PNG - Publication Quality, 300 DPI)

Perfect for reports, papers, presentations, and printing.

### 1. **executive_summary.png**
**The One-Page Wonder** 🌟
- 4 KPI cards (Avg Latency, TTFT, Throughput, Error Rate)
- Latency distribution histogram
- Throughput timeline
- Token generation pattern
- Percentile bars with labels

**Use case:** Executive presentations, status reports
**Size:** ~2-3 MB

---

### 2. **latency_overview.png**
**Complete Latency Analysis** 📈
- Large request latency histogram with mean/median lines
- Box plot comparison (Latency vs TTFT)
- TTFT distribution
- Inter-token latency distribution
- Throughput distribution
- Violin plots for distribution shape

**Use case:** Performance deep dives, optimization planning
**Size:** ~2-3 MB

---

### 3. **performance_timeline.png**
**Time-Series Performance Tracking** ⏱️
- Request latency with moving average and confidence band
- Throughput over time with mean line
- Token generation pattern (stacked bars)
- Cumulative error rate with error markers

**Use case:** Monitoring trends, detecting degradation
**Size:** ~2-3 MB

---

### 4. **percentile_analysis.png**
**SLA Compliance Dashboard** 🎯
- Grouped bar chart (P50, P75, P90, P95, P99)
- Tail latency amplification (ratio to P50)
- 2x and 3x threshold markers

**Use case:** SLA validation, capacity planning
**Size:** ~2-3 MB

---

### 5. **correlation_matrix.png**
**Relationship Discovery** 🔍
- Triangular heatmap with correlation coefficients
- Color-coded (Red=positive, Blue=negative)
- Annotated with exact values

**Use case:** Root cause analysis, understanding bottlenecks
**Size:** ~2-3 MB

---

### 6. **scatter_analysis.png**
**Multi-Dimensional Analysis** 🔬
6 scatter plots revealing relationships:
- Input length → Request latency (colored by output)
- Output length → Throughput (colored by reasoning tokens)
- TTFT → Total latency
- Reasoning tokens → Latency
- Inter-token latency → Throughput
- Total tokens → Latency

**Use case:** Understanding trade-offs, optimization targets
**Size:** ~2-3 MB

---

### 7. **error_analysis.png**
**Reliability Deep Dive** ⚠️
- Pie chart of error types
- Error occurrence timeline (scatter)
- Cumulative error rate trend
- Error summary statistics box

**Use case:** Debugging, reliability improvement
**Size:** ~2-3 MB

---

## 🌐 Interactive Charts (HTML - Web-Based)

Perfect for exploration, sharing via web, and interactive analysis.

### 8. **dashboard.html** ⭐
**THE MAIN DASHBOARD**
- Single-page application with all visualizations
- Professional gradient header
- Organized sections
- Embedded iframe architecture

**Use case:** Primary analysis tool, stakeholder sharing
**Size:** ~3 KB (+ linked files)

---

### 9. **summary_stats.html**
Interactive table with:
- Mean, Median, Std Dev
- Min, Max values
- P95, P99 percentiles
- All key metrics

**Size:** ~4.7 MB

---

### 10. **latency_distribution.html**
4-panel interactive histograms:
- Request latency
- TTFT
- Inter-token latency
- Throughput
With hover details and zoom

**Size:** ~4.7 MB

---

### 11. **performance_over_time.html**
3-panel time series:
- Latency with moving average
- Throughput trends
- Error rate
Interactive zoom and pan

**Size:** ~4.7 MB

---

### 12. **token_analysis.html**
2 scatter plots with color dimensions:
- Input length vs latency (colored by output)
- Output length vs throughput (colored by reasoning)
Hover for exact values

**Size:** ~4.7 MB

---

### 13. **percentile_analysis.html**
Grouped bar chart:
- P50, P75, P90, P95, P99
- All latency metrics
- Interactive legend

**Size:** ~4.7 MB

---

### 14. **correlation_heatmap.html**
Full correlation matrix:
- All metrics cross-referenced
- Color-coded cells
- Annotated values
- Interactive hover

**Size:** ~4.7 MB

---

### 15. **error_analysis.html**
2-panel error dashboard:
- Pie chart of error types
- Timeline scatter plot
With interactive tooltips

**Size:** ~4.7 MB

---

## 🎯 Recommended Workflow

### For Quick Review:
1. Open `dashboard.html` in browser
2. Review executive summary
3. Drill into specific metrics

### For Deep Analysis:
1. Start with `executive_summary.png`
2. Examine `latency_overview.png`
3. Check `performance_timeline.png`
4. Investigate `scatter_analysis.png`
5. Review `error_analysis.png`

### For Presentations:
1. Use `executive_summary.png` as overview slide
2. Pick specific charts from static PNGs
3. All are 300 DPI - perfect for projection

### For Papers/Reports:
1. Use static PNGs for LaTeX/Word documents
2. High resolution ensures clarity
3. Professional styling matches academic standards

---

## 📏 Technical Specifications

### Static Charts (PNG):
- **Resolution:** 300 DPI (publication quality)
- **Format:** PNG with transparency support
- **Color Scheme:** Color-blind friendly (Seaborn 'husl' and 'Set2')
- **Fonts:** Arial/DejaVu Sans (widely available)
- **Grid:** Alpha-blended for professional look

### Interactive Charts (HTML):
- **Library:** Plotly 6.3.1
- **Theme:** Dark mode for reduced eye strain
- **Features:** Zoom, pan, hover tooltips, export to PNG
- **Compatibility:** All modern browsers
- **Responsive:** Adapts to screen size

---

## 🎨 Visual Design Principles Applied

1. **Color Consistency:** Same palette across related charts
2. **White Space:** Adequate spacing prevents visual clutter
3. **Typography:** Bold titles, clear labels, readable sizes
4. **Gridlines:** Subtle (30% opacity) for reference without distraction
5. **Data-Ink Ratio:** Maximized per Edward Tufte's principles
6. **Statistical Honesty:** Error bars, confidence intervals where applicable

---

## 📊 Chart Type Selection Rationale

| Chart Type | Used For | Why |
|------------|----------|-----|
| **Histogram** | Distributions | Shows shape, skewness, modality |
| **Box Plot** | Quartiles | Identifies outliers, shows spread |
| **Violin Plot** | Distribution shape | Combines box plot + density |
| **Line Chart** | Time series | Reveals trends, patterns |
| **Scatter Plot** | Relationships | Shows correlations, clusters |
| **Bar Chart** | Comparisons | Easy categorical comparison |
| **Heatmap** | Correlations | Multi-dimensional relationships |
| **Pie Chart** | Proportions | Error type breakdown |

---

## 🔧 Customization Tips

### Change Color Scheme:
```python
# In the script, modify:
sns.set_palette("muted")  # or "bright", "pastel", "dark"
```

### Adjust DPI:
```python
DPI = 150  # For web (faster)
DPI = 600  # For print publications
```

### Modify Figure Sizes:
```python
FIGSIZE_WIDE = (20, 8)  # Wider charts
FIGSIZE_TALL = (12, 14)  # More vertical space
```

### Add Custom Annotations:
```python
ax.annotate('Important Event',
            xy=(x, y), xytext=(x+10, y+10),
            arrowprops=dict(arrowstyle='->'))
```

---

## 📈 Metrics Visualized

### Latency Metrics:
- ✅ Request Latency (end-to-end)
- ✅ TTFT (Time to First Token)
- ✅ Inter-Token Latency (generation speed)
- ✅ P50, P75, P90, P95, P99 percentiles

### Throughput Metrics:
- ✅ Output Token Throughput per User
- ✅ Throughput over time
- ✅ Throughput vs token length

### Token Metrics:
- ✅ Input Sequence Length
- ✅ Output Sequence Length
- ✅ Reasoning Token Count
- ✅ Total Token Count

### Reliability Metrics:
- ✅ Error Rate (%)
- ✅ Error Types Distribution
- ✅ Error Timeline

---

## 💡 Pro Tips

### For Performance Engineers:
- Focus on **scatter_analysis.png** for bottleneck identification
- Use **correlation_matrix.png** for root cause analysis
- Monitor **percentile_analysis.png** for SLA compliance

### For Presentations:
- **executive_summary.png** is your opening slide
- **latency_overview.png** for technical deep dive
- **error_analysis.png** if discussing reliability

### For Reports:
- All PNGs are 300 DPI - perfect for printing
- Include **correlation_matrix.png** for scientific rigor
- Use **performance_timeline.png** for trend analysis

### For Web Sharing:
- Send **dashboard.html** - no installation needed
- Recipients can explore interactively
- Works on mobile browsers

---

## 🚀 Advanced Analysis Suggestions

### Comparative Analysis:
Run the script on multiple profile exports and compare:
- Model versions (v1 vs v2)
- Concurrency levels (10 vs 100)
- Different hardware (A100 vs H100)

### Time-Based Analysis:
- Run daily/weekly for trend detection
- Overlay multiple runs on same chart
- Detect seasonal patterns

### A/B Testing:
- Compare treatment vs control
- Statistical significance testing
- Performance regression detection

---

## 📚 References & Inspiration

### Visualization Theory:
- Edward Tufte - "The Visual Display of Quantitative Information"
- Stephen Few - "Show Me the Numbers"
- Cole Nussbaumer Knaflic - "Storytelling with Data"

### Performance Analysis:
- Google - "The Tail at Scale" (importance of P99)
- Brendan Gregg - Systems Performance Engineering
- Gil Tene - "How NOT to Measure Latency"

### Python Visualization:
- Plotly documentation and examples
- Seaborn gallery
- Matplotlib best practices guide

---

## 🎓 Understanding the Visualizations

### What Makes a Good Visualization?

1. **Clear Purpose:** Each chart answers a specific question
2. **Appropriate Type:** Chart type matches data type
3. **Clean Design:** No chartjunk, maximum data-ink ratio
4. **Accessible:** Color-blind friendly, good contrast
5. **Actionable:** Leads to decisions, not just pretty pictures

### Common Pitfalls Avoided:

❌ 3D charts (distort perception)
❌ Too many colors (confusing)
❌ Pie charts with >5 slices (hard to compare)
❌ Dual y-axes (misleading)
❌ Missing context (no baselines, thresholds)

✅ 2D charts with depth through color
✅ Consistent, meaningful color palette
✅ Error types limited and clear
✅ Single y-axis per chart
✅ Mean, median, and threshold lines

---

## 🔬 Data Science Best Practices Applied

### Statistical Rigor:
- Moving averages to smooth noise
- Percentile calculations for distribution understanding
- Correlation analysis for relationships
- Outlier identification with box plots

### Visual Encoding:
- Position for primary values (most accurate)
- Color for categorical/continuous dimensions
- Size for emphasis (scatter plots)
- Shape for discrete categories

### Narrative Flow:
1. **Summary** → Overview understanding
2. **Distribution** → Shape and spread
3. **Timeline** → Temporal patterns
4. **Relationships** → Correlations
5. **Errors** → Reliability analysis

---

## 🎁 Bonus: Quick Stats Summary

Based on your data (101 requests analyzed):

### Performance:
- **Mean Latency:** ~9.5 seconds
- **Median Latency:** ~9.2 seconds
- **P95 Latency:** ~11.5 seconds
- **P99 Latency:** ~11.7 seconds

### Throughput:
- **Mean:** ~30 tokens/sec/user
- **Range:** 28-35 tokens/sec/user
- **Consistency:** Low variance (good!)

### Tokens:
- **Input:** 550 tokens (constant)
- **Output:** 138-248 tokens (varies)
- **Reasoning:** 118-248 tokens (o1-style model)

### Reliability:
- **Error Rate:** 21.8% (22 errors)
- **Error Type:** 100% RequestCancellationError
- **Pattern:** Evenly distributed (not clustered)

### Recommendations:
1. ⚠️ **High error rate** - investigate timeout settings
2. ✅ **Stable throughput** - system is consistent
3. ✅ **Low P99/P50 ratio** - good tail latency
4. 💡 **Reasoning tokens** - optimize for o1-style models

---

## 🛠️ Files in This Directory

```
📁 performance_visualizations/
├── 📊 Static Charts (PNG - 300 DPI)
│   ├── executive_summary.png        # One-page KPI dashboard
│   ├── latency_overview.png         # 6-panel latency analysis
│   ├── performance_timeline.png     # 4-panel time series
│   ├── percentile_analysis.png      # P50-P99 comparison
│   ├── correlation_matrix.png       # Metric relationships
│   ├── scatter_analysis.png         # 6-panel scatter plots
│   └── error_analysis.png           # 4-panel error deep dive
│
├── 🌐 Interactive Charts (HTML - Plotly)
│   ├── dashboard.html               # ⭐ MAIN DASHBOARD
│   ├── summary_stats.html           # Interactive table
│   ├── latency_distribution.html    # 4-panel histograms
│   ├── performance_over_time.html   # 3-panel time series
│   ├── token_analysis.html          # 2-panel scatter
│   ├── percentile_analysis.html     # Grouped bars
│   ├── correlation_heatmap.html     # Full correlation matrix
│   └── error_analysis.html          # Pie + timeline
│
└── 📚 Documentation
    ├── README.md                    # Comprehensive guide
    └── VISUALIZATIONS_INDEX.md      # This file
```

---

## 🚀 Quick Start Commands

### View Interactive Dashboard:
```bash
# Linux/Mac
firefox performance_visualizations/dashboard.html

# or
python -m http.server 8000
# Then open: http://localhost:8000/performance_visualizations/dashboard.html
```

### View Static Images:
```bash
# Image viewer
eog performance_visualizations/*.png

# Or open folder in file manager
nautilus performance_visualizations/
```

### Generate Fresh Visualizations:
```bash
# Interactive charts
python visualize_performance.py

# Static charts
python visualize_static_charts.py

# Both
python visualize_performance.py && python visualize_static_charts.py
```

---

## 📊 Chart Selection Guide

| Your Need | Best Chart(s) | Format |
|-----------|--------------|--------|
| Quick health check | executive_summary.png | Static |
| Detailed analysis | dashboard.html | Interactive |
| Report/Paper | Any *.png | Static |
| Team presentation | executive_summary.png + latency_overview.png | Static |
| Interactive demo | dashboard.html | Interactive |
| Print/PDF | All *.png files | Static |
| Root cause analysis | correlation_matrix.png + scatter_analysis.png | Static |
| Trend monitoring | performance_timeline.png | Static |
| SLA validation | percentile_analysis.png | Static |
| Error debugging | error_analysis.png | Static |

---

## 🎨 Design Philosophy

### Why Static AND Interactive?

**Static Charts (PNG):**
- ✅ Publication quality (papers, reports)
- ✅ Easy to embed in documents
- ✅ Fast loading, no dependencies
- ✅ Consistent across platforms
- ✅ Perfect for printing

**Interactive Charts (HTML):**
- ✅ Explore data dynamically
- ✅ Zoom into specific regions
- ✅ Hover for exact values
- ✅ Filter and compare
- ✅ Share via web browser

**Best of Both Worlds:** Use static for communication, interactive for investigation!

---

## 📈 Visualization Technology Stack

### Libraries Used:
- **Matplotlib 3.10.6** - Publication-quality static plots
- **Seaborn 0.13.2** - Beautiful statistical visualizations
- **Plotly 6.3.1** - Interactive web-based charts
- **Pandas** - Data manipulation
- **NumPy** - Numerical analysis

### Why These Libraries?

**Plotly:**
- Industry standard for interactive dashboards
- Used by Netflix, Airbnb, Tesla
- Web-based, no installation for viewers
- Supports 40+ chart types

**Matplotlib:**
- Most mature Python visualization library
- Publication quality (used in Nature, Science papers)
- Fine-grained control over every element
- LaTeX integration for equations

**Seaborn:**
- Built on Matplotlib
- Beautiful defaults
- Statistical visualization focus
- Perfect for distribution analysis

---

## 🏆 Best Practices Implemented

### Data Visualization:
✅ Choose right chart for data type
✅ Use color meaningfully
✅ Include reference lines (mean, median)
✅ Show confidence intervals
✅ Label everything clearly
✅ Use consistent scales

### Performance Monitoring:
✅ Track P95/P99 (not just averages)
✅ Monitor trends over time
✅ Identify outliers
✅ Correlate related metrics
✅ Measure error rates

### User Experience:
✅ Dark theme (reduced eye strain)
✅ Interactive exploration
✅ Multiple views of same data
✅ Clear documentation
✅ Quick access dashboard

---

## 🎓 Learning Resources

### Want to Learn More?

**Visualization:**
- [Plotly Python Documentation](https://plotly.com/python/)
- [Seaborn Tutorial](https://seaborn.pydata.org/tutorial.html)
- [Matplotlib Gallery](https://matplotlib.org/stable/gallery/index.html)

**Performance Analysis:**
- [Google's "Tail at Scale" Paper](https://research.google/pubs/pub40801/)
- [Systems Performance by Brendan Gregg](https://www.brendangregg.com/)
- [High Performance Browser Networking](https://hpbn.co/)

**LLM Performance:**
- [vLLM Documentation](https://docs.vllm.ai/)
- [TGI Performance Guide](https://huggingface.co/docs/text-generation-inference/)
- [LLM Inference Optimization](https://lilianweng.github.io/posts/2023-01-10-inference-optimization/)

---

## 🎯 Next Steps

### Immediate Actions:
1. ✅ Review dashboard.html for overall health
2. ⚠️ Investigate 22% error rate (RequestCancellationError)
3. 📊 Compare with baseline/previous runs
4. 🎯 Set up automated monitoring

### Long-term Improvements:
1. Schedule regular profiling runs
2. Set up alerting on P95/P99 thresholds
3. A/B test different configurations
4. Build historical trend database

### Advanced Analysis:
1. Add cost analysis ($/request)
2. Compare across different models
3. Real-time streaming dashboard
4. GPU utilization overlays

---

**🎨 Created with modern Python visualization best practices**
**📊 Designed for real-world performance analysis**
**🚀 Production-ready and publication-quality**

*Last updated: October 4, 2025*

